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

import time
from collections import deque
from collections.abc import Awaitable, Callable, Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

JSON = {"content-type": "application/json"}


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
            nonlocal seen, exceeded
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    exceeded = True
                    # Stop the stream rather than handing the handler a
                    # truncated body it might treat as complete.
                    return {"type": "http.disconnect"}
            return message

        await self.app(scope, counting_receive, send)
        if exceeded:  # pragma: no cover - handler already aborted
            return


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


__all__ = ["BodySizeLimitMiddleware", "RateLimitMiddleware"]
