"""Spawn-safe worker boundary for synchronous model inference."""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InferenceRequest:
    """Serializable request envelope sent to one disposable worker."""

    callable_: Any
    args: tuple[Any, ...]
    max_result_bytes: int


def _state_snapshot(callable_: Any) -> dict[str, Any] | None:
    owner = getattr(callable_, "__self__", None)
    state = getattr(owner, "__dict__", None)
    if not isinstance(state, dict):
        return None
    try:
        pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
    except (TypeError, ValueError, pickle.PicklingError):
        return None
    return dict(state)


def _encode(response: dict[str, Any], max_result_bytes: int) -> bytes:
    encoded = pickle.dumps(response, protocol=pickle.HIGHEST_PROTOCOL)
    if len(encoded) <= max_result_bytes:
        return encoded
    fallback = pickle.dumps(
        {"ok": False, "error": "result_too_large", "state": None},
        protocol=pickle.HIGHEST_PROTOCOL,
    )
    if len(fallback) > max_result_bytes:
        raise ValueError("inference result limit is too small")
    return fallback


def run_inference_worker(request: InferenceRequest, connection: Any) -> None:
    """Run the request and send only a bounded, generic response."""
    try:
        value = request.callable_(*request.args)
        response = {"ok": True, "value": value, "state": _state_snapshot(request.callable_)}
    except BaseException:
        response = {"ok": False, "error": "provider_failure", "state": _state_snapshot(request.callable_)}

    try:
        connection.send_bytes(_encode(response, request.max_result_bytes))
    except (BrokenPipeError, OSError, ValueError):
        # The parent may have timed out and closed its end. The worker is still
        # reaped by the parent; there is no useful error to report here.
        pass
    finally:
        connection.close()
