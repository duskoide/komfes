"""Unit tests for the consultation reducer, action policy and pricing tool.

Covers the §9.1 checks in the Agentic Workflow Plan: patch merging, refusal
to guess, correction invalidating a result, and the tool-call preconditions.
"""

from __future__ import annotations

import unittest

from hargaturun.consultation import (
    ASK_FOR_MISSING_FIELDS,
    CALL_PRICING_TOOL,
    EXPLAIN_RESULT,
    SHOW_CONFIRMATION,
    ConsultationState,
    PricingTool,
    PricingToolRefused,
    SessionStore,
    confirm,
    decide_action,
    merge_patch,
    validate_patch,
)
from hargaturun.pricing import CATEGORIES

COMPLETE = {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 10,
    "days_remaining": 2,
    "daily_sales": 5,
}


def _validate(patch: dict) -> dict:
    accepted, _ = validate_patch(patch, allowed_categories=CATEGORIES)
    return accepted


def _complete_state() -> ConsultationState:
    return merge_patch(ConsultationState(), _validate(COMPLETE))


class PatchValidationTest(unittest.TestCase):
    def test_accepts_several_fields_from_one_message(self):
        accepted = _validate(
            {"item_name": "Roti Tawar", "stock": 10, "original_price": 15000}
        )
        self.assertEqual(
            accepted, {"item_name": "Roti Tawar", "stock": 10, "original_price": 15000}
        )

    def test_rejects_unknown_keys(self):
        accepted, rejected = validate_patch(
            {"stock": 10, "discount_percent": 30, "recommended_price": 9000},
            allowed_categories=CATEGORIES,
        )
        self.assertEqual(accepted, {"stock": 10})
        self.assertCountEqual(rejected, ["discount_percent", "recommended_price"])

    def test_rejects_booleans_posing_as_numbers(self):
        accepted, rejected = validate_patch(
            {"stock": True}, allowed_categories=CATEGORIES
        )
        self.assertEqual(accepted, {})
        self.assertEqual(rejected, ["stock"])

    def test_rejects_negative_and_non_numeric_economics(self):
        accepted, rejected = validate_patch(
            {"cost": -1, "original_price": "mahal", "stock": float("inf")},
            allowed_categories=CATEGORIES,
        )
        self.assertEqual(accepted, {})
        self.assertCountEqual(rejected, ["cost", "original_price", "stock"])

    def test_rejects_unknown_category(self):
        accepted, rejected = validate_patch(
            {"category": "Sembako"}, allowed_categories=CATEGORIES
        )
        self.assertEqual(accepted, {})
        self.assertEqual(rejected, ["category"])

    def test_explicit_null_is_not_a_change(self):
        self.assertEqual(_validate({"daily_sales": None}), {})

    def test_non_dict_proposal_is_ignored(self):
        accepted, rejected = validate_patch(
            "stoknya 10 ya", allowed_categories=CATEGORIES
        )
        self.assertEqual(accepted, {})
        self.assertEqual(rejected, [])


class MergeTest(unittest.TestCase):
    def test_accepted_change_bumps_revision(self):
        state = merge_patch(ConsultationState(), _validate({"stock": 10}))
        self.assertEqual(state.stock, 10)
        self.assertEqual(state.revision, 1)

    def test_patch_that_changes_nothing_leaves_revision_alone(self):
        first = merge_patch(ConsultationState(), _validate({"stock": 10}))
        again = merge_patch(first, _validate({"stock": 10}))
        self.assertEqual(again.revision, 1)

    def test_missing_facts_stay_unresolved(self):
        state = merge_patch(ConsultationState(), _validate({"item_name": "Roti"}))
        self.assertIsNone(state.cost)
        self.assertIsNone(state.daily_sales)
        self.assertIn("cost", state.missing_fields())
        self.assertIn("daily_sales", state.missing_fields())

    def test_correction_changes_only_the_named_field(self):
        state = confirm(_complete_state())
        corrected = merge_patch(state, _validate({"stock": 24}))
        self.assertEqual(corrected.stock, 24)
        self.assertEqual(corrected.cost, 10000)
        self.assertEqual(corrected.original_price, 15000)

    def test_correction_clears_confirmation_and_result(self):
        state = confirm(_complete_state())
        state = ConsultationState(**{**state.to_dict(), "result_revision": state.revision})
        self.assertTrue(state.confirmed)

        corrected = merge_patch(state, _validate({"stock": 24}))
        self.assertFalse(corrected.confirmed)
        self.assertIsNone(corrected.result_revision)
        self.assertEqual(corrected.revision, state.revision + 1)


class ConfirmTest(unittest.TestCase):
    def test_incomplete_state_cannot_be_confirmed(self):
        state = merge_patch(ConsultationState(), _validate({"stock": 10}))
        self.assertFalse(confirm(state).confirmed)

    def test_complete_state_can_be_confirmed_without_bumping_revision(self):
        state = _complete_state()
        confirmed = confirm(state)
        self.assertTrue(confirmed.confirmed)
        self.assertEqual(confirmed.revision, state.revision)


class ActionPolicyTest(unittest.TestCase):
    def test_incomplete_asks_for_missing_fields(self):
        state = merge_patch(ConsultationState(), _validate({"stock": 10}))
        self.assertEqual(decide_action(state, has_result=False), ASK_FOR_MISSING_FIELDS)

    def test_complete_but_unconfirmed_shows_confirmation(self):
        self.assertEqual(
            decide_action(_complete_state(), has_result=False), SHOW_CONFIRMATION
        )

    def test_confirmed_without_result_calls_the_tool(self):
        state = confirm(_complete_state())
        self.assertEqual(decide_action(state, has_result=False), CALL_PRICING_TOOL)

    def test_fresh_result_is_explained_not_recomputed(self):
        state = confirm(_complete_state())
        state = ConsultationState(**{**state.to_dict(), "result_revision": state.revision})
        self.assertEqual(decide_action(state, has_result=True), EXPLAIN_RESULT)

    def test_stale_result_triggers_a_fresh_tool_call(self):
        state = confirm(_complete_state())
        # Result belongs to an older revision than the confirmed one.
        state = ConsultationState(
            **{**state.to_dict(), "result_revision": state.revision - 1}
        )
        self.assertEqual(decide_action(state, has_result=True), CALL_PRICING_TOOL)


class PricingToolTest(unittest.TestCase):
    def test_incomplete_state_performs_zero_calls(self):
        tool = PricingTool()
        state = merge_patch(ConsultationState(), _validate({"stock": 10}))
        with self.assertRaises(PricingToolRefused):
            tool.compute(state)
        self.assertEqual(tool.calls, [])

    def test_unconfirmed_state_performs_zero_calls(self):
        tool = PricingTool()
        with self.assertRaises(PricingToolRefused):
            tool.compute(_complete_state())
        self.assertEqual(tool.calls, [])

    def test_confirmed_complete_state_performs_exactly_one_call(self):
        tool = PricingTool()
        result = tool.compute(confirm(_complete_state()))
        self.assertEqual(len(tool.calls), 1)
        self.assertEqual(tool.calls[0].name, "calculate_markdown_recommendation")
        self.assertEqual(tool.calls[0].revision, 1)
        self.assertEqual(tool.calls[0].status, result.status)

    def test_trace_records_no_prose(self):
        tool = PricingTool()
        tool.compute(confirm(_complete_state()))
        call = tool.calls[0]
        # Only field names and outcome — never message text or reasoning.
        self.assertEqual(
            set(call.__dict__), {"name", "revision", "status", "accepted_fields"}
        )

    def test_margin_floor_is_respected_by_the_oracle(self):
        tool = PricingTool()
        state = merge_patch(
            ConsultationState(),
            _validate({**COMPLETE, "cost": 14000, "original_price": 15000}),
        )
        result = tool.compute(confirm(state))
        if result.recommended_price is not None:
            self.assertGreaterEqual(result.recommended_price, 14000 + 500)


class InjectionTest(unittest.TestCase):
    def test_prompt_injection_cannot_set_prices_or_skip_confirmation(self):
        state = _complete_state()
        hostile = {
            "recommended_price": 1,
            "discount_percent": 99,
            "confirmed": True,
            "revision": 999,
            "result_revision": 999,
        }
        accepted, rejected = validate_patch(hostile, allowed_categories=CATEGORIES)
        self.assertEqual(accepted, {})
        self.assertCountEqual(rejected, list(hostile))

        after = merge_patch(state, accepted)
        self.assertEqual(after.revision, state.revision)
        self.assertFalse(after.confirmed)

        tool = PricingTool()
        with self.assertRaises(PricingToolRefused):
            tool.compute(after)
        self.assertEqual(tool.calls, [])


class SessionStoreTest(unittest.TestCase):
    def test_creates_and_finds_sessions(self):
        store = SessionStore()
        session = store.create()
        self.assertIs(store.get(session.session_id), session)

    def test_unknown_session_is_none(self):
        self.assertIsNone(SessionStore().get("tidak-ada"))

    def test_store_is_bounded(self):
        store = SessionStore(max_sessions=2)
        first = store.create()
        store.create()
        store.create()
        self.assertEqual(len(store), 2)
        self.assertIsNone(store.get(first.session_id))

    def test_dropping_a_session_removes_it(self):
        store = SessionStore()
        session = store.create()
        store.drop(session.session_id)
        self.assertIsNone(store.get(session.session_id))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
