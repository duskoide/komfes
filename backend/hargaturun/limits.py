"""Request limits: body size and per-client rate limiting.

Issue #4 lists both as acceptance requirements rather than optional
hardening. Local inference is the expensive resource here — one oversized or
repeated request costs GPU time, so the cheap checks run before the request
ever reaches a handler.

Both are in-process and single-node on purpose. The preliminary round runs
one Compose stack on one laptop; a shared store would add a dependency the
round explicitly does not need.
"""

from __future__ import annotations

import os
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from starlette.types import ASGIApp, Message, Receive, Scope, Send

JSON = {"content-type": "application/json"}


@dataclass(frozen=True)
class ChatLimits:
    """Fail-closed operational limits for one chat process.

    Every environment override is parsed here so the API cannot accidentally
    apply different validation rules to different limits. Invalid or unsafe
    values fall back to the conservative defaults below.
    """

    model_url: str = "http://127.0.0.1:8080/v1"
    model_name: str = "hargaturun-qwen3.5-4b"
    max_body_bytes: int = 64 * 1024
    inference_timeout_seconds: float = 20.0
    model_timeout_seconds: float = 20.0
    max_turns: int = 20
    max_context_chars: int = 12_000
    max_output_tokens: int = 350
    max_sessions: int = 200
    rate_limit: int = 30
    rate_window_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "ChatLimits":
        model_timeout = _env_float(
            "HARGATURUN_MODEL_TIMEOUT", cls.model_timeout_seconds, minimum=0.1
        )
        return cls(
            model_url=os.getenv("HARGATURUN_MODEL_URL", cls.model_url),
            model_name=os.getenv("HARGATURUN_MODEL_NAME", cls.model_name),
            max_body_bytes=_env_int("HARGATURUN_MAX_BODY_BYTES", cls.max_body_bytes, minimum=1),

            inference_timeout_seconds=_env_float(
                "HARGATURUN_INFERENCE_TIMEOUT_SECONDS",
                model_timeout,
                minimum=0.1,
            ),
            model_timeout_seconds=model_timeout,
            max_turns=_env_int("HARGATURUN_MAX_TURNS", cls.max_turns, minimum=1),
            max_context_chars=_env_int(
                "HARGATURUN_MAX_CONTEXT_CHARS", cls.max_context_chars, minimum=1
            ),
            max_output_tokens=min(
                _env_int("HARGATURUN_MAX_OUTPUT_TOKENS", cls.max_output_tokens, minimum=1),
                512,
            ),
            max_sessions=_env_int("HARGATURUN_MAX_SESSIONS", cls.max_sessions, minimum=1),
            rate_limit=_env_int("HARGATURUN_RATE_LIMIT", cls.rate_limit, minimum=1),
            rate_window_seconds=_env_float(
                "HARGATURUN_RATE_WINDOW", cls.rate_window_seconds, minimum=0.1
            ),
        )


def _env_int(name: str, default: int, *, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= minimum else default


def _env_float(name: str, default: float, *, minimum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= minimum else default


class RequestBodyTooLarge(Exception):
    """Raised before a request handler can consume an oversized body."""


async def _reject(send: Send, status: int, detail: str) -> None:
    body = b'{"detail":"%s"}' % detail.encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    """Reject request bodies larger than ``max_bytes``.

    Counts bytes as they stream instead of trusting ``Content-Length``, so a
    lying or absent header cannot get a large body past the check.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int = 64 * 1024) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _reject(send, 413, "Permintaan terlalu besar.")
            return

        seen = 0
        exceeded = False

        async def counting_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    # Raise while Starlette is still reading the body. This
                    # guarantees a stable 413 instead of a parser-specific
                    # 400/422 response for chunked or lying requests.
                    raise RequestBodyTooLarge
            return message

        try:
            await self.app(scope, counting_receive, send)
        except RequestBodyTooLarge:
            await _reject(send, 413, "Permintaan terlalu besar.")


class RateLimitMiddleware:
    """Fixed-window rate limit per client address on selected path prefixes.

    Applied only to the inference endpoints. Health checks and static reads
    are left alone so probes are never throttled.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        limit: int = 30,
        window_seconds: float = 60.0,
        paths: Iterable[str] = ("/api/chat", "/api/recommend"),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.limit = limit
        self.window = window_seconds
        self.paths = tuple(paths)
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self._guarded(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        if self._over_limit(self._client(scope)):
            await _reject(send, 429, "Terlalu banyak permintaan. Coba lagi sebentar.")
            return

        await self.app(scope, receive, send)

    def _guarded(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.paths)

    @staticmethod
    def _client(scope: Scope) -> str:
        client = scope.get("client")
        return client[0] if client else "unknown"

    def _over_limit(self, key: str) -> bool:
        now = self.clock()
        window_start = now - self.window
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= self.limit:
            return True
        hits.append(now)
        # Bound the key space: a stream of distinct addresses must not grow
        # this dict without limit.
        if len(self._hits) > 1024:
            for stale_key in [k for k, v in self._hits.items() if not v]:
                del self._hits[stale_key]
        return False


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


__all__ = [
    "BodySizeLimitMiddleware",
    "ChatLimits",
    "RateLimitMiddleware",
    "RequestBodyTooLarge",
]
