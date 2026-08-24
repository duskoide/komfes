from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from hargaturun.api import create_app
from hargaturun.limits import ChatLimits
from hargaturun.model_client import OpenAICompatibleModel


COMPLETE = {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 20,
    "days_remaining": 2,
    "daily_sales": 2,
}


class Model:
    def __init__(self, *, fail=False, slow=False, completion_marker: str | None = None):
        self.fail = fail
        self.slow = slow
        self.completion_marker = completion_marker

    def parse(self, text: str) -> dict:
        if self.slow:
            time.sleep(0.3)
            if self.completion_marker:
                Path(self.completion_marker).write_text("completed", encoding="utf-8")
        if self.fail:
            raise RuntimeError("provider secret: http://internal.example/secret")
        return {"parsed_input": COMPLETE, "needs_confirmation": False, "missing_fields": []}

    def write(self, normalized_input: dict, engine_result: dict) -> dict:
        return {"explanation": "Aman untuk segera ditangani.", "promo_copy": "Harga spesial."}


class CustomBlockingModel:
    def __init__(self, marker: str):
        self.marker = marker

    def parse(self, text: str) -> dict:
        time.sleep(0.3)
        Path(self.marker).write_text("completed", encoding="utf-8")
        return {"parsed_input": COMPLETE, "needs_confirmation": False, "missing_fields": []}

    def write(self, normalized_input: dict, engine_result: dict) -> dict:
        return {"explanation": "ok", "promo_copy": "ok"}


class BlockingOpenAIModel(OpenAICompatibleModel):
    def __init__(self, marker: str):
        super().__init__()
        self.marker = marker

    def parse(self, text: str) -> dict:
        time.sleep(0.3)
        Path(self.marker).write_text("completed", encoding="utf-8")
        return {"parsed_input": COMPLETE, "needs_confirmation": False, "missing_fields": []}


def client(model: object) -> TestClient:
    return TestClient(create_app(database_path=":memory:", model=model))


class OperationalLimitsTest(unittest.TestCase):
    def test_defaults_are_sane_and_invalid_environment_fails_closed(self):
        with patch.dict(
            os.environ,
            {
                "HARGATURUN_MAX_BODY_BYTES": "-1",
                "HARGATURUN_INFERENCE_TIMEOUT_SECONDS": "invalid",
                "HARGATURUN_MAX_TURNS": "0",
                "HARGATURUN_MAX_CONTEXT_CHARS": "-4",
                "HARGATURUN_MAX_OUTPUT_TOKENS": "99999",
            },
            clear=False,
        ):
            limits = ChatLimits.from_env()
        self.assertEqual(limits.max_body_bytes, 64 * 1024)
        self.assertEqual(limits.inference_timeout_seconds, 20.0)
        self.assertEqual(limits.max_turns, 20)
        self.assertEqual(limits.max_context_chars, 12_000)
        self.assertEqual(limits.max_output_tokens, 512)

    def test_body_limit_rejects_over_limit_and_accepts_boundary(self):
        with patch.dict(os.environ, {"HARGATURUN_MAX_BODY_BYTES": "120"}, clear=False):
            limited = client(Model())
        # A real JSON request is below the configured limit at this boundary.
        self.assertNotEqual(limited.post("/api/chat", json={"action": "message", "text": "x"}).status_code, 413)
        response = limited.post("/api/chat", content=b"x" * 121, headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 413)
        self.assertNotIn("traceback", response.text.lower())

    def test_turn_and_context_budgets_return_generic_429(self):
        with patch.dict(
            os.environ,
            {"HARGATURUN_MAX_TURNS": "1", "HARGATURUN_MAX_CONTEXT_CHARS": "4"},
            clear=False,
        ):
            api = client(Model())
        first = api.post("/api/chat", json={"action": "message", "text": "abcd"})
        self.assertEqual(first.status_code, 200)
        second = api.post(
            "/api/chat",
            json={"action": "message", "session_id": first.json()["session_id"], "text": "x"},
        )
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json(), {"detail": "Batas konsultasi tercapai. Mulai sesi baru untuk melanjutkan."})

    def _assert_timeout_kills_provider(self, model: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "completed"
            model.marker = str(marker)
            with patch.dict(os.environ, {"HARGATURUN_INFERENCE_TIMEOUT_SECONDS": "0.1"}, clear=False):
                started = time.monotonic()
                response = client(model).post("/api/chat", json={"action": "message", "text": "roti"})
            elapsed = time.monotonic() - started
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["action"], "SAFE_FAILURE")
            self.assertLess(elapsed, 0.25)
            time.sleep(0.35)
            self.assertFalse(marker.exists(), "timed-out provider process kept running")

    def test_inference_timeout_terminates_custom_provider_process(self):
        self._assert_timeout_kills_provider(CustomBlockingModel("unused"))

    def test_inference_timeout_terminates_openai_provider_process(self):
        self._assert_timeout_kills_provider(BlockingOpenAIModel("unused"))

    def test_all_operational_environment_values_share_fail_closed_defaults(self):
        invalid = {
            "HARGATURUN_MAX_BODY_BYTES": "invalid",
            "HARGATURUN_MODEL_TIMEOUT": "invalid",
            "HARGATURUN_INFERENCE_TIMEOUT_SECONDS": "invalid",
            "HARGATURUN_MAX_TURNS": "0",
            "HARGATURUN_MAX_CONTEXT_CHARS": "-1",
            "HARGATURUN_MAX_OUTPUT_TOKENS": "0",
            "HARGATURUN_MAX_SESSIONS": "invalid",
            "HARGATURUN_RATE_LIMIT": "0",
            "HARGATURUN_RATE_WINDOW": "invalid",
        }
        with patch.dict(os.environ, invalid, clear=False):
            limits = ChatLimits.from_env()
        self.assertEqual(limits.max_body_bytes, ChatLimits.max_body_bytes)
        self.assertEqual(limits.model_timeout_seconds, ChatLimits.model_timeout_seconds)
        self.assertEqual(limits.inference_timeout_seconds, ChatLimits.model_timeout_seconds)
        self.assertEqual(limits.max_turns, ChatLimits.max_turns)
        self.assertEqual(limits.max_context_chars, ChatLimits.max_context_chars)
        self.assertEqual(limits.max_output_tokens, ChatLimits.max_output_tokens)
        self.assertEqual(limits.max_sessions, ChatLimits.max_sessions)
        self.assertEqual(limits.rate_limit, ChatLimits.rate_limit)
        self.assertEqual(limits.rate_window_seconds, ChatLimits.rate_window_seconds)

    def test_all_operational_environment_values_are_wired(self):
        values = {
            "HARGATURUN_MAX_BODY_BYTES": "4096",
            "HARGATURUN_MODEL_TIMEOUT": "3.5",
            "HARGATURUN_INFERENCE_TIMEOUT_SECONDS": "2.5",
            "HARGATURUN_MAX_TURNS": "7",
            "HARGATURUN_MAX_CONTEXT_CHARS": "800",
            "HARGATURUN_MAX_OUTPUT_TOKENS": "400",
            "HARGATURUN_MAX_SESSIONS": "11",
            "HARGATURUN_RATE_LIMIT": "9",
            "HARGATURUN_RATE_WINDOW": "12.5",
        }
        with patch.dict(os.environ, values, clear=False):
            limits = ChatLimits.from_env()
            app = create_app(database_path=":memory:", model=Model())
        self.assertEqual(limits.max_sessions, 11)
        self.assertEqual(limits.rate_limit, 9)
        self.assertEqual(limits.rate_window_seconds, 12.5)
        self.assertEqual(app.state.sessions._max, 11)



class RedactedLoggingTest(unittest.TestCase):
    def test_default_logs_never_include_message_or_provider_details(self):
        sensitive = "NAMA-PRIBADI-123 image-data-secret"
        with self.assertLogs("hargaturun.api", level=logging.INFO) as captured:
            response = client(Model()).post(
                "/api/chat", json={"action": "message", "text": sensitive}
            )
        self.assertEqual(response.status_code, 200)
        output = "\n".join(captured.output)
        self.assertNotIn(sensitive, output)
        self.assertNotIn("image-data-secret", output)

        with self.assertLogs("hargaturun.api", level=logging.INFO) as captured:
            response = client(Model(fail=True)).post(
                "/api/chat", json={"action": "message", "text": sensitive}
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("provider secret", "\n".join(captured.output))
        self.assertNotIn("internal.example", response.text)


class OutputTokenLimitTest(unittest.TestCase):
    def test_model_client_sends_bounded_output_tokens(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"choices":[{"message":{"content":"{}"}}]}'

        model = OpenAICompatibleModel(max_output_tokens=37)
        with patch("urllib.request.urlopen", return_value=Response()) as urlopen:
            model._complete("system", "user")
        request = urlopen.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body["max_tokens"], 37)


if __name__ == "__main__":
    unittest.main()
