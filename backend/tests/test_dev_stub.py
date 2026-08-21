"""Tests for the development stub's parser.

The stub is a demo tool, not the model, but it feeds the same orchestrator.
When it fabricated an item name from an arbitrary sentence, a later
correction overwrote the real one — a defect no orchestrator test could
catch, because the orchestrator faithfully merged what it was handed.

These tests pin the "never guess" rule at the boundary where it broke.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_STUB_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev_stub_model.py"
_spec = importlib.util.spec_from_file_location("dev_stub_model", _STUB_PATH)
assert _spec and _spec.loader
dev_stub_model = importlib.util.module_from_spec(_spec)
sys.modules["dev_stub_model"] = dev_stub_model
_spec.loader.exec_module(dev_stub_model)

parse_free_text = dev_stub_model.parse_free_text


class ItemDescriptionTest(unittest.TestCase):
    def test_reads_the_documented_demo_phrasing(self):
        out = parse_free_text("roti tawar 20 biji exp 2 hari harga 15rb modal 10rb")
        parsed = out["parsed_input"]
        self.assertEqual(parsed["item_name"], "Roti Tawar")
        self.assertEqual(parsed["category"], "Bakery")
        self.assertEqual(parsed["stock"], 20)
        self.assertEqual(parsed["days_remaining"], 2)
        self.assertEqual(parsed["original_price"], 15000)
        self.assertEqual(parsed["cost"], 10000)

    def test_reports_what_it_could_not_read(self):
        out = parse_free_text("roti tawar 20 biji exp 2 hari harga 15rb modal 10rb")
        self.assertIn("daily_sales", out["missing_fields"])
        self.assertTrue(out["needs_confirmation"])

    def test_missing_fields_mirror_the_nulls(self):
        out = parse_free_text("roti tawar 20 biji harga 15rb modal 10rb")
        parsed = out["parsed_input"]
        nulls = {k for k, v in parsed.items() if v is None}
        self.assertEqual(nulls, set(out["missing_fields"]))


class NeverGuessTest(unittest.TestCase):
    def test_a_correction_proposes_no_item_name(self):
        # The regression: leading words of "sehari laku 2" were read as a new
        # item name and overwrote the real one.
        out = parse_free_text("sehari laku 2")
        self.assertIsNone(out["parsed_input"]["item_name"])
        self.assertEqual(out["parsed_input"]["daily_sales"], 2)

    def test_a_bare_correction_proposes_only_the_named_fact(self):
        out = parse_free_text("stoknya 24")
        parsed = out["parsed_input"]
        self.assertIsNone(parsed["item_name"])
        self.assertIsNone(parsed["original_price"])
        self.assertIsNone(parsed["cost"])

    def test_never_invents_daily_sales(self):
        out = parse_free_text("roti tawar 20 biji harga 15rb modal 10rb")
        self.assertIsNone(out["parsed_input"]["daily_sales"])

    def test_never_invents_shelf_life(self):
        out = parse_free_text("roti tawar 20 biji exp 2 hari harga 15rb modal 10rb")
        self.assertIsNone(out["parsed_input"]["total_shelf_life"])


class RupiahTest(unittest.TestCase):
    def test_understands_rb_and_juta_suffixes(self):
        self.assertEqual(
            parse_free_text("kue 5 pcs harga 20rb modal 12rb")["parsed_input"][
                "original_price"
            ],
            20000,
        )
        self.assertEqual(
            parse_free_text("kue 5 pcs harga 1jt modal 500rb")["parsed_input"][
                "original_price"
            ],
            1_000_000,
        )

    def test_reads_plain_rupiah_amounts(self):
        self.assertEqual(
            parse_free_text("kue 5 pcs harga 20000 modal 12000")["parsed_input"][
                "original_price"
            ],
            20000,
        )


class ExpiryTest(unittest.TestCase):
    def test_today_is_zero_days(self):
        self.assertEqual(
            parse_free_text("roti 5 biji harga 10rb modal 5rb exp hari ini")[
                "parsed_input"
            ]["days_remaining"],
            0,
        )

    def test_tomorrow_is_one_day(self):
        self.assertEqual(
            parse_free_text("roti 5 biji harga 10rb modal 5rb besok kadaluarsa")[
                "parsed_input"
            ]["days_remaining"],
            1,
        )


class ContractShapeTest(unittest.TestCase):
    def test_output_carries_exactly_the_contract_keys(self):
        out = parse_free_text("roti tawar 20 biji harga 15rb modal 10rb")
        self.assertEqual(
            set(out), {"task", "parsed_input", "missing_fields", "needs_confirmation"}
        )
        self.assertEqual(out["task"], "parse")

    def test_written_prose_quotes_no_figures(self):
        prose = dev_stub_model.write_prose({})
        text = prose["explanation"] + prose["promo_copy"]
        # The writer validator rejects unsupported numbers, so the stub states
        # none and leaves figures in the structured fields.
        self.assertFalse(any(char.isdigit() for char in text))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
