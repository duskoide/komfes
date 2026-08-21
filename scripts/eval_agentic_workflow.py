#!/usr/bin/env python3
"""Measure the deterministic contract subset of the agentic workflow.

This harness intentionally does *not* claim full Agentic Workflow Plan §8.4
readiness. It measures only the deterministic workflow contract: tool policy,
state safety, stale-result invalidation, oracle safety, expected fixture
outcomes, and reproducibility. Real-model writing metrics and the direct-chat
comparison remain explicitly ``not_measured`` until their required artifacts
exist.

The evaluation suite is validated before replay and before the report path is
opened for writing. A malformed, empty, duplicate, or semantically unusable
suite therefore fails closed instead of producing a false all-zero report.

Usage:
    python scripts/eval_agentic_workflow.py [--cases PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys

# Keep evaluation/report generation from creating provenance noise in the tree.
sys.dont_write_bytecode = True

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from hargaturun.consultation import (  # noqa: E402
    ACTIONS,
    CALL_PRICING_TOOL,
    ITEM_FIELDS,
    REQUIRED_FIELDS,
    REQUEST_ACTIONS,
    ConsultationState,
    PricingTool,
    PricingToolRefused,
    Session,
    confirm as confirm_state,
    decide_action,
    merge_patch,
    validate_patch,
)
from hargaturun.pricing import (  # noqa: E402
    CATEGORIES,
    DISCOUNT_MAX,
    DISCOUNT_MIN,
    DISCOUNT_STEP,
    MIN_MARGIN_RP,
    PRICE_STEP,
    STATUS_INVALID,
    STATUS_NO_ACTION,
    STATUS_RECOMMENDATION,
    OracleResult,
    compute,
)

VALID_RESULT_STATUSES = {STATUS_RECOMMENDATION, STATUS_NO_ACTION, STATUS_INVALID}
CASE_KEYS = {"scenario_id", "case_id", "tags", "turns", "expect"}
TURN_KEYS = {"action", "patch"}
EXPECT_KEYS = {"final_action", "result_status", "tool_calls", "missing_fields", "state"}
STATE_FIELDS = set(ITEM_FIELDS) | {"confirmed", "revision", "result_revision"}


class SuiteValidationError(ValueError):
    """Raised when an evaluation suite cannot be trusted as a denominator."""


@dataclass
class Violation:
    case_id: str
    kind: str
    detail: str
    turn: int | None = None


@dataclass
class Counters:
    """Counts are reported with explicit case/turn/result denominators."""

    cases: int = 0
    turns: int = 0
    result_evaluations: int = 0
    tool_calls: int = 0
    premature_tool_calls: int = 0
    duplicate_tool_calls: int = 0
    missed_tool_calls: int = 0
    unauthorized_mutations: int = 0
    stale_result_exposures: int = 0
    stale_result_reuses: int = 0
    stale_result_invalidations: int = 0
    result_hash_violations: int = 0
    pricing_result_violations: int = 0
    margin_violations: int = 0
    discount_violations: int = 0
    price_consistency_violations: int = 0
    status_shape_violations: int = 0
    projection_violations: int = 0
    nondeterministic_results: int = 0
    final_action_mismatches: int = 0
    result_status_mismatches: int = 0
    state_mismatches: int = 0
    missing_field_mismatches: int = 0
    violations: list[Violation] = field(default_factory=list)

    def fail(
        self, case_id: str, kind: str, detail: str, turn: int | None = None
    ) -> None:
        self.violations.append(Violation(case_id, kind, detail, turn))


@dataclass
class ResultObservation:
    """One successful tool result, checked at its producing revision."""

    revision: int
    state: ConsultationState
    result: OracleResult
    payload: dict[str, Any]
    validation_errors: list[tuple[str, str]]
    reproducible: bool


@dataclass
class Run:
    """Observable result of replaying one case through a real Session."""

    final_action: str
    result_status: str | None
    result_price: int | None
    tool_calls: int
    state: ConsultationState
    missing_fields: list[str]
    authoritative_result: OracleResult | None
    result_payload: dict[str, Any] | None
    result_observations: list[ResultObservation]
    trace: list[dict[str, Any]]
    stale_result_exposures: int


def canonical_result(result: OracleResult | None) -> dict[str, Any] | None:
    """Canonical, complete oracle output; no status/price-only shortcuts."""
    return None if result is None else asdict(result)


def _hash_canonical_result(canonical: dict[str, Any] | None) -> str | None:
    if canonical is None:
        return None
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def result_hash(result: OracleResult | None) -> str | None:
    return _hash_canonical_result(canonical_result(result))


def validate_stored_result(
    payload: object,
    *,
    expected_canonical: dict[str, Any] | None = None,
) -> list[str]:
    """Validate the envelope and bind it to the result produced this time.

    A payload and hash can be replaced together, so checking only their
    internal consistency is not an integrity check.  ``expected_canonical`` is
    the immutable binding captured at the production boundary.
    """
    if not isinstance(payload, dict):
        return ["stored result is not an object"]
    canonical = payload.get("oracle")
    if not isinstance(canonical, dict):
        return ["stored result has no canonical oracle payload"]
    errors: list[str] = []
    expected_hash = _hash_canonical_result(canonical)
    if payload.get("result_hash") != expected_hash:
        errors.append("stored result_hash does not match canonical oracle payload")
    if payload.get("status") != canonical.get("status"):
        errors.append("stored status does not match canonical oracle payload")
    if expected_canonical is not None and canonical != expected_canonical:
        errors.append(
            "stored canonical oracle payload does not match the OracleResult "
            "produced for this invocation"
        )
    revision = payload.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        errors.append("stored result revision is invalid")
    return errors


def _record_result_hash_violation(
    *,
    counters: Counters | None,
    case_id: str,
    turn: int | None,
    violation_key: tuple[int, str],
    errors: list[str],
    reported_invalid_keys: set[tuple[int, str]],
) -> None:
    """Record one integrity failure once across production and trust checks."""
    if not errors or violation_key in reported_invalid_keys:
        return
    reported_invalid_keys.add(violation_key)
    if counters is not None:
        counters.result_hash_violations += 1
        counters.fail(case_id, "result_hash", "; ".join(errors), turn)


def _trusted_session_result(
    session: Session,
    *,
    counters: Counters | None,
    case_id: str,
    turn: int | None,
    reported_invalid_keys: set[tuple[int, str]],
    bound_results: dict[int, dict[str, Any]],
) -> bool:
    """Return whether the current stored payload is safe to reuse."""
    payload = session.result
    if payload is None:
        return False
    expected_revision = payload.get("revision")
    expected_canonical = (
        bound_results.get(expected_revision)
        if isinstance(expected_revision, int) and not isinstance(expected_revision, bool)
        else None
    )
    errors = validate_stored_result(
        payload, expected_canonical=expected_canonical
    )
    if expected_revision not in bound_results:
        errors.append(
            "stored result is not bound to an OracleResult produced in this replay"
        )
    expected_key = _hash_canonical_result(expected_canonical) or "unbound"
    revision = expected_revision if isinstance(expected_revision, int) else -1
    _record_result_hash_violation(
        counters=counters,
        case_id=case_id,
        turn=turn,
        violation_key=(revision, expected_key),
        errors=errors,
        reported_invalid_keys=reported_invalid_keys,
    )
    if errors:
        return False
    return payload.get("revision") == session.state.revision


def stale_result_exposed(session: Session) -> bool:
    """Observe the actual result-bearing Session, without hiding stale data."""
    if session.result is None:
        return False
    return session.result.get("revision") != session.state.revision


def _result_observation(
    *,
    case_id: str,
    turn: int,
    state: ConsultationState,
    oracle: OracleResult,
    payload: dict[str, Any],
    counters: Counters | None,
    reported_invalid_keys: set[tuple[int, str]],
) -> ResultObservation:
    """Validate and reproduce one result at the revision that produced it."""
    integrity_errors = validate_stored_result(
        payload, expected_canonical=canonical_result(oracle)
    )
    errors = validate_authoritative_result(state, oracle)
    errors.extend(("result_hash", detail) for detail in integrity_errors)
    expected_key = _hash_canonical_result(canonical_result(oracle)) or "unbound"
    _record_result_hash_violation(
        counters=counters,
        case_id=case_id,
        turn=turn,
        violation_key=(payload.get("revision", -1), expected_key),
        errors=integrity_errors,
        reported_invalid_keys=reported_invalid_keys,
    )
    reproduced = compute(state.to_pricing_input())
    reproducible = canonical_result(oracle) == canonical_result(reproduced)
    if not reproducible:
        errors.append(("nondeterminism", "tool result differs from a fresh oracle evaluation at the producing revision"))

    if counters is not None:
        counters.result_evaluations += 1
        safety_errors = [
            (kind, detail) for kind, detail in errors if kind != "result_hash"
        ]
        if safety_errors:
            counters.pricing_result_violations += 1
            kinds = {kind for kind, _ in safety_errors}
            for kind, detail in safety_errors:
                counters.fail(case_id, f"pricing_{kind}", detail, turn)
            if "margin" in kinds:
                counters.margin_violations += 1
            if "discount" in kinds:
                counters.discount_violations += 1
            if "price_consistency" in kinds:
                counters.price_consistency_violations += 1
            if "status_shape" in kinds:
                counters.status_shape_violations += 1
            if "projection" in kinds:
                counters.projection_violations += 1
        if not reproducible:
            counters.nondeterministic_results += 1

    return ResultObservation(
        revision=state.revision,
        state=state,
        result=oracle,
        payload=payload,
        validation_errors=errors,
        reproducible=reproducible,
    )


def _session_result(oracle: OracleResult, revision: int) -> dict[str, Any]:
    return {
        "revision": revision,
        "status": oracle.status,
        "oracle": canonical_result(oracle),
        "result_hash": result_hash(oracle),
    }


def replay(case: dict[str, Any], counters: Counters | None = None) -> Run:
    """Replay scripted extractor output through the real Session/reducer/tool.

    Result invalidation is recorded before and after ``Session.drop_result``.
    The final visibility check observes the Session object itself, so clearing a
    separate evaluator local cannot make a stale-result defect disappear.
    """
    session = Session(session_id=f"eval-{case['case_id']}")
    tool = PricingTool()
    action = decide_action(session.state, has_result=False)
    trace: list[dict[str, Any]] = []
    stale_exposures = 0
    result_observations: list[ResultObservation] = []
    reported_invalid_keys: set[tuple[int, str]] = set()
    # Bind each payload object to the complete OracleResult produced for it.
    bound_results: dict[int, dict[str, Any]] = {}

    for turn_index, turn in enumerate(case["turns"]):
        requested = turn["action"]
        if counters is not None:
            counters.turns += 1

        before_state = session.state
        before_result = session.result
        proposed: object = {}
        if requested in {"message", "confirm"}:
            proposed = turn.get("patch", {})
            accepted, rejected = validate_patch(
                proposed, allowed_categories=CATEGORIES
            )
            session.state = merge_patch(session.state, accepted)

            if rejected and counters is not None:
                for key in rejected:
                    if key in STATE_FIELDS and getattr(session.state, key, None) != getattr(
                        before_state, key, None
                    ):
                        counters.unauthorized_mutations += 1
                        counters.fail(
                            case["case_id"],
                            "unauthorized_mutation",
                            f"rejected key {key!r} changed the state",
                            turn_index,
                        )

            if session.state.revision != before_state.revision:
                # This mirrors api.py: observe the old result, then invalidate
                # the actual Session result-bearing state.
                result_before_invalidation = session.result is not None
                session.drop_result()
                invalidated = result_before_invalidation and session.result is None
                if counters is not None and invalidated:
                    counters.stale_result_invalidations += 1
                trace.append(
                    {
                        "turn": turn_index,
                        "event": "result_invalidation",
                        "revision_before": before_state.revision,
                        "revision_after": session.state.revision,
                        "result_present_before": result_before_invalidation,
                        "result_present_after": session.result is not None,
                        "invalidated": invalidated,
                    }
                )

            if requested == "confirm":
                session.state = confirm_state(session.state)

        has_trusted_result = _trusted_session_result(
            session,
            counters=counters,
            case_id=case["case_id"],
            turn=turn_index,
            reported_invalid_keys=reported_invalid_keys,
            bound_results=bound_results,
        )
        # Count each attempted stale access/use on this turn/action. Do not
        # deduplicate by payload identity: repeated exposures are distinct.
        if session.result is not None and session.result.get("revision") != session.state.revision:
            if counters is not None:
                counters.stale_result_reuses += 1
        action = decide_action(session.state, has_result=has_trusted_result)

        # Observe stale exposure before action dispatch; even a rejected
        # calculate/explain request is an attempted exposure event.
        if stale_result_exposed(session):
            stale_exposures += 1
            if counters is not None:
                counters.stale_result_exposures += 1
                counters.fail(
                    case["case_id"],
                    "stale_result_exposure",
                    "session exposed a result whose revision differs from state",
                    turn_index,
                )

        if requested == "calculate" and action != CALL_PRICING_TOOL:
            trace.append(
                {
                    "turn": turn_index,
                    "event": "tool_not_called",
                    "requested": requested,
                    "policy_action": action,
                }
            )
            continue

        if action == CALL_PRICING_TOOL:
            try:
                oracle = tool.compute(session.state)
            except PricingToolRefused:
                # The expected-call comparison in score() owns this count. Do
                # not count the same missed call once here and once there.
                trace.append(
                    {
                        "turn": turn_index,
                        "event": "tool_refused",
                        "requested": requested,
                    }
                )
                continue
            producing_state = session.state
            session.result = _session_result(oracle, producing_state.revision)
            bound_results[producing_state.revision] = canonical_result(oracle) or {}
            result_observations.append(
                _result_observation(
                    case_id=case["case_id"],
                    turn=turn_index,
                    state=producing_state,
                    oracle=oracle,
                    payload=session.result,
                    counters=counters,
                    reported_invalid_keys=reported_invalid_keys,
                )
            )
            _trusted_session_result(
                session,
                counters=counters,
                case_id=case["case_id"],
                turn=turn_index,
                reported_invalid_keys=reported_invalid_keys,
                bound_results=bound_results,
            )
            session.result_status = oracle.status
            session.state = ConsultationState(
                **{
                    **session.state.to_dict(),
                    "result_revision": session.state.revision,
                }
            )
            action = "EXPLAIN_RESULT"
            trace.append(
                {
                    "turn": turn_index,
                    "event": "tool_result",
                    "revision": session.state.revision,
                    "status": oracle.status,
                    "result_hash": result_hash(oracle),
                }
            )

    # Do not clear or rewrite Session.result before this observation. A broken
    # invalidation leaves the stale payload visible and is counted above.
    visible = _trusted_session_result(
        session,
        counters=counters,
        case_id=case["case_id"],
        turn=None,
        reported_invalid_keys=reported_invalid_keys,
        bound_results=bound_results,
    )
    result_payload = session.result if visible else None
    authoritative = (
        OracleResult(**result_payload["oracle"])
        if visible and result_payload is not None
        else None
    )
    result_status = session.result_status if authoritative is not None else None
    result_price = authoritative.recommended_price if authoritative is not None else None
    return Run(
        final_action=action,
        result_status=result_status,
        result_price=result_price,
        tool_calls=len(tool.calls),
        state=session.state,
        missing_fields=session.state.missing_fields(),
        authoritative_result=authoritative,
        result_payload=result_payload,
        result_observations=result_observations,
        trace=trace,
        stale_result_exposures=stale_exposures,
    )


def validate_authoritative_result(
    state: ConsultationState, actual: OracleResult
) -> list[tuple[str, str]]:
    """Validate safety shape and equality with a fresh complete oracle result."""
    errors: list[tuple[str, str]] = []
    expected = compute(state.to_pricing_input())
    actual_data = canonical_result(actual) or {}
    expected_data = canonical_result(expected) or {}

    for key in expected_data:
        if actual_data.get(key) != expected_data[key]:
            errors.append(
                (
                    "result_mismatch",
                    f"authoritative field {key!r}: got {actual_data.get(key)!r}, "
                    f"expected {expected_data[key]!r}",
                )
            )

    if actual.status not in VALID_RESULT_STATUSES:
        errors.append(("status_shape", f"unknown result status {actual.status!r}"))

    if actual.status == STATUS_RECOMMENDATION:
        if actual.discount_percent is None or not (
            DISCOUNT_MIN <= actual.discount_percent <= DISCOUNT_MAX
        ) or actual.discount_percent % DISCOUNT_STEP:
            errors.append(("discount", "discount is outside bounds or step"))
        if actual.recommended_price is None:
            errors.append(("price_consistency", "recommendation has no price"))
        else:
            if actual.recommended_price < state.cost + MIN_MARGIN_RP:
                errors.append(("margin", "recommended price is below cost plus margin"))
            if actual.recommended_price >= state.original_price:
                errors.append(("price_consistency", "recommendation is not a markdown"))
        if actual.expected_sell_through_units is None or not (
            0 <= actual.expected_sell_through_units <= state.stock
        ):
            errors.append(("projection", "sell-through projection exceeds stock or is missing"))
        if actual.expected_revenue is None or actual.expected_revenue < 0:
            errors.append(("projection", "revenue projection is invalid"))
        if actual.expected_loss_no_action is None or actual.expected_loss_no_action < 0:
            errors.append(("projection", "loss projection is invalid"))
    elif any(
        getattr(actual, key) is not None
        for key in (
            "discount_percent",
            "recommended_price",
            "timing",
            "expected_sell_through_units",
            "expected_revenue",
            "expected_loss_no_action",
            "confidence",
        )
    ):
        errors.append(("status_shape", "non-recommendation contains recommendation fields"))

    return errors


def score(case: dict[str, Any], counters: Counters) -> None:
    counters.cases += 1
    case_id = case["case_id"]
    run = replay(case, counters)
    expect = case["expect"]
    counters.tool_calls += run.tool_calls

    expected_calls = expect["tool_calls"]
    if run.tool_calls != expected_calls:
        # Each discrepancy is classified once: excess calls are premature or
        # duplicate; deficient calls are missed. Refusals are included here.
        if run.tool_calls > expected_calls:
            if expected_calls == 0:
                counters.premature_tool_calls += run.tool_calls
                counters.fail(case_id, "premature_tool_call", f"{run.tool_calls} call(s), expected 0")
            else:
                excess = run.tool_calls - expected_calls
                counters.duplicate_tool_calls += excess
                counters.fail(case_id, "duplicate_tool_call", f"{run.tool_calls} calls, expected {expected_calls}")
        else:
            missed = expected_calls - run.tool_calls
            counters.missed_tool_calls += missed
            counters.fail(case_id, "missed_tool_call", f"{run.tool_calls} calls, expected {expected_calls}")

    if run.final_action != expect["final_action"]:
        counters.final_action_mismatches += 1
        counters.fail(case_id, "final_action", f"got {run.final_action}, expected {expect['final_action']}")

    if "result_status" in expect and run.result_status != expect["result_status"]:
        counters.result_status_mismatches += 1
        counters.fail(case_id, "result_status", f"got {run.result_status}, expected {expect['result_status']}")

    if "missing_fields" in expect and sorted(run.missing_fields) != sorted(expect["missing_fields"]):
        counters.missing_field_mismatches += 1
        counters.fail(case_id, "missing_fields", f"got {run.missing_fields}, expected {expect['missing_fields']}")

    for key, value in expect.get("state", {}).items():
        actual = getattr(run.state, key)
        if actual != value:
            counters.state_mismatches += 1
            counters.fail(case_id, "state", f"{key} was {actual!r}, expected {value!r}")

    if run.authoritative_result is not None:
        # Each successful call was already validated at its producing revision.
        # Keep this final-result check for compatibility, but do not use it as
        # the denominator for per-call safety metrics.
        if not run.result_observations:
            counters.result_evaluations += 1
        errors = validate_authoritative_result(run.state, run.authoritative_result)
        if errors and not run.result_observations:
            counters.pricing_result_violations += 1
            kinds = set()
            for kind, detail in errors:
                kinds.add(kind)
                counters.fail(case_id, f"pricing_{kind}", detail)
            if "margin" in kinds:
                counters.margin_violations += 1
            if "discount" in kinds:
                counters.discount_violations += 1
            if "price_consistency" in kinds:
                counters.price_consistency_violations += 1
            if "status_shape" in kinds:
                counters.status_shape_violations += 1
            if "projection" in kinds:
                counters.projection_violations += 1

    again = replay(case)
    if canonical_result(again.authoritative_result) != canonical_result(run.authoritative_result):
        counters.nondeterministic_results += 1
        counters.fail(case_id, "nondeterminism", "complete authoritative result changed on replay")


def validate_suite(cases: object) -> list[str]:
    """Return all structural/semantic fixture errors before any replay."""
    errors: list[str] = []
    if not isinstance(cases, list) or not cases:
        return ["suite must contain at least one case"]

    case_ids: set[str] = set()
    for case_index, case in enumerate(cases, 1):
        prefix = f"case[{case_index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        unknown_case_keys = [key for key in case if key not in CASE_KEYS]
        if unknown_case_keys:
            errors.append(f"{prefix}: unknown fields {unknown_case_keys!r}")
        case_id = case.get("case_id")
        scenario_id = case.get("scenario_id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"{prefix}: case_id must be non-empty")
        elif case_id in case_ids:
            errors.append(f"{prefix}: duplicate case_id {case_id!r}")
        else:
            case_ids.add(case_id)
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            errors.append(f"{prefix}: scenario_id must be non-empty")
        tags = case.get("tags", [])
        if not isinstance(tags, list) or any(
            not isinstance(tag, str) or not tag.strip() for tag in tags
        ):
            errors.append(f"{prefix}: tags must be a list of non-empty strings")

        turns = case.get("turns")
        if not isinstance(turns, list) or not turns:
            errors.append(f"{prefix}: turns must be a non-empty list")
        else:
            for turn_index, turn in enumerate(turns, 1):
                turn_prefix = f"{prefix}.turn[{turn_index}]"
                if not isinstance(turn, dict):
                    errors.append(f"{turn_prefix}: must be an object")
                    continue
                unknown_turn_keys = [key for key in turn if key not in TURN_KEYS]
                if unknown_turn_keys:
                    errors.append(f"{turn_prefix}: unknown fields {unknown_turn_keys!r}")
                action = turn.get("action")
                if not isinstance(action, str) or action not in REQUEST_ACTIONS:
                    errors.append(f"{turn_prefix}: unsupported action {action!r}")
                if "patch" in turn:
                    patch = turn["patch"]
                    if not isinstance(patch, dict):
                        errors.append(f"{turn_prefix}: patch must be an object")
                    elif any(not isinstance(key, str) for key in patch):
                        errors.append(f"{turn_prefix}: patch keys must be strings")

        expect = case.get("expect")
        if not isinstance(expect, dict):
            errors.append(f"{prefix}: expect must be an object")
            continue
        unknown_expect_keys = [key for key in expect if key not in EXPECT_KEYS]
        if unknown_expect_keys:
            errors.append(f"{prefix}: unknown expectation fields {unknown_expect_keys!r}")
        if not isinstance(expect.get("tool_calls"), int) or isinstance(expect.get("tool_calls"), bool) or expect.get("tool_calls") < 0:
            errors.append(f"{prefix}: expect.tool_calls must be a non-negative integer")
        elif isinstance(turns, list) and expect["tool_calls"] > len(turns):
            errors.append(f"{prefix}: expect.tool_calls cannot exceed the number of turns")
        final_action = expect.get("final_action")
        if not isinstance(final_action, str) or final_action not in ACTIONS:
            errors.append(f"{prefix}: expect.final_action is not a valid workflow action")
        result_status = expect.get("result_status")
        if "result_status" in expect and result_status is not None:
            if not isinstance(result_status, str) or result_status not in VALID_RESULT_STATUSES:
                errors.append(f"{prefix}: expect.result_status is invalid")
            if expect.get("tool_calls") == 0:
                errors.append(
                    f"{prefix}: a non-null result_status requires an expected tool call"
                )
        if expect.get("final_action") == "EXPLAIN_RESULT" and expect.get("tool_calls") == 0:
            errors.append(
                f"{prefix}: EXPLAIN_RESULT requires an expected tool call"
            )
        if "missing_fields" in expect:
            missing = expect["missing_fields"]
            missing_is_valid = isinstance(missing, list)
            if missing_is_valid:
                missing_is_valid = all(
                    isinstance(field, str) and field in REQUIRED_FIELDS
                    for field in missing
                )
            if missing_is_valid:
                missing_is_valid = len(missing) == len(set(missing))
            if not missing_is_valid:
                errors.append(f"{prefix}: expect.missing_fields is invalid")
        if "state" in expect:
            state = expect["state"]
            if not isinstance(state, dict):
                errors.append(f"{prefix}: expect.state must be an object")
            else:
                unknown_state = [key for key in state if key not in STATE_FIELDS]
                if unknown_state:
                    errors.append(f"{prefix}: expect.state has unknown fields {unknown_state!r}")
                for key, value in state.items():
                    try:
                        json.dumps(value)
                    except (TypeError, ValueError):
                        errors.append(f"{prefix}: expect.state.{key} is not JSON-serializable")

    return errors


def load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise SuiteValidationError(f"cases file does not exist: {path}")
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise SuiteValidationError(f"line {line_number}: malformed JSON: {error.msg}") from error
        cases.append(value)
    errors = validate_suite(cases)
    if errors:
        raise SuiteValidationError("invalid evaluation suite:\n- " + "\n- ".join(errors))
    return cases


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _git_metadata() -> dict[str, Any]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
            ).stdout.rstrip("\r\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    status = run("status", "--porcelain", "--untracked-files=all")
    return {
        "commit": run("rev-parse", "HEAD"),
        "working_tree_dirty": status != "",
        "working_tree_status": status.splitlines() if status else [],
    }


def _source_metadata(cases_path: Path) -> dict[str, Any]:
    evaluator_path = Path(__file__).resolve()
    return {
        "evaluator_script": _repo_relative(evaluator_path),
        "evaluator_script_sha256": hashlib.sha256(evaluator_path.read_bytes()).hexdigest(),
        "cases_file": _repo_relative(cases_path),
        "cases_file_sha256": hashlib.sha256(cases_path.resolve().read_bytes()).hexdigest(),
        "suite_validation": "passed",
        **_git_metadata(),
    }


def _tool_metadata() -> dict[str, Any]:
    pricing_path = REPO / "backend/hargaturun/pricing.py"
    digest = hashlib.sha256(pricing_path.read_bytes()).hexdigest()
    return {
        "name": PricingTool.name,
        "implementation": _repo_relative(pricing_path),
        "implementation_sha256": digest,
        "result_schema": "OracleResult dataclass canonical fields",
    }


def _gate(status: str, *, count: int | None, denominator: int | None, reason: str | None = None) -> dict[str, Any]:
    measured = status in {"pass", "fail"}
    result = {
        "measurement": "measured" if measured else "not_measured",
        "status": status,
        "count": count,
        "denominator": denominator,
    }
    if reason:
        result["reason"] = reason
    return result


def evaluate(cases: list[dict[str, Any]]) -> Counters:
    counters = Counters()
    for case in cases:
        score(case, counters)
    return counters


def build_report(cases: list[dict[str, Any]], counters: Counters, cases_path: Path) -> dict[str, Any]:
    deterministic_gates = {
        "zero_premature_tool_calls": _gate("pass" if counters.premature_tool_calls == 0 else "fail", count=counters.premature_tool_calls, denominator=counters.turns),
        "zero_duplicate_tool_calls": _gate("pass" if counters.duplicate_tool_calls == 0 else "fail", count=counters.duplicate_tool_calls, denominator=counters.cases),
        "zero_missed_tool_calls": _gate("pass" if counters.missed_tool_calls == 0 else "fail", count=counters.missed_tool_calls, denominator=counters.cases),
        "zero_unauthorized_mutations": _gate("pass" if counters.unauthorized_mutations == 0 else "fail", count=counters.unauthorized_mutations, denominator=counters.turns),
        "zero_stale_result_exposures": _gate("pass" if counters.stale_result_exposures == 0 else "fail", count=counters.stale_result_exposures, denominator=counters.turns),
        "zero_stale_result_reuses": _gate("pass" if counters.stale_result_reuses == 0 else "fail", count=counters.stale_result_reuses, denominator=counters.turns),
        "zero_result_hash_violations": _gate("pass" if counters.result_hash_violations == 0 else "fail", count=counters.result_hash_violations, denominator=counters.result_evaluations),
        "zero_pricing_result_safety_violations": _gate("pass" if counters.pricing_result_violations == 0 else "fail", count=counters.pricing_result_violations, denominator=counters.result_evaluations),
        "zero_final_action_mismatches": _gate("pass" if counters.final_action_mismatches == 0 else "fail", count=counters.final_action_mismatches, denominator=counters.cases),
        "zero_result_status_mismatches": _gate("pass" if counters.result_status_mismatches == 0 else "fail", count=counters.result_status_mismatches, denominator=counters.cases),
        "zero_state_mismatches": _gate("pass" if counters.state_mismatches == 0 else "fail", count=counters.state_mismatches, denominator=counters.cases),
        "zero_missing_field_mismatches": _gate("pass" if counters.missing_field_mismatches == 0 else "fail", count=counters.missing_field_mismatches, denominator=counters.cases),
            "reproducible_complete_results": _gate("pass" if counters.nondeterministic_results == 0 else "fail", count=counters.nondeterministic_results, denominator=counters.result_evaluations),
    }
    subset_passed = all(gate["status"] == "pass" for gate in deterministic_gates.values())

    readiness_gates = {
        "zero_premature_pricing_tool_calls": _gate("pass" if counters.premature_tool_calls == 0 else "fail", count=counters.premature_tool_calls, denominator=counters.turns),
        "zero_deterministic_engine_safety_violations": _gate("pass" if counters.pricing_result_violations == 0 else "fail", count=counters.pricing_result_violations, denominator=counters.result_evaluations),
        "corrections_cannot_reuse_stale_result": _gate("pass" if counters.stale_result_reuses == 0 else "fail", count=counters.stale_result_reuses, denominator=counters.turns),
        "zero_result_hash_violations": _gate("pass" if counters.result_hash_violations == 0 else "fail", count=counters.result_hash_violations, denominator=counters.result_evaluations),
        "zero_unsupported_numerical_claims_after_validation": _gate("not_measured", count=None, denominator=None, reason="requires real-model writer outputs and validator/fallback traces"),
        "material_improvement_over_direct_chat": _gate("not_measured", count=None, denominator=None, reason="direct-chat baseline report is not implemented"),
        "every_result_reproducible_from_recorded_state_and_tool_version": _gate("pass" if counters.nondeterministic_results == 0 else "fail", count=counters.nondeterministic_results, denominator=counters.result_evaluations),
    }
    ready_for_submission = all(gate["status"] == "pass" for gate in readiness_gates.values())

    violations = []
    for violation in counters.violations:
        item = {"case_id": violation.case_id, "kind": violation.kind, "detail": violation.detail}
        if violation.turn is not None:
            item["turn"] = violation.turn
        violations.append(item)

    return {
        "system": "System B — deterministic workflow contract subset (not full §8.4 readiness)",
        "evaluation_scope": "scripted orchestration/oracle contract only; no real-model quality claim",
        "readiness_status": "ready_for_submission" if ready_for_submission else "not_ready",
        "ready_for_submission": ready_for_submission,
        "deterministic_subset_passed": subset_passed,
        "source": _source_metadata(cases_path),
        "tool": _tool_metadata(),
        "scenarios": sorted({case["scenario_id"] for case in cases}),
        "denominators": {
            "cases": counters.cases,
            "turns": counters.turns,
            "result_evaluations": counters.result_evaluations,
        },
        "counts": {
            "tool_calls": counters.tool_calls,
            "premature_tool_calls": counters.premature_tool_calls,
            "duplicate_tool_calls": counters.duplicate_tool_calls,
            "missed_tool_calls": counters.missed_tool_calls,
            "unauthorized_field_mutations": counters.unauthorized_mutations,
            "stale_result_exposures": counters.stale_result_exposures,
            "stale_result_reuses": counters.stale_result_reuses,
            "stale_result_invalidations_observed": counters.stale_result_invalidations,
            "result_hash_violations": counters.result_hash_violations,
            "pricing_result_violations": counters.pricing_result_violations,
            "margin_violations": counters.margin_violations,
            "discount_violations": counters.discount_violations,
            "price_consistency_violations": counters.price_consistency_violations,
            "status_shape_violations": counters.status_shape_violations,
            "projection_violations": counters.projection_violations,
            "nondeterministic_complete_results": counters.nondeterministic_results,
            "final_action_mismatches": counters.final_action_mismatches,
            "result_status_mismatches": counters.result_status_mismatches,
            "state_mismatches": counters.state_mismatches,
            "missing_field_mismatches": counters.missing_field_mismatches,
        },
        "deterministic_subset_gates": deterministic_gates,
        "readiness_gates_8_4": readiness_gates,
        "not_measured": {
            "reason": "The PR deliberately does not fabricate real-model or baseline evidence.",
            "metrics": [
                "extraction: valid schema, per-field accuracy, complete-state exact match",
                "corrections: corrected-field accuracy from natural language",
                "writing: unsupported numbers, status faithfulness, clarity rubric",
                "scope: out-of-domain redirect accuracy from natural language",
                "runtime: P50/P95 latency, failures, peak memory",
                "task completion and turns to confirmation on held-out natural language",
                "Baseline A — direct chat comparison (§8.1)",
            ],
        },
        "raw_failures": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(REPO / "data/eval/consultations.jsonl"))
    parser.add_argument("--out", default=str(REPO / "reports/agentic-workflow-safety.json"))
    args = parser.parse_args()
    cases_path = Path(args.cases)
    try:
        cases = load_cases(cases_path)
    except (OSError, UnicodeError, SuiteValidationError) as error:
        print(f"evaluation suite rejected: {error}", file=sys.stderr)
        return 2

    counters = evaluate(cases)
    report = build_report(cases, counters, cases_path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"cases: {counters.cases}  turns: {counters.turns}  tool calls: {counters.tool_calls}")
    print(f"deterministic subset: {'PASS' if report['deterministic_subset_passed'] else 'FAIL'}")
    print("full §8.4 submission readiness: NOT READY (real-model/baseline criteria are not measured)")
    for name, gate in report["readiness_gates_8_4"].items():
        print(f"  {gate['status'].upper():12} {name}")
    if counters.violations:
        print(f"\n{len(counters.violations)} raw failure(s):")
        for violation in counters.violations:
            suffix = f" turn={violation.turn}" if violation.turn is not None else ""
            print(f"  [{violation.kind}] {violation.case_id}{suffix}: {violation.detail}")
    print(f"\nreport: {_repo_relative(out)}")
    # The deterministic subset is independently useful; unmeasured full
    # readiness is represented in the report, not as a harness failure.
    return 0 if report["deterministic_subset_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
