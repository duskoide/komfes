"""Bounded consultation state, action policy and pricing tool.

Implements sections 3.1, 3.2 and 4 of ``docs/HargaTurun_Agentic_Workflow_Plan.md``.

Two boundaries are enforced here rather than trusted to the model:

* the model may only *propose* field patches — this module decides what is
  accepted, and code alone increments the revision;
* the pricing oracle is the sole numerical authority, reached only through
  :class:`PricingTool` and only for a revision the vendor confirmed.

There is no persistence: the preliminary round forbids chat history, so
sessions live in memory only and disappear with the process.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Iterable

from .pricing import (
    STATUS_INVALID,
    STATUS_NO_ACTION,
    STATUS_RECOMMENDATION,
    OracleResult,
    PricingInput,
    compute,
)

# --------------------------------------------------------------------------- #
# Action allowlist (§3.1)                                                     #
# --------------------------------------------------------------------------- #

ASK_FOR_MISSING_FIELDS = "ASK_FOR_MISSING_FIELDS"
SHOW_CONFIRMATION = "SHOW_CONFIRMATION"
CALL_PRICING_TOOL = "CALL_PRICING_TOOL"
EXPLAIN_RESULT = "EXPLAIN_RESULT"
REVISE_PROMO_COPY = "REVISE_PROMO_COPY"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
SAFE_FAILURE = "SAFE_FAILURE"

ACTIONS = frozenset(
    {
        ASK_FOR_MISSING_FIELDS,
        SHOW_CONFIRMATION,
        CALL_PRICING_TOOL,
        EXPLAIN_RESULT,
        REVISE_PROMO_COPY,
        OUT_OF_SCOPE,
        SAFE_FAILURE,
    }
)

# Request actions the client may ask for.
REQUEST_ACTIONS = frozenset(
    {"message", "confirm", "calculate", "explain", "revise_promo", "reset"}
)

# --------------------------------------------------------------------------- #
# State (§3.2)                                                                #
# --------------------------------------------------------------------------- #

ITEM_FIELDS = (
    "item_name",
    "category",
    "original_price",
    "cost",
    "stock",
    "days_remaining",
    "daily_sales",
    "total_shelf_life",
    "shop_name",
)

#: Facts the oracle cannot run without. ``total_shelf_life`` is absent on
#: purpose: the oracle falls back to a documented category default.
REQUIRED_FIELDS = (
    "item_name",
    "category",
    "original_price",
    "cost",
    "stock",
    "days_remaining",
    "daily_sales",
)

_INT_FIELDS = frozenset(
    {"original_price", "cost", "stock", "days_remaining", "daily_sales", "total_shelf_life"}
)
_STR_FIELDS = frozenset({"item_name", "category", "shop_name"})


@dataclass(frozen=True)
class ConsultationState:
    """Immutable consultation state. Every accepted change produces a copy."""

    item_name: str | None = None
    category: str | None = None
    original_price: int | None = None
    cost: int | None = None
    stock: int | None = None
    days_remaining: int | None = None
    daily_sales: int | None = None
    total_shelf_life: int | None = None
    shop_name: str | None = None

    confirmed: bool = False
    revision: int = 0
    result_revision: int | None = None

    def missing_fields(self) -> list[str]:
        return [f for f in REQUIRED_FIELDS if getattr(self, f) is None]

    def is_complete(self) -> bool:
        return not self.missing_fields()

    def to_dict(self) -> dict[str, Any]:
        return {
            **{f: getattr(self, f) for f in ITEM_FIELDS},
            "confirmed": self.confirmed,
            "revision": self.revision,
            "result_revision": self.result_revision,
        }

    def to_pricing_input(self) -> PricingInput:
        """Only valid on a complete state; callers must check first."""
        if not self.is_complete():
            raise ValueError("refusing to build pricing input from incomplete state")
        return PricingInput(
            category=self.category,
            original_price=self.original_price,
            cost=self.cost,
            stock=self.stock,
            days_remaining=self.days_remaining,
            daily_sales=self.daily_sales,
            total_shelf_life=self.total_shelf_life,
        )


def validate_patch(
    proposed: object,
    *,
    allowed_categories: Iterable[str],
) -> tuple[dict[str, Any], list[str]]:
    """Return ``(accepted, rejected_keys)`` for a proposed patch.

    Unknown keys, wrong types, booleans posing as numbers and non-finite or
    negative economics are dropped rather than coerced. A rejected patch
    changes nothing, so a bad model turn cannot corrupt confirmed facts.
    """
    if not isinstance(proposed, dict):
        return {}, []

    categories = set(allowed_categories)
    accepted: dict[str, Any] = {}
    rejected: list[str] = []

    for key, value in proposed.items():
        if key not in ITEM_FIELDS:
            rejected.append(key)
            continue
        if value is None:
            # Explicit null means "still unknown"; never treated as a change.
            continue

        if key in _INT_FIELDS:
            # bool is a subclass of int in Python: reject it explicitly.
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                rejected.append(key)
                continue
            if value != value or value in (float("inf"), float("-inf")):
                rejected.append(key)
                continue
            number = int(value)
            if number < 0:
                rejected.append(key)
                continue
            if key in {"original_price", "cost", "stock"} and number == 0 and key != "cost":
                # Zero price or zero stock is not a usable economic fact.
                rejected.append(key)
                continue
            accepted[key] = number
            continue

        if key in _STR_FIELDS:
            if not isinstance(value, str):
                rejected.append(key)
                continue
            text = value.strip()
            if not text:
                rejected.append(key)
                continue
            if key == "category" and text not in categories:
                rejected.append(key)
                continue
            accepted[key] = text

    return accepted, rejected


def merge_patch(state: ConsultationState, accepted: dict[str, Any]) -> ConsultationState:
    """Merge an already-validated patch.

    A patch that changes nothing leaves the revision untouched. Any real
    change bumps the revision, clears confirmation and invalidates the
    current result, so a stale recommendation can never be reused.
    """
    changes = {k: v for k, v in accepted.items() if getattr(state, k) != v}
    if not changes:
        return state
    return replace(
        state,
        **changes,
        revision=state.revision + 1,
        confirmed=False,
        result_revision=None,
    )


def confirm(state: ConsultationState) -> ConsultationState:
    """Confirm the current revision. Refused unless the state is complete."""
    if not state.is_complete():
        return state
    if state.confirmed:
        return state
    return replace(state, confirmed=True)


def decide_action(state: ConsultationState, *, has_result: bool) -> str:
    """The action policy. Preconditions live here, never in the model."""
    if not state.is_complete():
        return ASK_FOR_MISSING_FIELDS
    if not state.confirmed:
        return SHOW_CONFIRMATION
    if has_result and state.result_revision == state.revision:
        return EXPLAIN_RESULT
    return CALL_PRICING_TOOL


# --------------------------------------------------------------------------- #
# Pricing tool (§4)                                                           #
# --------------------------------------------------------------------------- #


class PricingToolRefused(RuntimeError):
    """Raised when a precondition for calling the oracle is not met."""


@dataclass
class ToolCall:
    """One sanitized trace event. Deliberately carries no prose and no
    chain-of-thought — only the fields and outcome."""

    name: str
    revision: int
    status: str
    accepted_fields: tuple[str, ...] = ()


class PricingTool:
    """Narrow typed adapter over :func:`pricing.compute`.

    Calls no model, no database and no network. Refuses any state that is
    incomplete or whose current revision is unconfirmed, which is what makes
    "calculation before confirmation performs zero tool calls" true by
    construction rather than by convention.
    """

    name = "calculate_markdown_recommendation"

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    def compute(self, state: ConsultationState) -> OracleResult:
        if not state.is_complete():
            raise PricingToolRefused("state is incomplete")
        if not state.confirmed:
            raise PricingToolRefused("current revision is not confirmed")

        result = compute(state.to_pricing_input())
        self.calls.append(
            ToolCall(
                name=self.name,
                revision=state.revision,
                status=result.status,
                accepted_fields=tuple(
                    f for f in REQUIRED_FIELDS if getattr(state, f) is not None
                ),
            )
        )
        return result


# --------------------------------------------------------------------------- #
# Sessions                                                                    #
# --------------------------------------------------------------------------- #


@dataclass
class Session:
    """One consultation. Held in memory only — no chat history is persisted."""

    session_id: str
    state: ConsultationState = field(default_factory=ConsultationState)
    result: dict[str, Any] | None = None
    result_status: str | None = None

    def drop_result(self) -> None:
        self.result = None
        self.result_status = None


class SessionStore:
    """In-memory session store with a bounded size.

    The cap is abuse protection, not caching: an unbounded dict keyed by a
    client-supplied id is a memory-growth vector.
    """

    def __init__(self, max_sessions: int = 200) -> None:
        self._sessions: dict[str, Session] = {}
        self._max = max_sessions

    def create(self) -> Session:
        if len(self._sessions) >= self._max:
            # Drop the oldest insertion; dicts preserve insertion order.
            oldest = next(iter(self._sessions))
            del self._sessions[oldest]
        session = Session(session_id=uuid.uuid4().hex)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def drop(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._sessions)


__all__ = [
    "ACTIONS",
    "ASK_FOR_MISSING_FIELDS",
    "CALL_PRICING_TOOL",
    "EXPLAIN_RESULT",
    "ITEM_FIELDS",
    "OUT_OF_SCOPE",
    "REQUEST_ACTIONS",
    "REQUIRED_FIELDS",
    "REVISE_PROMO_COPY",
    "SAFE_FAILURE",
    "SHOW_CONFIRMATION",
    "STATUS_INVALID",
    "STATUS_NO_ACTION",
    "STATUS_RECOMMENDATION",
    "ConsultationState",
    "PricingTool",
    "PricingToolRefused",
    "Session",
    "SessionStore",
    "ToolCall",
    "confirm",
    "decide_action",
    "merge_patch",
    "validate_patch",
]
