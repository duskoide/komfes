"""Frozen model I/O contracts — the parse and write tasks.

This is deliverable #2 in the Fine-Tuning Plan (§9): the frozen parse/write
schemas and prompts that the training data, the model, and the API all agree on.
It is the single place those three meet, so it must not drift.

Two model tasks (Fine-Tuning Plan §1.2, §2):

* ``parse`` — free text -> ``parsed_input`` + ``missing_fields`` + ``needs_confirmation``.
  The model extracts explicit facts only; it never invents economic values and
  never emits a recommendation.
* ``write`` — confirmed ``normalized_input`` + the deterministic ``engine_result``
  -> ``explanation`` + ``promo_copy``. The model treats the engine result as
  authoritative and may only reuse numbers already present in its input.

Validation here is intentionally pure-stdlib (no ``jsonschema`` dependency) so it
runs everywhere the oracle does — in tests and in the dataset generator's quality
gates (§3.6).
"""

from __future__ import annotations

from .pricing import (
    CATEGORIES,
    STATUS_INVALID,
    STATUS_NO_ACTION,
    STATUS_RECOMMENDATION,
    OracleResult,
)

# --------------------------------------------------------------------------- #
# Field contracts                                                             #
# --------------------------------------------------------------------------- #

ALLOWED_CATEGORIES: tuple[str, ...] = CATEGORIES

# Fields the model must produce in `parsed_input`. `shop_name` is the only
# optional one (Fine-Tuning Plan §2.1).
PARSE_REQUIRED_FIELDS: tuple[str, ...] = (
    "item_name",
    "category",
    "original_price",
    "cost",
    "stock",
    "days_remaining",
    "daily_sales",
    "total_shelf_life",
)
PARSE_OPTIONAL_FIELDS: tuple[str, ...] = ("shop_name",)
PARSE_ALL_FIELDS: tuple[str, ...] = PARSE_REQUIRED_FIELDS + PARSE_OPTIONAL_FIELDS

# Numeric parse fields, used by the round-trip and "no fabricated number" gates.
PARSE_NUMERIC_FIELDS: tuple[str, ...] = (
    "original_price",
    "cost",
    "stock",
    "days_remaining",
    "daily_sales",
    "total_shelf_life",
)

# Engine-result status vocabulary the *model* sees in the write task. The oracle
# internally uses "invalid_input"; the write task calls that "warning"
# (Fine-Tuning Plan §2.2). This module owns that single translation.
WRITE_STATUS_RECOMMENDATION = "recommendation"
WRITE_STATUS_NO_ACTION = "no_action"
WRITE_STATUS_WARNING = "warning"
WRITE_STATUSES: tuple[str, ...] = (
    WRITE_STATUS_RECOMMENDATION,
    WRITE_STATUS_NO_ACTION,
    WRITE_STATUS_WARNING,
)

# The recommendation engine_result carries exactly these keys (Fine-Tuning Plan
# §2.2 example).
ENGINE_RECOMMENDATION_KEYS: tuple[str, ...] = (
    "status",
    "discount_percent",
    "recommended_price",
    "timing",
    "expected_sell_through",
    "expected_revenue",
    "expected_loss_no_action",
    "confidence",
)


# --------------------------------------------------------------------------- #
# Frozen system prompts                                                        #
# --------------------------------------------------------------------------- #
# These are the frozen prompts referenced by the Fine-Tuning Plan. Keep them
# stable across baseline eval, training, and serving — changing them invalidates
# recorded evaluation runs (§4.1 records the prompt version with every result).

PARSE_PROMPT_VERSION = "parse-v1"
WRITE_PROMPT_VERSION = "write-v1"

PARSE_SYSTEM_PROMPT = """\
Anda adalah pengurai input untuk HargaTurun, asisten harga UMKM makanan Indonesia.
Tugas Anda HANYA mengekstrak fakta yang tertulis eksplisit dari teks pemilik toko
menjadi JSON. Anda tidak menghitung apa pun dan tidak memberi rekomendasi.

Keluarkan HANYA satu objek JSON dengan bentuk:
{"task":"parse","parsed_input":{"item_name","category","original_price","cost",
"stock","days_remaining","daily_sales","total_shelf_life","shop_name"},
"missing_fields":[...],"needs_confirmation":true|false}

Aturan:
- category harus salah satu dari: Bakery, Prepared Food, Dairy, Beverage, Produce,
  Snack, Canned, Other. Jika tidak jelas, gunakan null.
- Pertahankan nilai eksplisit setelah normalisasi satuan (15rb -> 15000, besok -> 1).
- Gunakan null untuk nilai yang tidak ada atau ambigu. JANGAN menebak harga, modal,
  laju penjualan, kategori, atau masa simpan dari bukti yang tidak cukup.
- daily_sales dan total_shelf_life wajib; jika tidak tertulis, biarkan null.
- needs_confirmation bernilai true bila ada field wajib yang null atau ambigu.
- Jangan menulis penjelasan, promosi, atau kalimat lain. JSON saja."""

WRITE_SYSTEM_PROMPT = """\
Anda adalah penulis teks untuk HargaTurun, asisten harga UMKM makanan Indonesia.
Anda menerima input yang sudah dikonfirmasi (normalized_input) dan hasil mesin
harga (engine_result) yang bersifat OTORITATIF. Tugas Anda menulis teks Bahasa
Indonesia yang wajar berdasarkan angka tersebut.

Keluarkan HANYA satu objek JSON:
{"task":"write","explanation":"...","promo_copy":"..."}

Aturan:
- Perlakukan engine_result sebagai final. JANGAN menghitung ulang atau mengubah
  angka apa pun. Salin angka HANYA dari engine_result atau normalized_input.
- explanation: 2-4 kalimat ringkas Bahasa Indonesia menjelaskan alasan hasilnya.
- promo_copy: 1-2 kalimat Bahasa Indonesia. JANGAN membuat promosi/diskon untuk
  status no_action atau warning; untuk kedua status itu promo_copy boleh kosong
  atau berupa imbauan singkat tanpa klaim diskon.
- Nada promo ramah dan mendesak secukupnya, tanpa klaim menyesatkan. JSON saja."""


# --------------------------------------------------------------------------- #
# OracleResult  ->  engine_result (the write task's authoritative input)      #
# --------------------------------------------------------------------------- #

def to_engine_result(result: OracleResult, unit: str = "pcs") -> dict:
    """Translate an :class:`OracleResult` into the ``engine_result`` object the
    write task consumes. This is the ONLY place the oracle's internal
    ``invalid_input`` status becomes the model-facing ``warning``."""
    if result.status == STATUS_RECOMMENDATION:
        return {"status": WRITE_STATUS_RECOMMENDATION, **result.recommendation_dict(unit)}
    if result.status == STATUS_NO_ACTION:
        return {
            "status": WRITE_STATUS_NO_ACTION,
            "message": result.message,
            "reassess_in_days": result.reassess_in_days,
        }
    if result.status == STATUS_INVALID:
        return {"status": WRITE_STATUS_WARNING, "message": result.message}
    raise ValueError(f"Unexpected oracle status: {result.status!r}")


# --------------------------------------------------------------------------- #
# Lightweight validators (stdlib only)                                        #
# --------------------------------------------------------------------------- #

def validate_parse_output(obj: object) -> list[str]:
    """Return a list of contract violations for a parse-task output. Empty list
    means valid. Used by tests and the generator's quality gates (§3.6)."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["parse output is not a JSON object"]
    if obj.get("task") != "parse":
        errors.append("task must be 'parse'")

    parsed = obj.get("parsed_input")
    if not isinstance(parsed, dict):
        errors.append("parsed_input must be an object")
        parsed = {}
    else:
        for key in parsed:
            if key not in PARSE_ALL_FIELDS:
                errors.append(f"unexpected parsed_input field: {key!r}")
        for field in PARSE_REQUIRED_FIELDS:
            if field not in parsed:
                errors.append(f"parsed_input missing key: {field!r}")

    category = parsed.get("category")
    if category is not None and category not in ALLOWED_CATEGORIES:
        errors.append(f"invalid category: {category!r}")

    # Parse targets must never carry recommendation fields (§3.6 gate 4).
    for leaked in ("discount_percent", "recommended_price", "recommendation",
                   "explanation", "promo_copy"):
        if leaked in obj or leaked in parsed:
            errors.append(f"parse output leaks recommendation field: {leaked!r}")

    missing = obj.get("missing_fields")
    if not isinstance(missing, list):
        errors.append("missing_fields must be a list")
        missing = []

    needs = obj.get("needs_confirmation")
    if not isinstance(needs, bool):
        errors.append("needs_confirmation must be a boolean")

    # Consistency: needs_confirmation must reflect the actual required-field gaps
    # (a null required field, or one named in missing_fields).
    gap = any(parsed.get(f) is None for f in PARSE_REQUIRED_FIELDS) or bool(missing)
    if isinstance(needs, bool) and needs != gap:
        errors.append(
            f"needs_confirmation={needs} contradicts required-field gaps (gap={gap})"
        )
    return errors


def validate_write_output(obj: object, allowed_numbers: set[int] | None = None) -> list[str]:
    """Return contract violations for a write-task output. When
    ``allowed_numbers`` is given, enforce §3.6 gate 6: the prose contains no
    integer absent from the engine input."""
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["write output is not a JSON object"]
    if obj.get("task") != "write":
        errors.append("task must be 'write'")

    explanation = obj.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        errors.append("explanation must be a non-empty string")

    promo = obj.get("promo_copy")
    if not isinstance(promo, str):
        errors.append("promo_copy must be a string")

    if allowed_numbers is not None:
        for text in (explanation, promo):
            if isinstance(text, str):
                for n in _extract_integers(text):
                    if n not in allowed_numbers:
                        errors.append(f"unsupported number in prose: {n}")
    return errors


def _extract_integers(text: str) -> list[int]:
    """Pull integers out of prose, tolerating Indonesian thousands separators
    (``Rp10.500`` -> 10500) and percents (``30%`` -> 30). Deliberately simple —
    it backs a safety gate, so over-collecting is fine (fails closed)."""
    out: list[int] = []
    token = ""
    for ch in text:
        if ch.isdigit():
            token += ch
        elif ch == "." and token:
            # possible thousands separator: keep accumulating, drop the dot
            continue
        else:
            if token:
                out.append(int(token))
                token = ""
    if token:
        out.append(int(token))
    return out


def allowed_numbers_for(normalized_input: dict, engine_result: dict) -> set[int]:
    """The set of integers a write output may legitimately mention: every number
    in the confirmed input and in the engine result."""
    allowed: set[int] = set()

    def add(value: object) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            allowed.add(value)
        elif isinstance(value, float) and value.is_integer():
            allowed.add(int(value))
        elif isinstance(value, str):
            allowed.update(_extract_integers(value))

    for source in (normalized_input, engine_result):
        for value in (source or {}).values():
            add(value)
    return allowed
