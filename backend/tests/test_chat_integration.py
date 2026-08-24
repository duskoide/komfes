"""Focused issue #4 acceptance and wire integration tests for POST /api/chat.

Covers the full conversational copilot flow and boundary guarantees:
1. Multi-turn message -> grouped gaps -> correction -> confirm -> calculate -> explain.
2. Premature calculation refusal (unconfirmed or incomplete states perform zero tool calls).
3. Exactly-one tool call and result reuse semantics across repeated calculate/explain actions.
4. Correction invalidation: post-calculation edits drop result and revoke confirmation.
5. Non-recommendation oracle outcomes (no_action, invalid_input) through the chat API.
6. Safe writer fallback on ModelContractError or ModelUnavailable (numbers survive).
7. Live loopback HTTP integration with the OpenAI-compatible development stub server.
"""

from __future__ import annotations

import socket
import threading
import unittest
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hargaturun.api import create_app
from hargaturun.model_client import ModelContractError, ModelUnavailable, OpenAICompatibleModel
from hargaturun.pricing import STATUS_INVALID, STATUS_NO_ACTION, STATUS_RECOMMENDATION

# Import the development stub handler directly from scripts/
import sys
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import dev_stub_model  # noqa: E402


pytestmark = pytest.mark.integration


class ScriptedModel:
    """Configurable model double to trace exact call counts and responses."""

    def __init__(self, parse_responses: list[dict] | None = None, *, fail_parse: bool = False, fail_write: bool = False, contract_error_write: bool = False):
        self._parse_queue = list(parse_responses or [])
        self.fail_parse = fail_parse
        self.fail_write = fail_write
        self.contract_error_write = contract_error_write
        self.parse_calls = 0
        self.write_calls = 0

    def parse(self, free_text: str) -> dict:
        self.parse_calls += 1
        if self.fail_parse:
            raise ModelUnavailable("Model offline")
        patch = self._parse_queue.pop(0) if self._parse_queue else {}
        return {
            "task": "parse",
            "parsed_input": patch,
            "missing_fields": [],
            "needs_confirmation": False,
        }

    def write(self, normalized_input: dict, engine_result: dict) -> dict:
        self.write_calls += 1
        if self.fail_write:
            raise ModelUnavailable("Writer offline")
        if self.contract_error_write:
            raise ModelContractError("Writer produced unsupported numbers")
        return {
            "task": "write",
            "explanation": "Stok berlebih, segera beri diskon sebelum kedaluwarsa.",
            "promo_copy": "Diskon spesial hari ini!",
        }


def _make_client(model) -> TestClient:
    return TestClient(create_app(database_path=":memory:", model=model))


class MultiTurnAcceptanceTest(unittest.TestCase):
    """End-to-end multi-turn conversation flow through POST /api/chat."""

    def test_full_consultation_lifecycle_with_correction_and_reuse(self):
        # Scripted sequence:
        # 1. Partial parse (name, stock, days, category) -> missing: cost, daily_sales, original_price
        # 2. Missing fields parse -> complete state
        # 3. Correction parse -> stock changed to 25
        model = ScriptedModel([
            {"item_name": "Roti Tawar", "stock": 20, "days_remaining": 2, "category": "Bakery"},
            {"cost": 10000, "daily_sales": 2, "original_price": 15000},
            {"stock": 25},
        ])
        client = _make_client(model)

        # Turn 1: Incomplete initial message
        t1 = client.post("/api/chat", json={"action": "message", "text": "Roti tawar 20 biji exp 2 hari"}).json()
        session_id = t1["session_id"]
        self.assertEqual(t1["action"], "ASK_FOR_MISSING_FIELDS")
        self.assertIn("cost", t1["missing_fields"])
        self.assertIn("daily_sales", t1["missing_fields"])
        self.assertIn("original_price", t1["missing_fields"])
        self.assertIsNone(t1["result"])
        self.assertEqual(t1["state"]["revision"], 1)
        self.assertFalse(t1["state"]["confirmed"])

        # Turn 2: Premature calculate on incomplete state -> refused
        t2 = client.post("/api/chat", json={"session_id": session_id, "action": "calculate"}).json()
        self.assertEqual(t2["action"], "ASK_FOR_MISSING_FIELDS")
        self.assertIsNone(t2["result"])
        self.assertEqual(model.write_calls, 0)

        # Turn 3: Supply remaining fields -> reaches complete unconfirmed state
        t3 = client.post("/api/chat", json={
            "session_id": session_id,
            "action": "message",
            "text": "harga 15rb modal 10rb laku 2 per hari",
        }).json()
        self.assertEqual(t3["action"], "SHOW_CONFIRMATION")
        self.assertEqual(t3["missing_fields"], [])
        self.assertFalse(t3["state"]["confirmed"])
        self.assertIsNone(t3["result"])
        self.assertEqual(t3["state"]["revision"], 2)

        # Turn 4: Premature calculate on unconfirmed state -> refused
        t4 = client.post("/api/chat", json={"session_id": session_id, "action": "calculate"}).json()
        self.assertEqual(t4["action"], "SHOW_CONFIRMATION")
        self.assertIsNone(t4["result"])
        self.assertEqual(model.write_calls, 0)

        # Turn 5: Correction before confirming
        t5 = client.post("/api/chat", json={
            "session_id": session_id,
            "action": "message",
            "text": "eh salah, stoknya 25 biji",
        }).json()
        self.assertEqual(t5["action"], "SHOW_CONFIRMATION")
        self.assertEqual(t5["state"]["stock"], 25)
        self.assertEqual(t5["state"]["revision"], 3)
        self.assertFalse(t5["state"]["confirmed"])

        # Turn 6: Confirm state -> confirms state and invokes oracle
        t6 = client.post("/api/chat", json={"session_id": session_id, "action": "confirm"}).json()
        self.assertEqual(t6["action"], "EXPLAIN_RESULT")
        self.assertTrue(t6["state"]["confirmed"])
        self.assertEqual(t6["state"]["revision"], 3)
        self.assertEqual(t6["state"]["result_revision"], 3)
        self.assertIsNotNone(t6["result"])
        self.assertEqual(t6["result"]["status"], "recommendation")
        self.assertEqual(t6["result"]["revision"], 3)
        self.assertEqual(model.write_calls, 1)

        # Verify oracle calculation bounds
        rec = t6["result"]["recommendation"]
        self.assertGreaterEqual(rec["recommended_price"], 10000 + 500)  # cost + margin floor
        self.assertLess(rec["recommended_price"], 15000)
        self.assertIn("explanation", t6["result"])
        self.assertTrue(t6["result"]["explanation"])

        # Turn 7: Subsequent calculate on unchanged revision -> result reused, no duplicate write call
        t7 = client.post("/api/chat", json={"session_id": session_id, "action": "calculate"}).json()
        self.assertEqual(t7["action"], "EXPLAIN_RESULT")
        self.assertEqual(t7["result"]["revision"], 3)
        self.assertEqual(model.write_calls, 1)  # write not called again

        # Turn 8: Post-calculation correction -> invalidates existing result
        model._parse_queue.append({"stock": 30})
        t8 = client.post("/api/chat", json={
            "session_id": session_id,
            "action": "message",
            "text": "tambah stok jadi 30",
        }).json()
        self.assertEqual(t8["action"], "SHOW_CONFIRMATION")
        self.assertEqual(t8["state"]["stock"], 30)
        self.assertEqual(t8["state"]["revision"], 4)
        self.assertFalse(t8["state"]["confirmed"])
        self.assertIsNone(t8["result"])
        self.assertIsNone(t8["state"]["result_revision"])

        # Turn 9: Calculate without re-confirming -> refused
        t9 = client.post("/api/chat", json={"session_id": session_id, "action": "calculate"}).json()
        self.assertEqual(t9["action"], "SHOW_CONFIRMATION")
        self.assertIsNone(t9["result"])


class NonRecommendationOutcomesTest(unittest.TestCase):
    """Verifies that no_action and invalid_input outcomes map correctly to the chat contract."""

    def test_no_action_outcome_contract(self):
        # Stock = 5, Days = 10, Daily sales = 5 -> easily sells out before expiry (no discount needed)
        model = ScriptedModel([
            {
                "item_name": "Susu UHT",
                "category": "Dairy",
                "original_price": 18000,
                "cost": 12000,
                "stock": 5,
                "days_remaining": 10,
                "daily_sales": 5,
            }
        ])
        client = _make_client(model)
        s1 = client.post("/api/chat", json={"action": "message", "text": "susu uht lengkap"}).json()
        session_id = s1["session_id"]
        client.post("/api/chat", json={"session_id": session_id, "action": "confirm"})
        calc = client.post("/api/chat", json={"session_id": session_id, "action": "calculate"}).json()

        self.assertEqual(calc["action"], "EXPLAIN_RESULT")
        self.assertEqual(calc["assistant_message"], "Barang ini belum perlu didiskon.")
        self.assertEqual(calc["result"]["status"], "no_action")
        self.assertIn("reassess_in_days", calc["result"])
        self.assertNotIn("recommendation", calc["result"])
        self.assertEqual(model.write_calls, 0)  # No prose generated for no_action

    def test_invalid_input_outcome_contract(self):
        # Cost >= Original price (15000 >= 12000) -> invalid margin
        model = ScriptedModel([
            {
                "item_name": "Kopi Susu",
                "category": "Beverage",
                "original_price": 12000,
                "cost": 15000,
                "stock": 10,
                "days_remaining": 2,
                "daily_sales": 2,
            }
        ])
        client = _make_client(model)
        s1 = client.post("/api/chat", json={"action": "message", "text": "kopi susu"}).json()
        session_id = s1["session_id"]
        client.post("/api/chat", json={"session_id": session_id, "action": "confirm"})
        calc = client.post("/api/chat", json={"session_id": session_id, "action": "calculate"}).json()

        self.assertEqual(calc["action"], "EXPLAIN_RESULT")
        self.assertEqual(calc["assistant_message"], "Ada yang perlu diperiksa dulu.")
        self.assertEqual(calc["result"]["status"], "invalid_input")
        self.assertIn("message", calc["result"])
        self.assertEqual(model.write_calls, 0)


class WriterFallbackAndOutageTest(unittest.TestCase):
    """Verifies that model writer errors degrade gracefully without losing numeric results."""

    def test_writer_contract_error_falls_back_to_empty_prose(self):
        model = ScriptedModel(
            [{"item_name": "Roti Tawar", "category": "Bakery", "original_price": 15000, "cost": 10000, "stock": 20, "days_remaining": 2, "daily_sales": 2}],
            contract_error_write=True,
        )
        client = _make_client(model)
        s1 = client.post("/api/chat", json={"action": "message", "text": "roti tawar lengkap"}).json()
        session_id = s1["session_id"]
        client.post("/api/chat", json={"session_id": session_id, "action": "confirm"})
        calc = client.post("/api/chat", json={"session_id": session_id, "action": "calculate"}).json()

        self.assertEqual(calc["action"], "EXPLAIN_RESULT")
        self.assertEqual(calc["result"]["status"], "recommendation")
        self.assertEqual(calc["result"]["explanation"], "")
        self.assertEqual(calc["result"]["promo_copy"], "")
        self.assertIsNotNone(calc["result"]["recommendation"]["recommended_price"])

    def test_parse_outage_returns_safe_failure_and_preserves_state(self):
        model = ScriptedModel(
            [{"item_name": "Roti Tawar", "category": "Bakery", "original_price": 15000}],
        )
        client = _make_client(model)
        s1 = client.post("/api/chat", json={"action": "message", "text": "roti tawar"}).json()
        session_id = s1["session_id"]
        self.assertEqual(s1["state"]["item_name"], "Roti Tawar")
        self.assertEqual(s1["state"]["revision"], 1)

        # Trigger model outage
        model.fail_parse = True
        s2 = client.post("/api/chat", json={"session_id": session_id, "action": "message", "text": "stok 20 exp besok"}).json()
        self.assertEqual(s2["action"], "SAFE_FAILURE")
        self.assertIn("Sistem AI sedang tidak tersedia", s2["assistant_message"])
        # State survived
        self.assertEqual(s2["state"]["item_name"], "Roti Tawar")
        self.assertEqual(s2["state"]["revision"], 1)


class LiveDevStubWireIntegrationTest(unittest.TestCase):
    """End-to-end test verifying FastAPI talking to the live dev stub HTTP server over TCP."""

    server: dev_stub_model.ThreadingHTTPServer
    server_thread: threading.Thread
    server_port: int

    @classmethod
    def setUpClass(cls):
        # Bind to loopback port 0 to get an ephemeral OS-assigned port
        cls.server = dev_stub_model.ThreadingHTTPServer(("127.0.0.1", 0), dev_stub_model.Handler)
        cls.server_port = cls.server.server_address[1]
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_wire_integration_with_live_http_dev_stub(self):
        model_url = f"http://127.0.0.1:{self.server_port}/v1"
        live_model = OpenAICompatibleModel(base_url=model_url, model="dev-stub", timeout=5.0)
        app = create_app(database_path=":memory:", model=live_model)
        client = TestClient(app)

        # Turn 1: Natural Indonesian phrasing
        r1 = client.post("/api/chat", json={"action": "message", "text": "roti tawar 20 biji exp 2 hari"}).json()
        self.assertEqual(r1["action"], "ASK_FOR_MISSING_FIELDS")
        self.assertEqual(r1["state"]["item_name"], "Roti Tawar")
        self.assertEqual(r1["state"]["category"], "Bakery")
        self.assertEqual(r1["state"]["stock"], 20)
        self.assertEqual(r1["state"]["days_remaining"], 2)
        session_id = r1["session_id"]

        # Turn 2: Provide missing facts in natural Indonesian
        r2 = client.post("/api/chat", json={"session_id": session_id, "action": "message", "text": "harga 15rb modal 10rb sehari 2"}).json()
        self.assertEqual(r2["action"], "SHOW_CONFIRMATION")
        self.assertEqual(r2["state"]["original_price"], 15000)
        self.assertEqual(r2["state"]["cost"], 10000)
        self.assertEqual(r2["state"]["daily_sales"], 2)
        self.assertEqual(r2["missing_fields"], [])

        # Turn 3: Confirm
        r3 = client.post("/api/chat", json={"session_id": session_id, "action": "confirm"}).json()
        self.assertTrue(r3["state"]["confirmed"])

        # Turn 4: Calculate
        r4 = client.post("/api/chat", json={"session_id": session_id, "action": "calculate"}).json()
        self.assertEqual(r4["action"], "EXPLAIN_RESULT")
        self.assertEqual(r4["result"]["status"], "recommendation")
        self.assertGreaterEqual(r4["result"]["recommendation"]["recommended_price"], 10500)
        self.assertLess(r4["result"]["recommendation"]["recommended_price"], 15000)
        # Prose generated by dev stub
        self.assertTrue(r4["result"]["explanation"])
        self.assertTrue(r4["result"]["promo_copy"])


if __name__ == "__main__":
    unittest.main()
