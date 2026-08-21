"""Synthetic dataset generator and quality gates for the parse/write tasks.

Implements deliverable #4 of the Fine-Tuning Plan (``docs/HargaTurun_FineTuning_Plan.md``
§3): a deterministic, stdlib-only generator that turns UMKM pricing *scenarios*
into labelled ``parse`` and ``write`` examples, plus the §3.6 quality gates that
must pass before any file is written.

Design rules taken straight from the plan:

* **Scenario first (§3.1).** A scenario owns a stable ``scenario_id``, one
  ``normalized_input`` and one ``engine_result`` (from the real
  :func:`hargaturun.pricing.compute`). Parse and write examples are *derived*
  from a scenario; augmented variants are never counted as new scenarios.
* **Leakage-safe split (§3.2).** The split is assigned per scenario *before* any
  paraphrase/variant expansion, so every variant of one scenario stays in one
  split. The three scenario-id sets are asserted disjoint.
* **Exact, reversible rendering (§3.3).** Colloquial number/day/unit labels are
  produced by renderers that only fire when the value is exactly representable,
  and every rendered numeric label is parsed back and asserted to round-trip.
* **No fabricated economics (§1.1, §3.4/§3.5).** The oracle computes every
  number; parse targets never carry recommendation fields; write prose reuses
  only numbers already present in its own input.

The generator is pure standard library so it runs anywhere the oracle does —
in unit tests and in CI — without a dependency install.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .pricing import (
    CATEGORIES,
    DEFAULT_SHELF_LIFE,
    STATUS_INVALID,
    STATUS_NO_ACTION,
    STATUS_RECOMMENDATION,
    PricingInput,
    compute,
)
from . import schemas


# --------------------------------------------------------------------------- #
# Errors                                                                      #
# --------------------------------------------------------------------------- #

class RoundTripError(ValueError):
    """A rendered numeric label did not parse back to its exact source value."""


class QualityGateError(ValueError):
    """One or more §3.6 dataset quality gates failed."""


# --------------------------------------------------------------------------- #
# Reversible renderers and their exact inverses (§3.3, §3.4)                   #
# --------------------------------------------------------------------------- #
# Every renderer returns ``None`` when the value cannot be represented exactly
# in that style, so the caller simply skips styles that would lose information.

def render_rupiah(value: int, style: str) -> str | None:
    """Render a whole-Rupiah amount in one colloquial style, or ``None`` if the
    style cannot represent ``value`` without rounding.

    Styles: ``full`` (``15000``), ``dots`` (``15.000``), ``rb`` (``15rb``),
    ``ribu`` (``15 ribu``), ``k`` (``15k``), ``jt`` (``1,5jt`` / ``2jt``).
    """
    if value < 0:
        return None
    if style == "full":
        return str(value)
    if style == "dots":
        return f"{value:,}".replace(",", ".")
    if style in ("rb", "ribu", "k"):
        if value == 0 or value % 1_000 != 0:
            return None
        thousands = value // 1_000
        return {"rb": f"{thousands}rb", "ribu": f"{thousands} ribu", "k": f"{thousands}k"}[style]
    if style == "jt":
        # Exact only when at most one decimal place of millions is needed.
        if value < 1_000_000 or value % 100_000 != 0:
            return None
        millions = value / 1_000_000
        text = f"{millions:.1f}".rstrip("0").rstrip(".")
        return f"{text.replace('.', ',')}jt"
    raise ValueError(f"unknown rupiah style: {style!r}")


def parse_rupiah(label: str) -> int:
    """Inverse of :func:`render_rupiah`. Raises :class:`RoundTripError` if the
    label does not resolve to a whole number of Rupiah."""
    s = label.strip().lower().replace("rp", "").replace(" ", "")
    multiplier = 1
    if s.endswith("jt"):
        multiplier, s = 1_000_000, s[:-2]
    elif s.endswith("ribu"):
        multiplier, s = 1_000, s[:-4]
    elif s.endswith("rb"):
        multiplier, s = 1_000, s[:-2]
    elif s.endswith("k"):
        multiplier, s = 1_000, s[:-1]
    s = s.replace(".", "")  # thousands separator
    try:
        value = (float(s.replace(",", ".")) if "," in s else int(s)) * multiplier
    except ValueError as exc:
        raise RoundTripError(f"cannot parse rupiah label {label!r}") from exc
    as_int = int(round(value))
    if as_int != value:
        raise RoundTripError(f"rupiah label {label!r} is not a whole number")
    return as_int


_DAY_WORDS = {0: "hari ini", 1: "besok", 2: "lusa"}
_DAY_WORDS_INVERSE = {word: value for value, word in _DAY_WORDS.items()}


def render_days(value: int, style: str) -> str | None:
    """Render an integer day count. ``word`` uses hari ini/besok/lusa where they
    apply; ``count`` uses ``"N hari"``. Returns ``None`` if unavailable."""
    if value < 0:
        return None
    if style == "word":
        return _DAY_WORDS.get(value)
    if style == "count":
        return f"{value} hari"
    raise ValueError(f"unknown day style: {style!r}")


def parse_days(label: str) -> int:
    """Inverse of :func:`render_days`."""
    text = label.strip().lower()
    if text in _DAY_WORDS_INVERSE:
        return _DAY_WORDS_INVERSE[text]
    stripped = text.replace("hari", "").strip()
    try:
        return int(stripped)
    except ValueError as exc:
        raise RoundTripError(f"cannot parse day label {label!r}") from exc


_COUNT_UNITS = ("pcs", "biji", "buah", "porsi")


def render_count(value: int, unit: str) -> str | None:
    """Render a whole count with an optional unit word (``""`` omits the unit)."""
    if value < 0:
        return None
    if unit == "":
        return str(value)
    if unit in _COUNT_UNITS:
        return f"{value} {unit}"
    raise ValueError(f"unknown count unit: {unit!r}")


def parse_count(label: str) -> int:
    """Inverse of :func:`render_count`."""
    text = label.strip().lower()
    for unit in _COUNT_UNITS:
        text = text.replace(unit, "")
    try:
        return int(text.strip())
    except ValueError as exc:
        raise RoundTripError(f"cannot parse count label {label!r}") from exc


# --------------------------------------------------------------------------- #
# Scenario model                                                              #
# --------------------------------------------------------------------------- #

_SPLITS = ("train", "validation", "test")


@dataclass(frozen=True)
class Scenario:
    """One canonical pricing situation. Examples derive from it (§3.1)."""

    scenario_id: str
    split: str
    normalized_input: dict          # full parse-complete input (all 9 fields)
    engine_result: dict             # write-task engine_result (via schemas)
    parseable: bool                 # False -> write-only (e.g. expired/fire-sale)


def _slug(category: str) -> str:
    return category.lower().replace(" ", "-")


def _make_scenario(
    index: int,
    split: str,
    *,
    category: str,
    item_name: str,
    shop_name: str,
    original_price: int,
    cost: int,
    stock: int,
    days_remaining: float,
    daily_sales: float,
    total_shelf_life: float,
    parseable: bool,
) -> Scenario:
    """Build one scenario, computing its authoritative engine_result."""
    result = compute(
        PricingInput(
            category=category,
            original_price=original_price,
            cost=cost,
            stock=stock,
            days_remaining=days_remaining,
            daily_sales=daily_sales,
            total_shelf_life=total_shelf_life,
        )
    )
    normalized_input = {
        "item_name": item_name,
        "category": category,
        "original_price": original_price,
        "cost": cost,
        "stock": stock,
        "days_remaining": days_remaining,
        "daily_sales": daily_sales,
        "total_shelf_life": total_shelf_life,
        "shop_name": shop_name,
    }
    return Scenario(
        scenario_id=f"{_slug(category)}-{index:06d}",
        split=split,
        normalized_input=normalized_input,
        engine_result=schemas.to_engine_result(result),
        parseable=parseable,
    )


# --------------------------------------------------------------------------- #
# Scenario value generation (§3.3)                                            #
# --------------------------------------------------------------------------- #

_ITEM_NAMES = {
    "Bakery": ["Roti Tawar", "Donat Cokelat", "Croissant", "Roti Sobek"],
    "Prepared Food": ["Nasi Kotak", "Ayam Geprek", "Gado-Gado", "Mie Ayam"],
    "Dairy": ["Susu UHT", "Yogurt Botol", "Keju Slice", "Es Krim Cup"],
    "Beverage": ["Jus Jeruk", "Teh Botol", "Kopi Susu", "Air Kelapa"],
    "Produce": ["Bayam Ikat", "Tomat", "Pisang Cavendish", "Cabai Merah"],
    "Snack": ["Keripik Singkong", "Kacang Telur", "Wafer Cokelat", "Biskuit"],
    "Canned": ["Sarden Kaleng", "Kornet", "Jagung Kaleng", "Susu Kental Manis"],
    "Other": ["Bumbu Instan", "Telur Ayam", "Tahu", "Tempe"],
}

_SHOP_NAMES = [
    "Toko Sari Bakery", "Kedai Bu Rina", "Warung Pak Andi",
    "Toko Berkah", "Kios Mama Ita", "",
]


def _round_to(value: int, step: int) -> int:
    return max(step, (value // step) * step)


def _gen_prices(rng: random.Random) -> tuple[int, int]:
    """Return (original_price, cost) with cost < original_price (§3.3)."""
    original_price = rng.randrange(2_000, 150_001, 500)
    # keep a real margin so most scenarios are priceable; leave headroom > Rp500
    max_cost = max(1_000, original_price - 1_000)
    cost = rng.randrange(1_000, max_cost + 1, 500)
    return original_price, cost


def _recommendation_scenario(index, split, rng, category) -> Scenario:
    """High sell-through pressure -> the oracle issues a markdown."""
    original_price, cost = _gen_prices(rng)
    days = rng.randint(1, 3)
    daily = rng.randint(1, 4)
    # stock well above what can sell in the remaining days -> pressure > 1
    stock = rng.randint(daily * days + 5, daily * days + 40)
    return _make_scenario(
        index, split, category=category,
        item_name=rng.choice(_ITEM_NAMES[category]),
        shop_name=rng.choice(_SHOP_NAMES),
        original_price=original_price, cost=cost, stock=min(stock, 100),
        days_remaining=days, daily_sales=daily,
        total_shelf_life=DEFAULT_SHELF_LIFE[category], parseable=True,
    )


def _no_action_scenario(index, split, rng, category) -> Scenario:
    """Plenty of shelf life left and low pressure -> no_action."""
    original_price, cost = _gen_prices(rng)
    shelf = DEFAULT_SHELF_LIFE[category]
    # days close to full shelf life -> low urgency; low stock -> low pressure
    days = max(2, int(shelf) - rng.randint(0, max(1, int(shelf) // 4)))
    daily = rng.randint(3, 8)
    stock = rng.randint(1, daily)  # sells faster than it stocks -> pressure < 1
    return _make_scenario(
        index, split, category=category,
        item_name=rng.choice(_ITEM_NAMES[category]),
        shop_name=rng.choice(_SHOP_NAMES),
        original_price=original_price, cost=cost, stock=stock,
        days_remaining=float(days), daily_sales=daily,
        total_shelf_life=shelf, parseable=True,
    )


def _expired_scenario(index, split, rng, category) -> Scenario:
    """days_remaining == 0 -> the oracle returns an expired warning."""
    original_price, cost = _gen_prices(rng)
    return _make_scenario(
        index, split, category=category,
        item_name=rng.choice(_ITEM_NAMES[category]),
        shop_name=rng.choice(_SHOP_NAMES),
        original_price=original_price, cost=cost,
        stock=rng.randint(1, 20), days_remaining=0,
        daily_sales=rng.randint(1, 6),
        total_shelf_life=DEFAULT_SHELF_LIFE[category], parseable=True,
    )


def _margin_warning_scenario(index, split, rng, category) -> Scenario:
    """cost >= original_price -> invalid-input warning (write-only: the input is
    economically invalid, so it is not a valid parse target)."""
    original_price = rng.randrange(3_000, 50_001, 500)
    cost = original_price + rng.randrange(0, 3_000, 500)  # >= price
    return _make_scenario(
        index, split, category=category,
        item_name=rng.choice(_ITEM_NAMES[category]),
        shop_name=rng.choice(_SHOP_NAMES),
        original_price=original_price, cost=cost,
        stock=rng.randint(1, 20), days_remaining=rng.randint(1, 3),
        daily_sales=rng.randint(1, 6),
        total_shelf_life=DEFAULT_SHELF_LIFE[category], parseable=False,
    )


def _fire_sale_scenario(index, split, rng, category) -> Scenario:
    """0 < days_remaining < 1 -> fire-sale recommendation (write-only: fractional
    days do not have a clean reversible free-text rendering)."""
    original_price, cost = _gen_prices(rng)
    return _make_scenario(
        index, split, category=category,
        item_name=rng.choice(_ITEM_NAMES[category]),
        shop_name=rng.choice(_SHOP_NAMES),
        original_price=original_price, cost=cost,
        stock=rng.randint(3, 30), days_remaining=0.5,
        daily_sales=rng.randint(1, 6),
        total_shelf_life=DEFAULT_SHELF_LIFE[category], parseable=False,
    )


# Each builder targets a specific engine outcome so quotas (§3.6 gate 7) are met
# deterministically rather than hoped for from random draws.
_STATUS_BUILDERS: tuple[Callable[..., Scenario], ...] = (
    _recommendation_scenario,
    _no_action_scenario,
    _expired_scenario,
    _margin_warning_scenario,
    _fire_sale_scenario,
)


# --------------------------------------------------------------------------- #
# Free-text rendering for parse examples (§3.4)                               #
# --------------------------------------------------------------------------- #

@dataclass
class RenderedField:
    """A numeric field as it appears in free text, kept for the round-trip gate."""

    field: str
    label: str
    value: int
    parser: Callable[[str], int]


def _pick_rupiah_label(value: int, rng: random.Random) -> str:
    styles = [s for s in ("full", "dots", "rb", "ribu", "k", "jt")
              if render_rupiah(value, s) is not None]
    style = rng.choice(styles)
    return render_rupiah(value, style)  # type: ignore[return-value]


def _render_parse_text(scenario: Scenario, rng: random.Random,
                       drop: set[str]) -> tuple[str, list[RenderedField]]:
    """Render a colloquial free-text message for a scenario, omitting any field
    in ``drop``. Returns the text and the numeric labels that must round-trip."""
    ni = scenario.normalized_input
    rendered: list[RenderedField] = []
    fragments: list[str] = []

    name = ni["item_name"]
    fragments.append(f"Jualan {name.lower()}" if rng.random() < 0.5 else f"Ada stok {name.lower()}")

    if "original_price" not in drop:
        label = _pick_rupiah_label(ni["original_price"], rng)
        fragments.append(f"harga jual Rp{label}")
        rendered.append(RenderedField("original_price", label, ni["original_price"], parse_rupiah))
    if "cost" not in drop:
        label = _pick_rupiah_label(ni["cost"], rng)
        fragments.append(f"modal Rp{label}")
        rendered.append(RenderedField("cost", label, ni["cost"], parse_rupiah))
    if "stock" not in drop:
        unit = rng.choice(_COUNT_UNITS + ("",))
        label = render_count(int(ni["stock"]), unit)
        fragments.append(f"sisa stok {label}")
        rendered.append(RenderedField("stock", label, int(ni["stock"]), parse_count))
    if "daily_sales" not in drop:
        unit = rng.choice(_COUNT_UNITS + ("",))
        label = render_count(int(ni["daily_sales"]), unit)
        fragments.append(f"biasanya laku {label} per hari")
        rendered.append(RenderedField("daily_sales", label, int(ni["daily_sales"]), parse_count))
    if "days_remaining" not in drop:
        value = int(ni["days_remaining"])
        style = "word" if (rng.random() < 0.5 and render_days(value, "word")) else "count"
        label = render_days(value, style)
        fragments.append(f"kadaluarsa {label}")
        rendered.append(RenderedField("days_remaining", label, value, parse_days))
    if "total_shelf_life" not in drop:
        value = int(ni["total_shelf_life"])
        label = render_days(value, "count")
        fragments.append(f"masa simpan {label}")
        rendered.append(RenderedField("total_shelf_life", label, value, parse_days))
    if "shop_name" not in drop and ni["shop_name"]:
        fragments.append(f"di {ni['shop_name']}")

    # category is expressed implicitly by the item name; when dropped the model
    # must return null rather than guessing (§3.4).
    rng.shuffle(fragments[1:])  # keep the item lead-in first, vary the rest
    text = ", ".join(fragments) + "."
    return text, rendered


def _parse_target(scenario: Scenario, drop: set[str]) -> dict:
    """Build the parse-task target JSON that satisfies ``validate_parse_output``."""
    ni = scenario.normalized_input
    parsed: dict = {}
    for field_name in schemas.PARSE_ALL_FIELDS:
        if field_name in drop:
            parsed[field_name] = None
        else:
            parsed[field_name] = ni[field_name]
    # shop_name may be an empty string in a scenario; the contract wants null
    if not parsed.get("shop_name"):
        parsed["shop_name"] = None
    missing = [f for f in schemas.PARSE_REQUIRED_FIELDS
               if parsed.get(f) is None]
    return {
        "task": "parse",
        "parsed_input": parsed,
        "missing_fields": missing,
        "needs_confirmation": bool(missing),
    }


# --------------------------------------------------------------------------- #
# Write-task prose templates (§3.5)                                           #
# --------------------------------------------------------------------------- #
# Prose reuses only numbers already present in normalized_input / engine_result
# so the §3.6 "no fabricated numbers" gate passes. Several skeletons per status
# keep the prose from collapsing onto one template.

def _rp(value: int) -> str:
    """Format whole Rupiah with Indonesian dot thousands separators: 48000 ->
    ``Rp48.000``. Done per-number so it never disturbs sentence punctuation."""
    return "Rp" + f"{value:,}".replace(",", ".")


def _write_target(scenario: Scenario, rng: random.Random) -> dict:
    er = scenario.engine_result
    ni = scenario.normalized_input
    name = ni["item_name"]
    status = er["status"]

    if status == schemas.WRITE_STATUS_RECOMMENDATION:
        disc = er["discount_percent"]
        price = _rp(er["recommended_price"])
        sell = er["expected_sell_through"]
        explanation = rng.choice([
            (f"{name} sebaiknya diskon {disc}% jadi {price}."
             f" Perkiraan terjual {sell} sebelum kadaluarsa."
             f" {er['timing']}."),
            (f"Rekomendasi: turunkan {name} sebesar {disc}% menjadi {price}."
             f" Dengan harga ini estimasi laku {sell}."
             f" {er['confidence']}."),
        ])
        promo = rng.choice([
            f"Diskon {disc}%! {name} sekarang cuma {price}.",
            f"Promo {name} turun {disc}% jadi {price}, buruan sebelum habis.",
        ])
        return {"task": "write", "explanation": explanation, "promo_copy": promo}

    if status == schemas.WRITE_STATUS_NO_ACTION:
        days = er["reassess_in_days"]
        explanation = rng.choice([
            (f"{name} belum perlu diskon karena kemungkinan besar laku normal"
             f" sebelum kadaluarsa. Cek lagi dalam {days} hari."),
            (f"Stok {name} masih aman untuk saat ini. Tinjau ulang dalam"
             f" {days} hari sebelum ambil keputusan diskon."),
        ])
        return {"task": "write", "explanation": explanation, "promo_copy": ""}

    # warning
    explanation = rng.choice([
        f"{name} tidak bisa didiskon aman saat ini. {er['message']}",
        f"Perhatian untuk {name}: {er['message']} Mohon tinjau kembali.",
    ])
    return {"task": "write", "explanation": explanation, "promo_copy": ""}


# --------------------------------------------------------------------------- #
# Example derivation                                                          #
# --------------------------------------------------------------------------- #

def _parse_examples(scenario: Scenario, rng: random.Random) -> list[dict]:
    """2-3 parse variants: complete, missing-field, and (sometimes) ambiguous."""
    if not scenario.parseable:
        return []
    examples: list[dict] = []

    # 1) complete variant
    text, rendered = _render_parse_text(scenario, rng, drop=set())
    examples.append(_parse_example_record(scenario, text, rendered, drop=set()))

    # 2) missing required field(s) -> needs_confirmation
    droppable = [f for f in ("cost", "daily_sales", "total_shelf_life",
                             "days_remaining", "category") ]
    drop = {rng.choice(droppable)}
    text, rendered = _render_parse_text(scenario, rng, drop=drop)
    examples.append(_parse_example_record(scenario, text, rendered, drop=drop))

    # 3) ~half the time, a second gap covering another required field
    if rng.random() < 0.5:
        drop2 = drop | {rng.choice([f for f in droppable if f not in drop])}
        text, rendered = _render_parse_text(scenario, rng, drop=drop2)
        examples.append(_parse_example_record(scenario, text, rendered, drop=drop2))

    return examples


def _parse_example_record(scenario, text, rendered, drop) -> dict:
    return {
        "task": "parse",
        "scenario_id": scenario.scenario_id,
        "split": scenario.split,
        "input_text": text,
        "target": _parse_target(scenario, drop),
        # kept for the round-trip gate; not part of the training record proper
        "_rendered": [(r.field, r.label, r.value) for r in rendered],
        "_parsers": {r.field: r.parser for r in rendered},
    }


def _write_examples(scenario: Scenario, rng: random.Random) -> list[dict]:
    return [{
        "task": "write",
        "scenario_id": scenario.scenario_id,
        "split": scenario.split,
        "normalized_input": scenario.normalized_input,
        "engine_result": scenario.engine_result,
        "target": _write_target(scenario, rng),
    }]


# --------------------------------------------------------------------------- #
# Split assignment (§3.2)                                                     #
# --------------------------------------------------------------------------- #

def _assign_splits(count: int, rng: random.Random) -> list[str]:
    """Deterministically assign an 80/10/10 split label per scenario index,
    shuffled so status builders are spread across splits."""
    labels: list[str] = []
    for i in range(count):
        labels.append(_SPLITS[0] if i < count * 0.8
                      else _SPLITS[1] if i < count * 0.9
                      else _SPLITS[2])
    rng.shuffle(labels)
    return labels


# --------------------------------------------------------------------------- #
# Top-level generation                                                        #
# --------------------------------------------------------------------------- #

def generate(seed: int = 20260817, scenarios_per_cell: int = 6
             ) -> tuple[list[Scenario], list[dict]]:
    """Generate scenarios and their derived examples deterministically.

    ``scenarios_per_cell`` scenarios are produced for every (category, status)
    pair, guaranteeing category and status quotas (§3.6 gate 7). With the 8
    categories and 5 status builders the default yields 240 scenarios.

    Returns ``(scenarios, examples)``. Call :func:`run_quality_gates` before
    trusting the output; :func:`write_dataset` does this for you.
    """
    rng = random.Random(seed)

    total = len(CATEGORIES) * len(_STATUS_BUILDERS) * scenarios_per_cell
    splits = _assign_splits(total, rng)

    scenarios: list[Scenario] = []
    index = 0
    for category in CATEGORIES:
        for builder in _STATUS_BUILDERS:
            for _ in range(scenarios_per_cell):
                scenarios.append(builder(index, splits[index], rng, category))
                index += 1

    examples: list[dict] = []
    for scenario in scenarios:
        examples.extend(_parse_examples(scenario, rng))
        examples.extend(_write_examples(scenario, rng))

    return scenarios, examples


# --------------------------------------------------------------------------- #
# Quality gates (§3.6)                                                        #
# --------------------------------------------------------------------------- #

def run_quality_gates(scenarios: list[Scenario], examples: list[dict],
                      *, min_categories: int = 8) -> list[str]:
    """Return a list of gate failures; empty means the dataset is releasable.

    Covers §3.6 gates 1-7. Gate 8 (fixed-seed reproducibility) is enforced by
    the test-suite, which regenerates and diffs; it cannot be self-checked here.
    """
    failures: list[str] = []
    by_id = {s.scenario_id: s for s in scenarios}

    # Gate 2: scenario-id sets disjoint across splits.
    split_ids = {name: set() for name in _SPLITS}
    for s in scenarios:
        if s.split not in split_ids:
            failures.append(f"scenario {s.scenario_id} has unknown split {s.split!r}")
        else:
            split_ids[s.split].add(s.scenario_id)
    for a in _SPLITS:
        for b in _SPLITS:
            if a < b and split_ids[a] & split_ids[b]:
                failures.append(f"scenario ids overlap between {a} and {b}")

    parse_count = 0
    write_count = 0
    status_seen: Counter = Counter()
    category_seen: set[str] = set()
    saw_needs_confirmation = False
    saw_complete = False

    for ex in examples:
        scenario = by_id.get(ex["scenario_id"])
        if scenario is None:
            failures.append(f"example references unknown scenario {ex['scenario_id']!r}")
            continue
        if ex["split"] != scenario.split:
            failures.append(f"example split {ex['split']!r} != scenario split {scenario.split!r}")

        if ex["task"] == "parse":
            parse_count += 1
            # Gate 1: validates against the parse schema.
            errs = schemas.validate_parse_output(ex["target"])
            failures.extend(f"{ex['scenario_id']}: parse target invalid: {e}" for e in errs)
            # Gate 4: parse targets carry no recommendation fields (validator
            # checks the target; also assert the raw record has no leak).
            if any(k in ex for k in ("engine_result", "recommendation")):
                failures.append(f"{ex['scenario_id']}: parse example leaks engine data")
            # Gate 3: every rendered numeric label round-trips exactly.
            for fname, label, value in ex.get("_rendered", []):
                parser = ex["_parsers"][fname]
                try:
                    got = parser(label)
                except RoundTripError as exc:
                    failures.append(f"{ex['scenario_id']}: {exc}")
                    continue
                if got != value:
                    failures.append(
                        f"{ex['scenario_id']}: {fname} label {label!r} -> {got} != {value}")
            if ex["target"]["needs_confirmation"]:
                saw_needs_confirmation = True
            else:
                saw_complete = True
            category_seen.add(scenario.normalized_input["category"])

        elif ex["task"] == "write":
            write_count += 1
            # Gate 5: write inputs carry a recorded engine_result matching the
            # oracle re-run on the same normalized input.
            expected = _recompute_engine_result(scenario.normalized_input)
            if ex["engine_result"] != expected:
                failures.append(f"{ex['scenario_id']}: engine_result does not match oracle")
            status_seen[ex["engine_result"]["status"]] += 1
            # Gates 1 + 6: schema-valid and no number absent from the input.
            allowed = schemas.allowed_numbers_for(ex["normalized_input"], ex["engine_result"])
            errs = schemas.validate_write_output(
                ex["target"], allowed_numbers=allowed,
                engine_status=ex["engine_result"]["status"])
            failures.extend(f"{ex['scenario_id']}: write target invalid: {e}" for e in errs)
            category_seen.add(scenario.normalized_input["category"])
        else:
            failures.append(f"{ex['scenario_id']}: unknown task {ex['task']!r}")

    # Gate 7: category and edge-case quotas.
    if len(category_seen) < min_categories:
        failures.append(f"only {len(category_seen)}/{min_categories} categories covered")
    for required_status in (schemas.WRITE_STATUS_RECOMMENDATION,
                            schemas.WRITE_STATUS_NO_ACTION,
                            schemas.WRITE_STATUS_WARNING):
        if status_seen[required_status] == 0:
            failures.append(f"no write examples with status {required_status!r}")
    if not saw_needs_confirmation:
        failures.append("no parse examples exercise needs_confirmation=true")
    if not saw_complete:
        failures.append("no complete parse examples (needs_confirmation=false)")
    if parse_count == 0 or write_count == 0:
        failures.append("dataset must contain both parse and write examples")

    return failures


def _recompute_engine_result(normalized_input: dict) -> dict:
    """Re-run the oracle on a scenario's normalized input for gate 5."""
    result = compute(
        PricingInput(
            category=normalized_input["category"],
            original_price=normalized_input["original_price"],
            cost=normalized_input["cost"],
            stock=normalized_input["stock"],
            days_remaining=normalized_input["days_remaining"],
            daily_sales=normalized_input["daily_sales"],
            total_shelf_life=normalized_input["total_shelf_life"],
        )
    )
    return schemas.to_engine_result(result)


# --------------------------------------------------------------------------- #
# Chat formatting (§5.4) and file output                                      #
# --------------------------------------------------------------------------- #

def to_chat_messages(example: dict) -> list[dict]:
    """Render a training example as chat messages using the frozen prompts.

    ``parse`` -> system + the raw free text; ``write`` -> system + a compact
    JSON envelope of normalized_input and engine_result. The assistant message
    is the example's target JSON.
    """
    if example["task"] == "parse":
        system = schemas.PARSE_SYSTEM_PROMPT
        user = example["input_text"]
    else:
        system = schemas.WRITE_SYSTEM_PROMPT
        user = json.dumps(
            {"normalized_input": example["normalized_input"],
             "engine_result": example["engine_result"]},
            ensure_ascii=False,
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": json.dumps(example["target"], ensure_ascii=False)},
    ]


def _training_record(example: dict) -> dict:
    """Strip the internal round-trip bookkeeping before writing to disk."""
    return {k: v for k, v in example.items() if not k.startswith("_")}


def write_dataset(out_dir: str | Path, *, seed: int = 20260817,
                  scenarios_per_cell: int = 6) -> dict:
    """Generate, gate, and write ``{train,validation,test}.jsonl`` under
    ``out_dir``. Raises :class:`QualityGateError` before writing if any gate
    fails. Returns a summary dict (counts per split/task)."""
    scenarios, examples = generate(seed=seed, scenarios_per_cell=scenarios_per_cell)
    failures = run_quality_gates(scenarios, examples)
    if failures:
        raise QualityGateError(
            f"{len(failures)} quality-gate failure(s):\n  - " + "\n  - ".join(failures[:20]))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {name: Counter() for name in _SPLITS}
    handles = {name: (out / f"{name}.jsonl").open("w", encoding="utf-8") for name in _SPLITS}
    try:
        for ex in examples:
            handles[ex["split"]].write(
                json.dumps(_training_record(ex), ensure_ascii=False) + "\n")
            summary[ex["split"]][ex["task"]] += 1
    finally:
        for handle in handles.values():
            handle.close()

    return {
        "scenarios": len(scenarios),
        "examples": len(examples),
        "per_split": {name: dict(counter) for name, counter in summary.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the parse/write dataset.")
    parser.add_argument("--out", default="data", help="output directory")
    parser.add_argument("--seed", type=int, default=20260817)
    parser.add_argument("--per-cell", type=int, default=6,
                        help="scenarios per (category, status) pair")
    args = parser.parse_args(argv)

    summary = write_dataset(args.out, seed=args.seed, scenarios_per_cell=args.per_cell)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
