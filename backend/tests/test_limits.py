"""Tests for body-size and rate limits, and the CORS default."""

from __future__ import annotations

import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hargaturun.api import _cors_origins
from hargaturun.limits import BodySizeLimitMiddleware, RateLimitMiddleware


def _app() -> FastAPI:
    """Minimal app with the two paths that matter: one guarded, one not."""
    app = FastAPI()

    @app.post("/api/chat")
    def chat(payload: dict):
        return {"ok": True, "size": len(payload.get("text", ""))}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


class BodySizeLimitTest(unittest.TestCase):
    def _client(self, max_bytes: int) -> TestClient:
        app = _app()
        app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)
        return TestClient(app)

    def test_small_body_passes(self):
        client = self._client(2048)
        response = client.post("/api/chat", json={"text": "roti tawar"})
        self.assertEqual(response.status_code, 200)

    def test_oversized_body_is_rejected_with_413(self):
        client = self._client(128)
        response = client.post("/api/chat", json={"text": "x" * 4096})
        self.assertEqual(response.status_code, 413)
        self.assertIn("terlalu besar", response.json()["detail"].lower())

    def test_lying_content_length_does_not_get_through(self):
        # The stream is counted, so a header that understates the body cannot
        # smuggle a large payload past the check.
        client = self._client(128)
        response = client.post(
            "/api/chat",
            content=b'{"text":"' + b"x" * 4096 + b'"}',
            headers={"Content-Type": "application/json", "Content-Length": "10"},
        )
        self.assertNotEqual(response.status_code, 200)


class RateLimitTest(unittest.TestCase):
    def _client(self, limit: int, ticks: list[float]) -> TestClient:
        app = _app()
        clock = iter(ticks)
        app.add_middleware(
            RateLimitMiddleware,
            limit=limit,
            window_seconds=60.0,
            clock=lambda: next(clock),
        )
        return TestClient(app)

    def test_requests_under_the_limit_pass(self):
        client = self._client(3, [0.0, 1.0, 2.0])
        for _ in range(3):
            self.assertEqual(
                client.post("/api/chat", json={"text": "hi"}).status_code, 200
            )

    def test_request_over_the_limit_is_rejected_with_429(self):
        client = self._client(2, [0.0, 1.0, 2.0])
        client.post("/api/chat", json={"text": "hi"})
        client.post("/api/chat", json={"text": "hi"})
        response = client.post("/api/chat", json={"text": "hi"})
        self.assertEqual(response.status_code, 429)

    def test_window_expiry_allows_traffic_again(self):
        client = self._client(1, [0.0, 1.0, 120.0])
        self.assertEqual(client.post("/api/chat", json={"text": "hi"}).status_code, 200)
        self.assertEqual(client.post("/api/chat", json={"text": "hi"}).status_code, 429)
        self.assertEqual(client.post("/api/chat", json={"text": "hi"}).status_code, 200)

    def test_health_checks_are_never_throttled(self):
        client = self._client(1, [0.0])
        for _ in range(5):
            self.assertEqual(client.get("/api/health").status_code, 200)


class CorsDefaultTest(unittest.TestCase):
    def test_default_is_not_a_wildcard(self):
        previous = os.environ.pop("HARGATURUN_CORS_ORIGINS", None)
        try:
            origins = _cors_origins()
        finally:
            if previous is not None:
                os.environ["HARGATURUN_CORS_ORIGINS"] = previous
        self.assertNotIn("*", origins)
        self.assertTrue(all(o.startswith("http://") for o in origins))

    def test_configured_origins_win(self):
        previous = os.environ.get("HARGATURUN_CORS_ORIGINS")
        os.environ["HARGATURUN_CORS_ORIGINS"] = "https://app.example, https://b.example"
        try:
            self.assertEqual(
                _cors_origins(), ["https://app.example", "https://b.example"]
            )
        finally:
            if previous is None:
                del os.environ["HARGATURUN_CORS_ORIGINS"]
            else:
                os.environ["HARGATURUN_CORS_ORIGINS"] = previous


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
