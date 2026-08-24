"""Explicit opt-in live local-model smoke test.

Requires a running local model server (e.g. llama.cpp via scripts/run-llama-server.sh
or LM Studio) on loopback.

Never runs by default. Opt in via:
    HARGATURUN_TEST_REAL_MODEL=1 pytest -m real_model
or:
    python scripts/run_dev_tests.py --real-model
"""

from __future__ import annotations

import os
import unittest
import urllib.error
import urllib.request

import pytest

from hargaturun.model_client import ModelUnavailable, OpenAICompatibleModel
from hargaturun.schemas import allowed_numbers_for, to_engine_result

pytestmark = pytest.mark.real_model


class RealModelSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        opted_in = os.getenv("HARGATURUN_TEST_REAL_MODEL", "").strip().lower() in ("1", "true", "yes")
        strict = os.getenv("HARGATURUN_STRICT_MODE", "").strip().lower() in ("1", "true", "yes")
        model_url = os.getenv("HARGATURUN_MODEL_URL", "http://127.0.0.1:8080/v1").rstrip("/")
        model_name = os.getenv("HARGATURUN_MODEL_NAME", "hargaturun-qwen3.5-4b")
        timeout = float(os.getenv("HARGATURUN_MODEL_TIMEOUT", "10"))

        if not opted_in:
            pytest.skip("Live local-model test disabled. Opt in via --real-model or HARGATURUN_TEST_REAL_MODEL=1.")

        # Check if local model server is reachable
        health_url = f"{model_url.rsplit('/v1', 1)[0]}/health"
        is_reachable = False
        try:
            req = urllib.request.Request(health_url, headers={"User-Agent": "HargaTurun-Test"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status in (200, 404):  # /health exists on llama.cpp; 404 means endpoint responded
                    is_reachable = True
        except Exception:
            # Fallback probe to /v1/models or /v1/chat/completions with empty body
            try:
                probe_url = f"{model_url}/models"
                req = urllib.request.Request(probe_url, headers={"User-Agent": "HargaTurun-Test"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status == 200:
                        is_reachable = True
            except Exception:
                is_reachable = False

        if not is_reachable:
            msg = f"Local model server at {model_url} is unreachable."
            if strict:
                raise RuntimeError(f"[STRICT ERROR] {msg}")
            pytest.skip(f"[SKIP] {msg}")

        cls.model = OpenAICompatibleModel(base_url=model_url, model=model_name, timeout=timeout)

    def test_live_model_parse_contract(self):
        sample_text = "Roti Tawar 20 biji exp 2 hari harga 15rb modal 10rb sehari laku 2"
        try:
            result = self.model.parse(sample_text)
        except ModelUnavailable as e:
            pytest.fail(f"Live model server failed during parse: {e}")

        self.assertIn("parsed_input", result)
        parsed = result["parsed_input"]
        self.assertEqual(parsed.get("category"), "Bakery")
        self.assertEqual(parsed.get("stock"), 20)
        self.assertEqual(parsed.get("days_remaining"), 2)
        self.assertEqual(parsed.get("original_price"), 15000)
        self.assertEqual(parsed.get("cost"), 10000)

    def test_live_model_write_contract(self):
        normalized_input = {
            "item_name": "Roti Tawar",
            "category": "Bakery",
            "original_price": 15000,
            "cost": 10000,
            "stock": 20,
            "days_remaining": 2.0,
            "daily_sales": 2.0,
            "total_shelf_life": 4.0,
        }
        engine_result = {
            "status": "recommendation",
            "discount_percent": 25,
            "recommended_price": 11500,
            "timing": "Mulai diskon hari ini",
            "expected_sell_through": "6 dari 20 pcs",
            "expected_revenue": 69000,
            "expected_loss_no_action": 170000,
            "confidence": "Cukup yakin",
        }
        try:
            prose = self.model.write(normalized_input, engine_result)
        except ModelUnavailable as e:
            pytest.fail(f"Live model server failed during write: {e}")

        self.assertIn("explanation", prose)
        self.assertIn("promo_copy", prose)
        self.assertTrue(isinstance(prose["explanation"], str) and prose["explanation"])
        self.assertTrue(isinstance(prose["promo_copy"], str) and prose["promo_copy"])


if __name__ == "__main__":
    unittest.main()
