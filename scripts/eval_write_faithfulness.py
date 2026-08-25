#!/usr/bin/env python3
"""Gate 1 — measure write-path numerical faithfulness against the real model.

This is the real-model complement to ``eval_agentic_workflow.py`` (which only
measures the deterministic orchestration/oracle subset). It drives the *writer*
task end to end: for every held-out case that produces an authoritative pricing
result, it asks the local model to write the ``explanation`` + ``promo_copy``,
then runs the frozen ``validate_write_output`` contract over the real output and
records how many numeric claims were not grounded in the confirmed input or the
engine result — before and after the single bounded repair attempt.

The Agentic Workflow Plan §8.4 gate this feeds is
``zero_unsupported_numerical_claims_after_validation``.

Honesty rules (identical in spirit to the safety harness):

* it reuses the *frozen* production contracts — ``WRITE_SYSTEM_PROMPT``,
  ``to_engine_result``, ``allowed_numbers_for``, ``validate_write_output`` — so
  what is measured is exactly what production enforces;
* if the model server is unreachable it reports ``not_measured`` with a reason
  and never fabricates a pass;
* it records model identity, prompt version, decoding parameters, and the git
  commit so a run can be reproduced and audited;
* an accepted output that still contains an unsupported number is surfaced as a
  raw failure rather than hidden.

Usage:
    python scripts/eval_write_faithfulness.py --url http://127.0.0.1:8080/v1
    python scripts/eval_write_faithfulness.py --require-model   # CI/strict
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
# Reuse the safety harness's validated suite loader and deterministic replay so
# the writable-case set is derived the same way production would see it.
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "backend"))

from eval_agentic_workflow import (  # noqa: E402
    SuiteValidationError,
    load_cases,
    replay,
)
from hargaturun.consultation import ITEM_FIELDS  # noqa: E402
from hargaturun.model_client import (  # noqa: E402
    ModelContractError,
    ModelUnavailable,
    OpenAICompatibleModel,
)
from hargaturun.schemas import (  # noqa: E402
    WRITE_PROMPT_VERSION,
    WRITE_SYSTEM_PROMPT,
    allowed_numbers_for,
    to_engine_result,
    validate_write_output,
)

# Outcome classification for one writer measurement.
VALID_FIRST_TRY = "valid_first_try"
VALID_AFTER_REPAIR = "valid_after_repair"
REJECTED_AFTER_REPAIR = "rejected_after_repair"  # fail-closed -> numbers-only
MALFORMED_JSON = "malformed_json"

UNSUPPORTED_PREFIX = "unsupported number in prose:"


def _payload(normalized_input: dict, engine_result: dict) -> str:
    """Mirror ``OpenAICompatibleModel.write`` request body exactly."""
    return json.dumps(
        {"normalized_input": normalized_input, "engine_result": engine_result},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _repair_payload(
    normalized_input: dict, engine_result: dict, invalid_output: object, errors: list[str]
) -> str:
    """Mirror ``OpenAICompatibleModel.write`` single repair body exactly."""
    return json.dumps(
        {
            "authoritative_input": {
                "normalized_input": normalized_input,
                "engine_result": engine_result,
            },
            "invalid_output": invalid_output,
            "contract_violations": errors,
            "instruction": (
                "Perbaiki JSON agar semua pelanggaran kontrak hilang. "
                "Jangan menambah atau mengubah angka. Keluarkan JSON saja."
            ),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _count_unsupported(errors: list[str]) -> int:
    return sum(1 for error in errors if error.startswith(UNSUPPORTED_PREFIX))


def _normalized_input(state: Any, oracle: Any) -> dict:
    """Confirmed item fields with the shelf life the oracle actually used,
    matching ``api.py`` before it calls ``model.write``."""
    normalized = {field: getattr(state, field) for field in ITEM_FIELDS}
    if oracle.used_shelf_life is not None:
        normalized["total_shelf_life"] = oracle.used_shelf_life
    return normalized


def measure_case(
    model: OpenAICompatibleModel, normalized_input: dict, engine_result: dict
) -> dict[str, Any]:
    """Instrumented write: initial output + one bounded repair, using the frozen
    validator. Returns per-case observations. Raises :class:`ModelUnavailable`
    so the caller can abort into ``not_measured`` instead of a partial pass."""
    status = engine_result.get("status")
    allowed = allowed_numbers_for(normalized_input, engine_result)

    try:
        first = model._complete(WRITE_SYSTEM_PROMPT, _payload(normalized_input, engine_result))
    except ModelContractError as error:
        return {
            "outcome": MALFORMED_JSON,
            "stage": "initial",
            "detail": str(error),
            "unsupported_initial": None,
            "unsupported_after_validation": 0,
            "repaired": False,
        }

    errors_first = validate_write_output(first, allowed, status)
    unsupported_first = _count_unsupported(errors_first)
    if not errors_first:
        return {
            "outcome": VALID_FIRST_TRY,
            "errors_initial": [],
            "unsupported_initial": 0,
            "unsupported_after_validation": 0,
            "repaired": False,
            "accepted_output": first,
        }

    # One bounded repair attempt, exactly like production.
    try:
        second = model._complete(
            WRITE_SYSTEM_PROMPT,
            _repair_payload(normalized_input, engine_result, first, errors_first),
        )
    except ModelContractError as error:
        return {
            "outcome": MALFORMED_JSON,
            "stage": "repair",
            "detail": str(error),
            "errors_initial": errors_first,
            "unsupported_initial": unsupported_first,
            "unsupported_after_validation": 0,
            "repaired": True,
        }

    errors_second = validate_write_output(second, allowed, status)
    if not errors_second:
        return {
            "outcome": VALID_AFTER_REPAIR,
            "errors_initial": errors_first,
            "unsupported_initial": unsupported_first,
            "unsupported_after_validation": 0,
            "repaired": True,
            "accepted_output": second,
        }

    # Still invalid after repair: production discards this and degrades to a
    # numbers-only result, so no unsupported number ever reaches the user.
    return {
        "outcome": REJECTED_AFTER_REPAIR,
        "errors_initial": errors_first,
        "errors_final": errors_second,
        "unsupported_initial": unsupported_first,
        "unsupported_final_discarded": _count_unsupported(errors_second),
        "unsupported_after_validation": 0,
        "repaired": True,
    }


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
    }


def _repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def build_report(
    *,
    cases_path: Path,
    model: OpenAICompatibleModel,
    measured: bool,
    reason: str | None,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    script_path = Path(__file__).resolve()
    source = {
        "evaluator_script": _repo_relative(script_path),
        "evaluator_script_sha256": hashlib.sha256(script_path.read_bytes()).hexdigest(),
        "cases_file": _repo_relative(cases_path),
        "cases_file_sha256": hashlib.sha256(cases_path.resolve().read_bytes()).hexdigest(),
        **_git_metadata(),
    }
    model_meta = {
        "base_url": model.base_url,
        "served_model_name": model.model,
        "identity_note": "whatever the server serves; no fine-tuned artifact is claimed",
        "write_prompt_version": WRITE_PROMPT_VERSION,
        "temperature": 0,
        "top_p": 1,
        "seed": 42,
        "max_output_tokens": model.max_output_tokens,
    }

    if not measured:
        return {
            "system": "Gate 1 — write-path numerical faithfulness (real model)",
            "plan_gate": "zero_unsupported_numerical_claims_after_validation (§8.4)",
            "measurement": "not_measured",
            "reason": reason,
            "source": source,
            "model": model_meta,
            "gate": {
                "zero_unsupported_numerical_claims_after_validation": {
                    "measurement": "not_measured",
                    "status": "not_measured",
                    "reason": reason,
                }
            },
        }

    by_outcome: dict[str, int] = {
        VALID_FIRST_TRY: 0,
        VALID_AFTER_REPAIR: 0,
        REJECTED_AFTER_REPAIR: 0,
        MALFORMED_JSON: 0,
    }
    unsupported_initial_total = 0
    unsupported_after_validation_total = 0
    raw_failures: list[dict[str, Any]] = []

    for obs in observations:
        by_outcome[obs["outcome"]] = by_outcome.get(obs["outcome"], 0) + 1
        if isinstance(obs.get("unsupported_initial"), int):
            unsupported_initial_total += obs["unsupported_initial"]
        unsupported_after_validation_total += obs.get("unsupported_after_validation", 0)
        # An accepted output must never contain an unsupported number. If it
        # does, that is a real contract/harness defect, not a pass.
        if obs["outcome"] in (VALID_FIRST_TRY, VALID_AFTER_REPAIR) and obs.get(
            "unsupported_after_validation", 0
        ):
            raw_failures.append(
                {
                    "case_id": obs["case_id"],
                    "kind": "unsupported_number_after_validation",
                    "detail": obs.get("accepted_output"),
                }
            )
        if obs["outcome"] == MALFORMED_JSON:
            raw_failures.append(
                {
                    "case_id": obs["case_id"],
                    "kind": "malformed_json",
                    "stage": obs.get("stage"),
                    "detail": obs.get("detail"),
                }
            )

    denominator = len(observations)
    accepted = by_outcome[VALID_FIRST_TRY] + by_outcome[VALID_AFTER_REPAIR]
    gate_status = (
        "pass"
        if unsupported_after_validation_total == 0 and denominator > 0
        else "fail"
    )

    return {
        "system": "Gate 1 — write-path numerical faithfulness (real model)",
        "plan_gate": "zero_unsupported_numerical_claims_after_validation (§8.4)",
        "measurement": "measured",
        "source": source,
        "model": model_meta,
        "denominators": {
            "writable_cases": denominator,
            "accepted_outputs": accepted,
        },
        "counts": {
            "valid_first_try": by_outcome[VALID_FIRST_TRY],
            "valid_after_repair": by_outcome[VALID_AFTER_REPAIR],
            "rejected_after_repair_numbers_only": by_outcome[REJECTED_AFTER_REPAIR],
            "malformed_json": by_outcome[MALFORMED_JSON],
            "unsupported_number_claims_before_validation": unsupported_initial_total,
            "unsupported_number_claims_after_validation": unsupported_after_validation_total,
        },
        "gate": {
            "zero_unsupported_numerical_claims_after_validation": {
                "measurement": "measured",
                "status": gate_status,
                "count": unsupported_after_validation_total,
                "denominator": accepted,
            }
        },
        "per_case": [
            {
                "case_id": obs["case_id"],
                "scenario_id": obs["scenario_id"],
                "engine_status": obs["engine_status"],
                "outcome": obs["outcome"],
                "unsupported_initial": obs.get("unsupported_initial"),
            }
            for obs in observations
        ],
        "raw_failures": raw_failures,
    }


def run(cases: list[dict[str, Any]], model: OpenAICompatibleModel) -> tuple[bool, str | None, list[dict[str, Any]]]:
    """Return ``(measured, reason, observations)``. Aborts to not_measured on
    the first model-unavailable error rather than reporting a partial pass."""
    observations: list[dict[str, Any]] = []
    for case in cases:
        outcome = replay(case)
        if outcome.authoritative_result is None:
            continue  # no current result to write about (ASK/blocked/invalidated)
        oracle = outcome.authoritative_result
        normalized_input = _normalized_input(outcome.state, oracle)
        engine_result = to_engine_result(oracle)
        try:
            obs = measure_case(model, normalized_input, engine_result)
        except ModelUnavailable:
            return False, f"model server unavailable at {model.base_url}", []
        obs["case_id"] = case["case_id"]
        obs["scenario_id"] = case["scenario_id"]
        obs["engine_status"] = engine_result.get("status")
        observations.append(obs)
    if not observations:
        return False, "no held-out case produced an authoritative result to write about", []
    return True, None, observations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(REPO / "data/eval/consultations.jsonl"))
    parser.add_argument("--out", default=str(REPO / "reports/write-faithfulness.json"))
    parser.add_argument("--url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="hargaturun-qwen3.5-4b")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-output-tokens", type=int, default=350)
    parser.add_argument(
        "--require-model",
        action="store_true",
        help="Exit non-zero if the model is unavailable (CI/strict).",
    )
    args = parser.parse_args()

    cases_path = Path(args.cases)
    try:
        cases = load_cases(cases_path)
    except (OSError, UnicodeError, SuiteValidationError) as error:
        print(f"evaluation suite rejected: {error}", file=sys.stderr)
        return 2

    model = OpenAICompatibleModel(
        base_url=args.url,
        model=args.model,
        timeout=args.timeout,
        max_output_tokens=args.max_output_tokens,
    )
    measured, reason, observations = run(cases, model)
    report = build_report(
        cases_path=cases_path,
        model=model,
        measured=measured,
        reason=reason,
        observations=observations,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not measured:
        print(f"write faithfulness: NOT MEASURED ({reason})")
        print(f"report: {_repo_relative(out)}")
        return 1 if args.require_model else 0

    gate = report["gate"]["zero_unsupported_numerical_claims_after_validation"]
    counts = report["counts"]
    print(
        f"write faithfulness: {gate['status'].upper()} "
        f"({counts['unsupported_number_claims_after_validation']} unsupported after validation "
        f"across {report['denominators']['accepted_outputs']} accepted outputs)"
    )
    print(
        f"  first-try valid={counts['valid_first_try']} "
        f"repaired={counts['valid_after_repair']} "
        f"rejected(numbers-only)={counts['rejected_after_repair_numbers_only']} "
        f"malformed={counts['malformed_json']}"
    )
    print(
        f"  raw model hallucinated numbers before validation: "
        f"{counts['unsupported_number_claims_before_validation']}"
    )
    print(f"report: {_repo_relative(out)}")
    return 0 if gate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
