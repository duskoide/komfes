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

import math
import re

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
PARSE_OUTPUT_KEYS: tuple[str, ...] = (
    "task",
    "parsed_input",
    "missing_fields",
    "needs_confirmation",
)
WRITE_OUTPUT_KEYS: tuple[str, ...] = ("task", "explanation", "promo_copy")

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

PARSE_PROMPT_VERSION = "parse-v2"
WRITE_PROMPT_VERSION = "write-v2"

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
- missing_fields harus memuat tepat field wajib yang bernilai null, sesuai urutan
  field pada parsed_input di atas.
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
- promo_copy: 1-2 kalimat Bahasa Indonesia untuk status recommendation. Untuk
  status no_action atau warning, promo_copy WAJIB berupa string kosong.
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
    """Return parse-contract violations; an empty list means valid.

    Missing required values are represented by ``null`` and must be mirrored
    exactly, in contract order, by ``missing_fields``. Non-null values still
    receive strict type and domain validation so malformed model output cannot
    enter either training data or the pricing engine.
    """
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["parse output is not a JSON object"]

    _validate_exact_keys(obj, PARSE_OUTPUT_KEYS, "parse output", errors)
    if obj.get("task") != "parse":
        errors.append("task must be 'parse'")

    parsed = obj.get("parsed_input")
    if not isinstance(parsed, dict):
        errors.append("parsed_input must be an object")
        parsed = {}
    else:
        allowed = set(PARSE_ALL_FIELDS)
        for key in parsed:
            if key not in allowed:
                errors.append(f"unexpected parsed_input field: {key!r}")
        for field in PARSE_REQUIRED_FIELDS:
            if field not in parsed:
                errors.append(f"parsed_input missing key: {field!r}")

    _validate_nullable_string(parsed, "item_name", errors, required=True)
    _validate_nullable_string(parsed, "shop_name", errors, required=False)

    category = parsed.get("category")
    if category is not None:
        if not isinstance(category, str):
            errors.append("category must be a string or null")
        elif category not in ALLOWED_CATEGORIES:
            errors.append(f"invalid category: {category!r}")

    _validate_nullable_integer(parsed, "original_price", errors, minimum=1)
    _validate_nullable_integer(parsed, "cost", errors, minimum=0)
    _validate_nullable_integer(parsed, "stock", errors, minimum=1)
    _validate_nullable_number(parsed, "days_remaining", errors, minimum=0, inclusive=True)
    _validate_nullable_number(parsed, "daily_sales", errors, minimum=0, inclusive=False)
    _validate_nullable_number(parsed, "total_shelf_life", errors, minimum=0, inclusive=False)

    # Parse targets must never carry recommendation fields (§3.6 gate 4).
    for leaked in ("discount_percent", "recommended_price", "recommendation",
                   "explanation", "promo_copy"):
        if leaked in obj or leaked in parsed:
            errors.append(f"parse output leaks recommendation field: {leaked!r}")

    missing = obj.get("missing_fields")
    if not isinstance(missing, list):
        errors.append("missing_fields must be a list")
        missing = []
    else:
        if any(not isinstance(field, str) for field in missing):
            errors.append("missing_fields entries must be strings")
        if len(missing) != len(set(field for field in missing if isinstance(field, str))):
            errors.append("missing_fields must not contain duplicates")
        unknown = [field for field in missing if field not in PARSE_REQUIRED_FIELDS]
        if unknown:
            errors.append(f"missing_fields contains unknown fields: {unknown!r}")

    expected_missing = [
        field for field in PARSE_REQUIRED_FIELDS
        if field not in parsed or parsed.get(field) is None
    ]
    if missing != expected_missing:
        errors.append(
            f"missing_fields must exactly match null required fields: {expected_missing!r}"
        )

    needs = obj.get("needs_confirmation")
    if not isinstance(needs, bool):
        errors.append("needs_confirmation must be a boolean")
    elif needs != bool(expected_missing):
        errors.append(
            f"needs_confirmation={needs} contradicts required-field gaps "
            f"(gap={bool(expected_missing)})"
        )
    return errors


def validate_write_output(
    obj: object,
    allowed_numbers: set[int | float] | None = None,
    engine_status: str | None = None,
) -> list[str]:
    """Return write-contract violations; an empty list means valid.

    ``engine_status`` is optional for backward compatibility, but callers that
    have the engine result should pass it. Doing so enforces that recommendations
    contain promo copy while ``no_action`` and ``warning`` never advertise one.
    """
    errors: list[str] = []
    if not isinstance(obj, dict):
        return ["write output is not a JSON object"]

    _validate_exact_keys(obj, WRITE_OUTPUT_KEYS, "write output", errors)
    if obj.get("task") != "write":
        errors.append("task must be 'write'")

    explanation = obj.get("explanation")
    if not isinstance(explanation, str) or not explanation.strip():
        errors.append("explanation must be a non-empty string")
    elif not 2 <= _sentence_count(explanation) <= 4:
        errors.append("explanation must contain 2-4 sentences")

    promo = obj.get("promo_copy")
    if not isinstance(promo, str):
        errors.append("promo_copy must be a string")
    else:
        promo_sentences = _sentence_count(promo)
        if engine_status == WRITE_STATUS_RECOMMENDATION:
            if not promo.strip():
                errors.append("recommendation promo_copy must be non-empty")
            elif not 1 <= promo_sentences <= 2:
                errors.append("recommendation promo_copy must contain 1-2 sentences")
        elif engine_status in (WRITE_STATUS_NO_ACTION, WRITE_STATUS_WARNING):
            if promo.strip():
                errors.append(f"{engine_status} promo_copy must be empty")
        elif engine_status is not None:
            errors.append(f"invalid engine_status: {engine_status!r}")
        elif promo.strip() and not 1 <= promo_sentences <= 2:
            errors.append("promo_copy must contain 1-2 sentences")

    if allowed_numbers is not None:
        for text in (explanation, promo):
            if isinstance(text, str):
                for number in _extract_numbers(text):
                    if number not in allowed_numbers:
                        errors.append(f"unsupported number in prose: {number}")
    return errors


def _validate_exact_keys(
    obj: dict, expected: tuple[str, ...], label: str, errors: list[str]
) -> None:
    allowed = set(expected)
    for key in obj:
        if key not in allowed:
            errors.append(f"unexpected {label} field: {key!r}")
    for key in expected:
        if key not in obj:
            errors.append(f"{label} missing key: {key!r}")


def _validate_nullable_string(
    obj: dict, field: str, errors: list[str], *, required: bool
) -> None:
    if field not in obj:
        if required:
            return  # missing-key error is emitted by the caller
        return
    value = obj[field]
    if value is not None and (not isinstance(value, str) or not value.strip()):
        errors.append(f"{field} must be a non-empty string or null")


def _validate_nullable_integer(
    obj: dict, field: str, errors: list[str], *, minimum: int
) -> None:
    if field not in obj or obj[field] is None:
        return
    value = obj[field]
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{field} must be an integer or null")
    elif value < minimum:
        errors.append(f"{field} must be >= {minimum}")


def _validate_nullable_number(
    obj: dict,
    field: str,
    errors: list[str],
    *,
    minimum: float,
    inclusive: bool,
) -> None:
    if field not in obj or obj[field] is None:
        return
    value = obj[field]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (isinstance(value, float) and not math.isfinite(value))
    ):
        errors.append(f"{field} must be a finite number or null")
    elif (value < minimum if inclusive else value <= minimum):
        operator = ">=" if inclusive else ">"
        errors.append(f"{field} must be {operator} {minimum:g}")


def _sentence_count(text: str) -> int:
    """Count non-empty sentence-like spans using terminal punctuation.

    A final span without punctuation still counts. Dots inside prices such as
    ``Rp10.500`` do not split because they are not followed by whitespace/end.
    """
    stripped = text.strip()
    if not stripped:
        return 0
    return len([part for part in re.split(r"[.!?]+(?:\s+|$)", stripped) if part.strip()])


_CURRENCY_RE = re.compile(r"(?i)\bRp\s*(\d{1,3}(?:\.\d{3})+|\d+)")
_NUMBER_RE = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?(?![\w])")


def _extract_numbers(text: str) -> list[int | float]:
    """Extract exact numeric claims from Indonesian prose.

    Rupiah thousands separators are normalized (``Rp10.500`` -> ``10500``),
    while decimals stay decimals (``4.5`` -> ``4.5``), preventing them from
    masquerading as an allowed integer such as ``45``.
    """
    out: list[int | float] = []
    chars = list(text)
    for match in _CURRENCY_RE.finditer(text):
        out.append(int(match.group(1).replace(".", "")))
        chars[match.start():match.end()] = " " * (match.end() - match.start())

    remainder = "".join(chars)
    for match in _NUMBER_RE.finditer(remainder):
        token = match.group(0)
        if "." in token or "," in token:
            out.append(float(token.replace(",", ".")))
        else:
            out.append(int(token))
    return out


def allowed_numbers_for(
    normalized_input: dict, engine_result: dict
) -> set[int | float]:
    """Numbers a write output may mention from confirmed input/engine output."""
    allowed: set[int | float] = set()

    def add(value: object) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)) and (
            not isinstance(value, float) or math.isfinite(value)
        ):
            allowed.add(value)
        elif isinstance(value, str):
            allowed.update(_extract_numbers(value))

    for source in (normalized_input, engine_result):
        for value in (source or {}).values():
            add(value)
    return allowed
