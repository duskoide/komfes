#!/usr/bin/env python3
"""Measure the deterministic half of the agentic-workflow evaluation.

Four of the six readiness conditions in Agentic Workflow Plan §8.4 do not
involve the language model at all: zero premature pricing-tool calls, zero
recommendations violating engine rules, no stale-result reuse, and
reproducibility from recorded state. Those are properties of the reducer,
the action policy and the tool, so they can be measured exactly, today,
without a GPU.

What this script does **not** measure is the language half — extraction
accuracy, correction accuracy, prose quality and latency — because that
needs the real model. Those metrics are reported as ``not_measured`` rather
than estimated, and the direct-chat baseline of §8.1 is likewise absent.
Reporting either from a stub would be fabrication.

Each case replays scripted extractor output. That is deliberate: it isolates
the orchestration boundary from model variance, and it is the only way to
test the contract-failure cases the plan asks for.

Usage:
    python scripts/eval_agentic_workflow.py [--cases PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from hargaturun.consultation import (  # noqa: E402
    CALL_PRICING_TOOL,
    ConsultationState,
    PricingTool,
    PricingToolRefused,
    confirm as confirm_state,
    decide_action,
    merge_patch,
    validate_patch,
)
from hargaturun.pricing import (  # noqa: E402
    CATEGORIES,
    MIN_MARGIN_RP,
    STATUS_RECOMMENDATION,
)


@dataclass
class Violation:
    case_id: str
    kind: str
    detail: str


@dataclass
class Counters:
    """Every metric is a count over an explicit denominator, per §8.3."""

    cases: int = 0
    turns: int = 0
    tool_calls: int = 0
    premature_tool_calls: int = 0
    duplicate_tool_calls: int = 0
    missed_tool_calls: int = 0
    unauthorized_mutations: int = 0
    stale_result_exposures: int = 0
    margin_violations: int = 0
    nondeterministic_results: int = 0
    final_action_mismatches: int = 0
    result_status_mismatches: int = 0
    state_mismatches: int = 0
    missing_field_mismatches: int = 0
    violations: list[Violation] = field(default_factory=list)

    def fail(self, case_id: str, kind: str, detail: str) -> None:
        self.violations.append(Violation(case_id, kind, detail))


@dataclass
class Run:
    """Outcome of replaying one case."""

    final_action: str
    result_status: str | None
    result_price: int | None
    tool_calls: int
    state: ConsultationState
    missing_fields: list[str]


def replay(case: dict, counters: Counters | None = None) -> Run:
    """Replay one case through the real reducer, policy and tool."""
    state = ConsultationState()
    tool = PricingTool()
    result_status: str | None = None
    result_price: int | None = None
    result_revision: int | None = None
    action = decide_action(state, has_result=False)

    for turn in case["turns"]:
        requested = turn["action"]
        if counters is not None:
            counters.turns += 1

        if requested in {"message", "confirm"}:
            proposed = turn.get("patch", {})
            accepted, rejected = validate_patch(
                proposed, allowed_categories=CATEGORIES
            )
            before = state
            state = merge_patch(state, accepted)

            if counters is not None and rejected:
                # A rejected key must not have moved the state at all.
                for key in rejected:
                    if getattr(state, key, None) != getattr(before, key, None):
                        counters.unauthorized_mutations += 1
                        counters.fail(
                            case["case_id"],
                            "unauthorized_mutation",
                            f"rejected key {key!r} changed the state",
                        )

            if state.revision != before.revision:
                result_status = None
                result_price = None
                result_revision = None

            if requested == "confirm":
                state = confirm_state(state)

        action = decide_action(state, has_result=result_status is not None)

        if requested == "calculate" and action != CALL_PRICING_TOOL:
            # Refusing here is correct; calling would be premature.
            continue

        if action == CALL_PRICING_TOOL:
            try:
                oracle = tool.compute(state)
            except PricingToolRefused:
                if counters is not None:
                    counters.missed_tool_calls += 1
                    counters.fail(
                        case["case_id"],
                        "missed_tool_call",
                        "policy said CALL_PRICING_TOOL but the tool refused",
                    )
                continue
            result_status = oracle.status
            result_price = oracle.recommended_price
            state = ConsultationState(
                **{**state.to_dict(), "result_revision": state.revision}
            )
            result_revision = state.revision
            action = "EXPLAIN_RESULT"

    exposed = result_status is not None and result_revision == state.revision
    return Run(
        final_action=action,
        result_status=result_status if exposed else None,
        result_price=result_price if exposed else None,
        tool_calls=len(tool.calls),
        state=state,
        missing_fields=state.missing_fields(),
    )


def score(case: dict, counters: Counters) -> None:
    counters.cases += 1
    case_id = case["case_id"]
    run = replay(case, counters)
    expect = case.get("expect", {})

    counters.tool_calls += run.tool_calls

    # Tool policy: a call is only legitimate on a confirmed, complete revision.
    expected_calls = expect.get("tool_calls")
    if expected_calls is not None and run.tool_calls != expected_calls:
        if run.tool_calls > expected_calls:
            if expected_calls == 0:
                counters.premature_tool_calls += run.tool_calls
                counters.fail(case_id, "premature_tool_call",
                              f"{run.tool_calls} call(s) on an unconfirmed state")
            else:
                counters.duplicate_tool_calls += run.tool_calls - expected_calls
                counters.fail(case_id, "duplicate_tool_call",
                              f"{run.tool_calls} calls, expected {expected_calls}")
        else:
            counters.missed_tool_calls += expected_calls - run.tool_calls
            counters.fail(case_id, "missed_tool_call",
                          f"{run.tool_calls} calls, expected {expected_calls}")

    if "final_action" in expect and run.final_action != expect["final_action"]:
        counters.final_action_mismatches += 1
        counters.fail(case_id, "final_action",
                      f"got {run.final_action}, expected {expect['final_action']}")

    if "result_status" in expect and run.result_status != expect["result_status"]:
        counters.result_status_mismatches += 1
        counters.fail(case_id, "result_status",
                      f"got {run.result_status}, expected {expect['result_status']}")

    if "missing_fields" in expect:
        if sorted(run.missing_fields) != sorted(expect["missing_fields"]):
            counters.missing_field_mismatches += 1
            counters.fail(case_id, "missing_fields",
                          f"got {run.missing_fields}, expected {expect['missing_fields']}")

    for key, value in expect.get("state", {}).items():
        actual = getattr(run.state, key, None)
        if actual != value:
            counters.state_mismatches += 1
            counters.fail(case_id, "state",
                          f"{key} was {actual!r}, expected {value!r}")

    # A result that outlived its revision must never be visible.
    if run.result_status is not None and run.state.result_revision != run.state.revision:
        counters.stale_result_exposures += 1
        counters.fail(case_id, "stale_result", "result survived a revision change")

    # The engine's margin floor is not negotiable.
    if run.result_status == STATUS_RECOMMENDATION and run.result_price is not None:
        cost = run.state.cost or 0
        if run.result_price < cost + MIN_MARGIN_RP:
            counters.margin_violations += 1
            counters.fail(case_id, "margin_violation",
                          f"price {run.result_price} below cost {cost} + {MIN_MARGIN_RP}")

    # Same recorded input must reproduce the same numbers.
    again = replay(case)
    if (again.result_status, again.result_price) != (run.result_status, run.result_price):
        counters.nondeterministic_results += 1
        counters.fail(case_id, "nondeterminism", "replay produced different numbers")


def _repo_relative(path: Path) -> str:
    """Repo-relative when possible; an absolute path otherwise, so a case file
    outside the tree is still recorded rather than crashing the run."""
    try:
        return str(path.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def commit_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(REPO / "data/eval/consultations.jsonl"))
    parser.add_argument("--out", default=str(REPO / "reports/agentic-workflow-safety.json"))
    args = parser.parse_args()

    cases = [
        json.loads(line)
        for line in Path(args.cases).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    counters = Counters()
    for case in cases:
        score(case, counters)

    gates = {
        "zero_premature_tool_calls": counters.premature_tool_calls == 0,
        "zero_duplicate_tool_calls": counters.duplicate_tool_calls == 0,
        "zero_unauthorized_mutations": counters.unauthorized_mutations == 0,
        "zero_stale_result_reuse": counters.stale_result_exposures == 0,
        "zero_margin_violations": counters.margin_violations == 0,
        "reproducible_numbers": counters.nondeterministic_results == 0,
    }

    report = {
        "system": "System B — customized workflow (deterministic half only)",
        "commit": commit_sha(),
        "cases_file": _repo_relative(Path(args.cases)),
        "scenarios": sorted({c["scenario_id"] for c in cases}),
        "denominators": {"cases": counters.cases, "turns": counters.turns},
        "counts": {
            "tool_calls": counters.tool_calls,
            "premature_tool_calls": counters.premature_tool_calls,
            "duplicate_tool_calls": counters.duplicate_tool_calls,
            "missed_tool_calls": counters.missed_tool_calls,
            "unauthorized_field_mutations": counters.unauthorized_mutations,
            "stale_result_exposures": counters.stale_result_exposures,
            "margin_violations": counters.margin_violations,
            "nondeterministic_results": counters.nondeterministic_results,
            "final_action_mismatches": counters.final_action_mismatches,
            "result_status_mismatches": counters.result_status_mismatches,
            "state_mismatches": counters.state_mismatches,
            "missing_field_mismatches": counters.missing_field_mismatches,
        },
        "readiness_gates_8_4": gates,
        "not_measured": {
            "reason": "requires the real local model; a stub would fabricate results",
            "metrics": [
                "extraction: valid schema, per-field accuracy, complete-state exact match",
                "corrections: corrected-field accuracy from natural language",
                "writing: unsupported numbers, status faithfulness, clarity rubric",
                "scope: out-of-domain redirect accuracy",
                "runtime: P50/P95 latency, peak memory",
                "Baseline A — direct chat comparison (§8.1)",
            ],
        },
        "raw_failures": [
            {"case_id": v.case_id, "kind": v.kind, "detail": v.detail}
            for v in counters.violations
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"cases: {counters.cases}  turns: {counters.turns}  tool calls: {counters.tool_calls}")
    for name, passed in gates.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    if counters.violations:
        print(f"\n{len(counters.violations)} raw failure(s):")
        for v in counters.violations:
            print(f"  [{v.kind}] {v.case_id}: {v.detail}")
    print(f"\nreport: {_repo_relative(out)}")
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
