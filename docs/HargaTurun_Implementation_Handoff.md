# HargaTurun — Implementation Handoff

> **Last revised:** conversational-copilot specification pivot
> **Target branch:** `main`
> **Purpose:** separate implemented facts from the newly approved product direction

## 1. Current state

This branch adds a working one-shot baseline around the existing pricing core: FastAPI/SQLite endpoints, an OpenAI-compatible parse/write model client, and an HTTP-backed Flutter web/PWA. It still does **not** contain the bounded multi-turn orchestrator, `POST /api/chat`, conversational chat UI, agent trace, complete Docker Compose stack, or measured direct-chat comparison specified by the new plan.

The product direction has changed from this one-shot baseline to a **constrained multi-turn pricing copilot**. The baseline remains useful and runnable, but should not be described as the completed agentic workflow. The pricing formula and safety boundary remain unchanged.

Do not describe planned conversational behavior as implemented until the corresponding code and tests land.

## 2. Authoritative document order

1. `HargaTurun_Penyisihan_SRS.md` — authoritative preliminary scope and acceptance contract.
2. `HargaTurun_Agentic_Workflow_Plan.md` — AI customization, workflow implementation, evaluation, and evidence plan.
3. `HargaTurun_Project_Spec.md` — product value, UX, architecture, and cross-round vision.
4. `HargaTurun_Final_SRS.md` — final-round marketplace extension only.
5. `HargaTurun_FineTuning_Plan.md` — superseded optional historical runbook; not current methodology.

The AIC technical guide records both the original fine-tuning wording and the later organizer clarification permitting advanced customization such as agentic workflows.

## 3. Implemented on `main`

### 3.1 Deterministic pricing oracle

`backend/hargaturun/pricing.py` is the sole numerical authority. It:

- validates confirmed economics and domains;
- computes supply pressure and expiry urgency;
- applies category bias;
- enforces discount bounds and a margin floor;
- returns recommendation, no-action, or invalid/warning outcomes;
- computes price, timing, projections, and confidence;
- has no model, network, database, or prose dependency.

The same confirmed input produces the same numbers.

### 3.2 Existing model contracts

`backend/hargaturun/schemas.py` currently defines one-shot parse and writer contracts plus strict validators. Useful pieces to preserve:

- exact allowed fields and categories;
- strict types and numeric domains;
- missing-field bookkeeping;
- engine-result serialization;
- numerical-claim faithfulness checks;
- status-appropriate writing checks.

These contracts are an implementation baseline, not the final chatbot API. They must evolve into:

- `extract_patch(message, current_state)` output;
- conversational intent and ambiguity output;
- revisioned state transitions;
- the existing tool-result-to-writer boundary.

### 3.3 Tests

The existing core suite validates oracle behavior and parse/write schema constraints:

```bash
cd backend
python3 -m unittest discover -s tests -v
```

Run it before and after every agentic-workflow change. The pivot must not weaken pricing invariants.

## 4. Approved target architecture

```text
Chat message
   -> model proposes field patch + intent
   -> code validates and merges revisioned state
   -> orchestrator selects an allowed action
      -> ask for missing facts
      -> show confirmation
      -> call typed pricing tool
      -> explain/revise faithful wording
      -> redirect out of scope
   -> output validator
   -> one repair attempt or safe fallback
```

Key invariants:

1. The model never owns authoritative state.
2. The model never sets confirmation or revision fields.
3. Missing or ambiguous economic facts remain unknown.
4. The pricing tool cannot run before explicit confirmation.
5. A correction invalidates old confirmation and result.
6. The writer cannot introduce unsupported numbers.
7. Repair is bounded to one attempt.
8. Out-of-domain requests preserve state and do not call tools.
9. No hidden chain-of-thought is stored or displayed; traces contain actions, validations, transitions, and tool metadata only.

## 5. Why the pivot is useful

The previous one-shot path usually detoured into a form because realistic messages omitted `daily_sales` or `total_shelf_life`. The conversational flow makes this expected behavior part of the product rather than a parsing failure:

- capture everything supplied;
- ask for all remaining gaps concisely;
- accept natural corrections;
- present a structured review;
- calculate only after confirmation.

The selling point is therefore not “chat.” It is turning a merchant conversation into a governed, explainable pricing decision.

## 6. Competition-customization position

The project selects the organizer-clarified **Agentic Workflow** route. A base Qwen3.5-4B artifact is acceptable only as one component of a demonstrably customized system. The compliance evidence must include:

- source implementation of state, actions, tool routing, and validation;
- test coverage for illegal transitions and safety cases;
- sanitized execution traces;
- direct-chat versus workflow evaluation on the same held-out cases;
- honest model/config/artifact identity;
- organizer announcement evidence and preferably written architecture confirmation.

A chat UI plus one prompt is not sufficient. LoRA is optional and is not currently claimed.

## 7. Implementation sequence

### Phase 1 — contracts

1. Define `ConversationState`, required fields, `revision`, confirmation, and result revision.
2. Define user actions and the orchestrator's action allowlist.
3. Define `ExtractPatchOutput` and update validators.
4. Freeze prompt/schema version names.

**Exit:** pure contract tests pass.

### Phase 2 — pure state and tool layer

1. Implement the state reducer/merge policy.
2. Invalidate confirmation/result on accepted changes.
3. Wrap `pricing.compute` in a typed `PricingTool`.
4. Add transition guards and sanitized trace events.

**Exit:** no model/network is needed to test all transitions and tool preconditions.

### Phase 3 — model integration

1. Implement patch extraction with current state and the latest message.
2. Validate and repair once.
3. Reuse/adapt the writer and numerical-faithfulness validator.
4. Add safe question/template and numbers-only fallbacks.

**Exit:** fake-model integration tests cover valid, malformed, unavailable, and adversarial outputs.

### Phase 4 — chat API and UI

1. Add synchronous `POST /api/chat`.
2. Build chat, known-field summary, grouped questions, confirmation card, result cards, and form fallback.
3. Keep preliminary mode free of auth, marketplace, persistent chat, analytics, and background jobs.

**Exit:** complete single-item consultation and correction/recalculation flow works locally.

### Phase 5 — evidence and packaging

1. Create manually reviewed held-out multi-turn consultations.
2. Implement direct-chat and workflow evaluators.
3. Save raw reports and representative traces.
4. Build one full application Compose path.
5. Validate from a clean clone.
6. Update proposal and record videos only after the exact submission build passes.

## 8. Tests that must be added

- complete first message still requires explicit confirmation;
- incomplete message asks a grouped question without tool use;
- correction changes only grounded fields;
- ambiguous correction preserves old value;
- confirmation with a missing field is impossible;
- calculate before confirmation is impossible;
- one confirmed revision calls the pricing tool exactly once;
- a changed revision cannot reuse an old result;
- unsupported writer numbers are rejected;
- second writer failure produces safe fallback;
- model outage preserves validated state;
- out-of-domain requests preserve state and call no tool;
- repeated confirmed state gives identical numerical output.

## 9. Open product and engineering decisions

Resolve these before implementation branches diverge:

1. **Client-carried versus server session state:** preliminary SRS permits client-carried validated state to avoid persistence. If server sessions are chosen, keep them transient and document cleanup.
2. **Explicit tool call syntax:** the typed backend adapter is required. Native model function-calling syntax is optional and should be chosen only if llama.cpp/model support is reliable.
3. **Model fallback:** decide whether confirmed structured input can always return numbers-only when writing is unavailable. Recommended: yes.
4. **Frontend scope:** preliminary mode must hide all marketplace/auth screens even if other branches contain them.
5. **Organizer confirmation:** ask whether multi-turn clarification inside one bounded consultation satisfies the preliminary “single core interaction” boundary.

## 10. Known documentation caveats

- `HargaTurun_FineTuning_Plan.md` retains detailed BF16 LoRA material for history and optional future experimentation. Its proposal snippets are not current.
- Source docstrings/tests may still reference the old Fine-Tuning Plan. Rename those references only when implementing the new contracts; do not change tested behavior merely for wording.
- `HargaTurun_LLM_Server_Setup.md` is a serving guide, not proof of agentic customization.
- The current full rulebook source linked by some older material may not be present; retain official source evidence separately.

## 11. Immediate next task

Implement Phase 1 and Phase 2 before changing the UI. The first demonstrable milestone should be a model-independent orchestrator test showing:

```text
message patch -> validated state -> grouped gaps -> confirmation
-> exactly one PricingTool call -> result -> correction -> stale result invalidated
```

That milestone establishes the core product and competition claim while keeping the existing pricing engine stable.
