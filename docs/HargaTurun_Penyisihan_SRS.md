# HargaTurun — Software Requirements Specification: Penyisihan MVP

> **Status:** Authoritative preliminary-round specification
> **Version:** 2.0 — constrained conversational copilot
> **Scope:** One bounded, synchronous, single-item pricing consultation
> **Companion documents:** [Project Spec](HargaTurun_Project_Spec.md), [Agentic Workflow Plan](HargaTurun_Agentic_Workflow_Plan.md), [AIC Technical Guide](AIC_Technical_Guide.md)

## 1. Purpose

HargaTurun helps an Indonesian food UMKM owner decide whether and how to discount one at-risk item. Instead of requiring a long form or interpreting one isolated sentence, the MVP provides a bounded chat consultation:

1. capture facts from colloquial Indonesian;
2. ask only for missing or ambiguous facts;
3. show an editable structured confirmation;
4. call a deterministic pricing tool after explicit confirmation;
5. explain the resulting recommendation, no-action decision, or warning.

The chatbot is a user interface to a governed agentic workflow. It is not a general assistant, and the language model is never the pricing authority.

## 2. Competition interpretation and scope rule

The original technical guide said pretrained models must be fine-tuned. The organizer later clarified that the underlying requirement is meaningful customization rather than an ordinary zero-shot call, and that advanced adaptation methods such as RAG, agentic workflows, tool/function calling, and integrated trained supporting models may satisfy it.

HargaTurun selects the **agentic workflow** route. Qualification evidence must show implemented orchestration, state, tool use, validation, and measured behavior. The team should retain the original organizer announcement and any written confirmation with submission materials.

The preliminary MVP remains narrowly scoped: one vendor consultation, synchronous turns, static model parameters, no background autonomy, and local reproducibility.

## 3. Goals and exclusions

### 3.1 Goals

- Let a vendor describe one item naturally in Bahasa Indonesia.
- Capture multiple facts from each message and support later corrections.
- Never guess cost, stock, sales rate, expiry, or other consequential facts.
- Require explicit confirmation of complete structured data.
- Use deterministic Python—not the model—for every number and safety outcome.
- Return an understandable action and faithful promotional-copy preview.
- Demonstrate customization beyond a direct zero-shot chatbot.

### 3.2 Explicit exclusions

The preliminary build must not include:

- generic business advice or unrestricted chat;
- publishing, deal feeds, claims, redemption, or stock reservation;
- authentication, user accounts, persistent chat history, analytics, or usage history;
- background jobs, autonomous scheduled agents, feedback loops, or auto-tuning;
- RAG, internet search, OCR, voice, multi-item processing, payment, maps, or delivery;
- native-only packaging that prevents the required local browser demonstration.

A static promo/deal-card preview is allowed as output from the consultation.

## 4. User experience

### 4.1 Primary interface

The primary interface combines:

- chat messages;
- a compact “data yang sudah dicatat” summary;
- grouped missing-field prompts/chips;
- an editable confirmation card;
- recommendation/no-action/warning cards;
- a structured-form fallback.

The assistant should extract all facts present in a message and ask for all remaining required facts together where practical. It should not force a one-question-per-field interview.

### 4.2 Supported intents

| Intent | Behavior |
|---|---|
| Start consultation | Create an empty state and extract supplied facts |
| Supply information | Propose and validate updates to unknown fields |
| Correct information | Replace specified fields, increment revision, invalidate confirmation/result |
| Confirm data | Mark the current complete revision confirmed |
| Calculate/recalculate | Invoke the pricing tool only for the confirmed current revision |
| Explain result | Explain the existing authoritative result without changing it |
| Revise promo wording | Rewrite wording while preserving authoritative status and numbers |
| Out of scope | Redirect to single-item stock pricing without changing state |

### 4.3 Example

```text
Vendor: Ada 20 roti tawar, lusa expired. Harga 15rb, modal 10rb,
        biasanya laku 4 sehari.
Assistant: Aku mencatat ... Berapa total masa simpan dan kategorinya?
Vendor: Bakery, masa simpan 5 hari.
Assistant: [editable confirmation card]
Vendor: Konfirmasi dan hitung.
Assistant: [pricing tool called] [recommendation card + explanation]
Vendor: Koreksi, stoknya 24.
Assistant: Stok diperbarui ke 24. Rekomendasi sebelumnya sudah tidak berlaku.
           [updated confirmation card]
```

## 5. Conversation state and transitions

### 5.1 State contract

```json
{
  "item_name": null,
  "category": null,
  "original_price": null,
  "cost": null,
  "stock": null,
  "days_remaining": null,
  "daily_sales": null,
  "total_shelf_life": null,
  "shop_name": null,
  "confirmed": false,
  "revision": 0
}
```

Required fields are all fields except `shop_name`. Allowed categories are `Bakery`, `Prepared Food`, `Dairy`, `Beverage`, `Produce`, `Snack`, `Canned`, and `Other`.

### 5.2 State rules

1. The model returns a **proposed patch**, never an authoritative full state.
2. Application code validates type, domain, source text, and allowed fields before merging.
3. Ambiguous or absent values remain `null`.
4. Accepted changes increment `revision`.
5. Any accepted change sets `confirmed=false` and invalidates an existing result.
6. Confirmation is valid only for the current revision.
7. Tool input is constructed from validated state, never directly from model output.
8. Transcript context may help interpretation but cannot override state.

### 5.3 Workflow states

```text
START
  -> COLLECTING
  -> READY_TO_CONFIRM
  -> CONFIRMED
  -> CALCULATING
  -> RECOMMENDATION | NO_ACTION | WARNING

Any state -> OUT_OF_SCOPE (business state unchanged)
Any model/tool error -> SAFE_FAILURE (validated state preserved)
Any accepted correction -> COLLECTING or READY_TO_CONFIRM
```

## 6. Functional requirements

| ID | Requirement |
|---|---|
| P-FR-1 | The UI starts one consultation for one item and accepts natural Indonesian messages. |
| P-FR-2 | A message may supply or correct multiple supported fields. |
| P-FR-3 | The model operation returns only a schema-constrained proposed patch, ambiguities, and recognized intent. |
| P-FR-4 | Unknown, unsupported, or ambiguous business values are not merged as facts. |
| P-FR-5 | The assistant shows known values and all current gaps after a meaningful update. |
| P-FR-6 | The assistant groups missing-field questions where practical. |
| P-FR-7 | Complete data produces an editable confirmation card, not an automatic calculation. |
| P-FR-8 | The pricing tool cannot run without explicit confirmation of the current revision. |
| P-FR-9 | `pricing.compute` is the sole authority for discount, price, timing, projections, confidence, no-action, and warnings. |
| P-FR-10 | The writer receives the confirmed state and complete authoritative engine result. |
| P-FR-11 | Generated prose may mention only numbers present in confirmed state or engine output. |
| P-FR-12 | Invalid prose triggers at most one validator-guided repair, followed by a safe fallback. |
| P-FR-13 | A correction invalidates old confirmation and old recommendation. |
| P-FR-14 | Out-of-domain chat returns a redirect and does not modify state or call tools. |
| P-FR-15 | A form fallback can produce the same validated state and pricing result. |
| P-FR-16 | The result provides `recommendation`, `no_action`, or `warning`; these are mutually exclusive. |
| P-FR-17 | The UI can display a sanitized trace in evaluation mode: state transition, validation result, tool name, and status—never hidden chain-of-thought. |
| P-FR-18 | All turns are synchronous; no job continues after the response is returned. |

## 7. Architecture

```text
Browser chat + structured cards
          |
          v
FastAPI chat endpoint
          |
          +--> ConversationOrchestrator
                  |-- validate/merge state patch
                  |-- enforce transition guards
                  |-- record sanitized trace
                  |
                  +--> local Qwen model: extract patch / write language
                  +--> PricingTool: pricing.compute()
                  +--> output validators and safe fallback
```

### 7.1 Language model responsibilities

The local base model is adapted through the workflow to:

- extract explicit facts and corrections from Indonesian messages;
- identify ambiguity without resolving it by guessing;
- generate concise, context-appropriate wording;
- explain the authoritative engine result;
- write or revise faithful promo copy.

It does not select arbitrary tools, own state, confirm on behalf of the user, or calculate prices.

### 7.2 Pricing tool

`PricingTool.compute` wraps the existing pure `pricing.compute(PricingInput)` implementation. The wrapper provides a stable name, typed arguments, trace event, and serializable result. The underlying formula and tests remain authoritative.

### 7.3 Model serving

- Qwen3.5-4B through local llama.cpp/OpenAI-compatible chat completion.
- Static documented parameters, including temperature `0`.
- Thinking disabled.
- Schema-constrained outputs.
- No inference-time internet dependency after artifact setup.

A base model is acceptable for the selected agentic route. A fine-tuned model may be substituted only after measured evaluation; documentation must identify which artifact is actually running.

## 8. API contract

### 8.1 `POST /api/chat`

Each request carries the current transient state, the new user message or explicit UI action, and the latest result identifier when relevant. The preliminary backend need not persist sessions.

```json
{
  "message": "stoknya ternyata 24",
  "action": "message",
  "state": {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 20,
    "days_remaining": 2,
    "daily_sales": 4,
    "total_shelf_life": 5,
    "shop_name": null,
    "confirmed": true,
    "revision": 2
  }
}
```

Allowed `action` values: `message`, `confirm`, `calculate`, `explain`, `revise_promo`, and `reset`.

Representative response:

```json
{
  "status": "ready_to_confirm",
  "assistant_message": "Stok diperbarui menjadi 24. Rekomendasi sebelumnya tidak lagi berlaku.",
  "state": {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 24,
    "days_remaining": 2,
    "daily_sales": 4,
    "total_shelf_life": 5,
    "shop_name": null,
    "confirmed": false,
    "revision": 3
  },
  "missing_fields": [],
  "result": null,
  "ui": { "show_confirmation": true },
  "trace_id": "..."
}
```

Allowed statuses: `collecting`, `ready_to_confirm`, `confirmed`, `recommendation`, `no_action`, `warning`, `out_of_scope`, `model_unavailable`, and `invalid_request`.

The server validates all client-carried state. A production extension may sign state, but account/session persistence is not required for the preliminary local demo.

### 8.2 Result shape

For `recommendation`, `result` contains the engine recommendation, explanation, promo copy, and static preview. `no_action` and `warning` never contain a publishable discounted offer.

## 9. Non-functional requirements

| ID | Requirement |
|---|---|
| P-NFR-1 | Warm turn P95 and full consultation latency are measured on declared hardware; target each normal turn under 10 seconds. |
| P-NFR-2 | Full preliminary stack starts with one documented `docker compose up --build` command. |
| P-NFR-3 | Inference is local/offline after one-time image/model setup. |
| P-NFR-4 | Prompt versions, model identity/hash, chat template, and decoding parameters are recorded. |
| P-NFR-5 | Confirmed identical state yields byte-identical numerical engine output. |
| P-NFR-6 | A model failure preserves state and cannot create a recommendation. |
| P-NFR-7 | No deals, users, chat transcripts, or analytics are persisted. |
| P-NFR-8 | Core UI and responses use clear Bahasa Indonesia. |

## 10. Acceptance tests

### 10.1 Conversation and state

- One message containing five facts populates all five fields.
- Missing cost and sales rate remain `null` and are requested together.
- `15rb`, `lusa`, and supported unit variants normalize correctly.
- “stoknya bukan 20, tapi 24” changes only stock, increments revision, and invalidates confirmation/result.
- An ambiguous correction does not overwrite an existing confirmed value.
- An out-of-domain question leaves business state byte-identical.

### 10.2 Tool gating and pricing safety

- Calculate before confirmation is rejected without a tool call.
- Confirmation with missing fields is rejected without a tool call.
- Confirmed complete state causes exactly one pricing-tool call.
- Tool arguments exactly match confirmed state.
- Repeating identical confirmed state produces identical numbers.
- Margin floor, expired item, no-action, and fire-sale cases match pricing tests.

### 10.3 Writing safety

- The writer receives the exact engine result.
- Unsupported numerical claims are rejected.
- No-action and warning never generate discount promo copy.
- One invalid response triggers one repair at most.
- A second failure returns a safe template or numbers-only result.

### 10.4 End-to-end demo

The proof path must show, without hidden steps:

1. natural first message;
2. grouped clarification;
3. structured confirmation card;
4. sanitized trace showing the pricing-tool call;
5. recommendation card;
6. correction and invalidation/recalculation;
7. one safe out-of-domain or model-failure case.

## 11. AI-customization evaluation

Use a held-out, manually reviewed set of representative Indonesian multi-turn consultations. Compare:

1. a direct base-model chatbot with a single HargaTurun system prompt;
2. the same base model inside the customized workflow.

Report:

- valid schema rate;
- per-field and complete-state accuracy;
- correction accuracy;
- missing/ambiguous recall and false completion;
- premature/illegal tool-call count;
- stale-result reuse count;
- unsupported numerical claims;
- engine-status faithfulness;
- completion rate and turns to confirmation;
- P50/P95 latency.

No target may be reported as achieved until the raw report exists. Evaluation artifacts and required evidence are defined in the Agentic Workflow Plan.

## 12. Traceability to competition expectations

| Expectation | HargaTurun response |
|---|---|
| Meaningful AI customization | Domain-specific agentic workflow with state, tools, validators, confirmation, repair, and evaluation |
| Core AI interaction | One bounded single-item consultation |
| Static parameters | Fixed model/prompt/config versions and deterministic pricing |
| Synchronous backend | One request/response per turn; no background agent |
| Local reproducibility | Docker Compose and local model serving |
| Scope discipline | No auth, marketplace, persistence, analytics, RAG, or bulk features in preliminary build |
| Explainability | Visible structured state, tool-derived result, concise explanation, sanitized trace |

## 13. Deferred final work

If the team advances, `HargaTurun_Final_SRS.md` adds publish, browse, claim, and redeem around a completed recommendation. The preliminary chatbot and pricing safety contracts remain unchanged.
