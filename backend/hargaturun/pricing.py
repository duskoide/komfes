"""HargaTurun deterministic pricing engine — the "oracle".

Single source of truth for every NUMBER in the system. Implements the 10-step
formula in ``docs/HargaTurun_Project_Spec.md`` §9.5. Pure functions, no I/O, no
model, no network: the same input always yields the same output (competition
rule: *parameter statis*, reproducible).

Used in two places — write once, use twice:

* production — the pricing authority behind ``POST /api/recommend``
* training   — the ground-truth generator for the fine-tuning dataset (§10)

The model never does arithmetic; this module never writes prose.

Penyisihan scope only: there is intentionally NO ``prev_stock`` argument, daily
re-run adjustment, or learning loop here — those belong to the final round
(see ``docs/HargaTurun_Penyisihan_SRS.md`` §5.5).

A few edge cases are under-specified in §9.5; where that happens this module
makes the choice that best honors the document's *stated hard guarantees* — the
recommended price is never below ``cost + Rp500``, and the displayed discount
never exceeds the margin ceiling — and marks the decision with a NOTE comment.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Constants (§9.5)                                                            #
# --------------------------------------------------------------------------- #

# The eight allowed categories. Canonical spelling matters — these strings are
# the enum shared with the API contract and the training data.
CATEGORIES: tuple[str, ...] = (
    "Bakery",
    "Prepared Food",
    "Dairy",
    "Beverage",
    "Produce",
    "Snack",
    "Canned",
    "Other",
)

# Default total shelf life (days) when the vendor does not supply one. Always
# disclosed in the result so the vendor can correct it.
DEFAULT_SHELF_LIFE: dict[str, float] = {
    "Bakery": 4,
    "Prepared Food": 3,
    "Dairy": 14,
    "Beverage": 5,
    "Produce": 7,
    "Snack": 90,
    "Canned": 365,
    "Other": 30,
}

# Soft elasticity prior (§9.5 Step 3). NOT a precise coefficient — a starting
# bias. Bakery discounts stimulate demand strongly; canned goods barely react.
CATEGORY_BIAS: dict[str, float] = {
    "Bakery": 1.3,
    "Prepared Food": 1.3,
    "Dairy": 1.1,
    "Beverage": 1.0,  # baseline
    "Produce": 1.1,
    "Snack": 0.9,
    "Canned": 0.7,
    "Other": 1.0,
}

# Tunable formula parameters (§9.5 "Parameter Tuning"). Starting values.
URGENCY_EXPONENT = 1.5           # how aggressively urgency ramps near expiry
BASE_SCALE = 80                  # maps the raw score into a discount-% range
PRESSURE_DIVISOR = 4.0           # pressure 1->5 maps to pressure_factor 0->1
SELLTHROUGH_DISCOUNT_FACTOR = 50  # crude "discount boosts demand" model

# Hard bounds / conventions.
DISCOUNT_MIN = 5     # percent — below this, not worth bothering
DISCOUNT_MAX = 70    # percent — absolute ceiling
DISCOUNT_STEP = 5    # discounts round to 5% (Indonesian pricing convention)
PRICE_STEP = 500     # prices round to Rp500 (Indonesian pricing convention)
MIN_MARGIN_RP = 500  # at least Rp500 profit per unit must remain

# Thresholds for the special cases / branches.
NO_ACTION_URGENCY = 0.7   # §9.5: no action if pressure <= 1.0 AND urgency < this
LOW_STOCK_UNITS = 2       # stock <= this -> minimal discount
LOW_STOCK_MAX_DISCOUNT = 15
FIRE_SALE_DAYS = 1.0      # days_remaining < this (but > 0) -> fire sale

# Result status values.
STATUS_RECOMMENDATION = "recommendation"
STATUS_NO_ACTION = "no_action"
STATUS_INVALID = "invalid_input"

# Confidence wording.
CONF_OK = "Cukup yakin"
CONF_LOW = "Prediksi kurang pasti"


# --------------------------------------------------------------------------- #
# Small deterministic numeric helpers                                         #
# --------------------------------------------------------------------------- #

def clamp(value: float, low: float, high: float) -> float:
    """Standard clamp. ``low`` must be <= ``high``."""
    return max(low, min(high, value))


def round_half_up(value: float) -> int:
    """Round to the nearest integer, ties going up. Deterministic (Python's
    built-in ``round`` uses banker's rounding, which surprises humans)."""
    return int(math.floor(value + 0.5))


def round_to_step(value: float, step: int) -> int:
    """Round to the nearest multiple of ``step``, ties going up."""
    return round_half_up(value / step) * step


def floor_to_step(value: float, step: int) -> int:
    """Round DOWN to a multiple of ``step`` (used to stay under a hard ceiling)."""
    return int(math.floor(value / step)) * step


def normalize_category(category: str) -> str:
    """Map arbitrary casing/spacing onto a canonical category. Raises for a
    genuinely unknown category — that is a programming/enum error the API layer
    should have caught, not a vendor-input case."""
    if category in CATEGORY_BIAS:
        return category
    key = " ".join(category.strip().split()).lower()
    for canonical in CATEGORIES:
        if canonical.lower() == key:
            return canonical
    raise ValueError(f"Unknown category: {category!r}. Expected one of {CATEGORIES}.")


# --------------------------------------------------------------------------- #
# Input / output data structures                                              #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PricingInput:
    """Confirmed, normalized inputs to the oracle. All economic fields must
    already be present and confirmed — the oracle never invents a value."""

    category: str
    original_price: int   # Rupiah per sellable unit
    cost: int             # Rupiah cost per sellable unit
    stock: int            # whole sellable units / servings
    days_remaining: float
    daily_sales: float
    total_shelf_life: float | None = None  # None -> category default


@dataclass(frozen=True)
class OracleResult:
    """One deterministic outcome. ``status`` selects which fields are set.

    * ``recommendation`` — all the numeric fields below are populated.
    * ``no_action``      — ``message`` + ``reassess_in_days``.
    * ``invalid_input``  — ``message`` (and ``expired`` when relevant).
    """

    status: str

    # --- recommendation fields --------------------------------------------
    discount_percent: int | None = None
    recommended_price: int | None = None
    timing: str | None = None
    expected_sell_through_units: int | None = None
    expected_revenue: int | None = None
    expected_loss_no_action: int | None = None
    confidence: str | None = None
    is_fire_sale: bool = False

    # --- no_action fields --------------------------------------------------
    reassess_in_days: int | None = None

    # --- invalid_input fields ---------------------------------------------
    expired: bool = False

    # --- shared / diagnostic ----------------------------------------------
    message: str | None = None
    stock: int | None = None
    used_shelf_life: float | None = None
    shelf_life_defaulted: bool = False
    pressure: float | None = None
    urgency: float | None = None

    def sell_through_text(self, unit: str = "pcs") -> str | None:
        """Render "8 dari 10 pcs" for the recommendation contract."""
        if self.expected_sell_through_units is None or self.stock is None:
            return None
        return f"{self.expected_sell_through_units} dari {self.stock} {unit}"

    def recommendation_dict(self, unit: str = "pcs") -> dict | None:
        """The ``recommendation`` object of the API response, or None if this
        result is not a recommendation."""
        if self.status != STATUS_RECOMMENDATION:
            return None
        return {
            "discount_percent": self.discount_percent,
            "recommended_price": self.recommended_price,
            "timing": self.timing,
            "expected_sell_through": self.sell_through_text(unit),
            "expected_revenue": self.expected_revenue,
            "expected_loss_no_action": self.expected_loss_no_action,
            "confidence": self.confidence,
        }


# --------------------------------------------------------------------------- #
# The oracle                                                                  #
# --------------------------------------------------------------------------- #

def compute(inp: PricingInput) -> OracleResult:
    """Run the §9.5 oracle on confirmed input and return exactly one outcome.

    Evaluation order (documented, because it resolves overlaps §9.5 leaves
    implicit):

    1. invalid economics / numbers  -> invalid_input
    2. already expired              -> invalid_input (expired)
    3. fire sale (expires today)    -> recommendation (aggressive, margin-safe)
    4. no action (low pressure)     -> no_action
    5. very low stock cap           -> recommendation (<=15%)
    6. normal formula               -> recommendation
    """
    category = normalize_category(inp.category)
    price = inp.original_price
    cost = inp.cost
    stock = inp.stock
    days = float(inp.days_remaining)
    daily = float(inp.daily_sales)

    shelf_defaulted = inp.total_shelf_life is None
    shelf = float(DEFAULT_SHELF_LIFE[category] if shelf_defaulted else inp.total_shelf_life)

    # -- 1. invalid economics / numbers ------------------------------------
    if price <= 0 or cost < 0 or stock <= 0 or daily <= 0 or shelf <= 0:
        return OracleResult(
            status=STATUS_INVALID,
            message="Input tidak valid. Mohon periksa angka harga, modal, stok, dan penjualan.",
            stock=stock if stock > 0 else None,
        )
    if cost >= price:
        return OracleResult(
            status=STATUS_INVALID,
            message="Harga modal ≥ harga jual. Mohon cek input Anda.",
            stock=stock,
        )

    # -- 2. already expired -------------------------------------------------
    if days <= 0:
        return OracleResult(
            status=STATUS_INVALID,
            expired=True,
            message="Item sudah kadaluarsa. Pertimbangkan untuk dibuang atau didonasikan.",
            stock=stock,
        )

    # -- shared intermediates (Steps 1-3, 5) --------------------------------
    days_of_supply = stock / daily
    pressure = days_of_supply / days
    life_consumed = clamp(1.0 - days / shelf, 0.0, 1.0)  # clamp: days may exceed shelf
    urgency = life_consumed ** URGENCY_EXPONENT
    bias = CATEGORY_BIAS[category]

    margin_percent = (price - cost) / price * 100.0
    # Margin ceiling (Step 5): keep at least Rp500 profit per unit.
    max_discount = min(DISCOUNT_MAX, margin_percent - (MIN_MARGIN_RP / price * 100.0))

    # -- 3. fire sale: expires today ---------------------------------------
    if days < FIRE_SALE_DAYS:
        # Override: go as deep as the margin ceiling allows. Max urgency
        # regardless of the pressure ratio (§9.5 special case).
        discount = _finalize_discount(raw=float(DISCOUNT_MAX), max_discount=max_discount)
        return _build_recommendation(
            discount=discount, price=price, cost=cost, stock=stock, days=days,
            daily=daily, pressure=pressure, urgency=urgency,
            timing="HARI INI SAJA!", is_fire_sale=True,
            shelf=shelf, shelf_defaulted=shelf_defaulted,
        )

    # -- 4. no action: item will likely sell before expiry ------------------
    if pressure <= 1.0 and urgency < NO_ACTION_URGENCY:
        # Reassess roughly halfway through the remaining runway (heuristic —
        # §9.5 leaves "X" unspecified; the vendor re-runs daily anyway).
        reassess = max(1, round_half_up(days / 2))
        return OracleResult(
            status=STATUS_NO_ACTION,
            message=(
                "Belum perlu diskon. Item ini kemungkinan terjual normal sebelum "
                f"kadaluarsa. Cek lagi dalam {reassess} hari."
            ),
            reassess_in_days=reassess,
            stock=stock,
            used_shelf_life=shelf,
            shelf_life_defaulted=shelf_defaulted,
            pressure=pressure,
            urgency=urgency,
        )

    # -- Steps 4 (raw discount) --------------------------------------------
    pressure_factor = clamp((pressure - 1.0) / PRESSURE_DIVISOR, 0.0, 1.0)
    raw_discount = pressure_factor * urgency * bias * BASE_SCALE

    # -- 5. very low stock: minimal discount, aggressive markdown not worth it
    if stock <= LOW_STOCK_UNITS:
        raw_discount = min(raw_discount, LOW_STOCK_MAX_DISCOUNT)

    # -- 6. finalize discount + price + projections -------------------------
    discount = _finalize_discount(raw=raw_discount, max_discount=max_discount)

    # Timing (Step 9). The pressure<=1.0 & urgency<0.7 branch already returned
    # above as no_action, so only the remaining two apply here.
    timing = "Bisa tunggu 1 hari, cek lagi besok" if pressure <= 1.5 else "Mulai diskon hari ini"

    return _build_recommendation(
        discount=discount, price=price, cost=cost, stock=stock, days=days,
        daily=daily, pressure=pressure, urgency=urgency,
        timing=timing, is_fire_sale=False,
        shelf=shelf, shelf_defaulted=shelf_defaulted,
    )


def _finalize_discount(raw: float, max_discount: float) -> int:
    """Clamp to [5, ceiling], round to 5%, and never overshoot the hard margin
    ceiling.

    NOTE: §9.5 Step 6 literally says ``round_to_5(clamp(raw, 5, max_discount))``.
    Rounding a value like 47.5 up to 50 would push the *displayed* discount past
    the margin ceiling and make it disagree with the (margin-protected) price.
    Since the margin ceiling is a stated HARD constraint, we round DOWN to the
    nearest 5% when the naive rounding would overshoot it. In the common case
    (e.g. the 30% worked example) this is byte-identical to the literal formula.
    When the ceiling is below 5% (razor-thin margin) this can yield 0 — the
    honest answer that no margin-safe discount exists; the price floor in
    ``_build_recommendation`` still guarantees ``price >= cost + Rp500``.
    """
    clamped = clamp(raw, DISCOUNT_MIN, max(DISCOUNT_MIN, max_discount))
    discount = round_to_step(clamped, DISCOUNT_STEP)
    if discount > max_discount:
        discount = floor_to_step(max_discount, DISCOUNT_STEP)
    return max(0, discount)


def _build_recommendation(
    *,
    discount: int,
    price: int,
    cost: int,
    stock: int,
    days: float,
    daily: float,
    pressure: float,
    urgency: float,
    timing: str,
    is_fire_sale: bool,
    shelf: float,
    shelf_defaulted: bool,
) -> OracleResult:
    """Steps 7, 8, 10 — turn a finalized discount into the full recommendation.
    Guarantees ``recommended_price >= cost + Rp500`` by construction."""
    # Step 7 — recommended price, with the absolute margin floor.
    recommended_price = round_to_step(price * (1 - discount / 100.0), PRICE_STEP)
    recommended_price = max(recommended_price, cost + MIN_MARGIN_RP)

    # Step 8 — impact projections.
    est_sell = min(stock, daily * days * (1 + discount / SELLTHROUGH_DISCOUNT_FACTOR))
    sell_units = min(stock, round_half_up(est_sell))
    expected_revenue = sell_units * recommended_price

    baseline_sell = min(stock, daily * days)
    expected_loss_no_action = max(0, round_half_up((stock - baseline_sell) * cost))

    # Step 10 — confidence.
    if daily < 1:
        confidence = CONF_LOW
    else:
        confidence = CONF_OK
    if pressure > 3 and urgency > 0.8:
        confidence = CONF_OK  # clear-cut situation regardless of data quality

    result = OracleResult(
        status=STATUS_RECOMMENDATION,
        discount_percent=discount,
        recommended_price=recommended_price,
        timing=timing,
        expected_sell_through_units=sell_units,
        expected_revenue=expected_revenue,
        expected_loss_no_action=expected_loss_no_action,
        confidence=confidence,
        is_fire_sale=is_fire_sale,
        stock=stock,
        used_shelf_life=shelf,
        shelf_life_defaulted=shelf_defaulted,
        pressure=pressure,
        urgency=urgency,
    )

    # Post-condition: the one guarantee the vendor relies on.
    assert result.recommended_price >= cost + MIN_MARGIN_RP
    return result
