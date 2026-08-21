"""Tests for the gold test set and its validator (Fine-Tuning Plan §3.2).

Two jobs: prove the shipped ``data/gold_test.jsonl`` is technically valid (zero
hard errors), and prove the validator actually catches the ways a gold record
can be wrong — otherwise "no hard errors" would be meaningless.
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hargaturun import dataset, gold, schemas  # noqa: E402


def _valid_parse_record() -> dict:
    return {
        "id": "t-parse-1", "task": "parse", "source": "gold", "review": "verified",
        "tags": ["slang", "Bakery"],
        "input_text": "kue cubit unik, harga 3rb modal 1rb, stok 10, exp besok, laku 5 sehari, tahan 2 hari",
        "target": {
            "task": "parse",
            "parsed_input": {
                "item_name": "Kue Cubit Unik", "category": "Bakery",
                "original_price": 3000, "cost": 1000, "stock": 10,
                "days_remaining": 1, "daily_sales": 5, "total_shelf_life": 2,
                "shop_name": None,
            },
            "missing_fields": [], "needs_confirmation": False,
        },
    }


def _valid_write_record() -> dict:
    ni = {
        "item_name": "Roti Unik", "category": "Bakery", "original_price": 20000,
        "cost": 12000, "stock": 25, "days_remaining": 1, "daily_sales": 5,
        "total_shelf_life": 4, "shop_name": "Toko Uji",
    }
    er = gold._recompute_engine_result(ni)
    # Build faithful prose from the real engine numbers.
    price = "Rp" + f"{er['recommended_price']:,}".replace(",", ".")
    original = "Rp" + f"{ni['original_price']:,}".replace(",", ".")
    return {
        "id": "t-write-1", "task": "write", "source": "gold", "review": "verified",
        "tags": ["recommendation", "Bakery"],
        "normalized_input": ni, "engine_result": er,
        "target": {
            "task": "write",
            "explanation": (f"Roti Unik sebaiknya diskon {er['discount_percent']}% menjadi "
                            f"{price} dari {original}. Perkiraan {er['expected_sell_through']} "
                            f"terjual sebelum kadaluarsa. {er['timing']}."),
            "promo_copy": f"Diskon {er['discount_percent']}%! Roti Unik jadi {price}.",
        },
    }


def _build_verified_write(rid: str, ni: dict, tags: list) -> dict:
    """Build a valid, verified write record for any engine status, with faithful
    prose that only cites numbers from the input/engine result."""
    er = gold._recompute_engine_result(ni)
    if er["status"] == schemas.WRITE_STATUS_RECOMMENDATION:
        price = "Rp" + f"{er['recommended_price']:,}".replace(",", ".")
        explanation = (f"{ni['item_name']} sebaiknya diskon {er['discount_percent']}% "
                       f"menjadi {price}. Perkiraan {er['expected_sell_through']} "
                       f"terjual. {er['timing']}.")
        promo = f"Diskon {er['discount_percent']}%! {ni['item_name']} {price}."
    else:
        # no_action / warning: quote the authoritative message, no promo.
        explanation = f"Perhatian untuk {ni['item_name']}. {er['message']}"
        promo = ""
    return {
        "id": rid, "task": "write", "source": "gold", "review": "verified",
        "tags": tags, "normalized_input": ni, "engine_result": er,
        "target": {"task": "write", "explanation": explanation, "promo_copy": promo},
    }


class TestShippedGoldFile(unittest.TestCase):
    """The real data/gold_test.jsonl must be internally correct."""

    @classmethod
    def setUpClass(cls):
        cls.records = gold.load_gold()

    def test_file_loads(self):
        self.assertGreater(len(self.records), 0)

    def test_no_hard_errors(self):
        errors, _warnings = gold.validate_gold_set(self.records)
        self.assertEqual(errors, [], msg="\n".join(errors))

    def test_every_parse_target_matches_contract(self):
        for r in self.records:
            if r["task"] == "parse":
                self.assertEqual(schemas.validate_parse_output(r["target"]), [],
                                 msg=r["id"])

    def test_every_write_engine_result_matches_oracle(self):
        for r in self.records:
            if r["task"] == "write":
                self.assertEqual(r["engine_result"],
                                 gold._recompute_engine_result(r["normalized_input"]),
                                 msg=r["id"])

    def test_coverage_spans_all_categories(self):
        report = gold.coverage_report(self.records)
        self.assertEqual(set(report["by_category"]), set(schemas.ALLOWED_CATEGORIES))
        for status in schemas.WRITE_STATUSES:
            self.assertGreater(report["by_write_status"].get(status, 0), 0)

    def test_ids_unique(self):
        ids = [r["id"] for r in self.records]
        self.assertEqual(len(ids), len(set(ids)))


class TestValidatorCatchesBrokenRecords(unittest.TestCase):
    def test_valid_records_pass(self):
        self.assertEqual(gold.validate_record(_valid_parse_record()), [])
        self.assertEqual(gold.validate_record(_valid_write_record()), [])

    def test_missing_source_marker_fails(self):
        rec = _valid_parse_record()
        del rec["source"]
        self.assertTrue(any("source" in e for e in gold.validate_record(rec)))

    def test_bad_review_state_fails(self):
        rec = _valid_parse_record()
        rec["review"] = "approved"  # not draft/verified
        self.assertTrue(any("review" in e for e in gold.validate_record(rec)))

    def test_wrong_missing_fields_fails(self):
        rec = _valid_parse_record()
        rec["target"]["parsed_input"]["cost"] = None  # now cost is null...
        # ...but missing_fields/needs_confirmation weren't updated -> contract break
        self.assertTrue(gold.validate_record(rec))

    def test_parse_record_with_engine_result_fails(self):
        rec = _valid_parse_record()
        rec["engine_result"] = {"status": "recommendation"}
        self.assertTrue(any("engine_result" in e for e in gold.validate_record(rec)))

    def test_tampered_engine_result_fails(self):
        rec = _valid_write_record()
        rec["engine_result"] = dict(rec["engine_result"], discount_percent=99)
        self.assertTrue(any("oracle" in e for e in gold.validate_record(rec)))

    def test_fabricated_number_in_prose_fails(self):
        rec = _valid_write_record()
        rec["target"]["promo_copy"] += " Hemat Rp999.999 khusus hari ini."
        self.assertTrue(gold.validate_record(rec))

    def test_warning_with_promo_fails(self):
        rec = _valid_write_record()
        rec["engine_result"] = {"status": "warning",
                                "message": "Item sudah kadaluarsa. Buang saja."}
        rec["normalized_input"]["days_remaining"] = 0  # make the oracle agree
        rec["target"] = {"task": "write",
                         "explanation": "Item ini sudah lewat tanggal. Item sudah kadaluarsa. Buang saja.",
                         "promo_copy": "Beli sekarang!"}  # promo on a warning is illegal
        self.assertTrue(gold.validate_record(rec))


class TestWholeSetChecks(unittest.TestCase):
    def test_duplicate_ids_flagged(self):
        a = _valid_parse_record()
        b = _valid_write_record()
        b["id"] = a["id"]  # collide
        errors, _ = gold.validate_gold_set([a, b], check_generator=False)
        self.assertTrue(any("duplicate id" in e for e in errors))

    def test_generator_leakage_flagged(self):
        _, examples = dataset.generate()
        stolen = next(e["input_text"] for e in examples if e["task"] == "parse")
        rec = _valid_parse_record()
        rec["input_text"] = stolen  # copied straight from the generator
        # target need not match; we only assert the leakage error appears.
        errors, _ = gold.validate_gold_set([rec], check_generator=True)
        self.assertTrue(any("generator" in e for e in errors))

    def test_below_target_and_drafts_are_warnings_not_errors(self):
        rec = _valid_parse_record()
        rec["review"] = "draft"
        errors, warnings = gold.validate_gold_set([rec], check_generator=False,
                                                  min_examples=200)
        self.assertEqual(errors, [])
        self.assertTrue(any("verified" in w for w in warnings))
        self.assertTrue(any("draft" in w for w in warnings))

    def test_complete_set_has_no_warnings(self):
        # A fully-populated set (>=200 verified, every category/status/tag) must
        # get a clean bill of health. Build real records for each write status.
        cats = list(schemas.ALLOWED_CATEGORIES)
        records = []
        base_parse = _valid_parse_record()
        for i in range(140):
            r = copy.deepcopy(base_parse)
            r["id"] = f"p-{i}"
            r["target"]["parsed_input"]["category"] = cats[i % len(cats)]
            r["tags"] = ["slang", "missing_field", "ambiguous"]
            if i % 2:
                r["target"]["parsed_input"]["cost"] = None
                r["target"]["missing_fields"] = ["cost"]
                r["target"]["needs_confirmation"] = True
            records.append(r)

        # Three write archetypes -> the three engine statuses.
        archetypes = [
            ({"item_name": "Roti Uji", "category": "Bakery", "original_price": 20000,
              "cost": 12000, "stock": 25, "days_remaining": 1, "daily_sales": 5,
              "total_shelf_life": 4, "shop_name": "Toko Uji"},
             ["recommendation", "fire_sale"]),
            ({"item_name": "Kaleng Uji", "category": "Canned", "original_price": 13000,
              "cost": 9000, "stock": 5, "days_remaining": 300, "daily_sales": 4,
              "total_shelf_life": 365, "shop_name": "Toko Uji"},
             ["no_action"]),
            ({"item_name": "Basi Uji", "category": "Dairy", "original_price": 8000,
              "cost": 4000, "stock": 10, "days_remaining": 0, "daily_sales": 5,
              "total_shelf_life": 14, "shop_name": "Toko Uji"},
             ["warning", "expired", "thin_margin"]),
        ]
        for i in range(70):
            ni, tags = archetypes[i % len(archetypes)]
            ni = dict(ni, category=cats[i % len(cats)])
            records.append(_build_verified_write(f"w-{i}", ni, tags))

        errors, warnings = gold.validate_gold_set(records, check_generator=False)
        self.assertEqual(errors, [], msg="\n".join(errors))
        self.assertEqual(warnings, [], msg="\n".join(warnings))


if __name__ == "__main__":
    unittest.main()
