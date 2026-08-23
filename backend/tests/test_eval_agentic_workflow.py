from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_agentic_workflow.py"
sys.path.insert(0, str(SCRIPT.parent))

import eval_agentic_workflow as evaluation  # noqa: E402
from hargaturun.consultation import ConsultationState, Session  # noqa: E402
from hargaturun.pricing import PricingInput, compute  # noqa: E402


CASES_PATH = SCRIPT.parents[1] / "data" / "eval" / "consultations.jsonl"


class SuiteValidationTest(unittest.TestCase):
    def setUp(self):
        self.cases = evaluation.load_cases(CASES_PATH)

    def test_empty_suite_is_rejected(self):
        self.assertIn("at least one case", evaluation.validate_suite([])[0])

    def test_duplicate_case_ids_are_rejected(self):
        duplicate = [self.cases[0], copy.deepcopy(self.cases[0])]
        errors = evaluation.validate_suite(duplicate)
        self.assertTrue(any("duplicate case_id" in error for error in errors))

    def test_structurally_invalid_action_and_expectation_are_rejected(self):
        invalid = copy.deepcopy(self.cases[0])
        invalid["turns"][0]["action"] = "invented"
        invalid["expect"]["tool_calls"] = 99
        errors = evaluation.validate_suite([invalid])
        self.assertTrue(any("unsupported action" in error for error in errors))
        self.assertTrue(any("cannot exceed" in error for error in errors))

    def test_semantically_unusable_result_expectation_is_rejected(self):
        invalid = copy.deepcopy(self.cases[0])
        invalid["expect"]["result_status"] = "recommendation"
        invalid["expect"]["tool_calls"] = 0
        errors = evaluation.validate_suite([invalid])
        self.assertTrue(any("requires an expected tool call" in error for error in errors))

    def test_arbitrary_json_types_fail_closed_without_type_errors(self):
        invalid = copy.deepcopy(self.cases[0])
        invalid["case_id"] = ["not", "an", "id"]
        invalid["scenario_id"] = {"not": "a string"}
        invalid["tags"] = [{"not": "a string"}]
        invalid["turns"][0]["action"] = {"not": "an action"}
        invalid["expect"]["final_action"] = ["not", "an action"]
        invalid["expect"]["result_status"] = {"not": "a status"}
        invalid["expect"]["missing_fields"] = [{"not": "a field"}]
        errors = evaluation.validate_suite([invalid])
        self.assertGreaterEqual(len(errors), 7)
        self.assertTrue(all(isinstance(error, str) for error in errors))

    def test_arbitrary_json_types_reject_through_cli_with_exit_two(self):
        invalid = copy.deepcopy(self.cases[0])
        invalid["expect"]["missing_fields"] = [{"unhashable": [1, 2]}]
        with tempfile.TemporaryDirectory() as directory:
            cases = Path(directory) / "cases.jsonl"
            report = Path(directory) / "report.json"
            cases.write_text(json.dumps(invalid) + "\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--cases", str(cases), "--out", str(report)],
                capture_output=True,
                text=True,
                env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(completed.returncode, 2)
            self.assertFalse(report.exists())

    def test_malformed_json_is_rejected_before_report_write(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = Path(directory) / "cases.jsonl"
            report = Path(directory) / "report.json"
            cases.write_text('{"case_id":\n', encoding="utf-8")
            report.write_text("sentinel", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "--cases", str(cases), "--out", str(report)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(report.read_text(encoding="utf-8"), "sentinel")


class ObservationAndSafetyTest(unittest.TestCase):
    def setUp(self):
        self.cases = evaluation.load_cases(CASES_PATH)

    def test_correction_records_invalidation_on_actual_result_bearing_state(self):
        case = next(case for case in self.cases if case["case_id"] == "produce-correct-stock")
        counters = evaluation.Counters()
        run = evaluation.replay(case, counters)
        self.assertEqual(counters.stale_result_invalidations, 1)
        self.assertEqual(counters.stale_result_exposures, 0)
        self.assertTrue(
            any(
                event.get("event") == "result_invalidation" and event["invalidated"]
                for event in run.trace
            )
        )
        self.assertIsNone(run.result_payload)

    def test_negative_regression_catches_broken_invalidation(self):
        case = next(case for case in self.cases if case["case_id"] == "produce-correct-stock")
        counters = evaluation.Counters()
        # Simulate the old bug: a correction does not clear the Session result.
        with patch.object(Session, "drop_result", lambda self: None):
            evaluation.replay(case, counters)
        self.assertGreater(counters.stale_result_exposures, 0)
        self.assertTrue(any(v.kind == "stale_result_exposure" for v in counters.violations))

    def test_result_hash_validation_catches_canonical_payload_tampering(self):
        case = next(case for case in self.cases if case["case_id"] == "produce-correct-stock")
        run = evaluation.replay(case)
        self.assertTrue(run.result_observations)
        payload = copy.deepcopy(run.result_observations[0].payload)
        payload["oracle"]["discount_percent"] = (payload["oracle"]["discount_percent"] or 0) + 5
        errors = evaluation.validate_stored_result(payload)
        self.assertIn("stored result_hash does not match canonical oracle payload", errors)

    def test_paired_payload_and_hash_tampering_is_rejected(self):
        case = next(case for case in self.cases if case["case_id"] == "produce-correct-stock")
        original_result = evaluation._session_result

        def paired_tamper(oracle, revision):
            alternate = replace(
                oracle,
                discount_percent=(oracle.discount_percent or 0) + 5,
            )
            return original_result(alternate, revision)

        counters = evaluation.Counters()
        with patch.object(evaluation, "_session_result", paired_tamper):
            run = evaluation.replay(case, counters)
        self.assertIsNone(run.result_payload)
        self.assertEqual(counters.result_hash_violations, 1)
        self.assertEqual(counters.pricing_result_violations, 0)
        self.assertEqual(sum(v.kind == "result_hash" for v in counters.violations), 1)

    def test_tampered_stored_result_is_rejected_before_reuse(self):
        case = next(case for case in self.cases if case["case_id"] == "produce-correct-stock")
        original_result = evaluation._session_result

        def tampered_result(oracle, revision):
            payload = original_result(oracle, revision)
            payload["result_hash"] = "0" * 64
            return payload

        counters = evaluation.Counters()
        with patch.object(evaluation, "_session_result", tampered_result):
            run = evaluation.replay(case, counters)
        self.assertGreater(counters.result_hash_violations, 0)
        self.assertIsNone(run.result_payload)
        self.assertTrue(any(v.kind == "result_hash" for v in counters.violations))

    def test_broken_invalidation_counts_each_stale_access_and_exposure(self):
        case = copy.deepcopy(
            next(case for case in self.cases if case["case_id"] == "produce-correct-stock")
        )
        case["turns"].extend([{"action": "calculate"}, {"action": "explain"}])
        counters = evaluation.Counters()
        with patch.object(Session, "drop_result", lambda self: None):
            run = evaluation.replay(case, counters)
        self.assertEqual(counters.stale_result_reuses, 3)
        self.assertEqual(counters.stale_result_exposures, 3)
        self.assertEqual(run.stale_result_exposures, 3)

    def test_each_successful_result_is_checked_at_its_producing_revision(self):
        case = copy.deepcopy(next(case for case in self.cases if case["case_id"] == "produce-recalculate-after-correction"))
        # The fixture intentionally stops before re-confirmation. Add the
        # corrected revision's confirmation and calculate turns to exercise
        # two successful calls in one replay.
        case["turns"].extend([{"action": "confirm"}, {"action": "calculate"}])
        counters = evaluation.Counters()
        run = evaluation.replay(case, counters)
        self.assertEqual(len(run.result_observations), 2)
        self.assertEqual(counters.result_evaluations, 2)
        self.assertTrue(all(not observation.validation_errors for observation in run.result_observations))

    def test_tampered_pre_correction_result_fails_at_production_call(self):
        case = next(case for case in self.cases if case["case_id"] == "produce-correct-stock")
        original_compute = evaluation.PricingTool.compute
        calls = 0

        def tampered(self, state):
            nonlocal calls
            result = original_compute(self, state)
            calls += 1
            if calls == 1 and result.discount_percent is not None:
                return replace(result, discount_percent=result.discount_percent + 5)
            return result

        counters = evaluation.Counters()
        with patch.object(evaluation.PricingTool, "compute", tampered):
            run = evaluation.replay(case, counters)
        self.assertEqual(len(run.result_observations), 1)
        self.assertGreater(counters.pricing_result_violations, 0)
        self.assertTrue(any("discount_percent" in detail for _, detail in run.result_observations[0].validation_errors))
        self.assertEqual(counters.result_evaluations, 1)

    def test_authoritative_validation_catches_discount_tampering(self):
        state = evaluation.merge_patch(ConsultationState(), evaluation.validate_patch(
            {
                "item_name": "Roti",
                "category": "Bakery",
                "original_price": 20000,
                "cost": 10000,
                "stock": 30,
                "days_remaining": 1,
                "daily_sales": 5,
            },
            allowed_categories=evaluation.CATEGORIES,
        )[0])
        state = evaluation.confirm_state(state)
        oracle = compute(state.to_pricing_input())
        tampered = replace(oracle, discount_percent=(oracle.discount_percent or 0) + 5)
        errors = evaluation.validate_authoritative_result(state, tampered)
        self.assertTrue(any(kind == "result_mismatch" and "discount_percent" in detail for kind, detail in errors))

    def test_canonical_result_contains_non_price_authoritative_fields(self):
        result = compute(PricingInput("Bakery", 20000, 10000, 30, 1, 5, 4))
        canonical = evaluation.canonical_result(result)
        self.assertIn("discount_percent", canonical)
        self.assertIn("timing", canonical)
        self.assertIn("confidence", canonical)
        self.assertIn("expected_revenue", canonical)


class CountingAndReadinessTest(unittest.TestCase):
    def setUp(self):
        self.cases = evaluation.load_cases(CASES_PATH)

    def test_missed_and_expected_mismatches_are_counted_once(self):
        case = copy.deepcopy(self.cases[0])
        case["expect"].update(
            {
                "tool_calls": 2,
                "final_action": "SHOW_CONFIRMATION",
                "result_status": "no_action",
                "missing_fields": ["cost"],
                "state": {"item_name": "Wrong item"},
            }
        )
        counters = evaluation.Counters()
        evaluation.score(case, counters)
        self.assertEqual(counters.missed_tool_calls, 1)
        self.assertEqual(counters.final_action_mismatches, 1)
        self.assertEqual(counters.result_status_mismatches, 1)
        self.assertEqual(counters.missing_field_mismatches, 1)
        self.assertEqual(counters.state_mismatches, 1)
        self.assertEqual(sum(v.kind == "missed_tool_call" for v in counters.violations), 1)

    def test_report_marks_full_readiness_not_measured(self):
        counters = evaluation.evaluate(self.cases)
        report = evaluation.build_report(self.cases, counters, CASES_PATH)
        self.assertTrue(report["deterministic_subset_passed"])
        self.assertFalse(report["ready_for_submission"])
        gates = report["readiness_gates_8_4"]
        self.assertEqual(gates["zero_unsupported_numerical_claims_after_validation"]["status"], "not_measured")
        self.assertEqual(gates["material_improvement_over_direct_chat"]["status"], "not_measured")
        self.assertEqual(report["readiness_status"], "not_ready")
        self.assertGreater(report["denominators"]["cases"], 0)
        self.assertEqual(
            report["deterministic_subset_gates"]["reproducible_complete_results"]["denominator"],
            counters.result_evaluations,
        )


if __name__ == "__main__":
    unittest.main()
