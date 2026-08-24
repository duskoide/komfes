from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from hargaturun.model_client import OpenAICompatibleModel, _decode_json_object
from hargaturun.pricing import PricingInput, compute
from hargaturun.schemas import to_engine_result


NORMALIZED_INPUT = {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 20000,
    "cost": 10000,
    "stock": 30,
    "days_remaining": 1,
    "daily_sales": 5,
    "total_shelf_life": 4,
    "shop_name": "Toko Sari",
}
ENGINE_RESULT = to_engine_result(
    compute(PricingInput("Bakery", 20000, 10000, 30, 1, 5, 4))
)

class ModelClientTest(unittest.TestCase):
    def test_malformed_timeout_environment_does_not_break_direct_construction(self):
        with patch.dict(os.environ, {"HARGATURUN_MODEL_TIMEOUT": "not-a-number"}):
            model = OpenAICompatibleModel()
        self.assertEqual(model.timeout, 20.0)

    def test_parse_normalizes_confirmation_bookkeeping_without_inventing_values(self):
        model = OpenAICompatibleModel()
        invalid = {
            "task": "parse",
            "parsed_input": {
                "item_name": "Kue Lapis",
                "category": "Bakery",
                "original_price": 25000,
                "cost": None,
                "stock": 5,
                "days_remaining": 1,
                "daily_sales": None,
                "total_shelf_life": None,
                "shop_name": None,
            },
            "missing_fields": ["cost", "daily_sales", "total_shelf_life", "shop_name"],
            "needs_confirmation": True,
        }
        repaired = {
            **invalid,
            "missing_fields": ["cost", "daily_sales", "total_shelf_life"],
        }
        with patch.object(
            OpenAICompatibleModel, "_complete", return_value=invalid
        ) as complete:
            self.assertEqual(model.parse("kue lapis 5 loyang exp besok harga 25rb"), repaired)

        complete.assert_called_once()
        self.assertIsNone(repaired["parsed_input"]["cost"])

    def test_write_accepts_valid_first_response(self):
        model = OpenAICompatibleModel()
        valid = {
            "task": "write",
            "explanation": "Stok melebihi penjualan normal. Diskon membantu barang terjual sebelum kadaluarsa.",
            "promo_copy": "Harga spesial untuk stok terbatas hari ini.",
        }
        with patch.object(OpenAICompatibleModel, "_complete", return_value=valid) as complete:
            self.assertEqual(model.write(NORMALIZED_INPUT, ENGINE_RESULT), valid)
        complete.assert_called_once()

    def test_write_repairs_one_contract_failure(self):
        model = OpenAICompatibleModel()
        invalid = {
            "task": "write",
            "explanation": "Stok perlu segera ditangani.",
            "promo_copy": "Harga spesial untuk stok terbatas hari ini.",
        }
        repaired = {
            "task": "write",
            "explanation": "Stok melebihi penjualan normal. Diskon membantu barang terjual sebelum kadaluarsa.",
            "promo_copy": "Harga spesial untuk stok terbatas hari ini.",
        }
        with patch.object(
            OpenAICompatibleModel, "_complete", side_effect=[invalid, repaired]
        ) as complete:
            self.assertEqual(model.write(NORMALIZED_INPUT, ENGINE_RESULT), repaired)

        self.assertEqual(complete.call_count, 2)
        repair_payload = json.loads(complete.call_args_list[1].args[1])
        self.assertIn(
            "explanation must contain 2-4 sentences",
            repair_payload["contract_violations"],
        )
        self.assertEqual(
            repair_payload["authoritative_input"]["engine_result"], ENGINE_RESULT
        )

    def test_decode_json_object_accepts_fenced_json(self):
        decoded = _decode_json_object('```json\n{"task":"parse"}\n```')
        self.assertEqual(decoded, {"task": "parse"})


if __name__ == "__main__":
    unittest.main()
