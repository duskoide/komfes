"""Tests for the synthetic dataset generator and its quality gates.

Fine-Tuning Plan §3. Pure stdlib like the rest of the deterministic core; no
files are written except inside a per-test temp directory.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hargaturun import dataset, schemas  # noqa: E402


class TestReversibleRenderers(unittest.TestCase):
    """§3.3: every rendered numeric label must parse back to its exact value."""

    def test_rupiah_round_trips_all_styles(self):
        for value in (2000, 5000, 15000, 73500, 100000, 1500000, 2000000):
            for style in ("full", "dots", "rb", "ribu", "k", "jt"):
                label = dataset.render_rupiah(value, style)
                if label is None:
                    continue
                self.assertEqual(dataset.parse_rupiah(label), value,
                                 msg=f"{value} via {style} -> {label!r}")

    def test_rupiah_style_declines_when_inexact(self):
        # 73_500 is not a whole number of thousands or a clean juta value.
        self.assertIsNone(dataset.render_rupiah(73_500, "rb"))
        self.assertIsNone(dataset.render_rupiah(73_500, "k"))
        self.assertIsNone(dataset.render_rupiah(73_500, "jt"))
        # dots and full always work.
        self.assertEqual(dataset.render_rupiah(73_500, "dots"), "73.500")
        self.assertEqual(dataset.render_rupiah(73_500, "full"), "73500")

    def test_jt_is_exact_or_none(self):
        self.assertEqual(dataset.render_rupiah(1_500_000, "jt"), "1,5jt")
        self.assertEqual(dataset.render_rupiah(2_000_000, "jt"), "2jt")
        self.assertEqual(dataset.parse_rupiah("1,5jt"), 1_500_000)
        self.assertIsNone(dataset.render_rupiah(1_250_000, "jt"))  # 2 decimals

    def test_days_round_trip(self):
        for value in range(0, 15):
            for style in ("word", "count"):
                label = dataset.render_days(value, style)
                if label is None:
                    continue
                self.assertEqual(dataset.parse_days(label), value)
        self.assertEqual(dataset.render_days(0, "word"), "hari ini")
        self.assertEqual(dataset.render_days(2, "word"), "lusa")
        self.assertIsNone(dataset.render_days(5, "word"))  # no word for 5

    def test_count_round_trip(self):
        for value in (0, 1, 7, 35, 100):
            for unit in dataset._COUNT_UNITS + ("",):
                self.assertEqual(dataset.parse_count(dataset.render_count(value, unit)), value)

    def test_bad_labels_raise(self):
        with self.assertRaises(dataset.RoundTripError):
            dataset.parse_rupiah("banyak")
        with self.assertRaises(dataset.RoundTripError):
            dataset.parse_days("nanti")
        with self.assertRaises(dataset.RoundTripError):
            dataset.parse_count("beberapa")


class TestGeneration(unittest.TestCase):
    def setUp(self):
        self.scenarios, self.examples = dataset.generate()

    def test_produces_scenarios_and_examples(self):
        self.assertGreater(len(self.scenarios), 0)
        self.assertGreater(len(self.examples), 0)
        tasks = {e["task"] for e in self.examples}
        self.assertEqual(tasks, {"parse", "write"})

    def test_split_ratio_is_80_10_10(self):
        counts = {name: 0 for name in dataset._SPLITS}
        for s in self.scenarios:
            counts[s.split] += 1
        total = len(self.scenarios)
        self.assertAlmostEqual(counts["train"] / total, 0.8, delta=0.02)
        self.assertAlmostEqual(counts["validation"] / total, 0.1, delta=0.02)
        self.assertAlmostEqual(counts["test"] / total, 0.1, delta=0.02)

    def test_split_sets_are_disjoint(self):
        by_split = {name: set() for name in dataset._SPLITS}
        for s in self.scenarios:
            by_split[s.split].add(s.scenario_id)
        self.assertEqual(by_split["train"] & by_split["validation"], set())
        self.assertEqual(by_split["train"] & by_split["test"], set())
        self.assertEqual(by_split["validation"] & by_split["test"], set())

    def test_all_variants_of_a_scenario_share_one_split(self):
        seen: dict[str, str] = {}
        for e in self.examples:
            prev = seen.setdefault(e["scenario_id"], e["split"])
            self.assertEqual(prev, e["split"])

    def test_all_gates_pass_on_generated_data(self):
        self.assertEqual(dataset.run_quality_gates(self.scenarios, self.examples), [])

    def test_every_category_and_status_covered(self):
        cats = {s.normalized_input["category"] for s in self.scenarios}
        self.assertEqual(cats, set(dataset.CATEGORIES))
        statuses = {s.engine_result["status"] for s in self.scenarios}
        self.assertEqual(statuses, set(schemas.WRITE_STATUSES))

    def test_parse_targets_validate_and_carry_no_recommendation(self):
        for e in self.examples:
            if e["task"] != "parse":
                continue
            self.assertEqual(schemas.validate_parse_output(e["target"]), [])
            self.assertNotIn("engine_result", e)

    def test_write_targets_validate_against_allowed_numbers(self):
        for e in self.examples:
            if e["task"] != "write":
                continue
            allowed = schemas.allowed_numbers_for(e["normalized_input"], e["engine_result"])
            errs = schemas.validate_write_output(
                e["target"], allowed_numbers=allowed,
                engine_status=e["engine_result"]["status"])
            self.assertEqual(errs, [], msg=f"{e['scenario_id']}: {errs}")

    def test_needs_confirmation_matches_missing_fields(self):
        for e in self.examples:
            if e["task"] != "parse":
                continue
            target = e["target"]
            self.assertEqual(target["needs_confirmation"], bool(target["missing_fields"]))


class TestDeterminism(unittest.TestCase):
    """§3.6 gate 8: a fixed seed reproduces scenario ids and labels."""

    def test_same_seed_reproduces_examples(self):
        _, a = dataset.generate(seed=42)
        _, b = dataset.generate(seed=42)
        self.assertEqual(
            [dataset._training_record(x) for x in a],
            [dataset._training_record(x) for x in b],
        )

    def test_different_seed_changes_output(self):
        _, a = dataset.generate(seed=1)
        _, b = dataset.generate(seed=2)
        self.assertNotEqual(
            [dataset._training_record(x) for x in a],
            [dataset._training_record(x) for x in b],
        )


class TestGatesCatchProblems(unittest.TestCase):
    """The gates must actually fail on bad data, not just pass on good data."""

    def setUp(self):
        self.scenarios, self.examples = dataset.generate()

    def test_round_trip_gate_catches_bad_label(self):
        parse_ex = next(e for e in self.examples if e["task"] == "parse" and e["_rendered"])
        fname, _label, value = parse_ex["_rendered"][0]
        parse_ex["_rendered"][0] = (fname, "99999", value + 1)  # label no longer matches
        failures = dataset.run_quality_gates(self.scenarios, self.examples)
        self.assertTrue(any("label" in f for f in failures))

    def test_engine_result_gate_catches_tampering(self):
        write_ex = next(e for e in self.examples if e["task"] == "write")
        write_ex["engine_result"] = dict(write_ex["engine_result"], status="recommendation",
                                          discount_percent=999)
        failures = dataset.run_quality_gates(self.scenarios, self.examples)
        self.assertTrue(failures)

    def test_fabricated_number_gate_catches_unsupported_prose(self):
        write_ex = next(e for e in self.examples
                        if e["task"] == "write"
                        and e["engine_result"]["status"] == schemas.WRITE_STATUS_NO_ACTION)
        write_ex["target"]["explanation"] += " Diskon 87% besar sekali."
        failures = dataset.run_quality_gates(self.scenarios, self.examples)
        self.assertTrue(any("87" in f or "invalid" in f for f in failures))


class TestOutputAndFormatting(unittest.TestCase):
    def test_write_dataset_creates_split_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = dataset.write_dataset(tmp, scenarios_per_cell=2)
            for name in dataset._SPLITS:
                path = Path(tmp) / f"{name}.jsonl"
                self.assertTrue(path.exists())
                for line in path.read_text(encoding="utf-8").splitlines():
                    record = json.loads(line)
                    self.assertNotIn("_rendered", record)  # bookkeeping stripped
                    self.assertIn(record["task"], ("parse", "write"))
            self.assertGreater(summary["examples"], 0)

    def test_to_chat_messages_uses_frozen_prompts(self):
        _, examples = dataset.generate(seed=7)
        parse_ex = next(e for e in examples if e["task"] == "parse")
        write_ex = next(e for e in examples if e["task"] == "write")

        parse_msgs = dataset.to_chat_messages(parse_ex)
        self.assertEqual(parse_msgs[0]["content"], schemas.PARSE_SYSTEM_PROMPT)
        self.assertEqual(parse_msgs[1]["content"], parse_ex["input_text"])
        self.assertEqual(json.loads(parse_msgs[2]["content"]), parse_ex["target"])

        write_msgs = dataset.to_chat_messages(write_ex)
        self.assertEqual(write_msgs[0]["content"], schemas.WRITE_SYSTEM_PROMPT)
        user = json.loads(write_msgs[1]["content"])
        self.assertIn("normalized_input", user)
        self.assertIn("engine_result", user)


if __name__ == "__main__":
    unittest.main()
