"""Gold test set: loader, validator, and coverage report.

The gold set (Fine-Tuning Plan §3.2) is the *primary* pre/post quality claim for
the fine-tuned model. Unlike the synthetic split from :mod:`hargaturun.dataset`,
every gold example is **authored or verified by a human** and must not come from
the training generator or its templates. It is the independent ruler that answers
"is the model actually correct?" (Plan §4.2/§4.3 metrics run against this file).

This module does not *create* gold data — it cannot, because the value is the
human judgement in it. It provides the tooling a reviewer needs:

* :func:`load_gold` — read ``data/gold_test.jsonl``.
* :func:`validate_gold_set` — separate **hard errors** (a record is technically
  broken: bad schema, an ``engine_result`` that disagrees with the oracle, prose
  citing a number no input supports, or text copied from the generator) from
  **warnings** (the set is technically valid but not yet complete: below the
  200-example target, still-draft records, or a missing coverage stratum).
* :func:`coverage_report` — counts by task, review status, category, and tag.
* ``python3 -m hargaturun.gold`` — run both and print a review dashboard.

The split is deliberate: hard errors must be zero before the file is trusted;
warnings are the human's remaining to-do list.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .pricing import PricingInput, compute
from . import schemas

DEFAULT_GOLD_PATH = Path(__file__).resolve().parents[1] / "data" / "gold_test.jsonl"

#: Target size for the final quality claim (Plan §3.2). Below this the set is
#: valid but not yet authoritative.
MIN_EXAMPLES = 200

VALID_TASKS = ("parse", "write")
VALID_REVIEW = ("draft", "verified")

#: Coverage strata the reviewer should hit (surfaced as warnings, not errors).
EXPECTED_TAGS = (
    "slang", "missing_field", "ambiguous",           # parse difficulty
    "recommendation", "no_action", "warning",         # write statuses
    "fire_sale", "expired", "thin_margin",            # edge economics
)


# --------------------------------------------------------------------------- #
# Loading                                                                     #
# --------------------------------------------------------------------------- #

def load_gold(path: str | Path = DEFAULT_GOLD_PATH) -> list[dict]:
    """Read a JSONL gold file into a list of records. Blank lines are skipped.

    Raises ``FileNotFoundError`` if the file is missing and ``ValueError`` with
    the line number if any line is not valid JSON.
    """
    records: list[dict] = []
    text = Path(path).read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"gold line {lineno}: invalid JSON: {exc}") from exc
    return records


# --------------------------------------------------------------------------- #
# Per-record validation (hard errors only)                                    #
# --------------------------------------------------------------------------- #

def _recompute_engine_result(normalized_input: dict) -> dict:
    result = compute(
        PricingInput(
            category=normalized_input["category"],
            original_price=normalized_input["original_price"],
            cost=normalized_input["cost"],
            stock=normalized_input["stock"],
            days_remaining=normalized_input["days_remaining"],
            daily_sales=normalized_input["daily_sales"],
            total_shelf_life=normalized_input["total_shelf_life"],
        )
    )
    return schemas.to_engine_result(result)


def validate_record(record: dict) -> list[str]:
    """Return hard errors for one gold record; empty means technically valid."""
    errors: list[str] = []
    rid = record.get("id", "<no id>")

    if not isinstance(record.get("id"), str) or not record["id"].strip():
        errors.append(f"{rid}: 'id' must be a non-empty string")
    if record.get("source") != "gold":
        errors.append(f"{rid}: 'source' must be 'gold' (provenance marker)")
    if record.get("review") not in VALID_REVIEW:
        errors.append(f"{rid}: 'review' must be one of {VALID_REVIEW}")
    if "tags" in record and not (
        isinstance(record["tags"], list)
        and all(isinstance(t, str) for t in record["tags"])
    ):
        errors.append(f"{rid}: 'tags' must be a list of strings")

    task = record.get("task")
    if task not in VALID_TASKS:
        errors.append(f"{rid}: 'task' must be one of {VALID_TASKS}")
        return errors

    if task == "parse":
        if not isinstance(record.get("input_text"), str) or not record["input_text"].strip():
            errors.append(f"{rid}: parse record needs a non-empty 'input_text'")
        for forbidden in ("normalized_input", "engine_result"):
            if forbidden in record:
                errors.append(f"{rid}: parse record must not contain '{forbidden}'")
        errors.extend(
            f"{rid}: parse target invalid: {e}"
            for e in schemas.validate_parse_output(record.get("target"))
        )

    else:  # write
        ni = record.get("normalized_input")
        er = record.get("engine_result")
        if not isinstance(ni, dict):
            errors.append(f"{rid}: write record needs a 'normalized_input' object")
            return errors
        if not isinstance(er, dict):
            errors.append(f"{rid}: write record needs an 'engine_result' object")
            return errors
        # The oracle is authoritative: a gold write case is only valid if its
        # recorded engine_result is exactly what the engine produces.
        try:
            expected = _recompute_engine_result(ni)
        except (KeyError, TypeError) as exc:
            errors.append(f"{rid}: normalized_input is not a valid engine input: {exc}")
            return errors
        if er != expected:
            errors.append(
                f"{rid}: engine_result disagrees with the oracle; expected {expected}")
        allowed = schemas.allowed_numbers_for(ni, er)
        errors.extend(
            f"{rid}: write target invalid: {e}"
            for e in schemas.validate_write_output(
                record.get("target"), allowed_numbers=allowed,
                engine_status=er.get("status"))
        )

    return errors


# --------------------------------------------------------------------------- #
# Whole-set validation (hard errors + warnings)                               #
# --------------------------------------------------------------------------- #

def _generator_parse_texts() -> set[str]:
    """Free-text inputs the training generator can produce, for the leakage
    check. Imported lazily so validating a gold file never requires generation
    unless the caller asks for it."""
    from .dataset import generate

    _, examples = generate()
    return {e["input_text"] for e in examples if e["task"] == "parse"}


def validate_gold_set(
    records: list[dict],
    *,
    check_generator: bool = True,
    min_examples: int = MIN_EXAMPLES,
) -> tuple[list[str], list[str]]:
    """Validate the whole set. Returns ``(errors, warnings)``.

    ``errors`` are blocking (broken records, duplicate ids, or text copied from
    the generator). ``warnings`` are the reviewer's remaining work (too few
    verified examples, still-draft records, missing coverage).
    """
    errors: list[str] = []
    warnings: list[str] = []

    ids = Counter(r.get("id") for r in records)
    for rid, count in ids.items():
        if count > 1:
            errors.append(f"duplicate id {rid!r} appears {count} times")

    for record in records:
        errors.extend(validate_record(record))

    # Leakage guard (§3.2): gold text must not be generator output.
    if check_generator:
        generated = _generator_parse_texts()
        for record in records:
            if record.get("task") == "parse" and record.get("input_text") in generated:
                errors.append(
                    f"{record.get('id')}: input_text is identical to a generator "
                    f"example (gold must be independent)")

    # ---- warnings: completeness and coverage ----
    verified = [r for r in records if r.get("review") == "verified"]
    drafts = [r for r in records if r.get("review") == "draft"]
    if len(verified) < min_examples:
        warnings.append(
            f"only {len(verified)} verified example(s); need {min_examples} "
            f"for the primary quality claim (Plan §3.2)")
    if drafts:
        warnings.append(f"{len(drafts)} record(s) still marked 'draft' — need human review")

    report = coverage_report(records)
    missing_categories = set(schemas.ALLOWED_CATEGORIES) - set(report["by_category"])
    if missing_categories:
        warnings.append(f"categories not covered: {sorted(missing_categories)}")
    for status in schemas.WRITE_STATUSES:
        if report["by_write_status"].get(status, 0) == 0:
            warnings.append(f"no write examples with status {status!r}")
    for tag in EXPECTED_TAGS:
        if report["by_tag"].get(tag, 0) == 0:
            warnings.append(f"no examples tagged {tag!r}")
    if report["parse_needs_confirmation"] == 0:
        warnings.append("no parse examples with needs_confirmation=true")
    if report["parse_complete"] == 0:
        warnings.append("no complete parse examples (needs_confirmation=false)")

    return errors, warnings


# --------------------------------------------------------------------------- #
# Coverage report                                                             #
# --------------------------------------------------------------------------- #

def coverage_report(records: list[dict]) -> dict:
    """Count records by task, review status, category, tag, and write status."""
    by_task: Counter = Counter()
    by_review: Counter = Counter()
    by_category: Counter = Counter()
    by_tag: Counter = Counter()
    by_write_status: Counter = Counter()
    parse_needs_confirmation = 0
    parse_complete = 0

    for record in records:
        by_task[record.get("task")] += 1
        by_review[record.get("review")] += 1
        for tag in record.get("tags", []):
            by_tag[tag] += 1

        if record.get("task") == "parse":
            parsed = (record.get("target") or {}).get("parsed_input", {})
            category = parsed.get("category")
            if category:
                by_category[category] += 1
            if (record.get("target") or {}).get("needs_confirmation"):
                parse_needs_confirmation += 1
            else:
                parse_complete += 1
        elif record.get("task") == "write":
            category = (record.get("normalized_input") or {}).get("category")
            if category:
                by_category[category] += 1
            status = (record.get("engine_result") or {}).get("status")
            if status:
                by_write_status[status] += 1

    return {
        "total": len(records),
        "by_task": dict(by_task),
        "by_review": dict(by_review),
        "by_category": dict(by_category),
        "by_tag": dict(by_tag),
        "by_write_status": dict(by_write_status),
        "parse_needs_confirmation": parse_needs_confirmation,
        "parse_complete": parse_complete,
    }


# --------------------------------------------------------------------------- #
# CLI review dashboard                                                        #
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and summarize the gold test set.")
    parser.add_argument("--path", default=str(DEFAULT_GOLD_PATH))
    parser.add_argument("--no-generator-check", action="store_true",
                        help="skip the (slower) leakage check against the generator")
    parser.add_argument("--min-examples", type=int, default=MIN_EXAMPLES)
    args = parser.parse_args(argv)

    records = load_gold(args.path)
    errors, warnings = validate_gold_set(
        records, check_generator=not args.no_generator_check,
        min_examples=args.min_examples)
    report = coverage_report(records)

    print(f"Gold test set: {args.path}")
    print(f"  records            : {report['total']}")
    print(f"  by task            : {report['by_task']}")
    print(f"  by review          : {report['by_review']}")
    print(f"  by category        : {report['by_category']}")
    print(f"  by write status    : {report['by_write_status']}")
    print(f"  parse complete     : {report['parse_complete']}")
    print(f"  parse needs_confirm : {report['parse_needs_confirmation']}")
    print(f"  by tag             : {report['by_tag']}")
    print()
    if errors:
        print(f"HARD ERRORS ({len(errors)}) — must be fixed before trusting the set:")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("HARD ERRORS: none. Every record is technically valid.")
    print()
    if warnings:
        print(f"WARNINGS ({len(warnings)}) — reviewer to-do list:")
        for w in warnings:
            print(f"  • {w}")
    else:
        print("WARNINGS: none. Set is complete.")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
