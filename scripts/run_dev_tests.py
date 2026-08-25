#!/usr/bin/env python3
"""Unified Developer Test Suite Runner for HargaTurun (Issue #4).

Orchestrates a tiered developer test experience:
  - Tier 1 (Default): Fast deterministic backend unit/contract tests and safety evaluation replay (< 3s).
  - Tier 2: Backend unit checks + Frontend Flutter unit/widget tests.
  - Tier 3: Live in-process / loopback wire integration tests (FastAPI + dev stub).
  - Tier 4: Explicit opt-in live local-model server smoke test and Compose configuration checks.

Usage:
    python scripts/run_dev_tests.py                   # Run default Tier 1 checks
    python scripts/run_dev_tests.py --tier 2          # Run Tier 2 (Backend + Frontend)
    python scripts/run_dev_tests.py --tier 3          # Run Tier 3 (Integration)
    python scripts/run_dev_tests.py --real-model      # Opt in to live local-model smoke test
    python scripts/run_dev_tests.py --compose         # Opt in to Compose config smoke test
    python scripts/run_dev_tests.py --tier all        # Run all available tiers
    python scripts/run_dev_tests.py --strict          # Fail if optional prerequisites are missing

Exit codes:
    0: All requested tests passed (or cleanly skipped optional tiers in non-strict mode).
    1: One or more test assertions failed.
    2: Prerequisite missing in --strict mode or invalid configuration.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

# Avoid bytecode generation noise
sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"

# Single source of truth for the local model endpoint, shared by every tier-4
# suite so the smoke test and the faithfulness gate never disagree about where
# the server lives.
DEFAULT_MODEL_URL = "http://127.0.0.1:8080/v1"


def _pytest_summary_counts(output: str) -> dict[str, int]:
    """Parse pytest's terminal summary into {passed, failed, skipped, ...}.

    Substring checks like ``"skipped" in output`` are unsafe because pytest's
    summary reports a *count* of skipped tests (opt-in suites skip by design),
    so the word is present even on a run that failed. We read the actual
    numbers instead.
    """
    counts: dict[str, int] = {}
    for count, label in re.findall(
        r"(\d+)\s+(passed|failed|skipped|error|errors|deselected|xfailed|xpassed)",
        output,
    ):
        key = "error" if label == "errors" else label
        counts[key] = counts.get(key, 0) + int(count)
    return counts


class StepResult(NamedTuple):
    name: str
    tier: str
    status: str  # "PASS", "FAIL", "SKIP"
    duration_s: float
    message: str = ""


# ANSI Color helpers
USE_COLOR = sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def _c(text: str, color_code: str) -> str:
    return f"\033[{color_code}m{text}\033[0m" if USE_COLOR else text


def green(text: str) -> str:
    return _c(text, "32;1")


def red(text: str) -> str:
    return _c(text, "31;1")


def yellow(text: str) -> str:
    return _c(text, "33;1")


def cyan(text: str) -> str:
    return _c(text, "36;1")


def bold(text: str) -> str:
    return _c(text, "1")


def run_backend_unit(verbose: bool = False) -> StepResult:
    start = time.time()
    pytest_bin = shutil.which("pytest")
    cmd: list[str]
    if shutil.which("uv"):
        cmd = ["uv", "run", "--extra", "dev", "python", "-m", "pytest", "-q", "-m", "not (integration or real_model or compose)"]
    elif pytest_bin:
        cmd = [pytest_bin, "-q", "-m", "not (integration or real_model or compose)"]
    else:
        cmd = [sys.executable, "-m", "unittest", "discover", "tests"]

    if verbose:
        cmd = [arg for arg in cmd if arg != "-q"] + ["-v"]

    env = {**os.environ, "PYTHONPATH": str(BACKEND_DIR), "PYTHONDONTWRITEBYTECODE": "1"}
    res = subprocess.run(cmd, cwd=str(BACKEND_DIR), capture_output=not verbose, text=True, env=env)
    dur = time.time() - start

    if res.returncode == 0:
        return StepResult("Backend Unit & Contracts", "Tier 1", "PASS", dur)
    msg = "" if verbose else (res.stderr or res.stdout).strip()
    return StepResult("Backend Unit & Contracts", "Tier 1", "FAIL", dur, msg)


def run_eval_harness(cases_path: Path | None = None, verbose: bool = False) -> StepResult:
    start = time.time()
    script = REPO_ROOT / "scripts" / "eval_agentic_workflow.py"
    cases = cases_path or (REPO_ROOT / "data" / "eval" / "consultations.jsonl")
    temp_report = Path("/tmp/agentic-workflow-safety-dev-run.json")

    if not script.exists():
        return StepResult("Agentic Workflow Safety Replay", "Tier 1", "FAIL", 0.0, f"{script} not found")
    if not cases.exists():
        return StepResult("Agentic Workflow Safety Replay", "Tier 1", "FAIL", 0.0, f"{cases} not found")

    cmd = [sys.executable, str(script), "--cases", str(cases), "--out", str(temp_report)]
    env = {**os.environ, "PYTHONPATH": str(BACKEND_DIR), "PYTHONDONTWRITEBYTECODE": "1"}
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=not verbose, text=True, env=env)
    dur = time.time() - start

    if res.returncode == 0:
        return StepResult("Agentic Workflow Safety Replay", "Tier 1", "PASS", dur)
    msg = "" if verbose else (res.stderr or res.stdout).strip()
    return StepResult("Agentic Workflow Safety Replay", "Tier 1", "FAIL", dur, msg)


def run_frontend(strict: bool = False, verbose: bool = False) -> StepResult:
    start = time.time()
    flutter_bin = shutil.which("flutter")
    if not flutter_bin:
        if strict:
            return StepResult("Frontend Widget & Unit Tests", "Tier 2", "FAIL", 0.0, "Flutter SDK not found on PATH in --strict mode")
        return StepResult("Frontend Widget & Unit Tests", "Tier 2", "SKIP", 0.0, "Flutter SDK not found on PATH")

    cmd = [flutter_bin, "test"]
    res = subprocess.run(cmd, cwd=str(FRONTEND_DIR), capture_output=not verbose, text=True)
    dur = time.time() - start

    if res.returncode == 0:
        return StepResult("Frontend Widget & Unit Tests", "Tier 2", "PASS", dur)
    msg = "" if verbose else (res.stderr or res.stdout).strip()
    return StepResult("Frontend Widget & Unit Tests", "Tier 2", "FAIL", dur, msg)


def run_integration(verbose: bool = False) -> StepResult:
    start = time.time()
    pytest_bin = shutil.which("pytest")
    cmd: list[str]
    if shutil.which("uv"):
        cmd = ["uv", "run", "--extra", "dev", "python", "-m", "pytest", "-q", "-m", "integration"]
    elif pytest_bin:
        cmd = [pytest_bin, "-q", "-m", "integration"]
    else:
        cmd = [sys.executable, "-m", "unittest", "tests/test_chat_integration.py"]

    if verbose:
        cmd = [arg for arg in cmd if arg != "-q"] + ["-v"]

    env = {**os.environ, "PYTHONPATH": str(BACKEND_DIR), "PYTHONDONTWRITEBYTECODE": "1"}
    res = subprocess.run(cmd, cwd=str(BACKEND_DIR), capture_output=not verbose, text=True, env=env)
    dur = time.time() - start

    if res.returncode == 0:
        return StepResult("Live Service & Wire Integration", "Tier 3", "PASS", dur)
    msg = "" if verbose else (res.stderr or res.stdout).strip()
    return StepResult("Live Service & Wire Integration", "Tier 3", "FAIL", dur, msg)


def run_real_model(
    model_url: str | None = None,
    strict: bool = False,
    verbose: bool = False,
    multimodal: bool = False,
) -> StepResult:
    start = time.time()
    pytest_bin = shutil.which("pytest")
    if shutil.which("uv"):
        cmd = ["uv", "run", "--extra", "dev", "python", "-m", "pytest", "-q", "-m", "real_model"]
    else:
        cmd = [pytest_bin or "pytest", "-q", "-m", "real_model"]
    if verbose:
        cmd = [arg for arg in cmd if arg != "-q"] + ["-v"]

    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HARGATURUN_TEST_REAL_MODEL": "1",
        **({"HARGATURUN_TEST_MULTIMODAL": "1"} if multimodal else {}),
    }
    # Always resolve the endpoint so an up server is never misreported as
    # unreachable just because --model-url was omitted.
    env["HARGATURUN_MODEL_URL"] = model_url or DEFAULT_MODEL_URL
    if strict:
        env["HARGATURUN_STRICT_MODE"] = "1"

    res = subprocess.run(cmd, cwd=str(BACKEND_DIR), capture_output=not verbose, text=True, env=env)
    dur = time.time() - start

    output = (res.stderr + "\n" + res.stdout) if not verbose else ""
    counts = _pytest_summary_counts(output)
    ran = counts.get("passed", 0) + counts.get("failed", 0) + counts.get("error", 0)

    if res.returncode == 0:
        # A clean exit with nothing executed means the suite skipped itself
        # (server unreachable). Verbose runs suppress captured output, so fall
        # back to PASS there since returncode 0 already proves success.
        if not verbose and ran == 0 and counts.get("skipped", 0):
            return StepResult("Live Local-Model Smoke Test", "Tier 4", "SKIP", dur, "Model server unreachable at configured endpoint")
        return StepResult("Live Local-Model Smoke Test", "Tier 4", "PASS", dur)

    # Non-zero exit with no test actually run == a collection/skip-time abort,
    # not a genuine assertion failure. Only treat that as SKIP in non-strict.
    if not strict and ran == 0 and counts.get("skipped", 0):
        return StepResult("Live Local-Model Smoke Test", "Tier 4", "SKIP", dur, "Model server unreachable")

    msg = "" if verbose else output.strip()
    return StepResult("Live Local-Model Smoke Test", "Tier 4", "FAIL", dur, msg)


def run_write_faithfulness(
    model_url: str | None = None,
    strict: bool = False,
    verbose: bool = False,
) -> StepResult:
    """Gate 1 real-model check: drive the writer task and measure whether any
    unsupported numeric claim survives validation. SKIPs when the model server
    is unreachable (unless --strict), mirroring the smoke-test tier."""
    name = "Write-Path Numerical Faithfulness (Gate 1)"
    start = time.time()
    script = REPO_ROOT / "scripts" / "eval_write_faithfulness.py"
    if not script.exists():
        return StepResult(name, "Tier 4", "FAIL", 0.0, f"{script} not found")

    temp_report = Path("/tmp/write-faithfulness-dev-run.json")
    cmd = [sys.executable, str(script), "--out", str(temp_report), "--url", model_url or DEFAULT_MODEL_URL]
    if strict:
        cmd += ["--require-model"]

    env = {**os.environ, "PYTHONPATH": str(BACKEND_DIR), "PYTHONDONTWRITEBYTECODE": "1"}
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=not verbose, text=True, env=env)
    dur = time.time() - start

    # Prefer the structured report over parsing stdout.
    measurement = gate_status = None
    reason = ""
    try:
        import json as _json
        report = _json.loads(temp_report.read_text(encoding="utf-8"))
        measurement = report.get("measurement")
        gate = report.get("gate", {}).get(
            "zero_unsupported_numerical_claims_after_validation", {}
        )
        gate_status = gate.get("status")
        reason = report.get("reason") or gate.get("reason") or ""
    except (OSError, ValueError):
        pass

    if measurement == "measured":
        if gate_status == "pass":
            return StepResult(name, "Tier 4", "PASS", dur)
        return StepResult(name, "Tier 4", "FAIL", dur, "unsupported numerical claims survived validation")
    if measurement == "not_measured":
        if strict:
            return StepResult(name, "Tier 4", "FAIL", dur, reason or "model server unreachable in --strict mode")
        return StepResult(name, "Tier 4", "SKIP", dur, reason or "model server unreachable")
    if res.returncode == 0 and not strict:
        return StepResult(name, "Tier 4", "SKIP", dur, "no report produced")
    msg = "" if verbose else (res.stderr or res.stdout).strip()
    return StepResult(name, "Tier 4", "FAIL", dur, msg)


def run_compose(strict: bool = False, verbose: bool = False) -> StepResult:
    start = time.time()
    has_runtime = shutil.which("docker") or shutil.which("podman-compose") or shutil.which("podman")
    if not has_runtime:
        if strict:
            return StepResult("Compose Stack Configuration", "Tier 4", "FAIL", 0.0, "Neither Docker nor Podman found on PATH in --strict mode")
        return StepResult("Compose Stack Configuration", "Tier 4", "SKIP", 0.0, "Neither Docker nor Podman found on PATH")

    pytest_bin = shutil.which("pytest")
    if shutil.which("uv"):
        cmd = ["uv", "run", "--extra", "dev", "python", "-m", "pytest", "-q", "-m", "compose"]
    else:
        cmd = [pytest_bin or "pytest", "-q", "-m", "compose"]
    if verbose:
        cmd = [arg for arg in cmd if arg != "-q"] + ["-v"]

    env = {
        **os.environ,
        "PYTHONPATH": str(BACKEND_DIR),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HARGATURUN_TEST_COMPOSE": "1",
    }
    if strict:
        env["HARGATURUN_STRICT_MODE"] = "1"

    res = subprocess.run(cmd, cwd=str(BACKEND_DIR), capture_output=not verbose, text=True, env=env)
    dur = time.time() - start

    if res.returncode == 0:
        return StepResult("Compose Stack Configuration", "Tier 4", "PASS", dur)
    msg = "" if verbose else (res.stderr or res.stdout).strip()
    return StepResult("Compose Stack Configuration", "Tier 4", "FAIL", dur, msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--tier",
        choices=["1", "2", "3", "4", "all"],
        default="1",
        help="Test tier to run (1: Fast default, 2: Full local, 3: Wire integration, 4: Opt-in smoke, all: All tiers)",
    )
    parser.add_argument("-b", "--backend", action="store_true", help="Run backend unit & contract tests")
    parser.add_argument("-e", "--eval", action="store_true", help="Run agentic workflow safety replay harness")
    parser.add_argument("-f", "--frontend", action="store_true", help="Run frontend widget & unit tests")
    parser.add_argument("-i", "--integration", action="store_true", help="Run live wire integration tests")
    parser.add_argument("--real-model", action="store_true", help="Opt in to live local-model smoke test (Tier 4)")
    parser.add_argument("--multimodal", action="store_true", help="Also run the opt-in mmproj readiness/image smoke test")
    parser.add_argument("--compose", action="store_true", help="Opt in to Compose stack config test (Tier 4)")
    parser.add_argument("--strict", action="store_true", help="Fail if optional prerequisites are missing")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed test runner output")
    parser.add_argument("--cases", type=Path, help="Override path to consultations.jsonl evaluation cases")
    parser.add_argument("--model-url", type=str, help=f"Override local model server URL (default: {DEFAULT_MODEL_URL})")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(bold("=" * 78))
    print(bold(f" HargaTurun Developer Test Suite (Issue #4) — Tier {args.tier.upper()}"))
    print(bold("=" * 78))

    results: list[StepResult] = []

    # Tier selection and explicit sub-flags are ADDITIVE, not mutually
    # exclusive: `--tier all --real-model` runs every tier, and a bare
    # `--real-model` runs only that suite. A tier implies the suites at or
    # below it (tier 2 includes tier 1; `all` includes everything).
    tier = args.tier
    tier_wants_1 = tier in ("1", "2", "all")
    tier_wants_2 = tier in ("2", "all")
    tier_wants_3 = tier in ("3", "all")
    tier_wants_4 = tier in ("4", "all")

    # An explicit sub-flag on its own narrows the run to just those suites; but
    # once combined with a tier it only adds to what the tier already selects.
    explicit_flags = any([args.backend, args.eval, args.frontend, args.integration, args.real_model, args.multimodal, args.compose])
    # When the user passes a non-default tier we always honor it; when they only
    # pass sub-flags (tier left at its "1" default) we let the flags drive.
    tier_specified = tier != "1" or not explicit_flags

    run_tier1_unit = args.backend or (tier_specified and tier_wants_1)
    run_tier1_eval = args.eval or (tier_specified and tier_wants_1)
    run_tier2_front = args.frontend or (tier_specified and tier_wants_2)
    run_tier3_integ = args.integration or (tier_specified and tier_wants_3)
    run_tier4_model = (
        args.real_model
        or args.multimodal
        or (tier_wants_4 and (tier == "4" or os.getenv("HARGATURUN_TEST_REAL_MODEL") == "1" or args.real_model or args.multimodal))
    )
    run_tier4_comp = (
        args.compose
        or (tier_wants_4 and (tier == "4" or os.getenv("HARGATURUN_TEST_COMPOSE") == "1" or args.compose))
    )

    # If tier 4 was requested via `--tier 4`/`--tier all` without model/compose
    # sub-flags, run both tier-4 suites rather than silently skipping them.
    if tier_wants_4 and not (args.real_model or args.multimodal or args.compose):
        run_tier4_model = True
        run_tier4_comp = True

    # Tier 1: Backend Unit
    if run_tier1_unit:
        print(cyan("\n[1/4] Running Tier 1: Backend Unit & Contract Tests..."))
        res = run_backend_unit(verbose=args.verbose)
        results.append(res)
        print(f"      {green('PASS') if res.status == 'PASS' else red('FAIL')} in {res.duration_s:.2f}s")
        if res.message:
            print(f"      {red(res.message)}")

    # Tier 1: Safety Replay Harness
    if run_tier1_eval:
        print(cyan("\n[1/4] Running Tier 1: Agentic Workflow Safety Replay..."))
        res = run_eval_harness(cases_path=args.cases, verbose=args.verbose)
        results.append(res)
        print(f"      {green('PASS') if res.status == 'PASS' else red('FAIL')} in {res.duration_s:.2f}s")
        if res.message:
            print(f"      {red(res.message)}")

    # Tier 2: Frontend
    if run_tier2_front:
        print(cyan("\n[2/4] Running Tier 2: Frontend Widget & Unit Tests..."))
        res = run_frontend(strict=args.strict, verbose=args.verbose)
        results.append(res)
        if res.status == "PASS":
            print(f"      {green('PASS')} in {res.duration_s:.2f}s")
        elif res.status == "SKIP":
            print(f"      {yellow('SKIP')} ({res.message})")
        else:
            print(f"      {red('FAIL')} in {res.duration_s:.2f}s")
            if res.message:
                print(f"      {red(res.message)}")

    # Tier 3: Wire Integration
    if run_tier3_integ:
        print(cyan("\n[3/4] Running Tier 3: Live Service & Wire Integration Tests..."))
        res = run_integration(verbose=args.verbose)
        results.append(res)
        print(f"      {green('PASS') if res.status == 'PASS' else red('FAIL')} in {res.duration_s:.2f}s")
        if res.message:
            print(f"      {red(res.message)}")

    # Tier 4: Real Model
    if run_tier4_model:
        print(cyan("\n[4/4] Running Tier 4: Live Local-Model Server Smoke Test..."))
        res = run_real_model(model_url=args.model_url, strict=args.strict, verbose=args.verbose, multimodal=args.multimodal)
        results.append(res)
        if res.status == "PASS":
            print(f"      {green('PASS')} in {res.duration_s:.2f}s")
        elif res.status == "SKIP":
            print(f"      {yellow('SKIP')} ({res.message})")
        else:
            print(f"      {red('FAIL')} in {res.duration_s:.2f}s")
            if res.message:
                print(f"      {red(res.message)}")

        print(cyan("\n[4/4] Running Tier 4: Write-Path Numerical Faithfulness (Gate 1)..."))
        res = run_write_faithfulness(model_url=args.model_url, strict=args.strict, verbose=args.verbose)
        results.append(res)
        if res.status == "PASS":
            print(f"      {green('PASS')} in {res.duration_s:.2f}s")
        elif res.status == "SKIP":
            print(f"      {yellow('SKIP')} ({res.message})")
        else:
            print(f"      {red('FAIL')} in {res.duration_s:.2f}s")
            if res.message:
                print(f"      {red(res.message)}")

    # Tier 4: Compose
    if run_tier4_comp:
        print(cyan("\n[4/4] Running Tier 4: Compose Stack Configuration Smoke Test..."))
        res = run_compose(strict=args.strict, verbose=args.verbose)
        results.append(res)
        if res.status == "PASS":
            print(f"      {green('PASS')} in {res.duration_s:.2f}s")
        elif res.status == "SKIP":
            print(f"      {yellow('SKIP')} ({res.message})")
        else:
            print(f"      {red('FAIL')} in {res.duration_s:.2f}s")
            if res.message:
                print(f"      {red(res.message)}")

    # Summary
    print("\n" + bold("=" * 78))
    print(bold(" Test Execution Summary"))
    print(bold("=" * 78))
    for r in results:
        status_str = green("PASS") if r.status == "PASS" else (yellow("SKIP") if r.status == "SKIP" else red("FAIL"))
        note = f" ({r.message})" if r.status == "SKIP" and r.message else ""
        print(f"  [{r.tier}] {r.name:<38} {status_str:>6} ({r.duration_s:.2f}s){note}")

    failures = [r for r in results if r.status == "FAIL"]
    total_time = sum(r.duration_s for r in results)

    print("-" * 78)
    if failures:
        print(red(f"❌ {len(failures)} suite(s) failed out of {len(results)} in {total_time:.2f}s."))
        return 1

    print(green(f"✅ All {len(results)} executed suites passed/skipped cleanly in {total_time:.2f}s."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
