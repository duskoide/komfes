"""Tests for the deterministic pricing oracle (docs/HargaTurun_Project_Spec.md §9.5).

Pure-stdlib so they run with no dependencies:

    cd backend
    python -m unittest discover -s tests -v

These assert the behavior of the FORMULA, which is the authoritative source of
truth by design. Where the spec's *illustrative example JSON* disagrees with the
formula (see test_canonical_roti_tawar_is_no_action), the formula wins.
"""

import random
import sys
import unittest
from pathlib import Path

# Make `hargaturun` importable without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hargaturun.pricing import (  # noqa: E402
    CATEGORIES,
    DISCOUNT_MAX,
    MIN_MARGIN_RP,
    STATUS_INVALID,
    STATUS_NO_ACTION,
    STATUS_RECOMMENDATION,
    PricingInput,
    compute,
    floor_to_step,
    round_to_step,
)


class TestHelpers(unittest.TestCase):
    def test_round_to_step_half_up(self):
        self.assertEqual(round_to_step(47.5, 5), 50)   # tie -> up
        self.assertEqual(round_to_step(12.4, 5), 10)
        self.assertEqual(round_to_step(12.5, 5), 15)
        self.assertEqual(round_to_step(10500, 500), 10500)
        self.assertEqual(round_to_step(10499, 500), 10500)
        self.assertEqual(round_to_step(10250, 500), 10500)  # tie -> up
        self.assertEqual(round_to_step(10249, 500), 10000)

    def test_floor_to_step_stays_under_ceiling(self):
        self.assertEqual(floor_to_step(47.5, 5), 45)
        self.assertEqual(floor_to_step(50, 5), 50)
        self.assertEqual(floor_to_step(3, 5), 0)


class TestValiditySafetyGates(unittest.TestCase):
    def test_cost_at_or_above_price_is_invalid(self):
        r = compute(PricingInput("Bakery", 10000, 10000, 10, 2, 5))
        self.assertEqual(r.status, STATUS_INVALID)
        self.assertIn("modal", r.message.lower())

    def test_cost_above_price_is_invalid(self):
        r = compute(PricingInput("Bakery", 10000, 12000, 10, 2, 5))
        self.assertEqual(r.status, STATUS_INVALID)

    def test_already_expired_is_invalid_and_flagged(self):
        r = compute(PricingInput("Bakery", 15000, 10000, 10, 0, 5))
        self.assertEqual(r.status, STATUS_INVALID)
        self.assertTrue(r.expired)
        self.assertIn("kadaluarsa", r.message.lower())

    def test_negative_days_is_expired(self):
        r = compute(PricingInput("Bakery", 15000, 10000, 10, -3, 5))
        self.assertEqual(r.status, STATUS_INVALID)
        self.assertTrue(r.expired)

    def test_nonpositive_numbers_are_invalid(self):
        for bad in (
            PricingInput("Bakery", 0, 0, 10, 2, 5),       # price 0
            PricingInput("Bakery", 15000, 10000, 0, 2, 5),  # stock 0
            PricingInput("Bakery", 15000, 10000, 10, 2, 0),  # daily_sales 0
        ):
            self.assertEqual(compute(bad).status, STATUS_INVALID)

    def test_non_finite_numbers_are_invalid_without_crashing(self):
        factories = (
            lambda value: PricingInput("Bakery", value, 10000, 10, 2, 5, 4),
            lambda value: PricingInput("Bakery", 15000, value, 10, 2, 5, 4),
            lambda value: PricingInput("Bakery", 15000, 10000, value, 2, 5, 4),
            lambda value: PricingInput("Bakery", 15000, 10000, 10, value, 5, 4),
            lambda value: PricingInput("Bakery", 15000, 10000, 10, 2, value, 4),
            lambda value: PricingInput("Bakery", 15000, 10000, 10, 2, 5, value),
        )
        for value in (float("nan"), float("inf"), float("-inf")):
            for make_input in factories:
                with self.subTest(value=value, factory=make_input):
                    self.assertEqual(compute(make_input(value)).status, STATUS_INVALID)

    def test_boolean_numeric_input_is_invalid(self):
        self.assertEqual(
            compute(PricingInput("Bakery", 15000, 10000, 10, True, 5, 4)).status,
            STATUS_INVALID,
        )

    def test_money_and_stock_require_integer_values(self):
        for bad in (
            PricingInput("Bakery", 15000.5, 10000, 10, 2, 5, 4),
            PricingInput("Bakery", 15000, 10000.5, 10, 2, 5, 4),
            PricingInput("Bakery", 15000, 10000, 10.5, 2, 5, 4),
        ):
            with self.subTest(input=bad):
                self.assertEqual(compute(bad).status, STATUS_INVALID)

    def test_extreme_integer_is_invalid_without_overflow(self):
        r = compute(PricingInput("Bakery", 10**10000, 0, 30, 1, 5, 4))
        self.assertEqual(r.status, STATUS_INVALID)

    def test_margin_too_thin_for_minimum_discount_is_invalid(self):
        r = compute(PricingInput("Bakery", 10000, 9300, 30, 1, 5, 4))
        self.assertEqual(r.status, STATUS_INVALID)
        self.assertIn("margin", r.message.lower())

    def test_thin_margin_does_not_override_no_action(self):
        r = compute(PricingInput("Bakery", 10000, 9300, 5, 5, 5, 4))
        self.assertEqual(r.status, STATUS_NO_ACTION)

    def test_minimum_discount_margin_boundary_is_valid(self):
        # Rp1,000 margin permits exactly 5% off while retaining Rp500 profit.
        r = compute(PricingInput("Bakery", 10000, 9000, 30, 1, 5, 4))
        self.assertEqual(r.status, STATUS_RECOMMENDATION)
        self.assertEqual(r.discount_percent, 5)
        self.assertEqual(r.recommended_price, 9500)

    def test_low_price_rounding_still_produces_a_markdown(self):
        # Nearest-Rp500 rounding would turn a 5% markdown on Rp3.460 into
        # Rp3.500. The engine must choose the lower price step instead.
        r = compute(PricingInput("Canned", 3460, 1098, 89, 12.55, 28.12, 178.9))
        self.assertEqual(r.status, STATUS_RECOMMENDATION)
        self.assertLess(r.recommended_price, 3460)
        self.assertGreaterEqual(r.recommended_price, 1098 + MIN_MARGIN_RP)

    def test_unknown_category_raises(self):
        with self.assertRaises(ValueError):
            compute(PricingInput("Electronics", 15000, 10000, 10, 2, 5))

    def test_category_normalization(self):
        # Case/spacing-insensitive; must still price normally.
        r = compute(PricingInput("prepared   food", 25000, 10000, 40, 1, 8))
        self.assertEqual(r.status, STATUS_RECOMMENDATION)


class TestCanonicalExample(unittest.TestCase):
    def test_canonical_roti_tawar_is_no_action(self):
        """The doc's headline roti-tawar input (price 15000, cost 10000,
        stock 10, 2 days left, shelf 4, sells 5/day) has pressure exactly 1.0
        and urgency 0.35 < 0.7 -> the *base* penyisihan formula returns
        NO_ACTION. The 30%/Rp10.500 figure in the example JSON comes from the
        daily-re-run scenario (yesterday's slower sell-through bumps pressure),
        which is explicitly out of scope this round. Documented, not a bug."""
        r = compute(PricingInput("Bakery", 15000, 10000, 10, 2, 5, total_shelf_life=4))
        self.assertEqual(r.status, STATUS_NO_ACTION)
        self.assertGreaterEqual(r.reassess_in_days, 1)
        self.assertAlmostEqual(r.pressure, 1.0, places=6)


class TestSurplusRecommendation(unittest.TestCase):
    """A clear surplus (30 units, 1 day left, sells 5/day) — regression on the
    exact numbers, hand-derived from §9.5."""

    def setUp(self):
        self.r = compute(PricingInput("Bakery", 20000, 10000, 30, 1, 5, total_shelf_life=4))

    def test_status(self):
        self.assertEqual(self.r.status, STATUS_RECOMMENDATION)

    def test_discount_respects_margin_ceiling_after_rounding(self):
        # raw ~67.6 -> clamp to ceiling 47.5 -> would round to 50 but that
        # overshoots the ceiling, so it floors to 45.
        self.assertEqual(self.r.discount_percent, 45)

    def test_price(self):
        # round_to_500(20000 * 0.55) = 11000, above the cost+500 floor.
        self.assertEqual(self.r.recommended_price, 11000)
        self.assertGreaterEqual(self.r.recommended_price, 10000 + MIN_MARGIN_RP)

    def test_timing_pressure_high(self):
        self.assertEqual(self.r.timing, "Mulai diskon hari ini")

    def test_projections(self):
        # sell = min(30, round(5*1*(1+45/50)=9.5)) = 10 ; revenue = 10*11000
        self.assertEqual(self.r.expected_sell_through_units, 10)
        self.assertEqual(self.r.expected_revenue, 110000)
        # baseline = min(30, 5) = 5 ; loss = (30-5)*10000
        self.assertEqual(self.r.expected_loss_no_action, 250000)

    def test_sell_through_text(self):
        self.assertEqual(self.r.sell_through_text(), "10 dari 30 pcs")

    def test_recommendation_dict_shape(self):
        d = self.r.recommendation_dict()
        self.assertEqual(
            set(d),
            {
                "discount_percent", "recommended_price", "timing",
                "expected_sell_through", "expected_revenue",
                "expected_loss_no_action", "confidence",
            },
        )


class TestSpecialCases(unittest.TestCase):
    def test_fire_sale_expires_today(self):
        r = compute(PricingInput("Prepared Food", 25000, 10000, 20, 0.5, 8, total_shelf_life=3))
        self.assertEqual(r.status, STATUS_RECOMMENDATION)
        self.assertTrue(r.is_fire_sale)
        self.assertEqual(r.timing, "HARI INI SAJA!")
        self.assertLessEqual(r.discount_percent, DISCOUNT_MAX)
        self.assertGreaterEqual(r.recommended_price, 10000 + MIN_MARGIN_RP)

    def test_fire_sale_with_too_little_margin_returns_warning(self):
        # A 5% markdown cannot fit while retaining Rp500 profit, so issuing a
        # 0% "fire sale" would be misleading.
        r = compute(PricingInput("Bakery", 11000, 10000, 20, 0.5, 8, total_shelf_life=4))
        self.assertEqual(r.status, STATUS_INVALID)
        self.assertFalse(r.is_fire_sale)
        self.assertIn("margin", r.message.lower())

    def test_low_stock_minimal_discount(self):
        # Even under heavy pressure, 1-2 units get at most a 15% markdown.
        r = compute(PricingInput("Bakery", 20000, 10000, 2, 1, 1, total_shelf_life=4))
        if r.status == STATUS_RECOMMENDATION:
            self.assertLessEqual(r.discount_percent, 15)

    def test_no_action_far_expiry(self):
        # Snack early in its life (80 of 90 days left): no surplus pressure and
        # urgency well below 0.7 -> no action. (Note: an item *near* end of a
        # long shelf life is NOT no-action — relative urgency still fires.)
        r = compute(PricingInput("Snack", 15000, 10000, 10, 80, 5, total_shelf_life=90))
        self.assertEqual(r.status, STATUS_NO_ACTION)

    def test_shelf_life_default_applied_and_disclosed(self):
        r = compute(PricingInput("Bakery", 20000, 10000, 30, 1, 5))  # no shelf life
        self.assertTrue(r.shelf_life_defaulted)
        self.assertEqual(r.used_shelf_life, 4)


class TestConfidence(unittest.TestCase):
    def test_low_confidence_when_daily_sales_below_one(self):
        r = compute(PricingInput("Bakery", 20000, 10000, 30, 2, 0.5, total_shelf_life=4))
        if r.status == STATUS_RECOMMENDATION:
            self.assertEqual(r.confidence, "Prediksi kurang pasti")

    def test_clear_cut_situation_is_confident(self):
        # High pressure (200) + high urgency (~0.89, 1 of 14 shelf days left)
        # -> confident even though daily_sales < 1 would normally read "kurang
        # pasti". This exercises the §9.5 Step-10 override.
        r = compute(PricingInput("Dairy", 20000, 10000, 100, 1, 0.5, total_shelf_life=14))
        self.assertEqual(r.status, STATUS_RECOMMENDATION)
        self.assertEqual(r.confidence, "Cukup yakin")


class TestDeterminism(unittest.TestCase):
    def test_same_input_same_output(self):
        a = compute(PricingInput("Beverage", 22000, 8000, 40, 1, 6, total_shelf_life=5))
        b = compute(PricingInput("Beverage", 22000, 8000, 40, 1, 6, total_shelf_life=5))
        self.assertEqual(a, b)


class TestInvariantsFuzz(unittest.TestCase):
    """The hard guarantees must hold for every input the oracle accepts."""

    def test_margin_floor_and_bounds_hold_everywhere(self):
        rng = random.Random(42)  # fixed seed -> deterministic test
        for _ in range(20000):
            category = rng.choice(CATEGORIES)
            price = rng.randint(2000, 150000)
            cost = rng.randint(0, price)  # includes cost == price (invalid)
            stock = rng.randint(1, 100)
            days = round(rng.uniform(0.0, 60.0), 2)
            daily = round(rng.uniform(0.0, 50.0), 2)
            shelf = rng.choice([None, round(rng.uniform(1, 365), 1)])
            r = compute(PricingInput(category, price, cost, stock, days, daily, shelf))

            self.assertIn(r.status, (STATUS_RECOMMENDATION, STATUS_NO_ACTION, STATUS_INVALID))

            if r.status == STATUS_RECOMMENDATION:
                # The one guarantee the vendor relies on.
                self.assertGreaterEqual(
                    r.recommended_price, cost + MIN_MARGIN_RP,
                    msg=f"margin floor broken: {r} for price={price} cost={cost}",
                )
                # Discount within documented bounds and a multiple of 5.
                self.assertGreaterEqual(r.discount_percent, 0)
                self.assertLessEqual(r.discount_percent, DISCOUNT_MAX)
                self.assertEqual(r.discount_percent % 5, 0)
                # Recommendations are real markdowns, never a 0% offer or a
                # price increase caused by applying the absolute floor.
                self.assertGreaterEqual(r.discount_percent, 5)
                self.assertLess(r.recommended_price, price)
                # Displayed discount never exceeds the margin ceiling: the
                # discounted price implied by discount_percent still clears cost.
                self.assertGreaterEqual(
                    price * (1 - r.discount_percent / 100.0), cost,
                    msg=f"discount over margin ceiling: {r}",
                )
                # Price is a multiple of Rp500 — unless the cost+500 floor was
                # applied, which need not itself be a round number.
                self.assertTrue(
                    r.recommended_price % 500 == 0
                    or r.recommended_price == cost + MIN_MARGIN_RP
                )
                # Projections are sane.
                self.assertLessEqual(r.expected_sell_through_units, stock)
                self.assertGreaterEqual(r.expected_sell_through_units, 0)
                self.assertGreaterEqual(r.expected_loss_no_action, 0)

            elif r.status == STATUS_NO_ACTION:
                self.assertGreaterEqual(r.reassess_in_days, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
