"""Tests for the frozen parse/write model contracts (Fine-Tuning Plan §2, §3.6)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hargaturun.pricing import PricingInput, compute  # noqa: E402
from hargaturun.schemas import (  # noqa: E402
    WRITE_STATUS_NO_ACTION,
    WRITE_STATUS_RECOMMENDATION,
    WRITE_STATUS_WARNING,
    allowed_numbers_for,
    to_engine_result,
    validate_parse_output,
    validate_write_output,
)


def _valid_parse():
    return {
        "task": "parse",
        "parsed_input": {
            "item_name": "Roti Tawar",
            "category": "Bakery",
            "original_price": 15000,
            "cost": 10000,
            "stock": 10,
            "days_remaining": 2,
            "daily_sales": 5,
            "total_shelf_life": 4,
            "shop_name": "Toko Sari Bakery",
        },
        "missing_fields": [],
        "needs_confirmation": False,
    }


class TestParseValidation(unittest.TestCase):
    def test_complete_parse_is_valid(self):
        self.assertEqual(validate_parse_output(_valid_parse()), [])

    def test_missing_required_field_flags(self):
        obj = _valid_parse()
        del obj["parsed_input"]["cost"]
        self.assertTrue(any("cost" in e for e in validate_parse_output(obj)))

    def test_needs_confirmation_must_match_gaps(self):
        # A null required field but needs_confirmation=False is a contradiction
        # (this is the safety-critical "false completion" shape).
        obj = _valid_parse()
        obj["parsed_input"]["daily_sales"] = None
        obj["needs_confirmation"] = False
        self.assertTrue(any("contradicts" in e for e in validate_parse_output(obj)))
        # Setting it true resolves the contradiction.
        obj["needs_confirmation"] = True
        self.assertEqual(validate_parse_output(obj), [])

    def test_invalid_category_flags(self):
        obj = _valid_parse()
        obj["parsed_input"]["category"] = "Electronics"
        self.assertTrue(any("category" in e for e in validate_parse_output(obj)))

    def test_leaked_recommendation_field_flags(self):
        obj = _valid_parse()
        obj["parsed_input"]["discount_percent"] = 30
        self.assertTrue(any("leak" in e for e in validate_parse_output(obj)))

    def test_unexpected_field_flags(self):
        obj = _valid_parse()
        obj["parsed_input"]["surprise"] = 1
        self.assertTrue(any("unexpected" in e for e in validate_parse_output(obj)))


class TestEngineResultAdapter(unittest.TestCase):
    def test_recommendation_maps_with_all_keys(self):
        r = compute(PricingInput("Bakery", 20000, 10000, 30, 1, 5, total_shelf_life=4))
        er = to_engine_result(r)
        self.assertEqual(er["status"], WRITE_STATUS_RECOMMENDATION)
        self.assertEqual(er["recommended_price"], r.recommended_price)
        self.assertIn("expected_sell_through", er)

    def test_no_action_maps_to_no_action(self):
        r = compute(PricingInput("Snack", 15000, 10000, 10, 80, 5, total_shelf_life=90))
        er = to_engine_result(r)
        self.assertEqual(er["status"], WRITE_STATUS_NO_ACTION)
        self.assertIn("reassess_in_days", er)

    def test_invalid_maps_to_warning(self):
        r = compute(PricingInput("Bakery", 10000, 12000, 10, 2, 5))  # cost > price
        er = to_engine_result(r)
        self.assertEqual(er["status"], WRITE_STATUS_WARNING)
        self.assertIn("message", er)


class TestWriteValidation(unittest.TestCase):
    def test_valid_write_passes(self):
        obj = {
            "task": "write",
            "explanation": "Roti tawar mendekati batas jual. Diskon membantu mempercepat penjualan.",
            "promo_copy": "Roti Tawar hemat 45% hari ini, hanya Rp11.000!",
        }
        allowed = {45, 11000}
        self.assertEqual(validate_write_output(obj, allowed), [])

    def test_unsupported_number_flags(self):
        obj = {
            "task": "write",
            "explanation": "Diskon 99% besar sekali.",  # 99 not allowed
            "promo_copy": "",
        }
        errs = validate_write_output(obj, allowed_numbers={45, 11000})
        self.assertTrue(any("unsupported number" in e for e in errs))

    def test_empty_explanation_flags(self):
        obj = {"task": "write", "explanation": "  ", "promo_copy": "ok"}
        self.assertTrue(any("explanation" in e for e in validate_write_output(obj)))


class TestAllowedNumbers(unittest.TestCase):
    def test_extracts_prices_percents_and_input(self):
        r = compute(PricingInput("Bakery", 20000, 10000, 30, 1, 5, total_shelf_life=4))
        er = to_engine_result(r)
        norm = {"original_price": 20000, "cost": 10000, "stock": 30}
        allowed = allowed_numbers_for(norm, er)
        # Numbers from input and engine result are all present.
        self.assertIn(20000, allowed)
        self.assertIn(r.recommended_price, allowed)
        self.assertIn(r.discount_percent, allowed)
        # "10 dari 30 pcs" contributes 10 and 30.
        self.assertIn(30, allowed)

    def test_rupiah_thousands_separator_parsed(self):
        # A prose price like Rp10.500 must round-trip to the integer 10500.
        obj = {"task": "write", "explanation": "Harga Rp10.500 saja.", "promo_copy": ""}
        self.assertEqual(validate_write_output(obj, allowed_numbers={10500}), [])
        self.assertTrue(validate_write_output(obj, allowed_numbers={10000}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
