from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import multiprocessing
import os
import pickle
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .consultation import (
    ASK_FOR_MISSING_FIELDS,
    CALL_PRICING_TOOL,
    EXPLAIN_RESULT,
    OUT_OF_SCOPE,
    REQUEST_ACTIONS,
    SAFE_FAILURE,
    SHOW_CONFIRMATION,
    ConsultationState,
    PricingTool,
    PricingToolRefused,
    SessionStore,
    confirm as confirm_state,
    decide_action,
    merge_patch,
    validate_patch,
)
from .database import Database
from .inference_worker import InferenceRequest, run_inference_worker
from .image_ingestion import (
    ImageIngestionError,
    ImageLimits,
    decode_data_uri,
    normalize_image,
    reject_remote_url,
)
from .limits import BodySizeLimitMiddleware, ChatLimits, RateLimitMiddleware
from .model_client import ModelContractError, ModelUnavailable, OpenAICompatibleModel, TextModel
from .pricing import (
    CATEGORIES,
    MIN_MARGIN_RP,
    STATUS_INVALID,
    STATUS_NO_ACTION,
    STATUS_RECOMMENDATION,
    PricingInput,
    compute,
)
from .schemas import to_engine_result

logger = logging.getLogger("hargaturun.api")
UTC = timezone.utc
DEAL_STATUSES = ("active", "sold_out", "removed")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecommendRequest(StrictModel):
    free_text: str | None = Field(default=None, min_length=1, max_length=1000)
    item_name: str | None = Field(default=None, min_length=1, max_length=160)
    category: str | None = None
    original_price: int | None = None
    cost: int | None = None
    stock: int | None = None
    days_remaining: float | None = None
    daily_sales: float | None = None
    total_shelf_life: float | None = None
    shop_name: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def exactly_one_input_mode(self) -> "RecommendRequest":
        structured = any(
            getattr(self, field) is not None
            for field in (
                "item_name", "category", "original_price", "cost", "stock",
                "days_remaining", "daily_sales", "total_shelf_life", "shop_name",
            )
        )
        if bool(self.free_text) == structured:
            raise ValueError("send exactly one of free_text or structured item fields")
        return self


class PublishDealRequest(StrictModel):
    item_name: str = Field(min_length=1, max_length=160)
    shop_name: str = Field(min_length=1, max_length=160)
    category: str
    original_price: int = Field(gt=0)
    cost: int = Field(ge=0)
    deal_price: int = Field(gt=0)
    discount_percent: int = Field(ge=0, le=99)
    days_remaining: float = Field(ge=0)
    initial_stock: int = Field(gt=0)
    promo_copy: str = Field(default="", max_length=1000)


class PhoneRequest(StrictModel):
    phone: str = Field(pattern=r"^\+62\d{9,13}$")


class OtpVerifyRequest(PhoneRequest):
    otp: str = Field(pattern=r"^\d{6}$")


class ShopRequest(StrictModel):
    shop_name: str = Field(min_length=1, max_length=160)
    business_type: str = Field(min_length=1, max_length=80)
    short_address: str | None = Field(default=None, max_length=300)


class ChatRequest(StrictModel):
    session_id: str | None = Field(default=None, min_length=1, max_length=64)
    action: str = Field(default="message", min_length=1, max_length=32)
    text: str | None = Field(default=None, max_length=1000)
    patch: dict[str, Any] | None = None
    image_data_uri: str | None = Field(default=None, max_length=7_500_000)


class ImageChatForm(StrictModel):
    session_id: str | None = Field(default=None, min_length=1, max_length=64)
    action: str = Field(default="message", min_length=1, max_length=32)
    text: str | None = Field(default=None, max_length=1000)


def create_app(
    *,
    database_path: str | Path | None = None,
    model: TextModel | None = None,
) -> FastAPI:
    limits = ChatLimits.from_env()
    image_limits = ImageLimits(
        max_bytes=limits.image_max_bytes,
        max_pixels=limits.image_max_pixels,
        max_width=limits.image_max_width,
        max_height=limits.image_max_height,
        max_frames=limits.image_max_frames,
        max_decoded_bytes=limits.image_max_decoded_bytes,
        temp_ttl_seconds=limits.image_temp_ttl_seconds,
    )
    database = Database(database_path or os.getenv("HARGATURUN_DB", "data/hargaturun.db"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.initialize()
        yield

    app = FastAPI(title="HargaTurun API", version="0.1.0", lifespan=lifespan)
    app.state.database = database
    app.state.model = model or OpenAICompatibleModel(
        base_url=limits.model_url,
        model=limits.model_name,
        max_output_tokens=limits.max_output_tokens,
        timeout=limits.model_timeout_seconds,
    )
    app.state.sessions = SessionStore(
        max_sessions=limits.max_sessions,
        max_turns=limits.max_turns,
        max_context_chars=limits.max_context_chars,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Dipasang setelah CORS supaya penolakan tetap membawa header CORS dan
    # browser bisa membaca statusnya, bukan melihatnya sebagai kegagalan jaringan.
    app.add_middleware(
        RateLimitMiddleware,
        limit=limits.rate_limit,
        window_seconds=limits.rate_window_seconds,
    )
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=limits.max_body_bytes,
        multipart_max_bytes=max(limits.max_body_bytes, limits.image_max_bytes + 64 * 1024),
    )

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/api/recommend", response_model=None)
    def recommend(payload: RecommendRequest):
        input_data: dict[str, Any]
        used_model_for_parse = payload.free_text is not None
        if used_model_for_parse:
            try:
                parsed = app.state.model.parse(payload.free_text)
            except (ModelUnavailable, ModelContractError):
                return JSONResponse(
                    status_code=502,
                    content={
                        "status": "model_unavailable",
                        "message": "Sistem AI sedang tidak tersedia. Coba lagi sebentar.",
                    },
                )
            input_data = _normalize_display_names(parsed["parsed_input"])
            if parsed["needs_confirmation"]:
                return JSONResponse(
                    status_code=422,
                    content={
                        "status": "needs_confirmation",
                        "parsed_input": input_data,
                        "missing_fields": parsed["missing_fields"],
                    },
                )
        else:
            input_data = _normalize_display_names(
                payload.model_dump(exclude_none=True, exclude={"free_text"})
            )

        missing = _missing_pricing_fields(input_data)
        if missing:
            return JSONResponse(
                status_code=422,
                content={
                    "status": "needs_confirmation",
                    "parsed_input": input_data,
                    "missing_fields": missing,
                },
            )
        if input_data["category"] not in CATEGORIES:
            return JSONResponse(
                status_code=422,
                content={"status": "invalid_input", "message": "Kategori barang tidak valid."},
            )

        oracle = compute(
            PricingInput(
                category=input_data["category"],
                original_price=input_data["original_price"],
                cost=input_data["cost"],
                stock=input_data["stock"],
                days_remaining=input_data["days_remaining"],
                daily_sales=input_data["daily_sales"],
                total_shelf_life=input_data.get("total_shelf_life"),
            )
        )
        if oracle.status == STATUS_INVALID:
            return JSONResponse(
                status_code=422,
                content={"status": "invalid_input", "message": oracle.message},
            )
        if oracle.status == STATUS_NO_ACTION:
            return {
                "status": "no_action",
                "message": oracle.message,
                "reassess_in_days": oracle.reassess_in_days,
            }

        normalized = {
            **input_data,
            "total_shelf_life": oracle.used_shelf_life,
        }
        engine_result = to_engine_result(oracle)
        explanation = ""
        promo_copy = ""
        try:
            prose = app.state.model.write(normalized, engine_result)
            explanation = prose["explanation"]
            promo_copy = prose["promo_copy"]
        except (ModelUnavailable, ModelContractError):
            # Numbers-only degradation: pricing remains fully authoritative and
            # the structured flow still works when local inference is offline.
            pass

        recommendation = oracle.recommendation_dict()
        return {
            "status": "recommendation",
            "normalized_input": normalized,
            "recommendation": recommendation,
            "explanation": explanation,
            "promo_copy": promo_copy,
            "preview": {
                "item_name": normalized["item_name"],
                "shop_name": normalized.get("shop_name") or "Tokomu",
                "original_price": normalized["original_price"],
                "deal_price": recommendation["recommended_price"],
                "discount_percent": recommendation["discount_percent"],
                "days_remaining": normalized["days_remaining"],
                "stock": normalized["stock"],
            },
        }

    @app.post("/api/chat", response_model=None)
    async def chat(payload: ChatRequest):
        normalized = None
        if payload.image_data_uri is not None:
            try:
                raw, media_type = decode_data_uri(payload.image_data_uri, image_limits)
                normalized = normalize_image(raw, media_type, image_limits)
                payload = payload.model_copy(update={"image_data_uri": normalized.data_uri()})
            except ImageIngestionError:
                return JSONResponse(status_code=422, content={"detail": "Gambar tidak valid."})
        try:
            return await _chat_turn(payload)
        finally:
            if normalized is not None:
                normalized.cleanup()

    async def _chat_turn(payload: ChatRequest):
        """One synchronous consultation turn.

        Every decision below is taken by code. The model is asked only to
        propose field patches; it never chooses the action, never supplies a
        number, and cannot reach the pricing tool directly.
        """
        if payload.action not in REQUEST_ACTIONS:
            return JSONResponse(
                status_code=422,
                content={"detail": "Aksi tidak dikenal."},
            )

        sessions: SessionStore = app.state.sessions

        if payload.session_id is None:
            session = sessions.create()
        else:
            session = sessions.get(payload.session_id)
            if session is None:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Sesi konsultasi tidak ditemukan."},
                )

        if payload.action == "reset":
            sessions.drop(session.session_id)
            fresh = sessions.create()
            return _chat_response(
                fresh,
                action=ASK_FOR_MISSING_FIELDS,
                message="Oke, kita mulai dari awal. Cerita saja barangmu.",
            )

        if not sessions.accept_turn(session.session_id, payload.action, len(payload.text or "")):
            logger.info("chat event=limit_rejected action=%s", payload.action)
            return JSONResponse(
                status_code=429,
                content={"detail": "Batas konsultasi tercapai. Mulai sesi baru untuk melanjutkan."},
            )
        logger.info("chat event=accepted action=%s", payload.action)

        # --- gather a proposed patch ------------------------------------- #
        proposed: object = {}
        if payload.action == "message":
            if not (payload.text or "").strip() and payload.image_data_uri is None:
                return JSONResponse(
                    status_code=422,
                    content={"detail": "Pesan tidak boleh kosong."},
                )
            try:
                if payload.image_data_uri is not None:
                    parser = getattr(app.state.model, "parse_multimodal")
                    parsed = await _run_inference(
                        parser,
                        payload.text or "",
                        payload.image_data_uri,
                        timeout=limits.inference_timeout_seconds,
                    )
                    parsed_input = parsed.get("parsed_input", {})
                    proposed = _image_safe_proposal(parsed_input)
                    # Images never establish pricing facts.
                    proposed = {
                        key: value for key, value in proposed.items()
                        if key not in {"original_price", "cost", "daily_sales"}
                    }
                else:
                    parsed = await _run_inference(
                        app.state.model.parse,
                        payload.text or "",
                        timeout=limits.inference_timeout_seconds,
                    )
                    proposed = parsed.get("parsed_input", {})
            except Exception:
                # State survives an outage: nothing is merged, nothing is lost.
                # Provider details are intentionally not returned.
                return _chat_response(
                    session,
                    action=SAFE_FAILURE,
                    message=(
                        "Sistem AI sedang tidak tersedia. Datamu tetap tersimpan — "
                        "coba lagi, atau isi form manual."
                    ),
                )
        elif payload.action == "confirm":
            proposed = payload.patch or {}

        accepted, _rejected = validate_patch(proposed, allowed_categories=CATEGORIES)
        before = session.state
        session.state = merge_patch(session.state, accepted)
        if session.state.revision != before.revision:
            # An accepted change invalidates any previous result.
            session.drop_result()

        if payload.action == "confirm":
            session.state = confirm_state(session.state)

        # --- decide and act ---------------------------------------------- #
        action = decide_action(session.state, has_result=session.result is not None)

        if payload.action == "calculate" and action != CALL_PRICING_TOOL:
            # Explicit calculate on an unconfirmed or incomplete state performs
            # no tool call at all; the client is told what is still needed.
            return _chat_response(session, action=action, message=_prompt_for(action, session))

        if action == CALL_PRICING_TOOL:
            tool: PricingTool = PricingTool()
            try:
                oracle = tool.compute(session.state)
            except PricingToolRefused:
                return _chat_response(
                    session,
                    action=SAFE_FAILURE,
                    message="Datanya belum siap dihitung.",
                )

            session.result = await _result_payload(
                session.state,
                oracle,
                app.state.model,
                timeout=limits.inference_timeout_seconds,
            )
            session.result_status = oracle.status
            session.state = ConsultationState(
                **{**session.state.to_dict(), "result_revision": session.state.revision}
            )
            action = EXPLAIN_RESULT

        return _chat_response(session, action=action, message=_prompt_for(action, session))

    @app.post("/api/chat/image", response_model=None)
    async def chat_image(
        session_id: str | None = Form(default=None),
        action: str = Form(default="message"),
        text: str | None = Form(default=None),
        image: UploadFile = File(...),
        image_url: str | None = Form(default=None),
    ):
        """Bounded multipart image variant; bytes are validated before inference."""
        if image_url is not None:
            try:
                reject_remote_url(image_url)
            except ImageIngestionError:
                return JSONResponse(status_code=422, content={"detail": "Gambar tidak valid."})
        try:
            raw = await image.read(limits.image_max_bytes + 1)
            normalized = normalize_image(raw, image.content_type, image_limits)
        except ImageIngestionError:
            return JSONResponse(status_code=422, content={"detail": "Gambar tidak valid."})
        try:
            if action != "message":
                return JSONResponse(status_code=422, content={"detail": "Aksi tidak dikenal."})
            if not (text or "").strip():
                text = "Ekstrak fakta eksplisit dari gambar saja."
            payload = ChatRequest(
                session_id=session_id,
                action=action,
                text=text,
                image_data_uri=normalized.data_uri(),
            )
            return await chat(payload)
        finally:
            normalized.cleanup()

    @app.post("/api/auth/otp/request", status_code=204)
    def request_otp(_: PhoneRequest) -> Response:
        return Response(status_code=204)

    @app.post("/api/auth/otp/verify")
    def verify_otp(payload: OtpVerifyRequest) -> dict:
        expected = os.getenv("HARGATURUN_DEMO_OTP", "123456")
        if not hmac.compare_digest(payload.otp, expected):
            raise HTTPException(status_code=422, detail="Kode salah.")
        with database.connect() as connection:
            shop = connection.execute(
                "SELECT shop_name, business_type, short_address FROM shops WHERE phone = ?",
                (payload.phone,),
            ).fetchone()
        shop_data = dict(shop) if shop else None
        return {
            "phone": payload.phone,
            "token": _make_token(payload.phone),
            "is_new_vendor": shop is None,
            "shop": _normalize_display_names(shop_data) if shop_data else None,
        }

    @app.post("/api/shops")
    def save_shop(
        payload: ShopRequest,
        phone: Annotated[str, Depends(_authenticated_phone)],
    ) -> dict:
        shop_data = _normalize_display_names(payload.model_dump())
        if not shop_data["shop_name"]:
            raise HTTPException(status_code=422, detail="Nama toko wajib diisi.")
        with database.session() as connection:
            connection.execute(
                """INSERT INTO shops(phone, shop_name, business_type, short_address)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(phone) DO UPDATE SET
                     shop_name=excluded.shop_name,
                     business_type=excluded.business_type,
                     short_address=excluded.short_address""",
                (
                    phone,
                    shop_data["shop_name"],
                    shop_data["business_type"],
                    shop_data["short_address"],
                ),
            )
        return shop_data

    @app.post("/api/deals", status_code=201)
    def publish_deal(payload: PublishDealRequest) -> dict:
        if payload.category not in CATEGORIES:
            raise HTTPException(status_code=422, detail="Kategori barang tidak valid.")
        if payload.cost >= payload.original_price:
            raise HTTPException(status_code=422, detail="Harga modal harus di bawah harga jual.")
        if payload.deal_price < payload.cost + MIN_MARGIN_RP:
            raise HTTPException(status_code=422, detail="Harga deal di bawah modal + Rp500.")
        if payload.deal_price >= payload.original_price:
            raise HTTPException(status_code=422, detail="Harga deal harus di bawah harga asli.")
        computed_discount = round(100 - payload.deal_price / payload.original_price * 100)
        if abs(computed_discount - payload.discount_percent) > 1:
            raise HTTPException(status_code=422, detail="Persentase diskon tidak sesuai harga deal.")

        display_names = _normalize_display_names(
            {"item_name": payload.item_name, "shop_name": payload.shop_name}
        )
        if not display_names["item_name"] or not display_names["shop_name"]:
            raise HTTPException(
                status_code=422,
                detail="Nama barang dan nama toko wajib diisi.",
            )
        deal_id = secrets.token_hex(12)
        created_at = _now()
        with database.session() as connection:
            connection.execute(
                """INSERT INTO deals(
                     id,item_name,shop_name,category,original_price,cost,deal_price,
                     discount_percent,days_remaining,initial_stock,remaining_stock,
                     promo_copy,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    deal_id, display_names["item_name"], display_names["shop_name"], payload.category,
                    payload.original_price, payload.cost, payload.deal_price,
                    payload.discount_percent, payload.days_remaining,
                    payload.initial_stock, payload.initial_stock, payload.promo_copy,
                    "active", created_at,
                ),
            )
            row = connection.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        return _deal_dict(row)

    @app.get("/api/deals")
    def list_deals(
        deal_status: Annotated[str | None, Query(alias="status")] = None,
        shop_name: str | None = None,
    ) -> list[dict]:
        if deal_status is not None and deal_status not in DEAL_STATUSES:
            raise HTTPException(status_code=422, detail="Status deal tidak valid.")
        clauses: list[str] = []
        values: list[Any] = []
        if deal_status:
            clauses.append("status = ?")
            values.append(deal_status)
        if shop_name:
            clauses.append("shop_name = ?")
            values.append(shop_name)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with database.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM deals{where} ORDER BY days_remaining ASC, created_at DESC",
                values,
            ).fetchall()
        return [_deal_dict(row) for row in rows]

    @app.delete("/api/deals/{deal_id}", status_code=204)
    def remove_deal(deal_id: str) -> Response:
        with database.session() as connection:
            cursor = connection.execute(
                "UPDATE deals SET status = 'removed' WHERE id = ?",
                (deal_id,),
            )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Deal tidak ditemukan.")
        return Response(status_code=204)

    @app.post("/api/deals/{deal_id}/claims", status_code=201)
    def claim_deal(deal_id: str) -> dict:
        with database.transaction(immediate=True) as connection:
            deal = connection.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
            if deal is None or deal["status"] != "active" or deal["remaining_stock"] <= 0:
                raise HTTPException(status_code=409, detail="Stok sudah habis atau deal tidak tersedia.")
            remaining = deal["remaining_stock"] - 1
            next_status = "sold_out" if remaining == 0 else "active"
            connection.execute(
                "UPDATE deals SET remaining_stock = ?, status = ? WHERE id = ?",
                (remaining, next_status, deal_id),
            )
            code = _new_claim_code(connection)
            created_at = _now()
            connection.execute(
                "INSERT INTO claims(code, deal_id, status, created_at) VALUES (?, ?, 'claimed', ?)",
                (code, deal_id, created_at),
            )
            claim = connection.execute(
                _CLAIM_SELECT + " WHERE claims.code = ?", (code,),
            ).fetchone()
        return _claim_dict(claim)

    @app.post("/api/claims/{code}/redeem")
    def redeem_claim(code: str) -> dict:
        normalized = code.strip().upper()
        with database.transaction(immediate=True) as connection:
            claim = connection.execute(
                _CLAIM_SELECT + " WHERE UPPER(claims.code) = ?", (normalized,),
            ).fetchone()
            if claim is None:
                raise HTTPException(status_code=404, detail="Kode tidak ditemukan. Cek lagi hurufnya.")
            if claim["status"] == "redeemed":
                raise HTTPException(status_code=409, detail="Kode ini sudah digunakan.")
            # Claims reserve stock at claim time and remain redeemable after a
            # vendor removes the public listing (Final SRS §7.5 policy).
            redeemed_at = _now()
            connection.execute(
                "UPDATE claims SET status = 'redeemed', redeemed_at = ? WHERE code = ?",
                (redeemed_at, claim["code"]),
            )
            updated = connection.execute(
                _CLAIM_SELECT + " WHERE claims.code = ?", (claim["code"],),
            ).fetchone()
        return _claim_dict(updated)

    @app.get("/api/claims")
    def list_claims() -> list[dict]:
        with database.connect() as connection:
            rows = connection.execute(_CLAIM_SELECT + " ORDER BY claims.created_at DESC").fetchall()
        return [_claim_dict(row) for row in rows]

    @app.get("/api/deals/{deal_id}/claims")
    def list_deal_claims(deal_id: str) -> list[dict]:
        with database.connect() as connection:
            exists = connection.execute("SELECT 1 FROM deals WHERE id = ?", (deal_id,)).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail="Deal tidak ditemukan.")
            rows = connection.execute(
                _CLAIM_SELECT + " WHERE claims.deal_id = ? ORDER BY claims.created_at DESC",
                (deal_id,),
            ).fetchall()
        return [_claim_dict(row) for row in rows]

    return app


_FIELD_LABELS = {
    "item_name": "nama barangnya",
    "category": "kategorinya",
    "original_price": "harga jual sekarang",
    "cost": "harga modal per barang",
    "stock": "jumlah stoknya",
    "days_remaining": "sisa berapa hari lagi",
    "daily_sales": "rata-rata terjual per hari",
}


def _image_safe_proposal(proposed: object) -> dict[str, Any]:
    """Keep image extraction advisory and never accept economic guesses.

    The model may identify labels/names and unambiguous physical facts, but
    image-derived cost and sales-rate values can never enter consultation state.
    Confirmation remains required because this is still model output.
    """
    if not isinstance(proposed, dict):
        return {}
    allowed = {
        "item_name", "category", "stock", "days_remaining",
        "total_shelf_life", "shop_name",
    }
    return {key: value for key, value in proposed.items() if key in allowed}


def _prompt_for(action: str, session: Any) -> str:
    """Assistant copy chosen by action, not generated by the model."""
    state = session.state
    if action == ASK_FOR_MISSING_FIELDS:
        missing = [_FIELD_LABELS.get(f, f) for f in state.missing_fields()]
        if not missing:
            return "Sudah lengkap."
        if len(missing) == 1:
            return f"Tinggal satu lagi: {missing[0]}?"
        return "Tinggal beberapa ini: " + ", ".join(missing) + "."
    if action == SHOW_CONFIRMATION:
        return "Semua sudah kucatat. Cek dulu, kalau ada yang salah perbaiki."
    if action == EXPLAIN_RESULT:
        if session.result_status == STATUS_RECOMMENDATION:
            return "Ini rekomendasinya."
        if session.result_status == STATUS_NO_ACTION:
            return "Barang ini belum perlu didiskon."
        return "Ada yang perlu diperiksa dulu."
    if action == OUT_OF_SCOPE:
        return "Aku cuma bisa bantu soal harga diskon satu barang."
    return "Ada kendala di sistem. Datamu tetap tersimpan."




async def _result_payload(
    state: Any,
    oracle: Any,
    model: Any,
    *,
    timeout: float,
) -> dict:
    """Serialize one oracle outcome for the chat contract.

    Prose is requested from the model only after the numbers exist, and its
    absence degrades to numbers-only rather than failing the turn.
    """
    if oracle.status == STATUS_NO_ACTION:
        return {
            "status": "no_action",
            "revision": state.revision,
            "message": oracle.message,
            "reassess_in_days": oracle.reassess_in_days,
        }
    if oracle.status == STATUS_INVALID:
        return {
            "status": "invalid_input",
            "revision": state.revision,
            "message": oracle.message,
        }

    normalized = {**state.to_dict(), "total_shelf_life": oracle.used_shelf_life}
    for key in ("confirmed", "revision", "result_revision"):
        normalized.pop(key, None)

    explanation = ""
    promo_copy = ""
    try:
        prose = await _run_inference(
            model.write,
            normalized,
            to_engine_result(oracle),
            timeout=timeout,
        )
        explanation = prose["explanation"]
        promo_copy = prose["promo_copy"]
    except Exception:
        pass

    recommendation = oracle.recommendation_dict()
    return {
        "status": "recommendation",
        "revision": state.revision,
        "normalized_input": normalized,
        "recommendation": recommendation,
        "explanation": explanation,
        "promo_copy": promo_copy,
        "preview": {
            "item_name": normalized["item_name"],
            "shop_name": normalized.get("shop_name") or "Tokomu",
            "original_price": normalized["original_price"],
            "deal_price": recommendation["recommended_price"],
            "discount_percent": recommendation["discount_percent"],
            "days_remaining": normalized["days_remaining"],
            "stock": normalized["stock"],
        },
    }


def _chat_response(session: Any, *, action: str, message: str) -> dict:
    state = session.state
    result = session.result
    # A result is only exposed while its revision still matches the state.
    if result is not None and result.get("revision") != state.revision:
        result = None
    return {
        "session_id": session.session_id,
        "action": action,
        "assistant_message": message,
        "state": state.to_dict(),
        "missing_fields": state.missing_fields(),
        "ambiguous_fields": [],
        "result": result,
    }


_MAX_INFERENCE_RESULT_BYTES = 1 * 1024 * 1024


def _apply_worker_state(callable_: Any, state: dict[str, Any] | None) -> None:
    owner = getattr(callable_, "__self__", None)
    target = getattr(owner, "__dict__", None)
    if isinstance(target, dict) and isinstance(state, dict):
        target.clear()
        target.update(state)


async def _run_inference(callable_: Any, *args: Any, timeout: float) -> Any:
    """Run every synchronous provider call in a disposable spawn worker."""
    if os.name == "nt":
        raise RuntimeError("cancellable inference is unsupported on Windows; use Linux or macOS")

    context = multiprocessing.get_context("spawn")
    parent = child = None
    process = None
    try:
        parent, child = context.Pipe(duplex=False)
        request = InferenceRequest(
            callable_=callable_,
            args=tuple(args),
            max_result_bytes=_MAX_INFERENCE_RESULT_BYTES,
        )
        process = context.Process(target=run_inference_worker, args=(request, child))
        process.start()
        child.close()
        child = None
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            if parent.poll():
                response = pickle.loads(parent.recv_bytes(_MAX_INFERENCE_RESULT_BYTES))
                _apply_worker_state(callable_, response.get("state"))
                if not response.get("ok"):
                    raise RuntimeError("inference failed")
                return response["value"]
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            await asyncio.sleep(min(0.01, remaining))
    finally:
        if parent is not None:
            parent.close()
        if child is not None:
            child.close()
        if process is not None and process.pid is not None:
            if process.is_alive():
                process.terminate()
            await asyncio.to_thread(process.join, 1.0)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join, 1.0)


def _normalize_display_names(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    for field in ("item_name", "shop_name"):
        value = normalized.get(field)
        if isinstance(value, str):
            normalized[field] = _strip_wrapping_quotes(value)
    return normalized


def _strip_wrapping_quotes(value: str) -> str:
    """Remove quote punctuation wrapped around a user-visible name only."""
    result = value.strip()
    quote_pairs = (("'", "'"), ('"', '"'), ("‘", "’"), ("“", "”"), ("«", "»"))
    while len(result) >= 2:
        pair = next(
            ((opening, closing) for opening, closing in quote_pairs
             if result.startswith(opening) and result.endswith(closing)),
            None,
        )
        if pair is None:
            break
        unwrapped = result[len(pair[0]):-len(pair[1])].strip()
        if not unwrapped:
            return ""
        result = unwrapped
    return result


def _missing_pricing_fields(data: dict[str, Any]) -> list[str]:
    required = (
        "item_name", "category", "original_price", "cost", "stock",
        "days_remaining", "daily_sales",
    )
    return [
        field
        for field in required
        if data.get(field) is None
        or (isinstance(data.get(field), str) and not data[field].strip())
    ]


def _cors_origins() -> list[str]:
    configured = os.getenv("HARGATURUN_CORS_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    # Default lokal, bukan wildcard: origin produksi harus dinyatakan eksplisit
    # lewat HARGATURUN_CORS_ORIGINS. Port 3000 = frontend compose (HARGATURUN_WEB_PORT),
    # 5555 = `flutter run` dev server, 8080 = build web lokal.
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5555",
        "http://127.0.0.1:5555",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _token_secret() -> bytes:
    return os.getenv("HARGATURUN_TOKEN_SECRET", "local-demo-only-change-me").encode()


def _make_token(phone: str) -> str:
    payload = base64.urlsafe_b64encode(phone.encode()).decode().rstrip("=")
    signature = hmac.new(_token_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _authenticated_phone(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sesi tidak valid.")
    token = authorization[7:]
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(_token_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        padding = "=" * (-len(payload) % 4)
        phone = base64.urlsafe_b64decode(payload + padding).decode()
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail="Sesi tidak valid.") from None
    return phone


def _deal_dict(row: Any) -> dict:
    return {
        "id": row["id"],
        "item_name": _strip_wrapping_quotes(row["item_name"]),
        "shop_name": _strip_wrapping_quotes(row["shop_name"]),
        "category": row["category"],
        "original_price": row["original_price"],
        "cost": row["cost"],
        "deal_price": row["deal_price"],
        "discount_percent": row["discount_percent"],
        "days_remaining": row["days_remaining"],
        "initial_stock": row["initial_stock"],
        "remaining_stock": row["remaining_stock"],
        "promo_copy": row["promo_copy"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


_CLAIM_SELECT = """
SELECT claims.code, claims.deal_id, claims.status, claims.created_at, claims.redeemed_at,
       deals.item_name, deals.shop_name, deals.deal_price AS price_to_pay,
       deals.status AS deal_status
FROM claims JOIN deals ON deals.id = claims.deal_id
"""


def _claim_dict(row: Any) -> dict:
    return {
        "code": row["code"],
        "deal_id": row["deal_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "redeemed_at": row["redeemed_at"],
        "item_name": _strip_wrapping_quotes(row["item_name"]),
        "shop_name": _strip_wrapping_quotes(row["shop_name"]),
        "price_to_pay": row["price_to_pay"],
    }


def _new_claim_code(connection: Any) -> str:
    for _ in range(100):
        code = f"HT-{secrets.randbelow(9000) + 1000}"
        if connection.execute("SELECT 1 FROM claims WHERE code = ?", (code,)).fetchone() is None:
            return code
    raise HTTPException(status_code=503, detail="Tidak dapat membuat kode klaim.")
