# HargaTurun — Product Specification

> **Version:** 3.0 — Conversational pricing copilot pivot
> **Competition:** COMPFEST 18 AI Innovation Challenge
> **Theme:** AI for the Backbone of the Economy — Smart Commerce
> **Status:** Product and architecture target; implementation claims are tracked separately in the handoff

## 1. Product definition

HargaTurun is a **conversational inventory-rescue copilot** for Indonesian food UMKM. A vendor describes one at-risk product in everyday Indonesian. The copilot extracts the facts already given, asks only for missing or ambiguous economic inputs, presents an editable confirmation card, calls a deterministic pricing tool, and explains the recommended action.

It is not a generic chatbot and not a model that guesses prices. It is a bounded decision workflow combining language understanding with explicit application state, human confirmation, deterministic tools, and output guardrails.

### 1.1 Problem

Small food businesses routinely decide markdown timing and depth from intuition. Forms and enterprise revenue-management systems are too heavy for merchants who work from a phone and think in phrases such as:

> “Ada 20 roti, lusa expired, modal sepuluh ribu, biasanya laku empat sehari.”

The business needs an immediate answer without sacrificing margin or trusting hallucinated arithmetic.

### 1.2 Product promise

> **Ceritakan stokmu seperti biasa. HargaTurun membantu melengkapi datanya, menghitung tindakan yang aman, dan menjelaskan apa yang harus dilakukan.**

### 1.3 Differentiation

The defensible value is the combination of:

1. colloquial Indonesian multi-turn capture;
2. backend-owned structured state rather than model-owned memory;
3. refusal to guess missing economic facts;
4. explicit vendor confirmation;
5. deterministic pricing with hard margin and expiry rules;
6. conversational corrections and safe recalculation;
7. explainable output and ready-to-use promo copy.

A plain chat interface or a single “act as a pricing expert” prompt is not sufficient.

## 2. Users and jobs

### 2.1 Primary user

An owner or manager of a warung, bakery, café, home food business, or other Indonesian food UMKM who:

- makes pricing decisions personally;
- has low-to-moderate technical literacy;
- commonly uses conversational mobile interfaces;
- lacks reliable markdown guidance;
- needs a result in minutes, not a dashboard.

### 2.2 Jobs to be done

| Job | Product response |
|---|---|
| Describe stock quickly | Natural Indonesian chat, including abbreviations and reordered facts |
| Avoid repetitive forms | Capture all facts in one message and ask only for gaps |
| Correct misunderstandings | Apply a validated state patch and show the updated card |
| Protect margin | Pricing tool enforces the margin floor and discount bounds |
| Know when to act | Tool returns recommendation, no-action, or warning |
| Trust the result | Confirmation, visible inputs, deterministic numbers, concise explanation |
| Promote the item | Generate faithful promotional copy from the authoritative result |

### 2.3 Anti-users and out-of-domain requests

The preliminary assistant is not for large retail chains, non-food pricing, accounting, legal advice, health/safety certification, generic business coaching, customer support, or unrestricted conversation. It redirects unsupported requests to the single-item pricing consultation.

## 3. Product experience

### 3.1 Primary consultation

```text
START
  -> COLLECTING
  -> READY_TO_CONFIRM
  -> CONFIRMED
  -> CALCULATING
  -> RECOMMENDATION | NO_ACTION | WARNING
```

Additional transitions:

- any accepted correction after `READY_TO_CONFIRM` returns to `COLLECTING` or `READY_TO_CONFIRM`;
- any accepted correction after a result invalidates confirmation and the old result;
- out-of-domain input produces `OUT_OF_SCOPE` without changing business state;
- model/tool failure produces `SAFE_FAILURE`, preserving validated state.

### 3.2 Example

1. Vendor: “20 roti tawar, lusa expired, harga 15rb, modal 10rb, laku 4 sehari.”
2. The assistant captures five fields and asks for category/total shelf life if needed.
3. The vendor answers in one message.
4. The assistant shows an editable confirmation card.
5. The vendor confirms and requests calculation.
6. The orchestrator calls the pricing tool.
7. The assistant displays a recommendation card and a concise explanation.
8. If the vendor says “stoknya ternyata 24,” the old result is marked stale and must be reconfirmed/recalculated.

### 3.3 User interface

Chat bubbles provide natural interaction, but structured components provide trust:

- known-field summary after meaningful updates;
- missing-field chips or grouped prompt;
- editable confirmation card;
- recommendation/no-action/warning card;
- `Ubah data`, `Konfirmasi & hitung`, and `Hitung ulang` controls;
- optional structured-form fallback;
- visible safe-error state that never loses confirmed input.

The assistant should ask for all currently missing fields in one concise turn where practical, rather than interrogating one field at a time.

## 4. Authoritative business state

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

Required before calculation: `item_name`, `category`, `original_price`, `cost`, `stock`, `days_remaining`, `daily_sales`, and `total_shelf_life`. `shop_name` is optional.

Rules:

- the model may propose only allowed fields;
- application validators accept, reject, or mark a proposed value ambiguous;
- missing values remain `null`;
- accepted corrections increment `revision`;
- corrections set `confirmed=false` and invalidate prior results;
- transcript text is context, not the source of truth;
- the pricing tool receives only validated, complete, explicitly confirmed state.

## 5. Agentic architecture

### 5.1 Components

| Component | Owns | Must not own |
|---|---|---|
| Language model | Proposed field patches and concise Indonesian language | Prices, state truth, confirmation, unrestricted actions |
| Orchestrator | State machine, allowed actions, tool routing, trace, retry limit | Pricing arithmetic |
| State validator | Types, domains, allowed fields, ambiguity, merge policy | Natural-language generation |
| Pricing tool | All numerical recommendations and safety outcomes | Chat wording or persistence |
| Output validator | Schema, engine-status faithfulness, supported numbers | New business facts |
| UI | Conversation and structured controls | Recomputing or overriding tool results |

### 5.2 Allowed agent actions

- `ASK_FOR_MISSING_FIELDS`
- `SHOW_CONFIRMATION`
- `CALL_PRICING_TOOL`
- `EXPLAIN_RESULT`
- `REVISE_PROMO_COPY`
- `OUT_OF_SCOPE`
- `SAFE_FAILURE`

There are no arbitrary shell, network, database, purchasing, messaging, or publication tools in the preliminary assistant.

### 5.3 Model calls

The initial implementation may use two schema-constrained model operations:

1. **`extract_patch(message, current_state)`** → proposed updates, ambiguities, and user intent.
2. **`write_response(state, engine_result, response_kind)`** → explanation/promo text using only authoritative values.

The orchestrator, not the model, decides whether prerequisites permit the pricing tool call. Native function calling is optional and must not be claimed unless implemented and tested.

### 5.4 Pricing tool

`pricing.compute(PricingInput)` remains a pure function and the sole numerical authority. It computes:

- no-action, recommendation, or warning status;
- discount and recommended price;
- timing;
- expected sell-through and revenue;
- expected loss without action;
- confidence wording;
- margin-floor and expiry safety outcomes.

Core guarantees include bounded discounts, deterministic output, and no recommendation below the documented margin floor. The implementation and tests—not model prose—are authoritative for exact arithmetic.

### 5.5 Guardrails

- JSON Schema on every model operation.
- Exact allowed-field list for patches.
- Deterministic normalization for Rupiah, quantities, and relative-day expressions.
- Explicit confirmation gate before calculation.
- Unsupported numerical claims rejected from generated prose.
- At most one validator-guided repair attempt.
- Safe template or numbers-only fallback when writing fails.
- Trace event for each transition and tool invocation, with no hidden chain-of-thought.

## 6. Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | The user can begin one single-item consultation with a natural Indonesian message. |
| FR-2 | The system extracts every explicit supported fact from a message into a proposed state patch. |
| FR-3 | Missing or ambiguous economic facts remain unknown and are requested; the system never silently invents them. |
| FR-4 | The user can correct one or more captured fields in a later message. |
| FR-5 | The UI shows current structured state and all missing fields. |
| FR-6 | A calculation requires complete state and explicit confirmation. |
| FR-7 | The orchestrator invokes the deterministic pricing tool exactly once per confirmed revision unless the user explicitly recalculates. |
| FR-8 | The model cannot override tool status or numerical output. |
| FR-9 | A successful result includes action, price/discount when applicable, timing, projections, explanation, and promo preview. |
| FR-10 | A no-action result does not advertise a discount. |
| FR-11 | A warning produces no publishable recommendation. |
| FR-12 | A correction after a result marks that result stale and requires reconfirmation. |
| FR-13 | Out-of-domain requests are redirected without corrupting state. |
| FR-14 | The user can switch to an equivalent structured form fallback. |
| FR-15 | All requests are synchronous; there is no background autonomous agent. |
| FR-16 | The system exposes a sanitized execution trace for evaluation/debug mode. |

## 7. Non-functional requirements

| ID | Target |
|---|---|
| NFR-1 | Warm conversational turn target under 10 seconds on declared hardware; report measured P50/P95. |
| NFR-2 | Static documented inference parameters and fixed prompt/config versions. |
| NFR-3 | Local inference with no internet dependency after setup. |
| NFR-4 | Full preliminary stack starts through one documented Docker Compose command. |
| NFR-5 | Bahasa Indonesia is the default interaction language. |
| NFR-6 | No persistent accounts, chat history, deals, or analytics in the preliminary build. |
| NFR-7 | Same confirmed structured state always yields identical numerical output. |
| NFR-8 | Errors preserve validated state and never fabricate a recommendation. |

## 8. AI customization and qualification

The project uses the organizer-approved **agentic workflow** adaptation route rather than treating LoRA as mandatory. Customization is demonstrated by domain-specific orchestration, tools, state, confirmation, validators, and repair behavior—not by UI branding or a long system prompt.

Required evidence:

- workflow and state diagrams;
- source-level tool and transition contracts;
- representative execution traces;
- direct-chat baseline versus workflow evaluation;
- prompt/config/model identity;
- test cases for correction, confirmation, tool gating, numerical faithfulness, and safe failure;
- an organizer clarification record retained with submission materials.

Parameter fine-tuning may be evaluated later if it solves measured language failures. It is not a substitute for the workflow and must not be claimed without real artifacts.

## 9. Round boundaries

### 9.1 Preliminary

In scope:

- bounded single-item chat;
- transient consultation state;
- confirmation and correction;
- deterministic pricing-tool call;
- explanation and promo preview;
- structured fallback;
- local Docker Compose demo.

Out of scope:

- authentication;
- persistent chat/history;
- publishing and consumer marketplace;
- claims and redemption;
- analytics and feedback loops;
- OCR, voice, multi-item processing;
- RAG or web search;
- background jobs and autonomous action.

### 9.2 Final extension

The final may attach the confirmed recommendation to a minimal publish/browse/claim/redeem loop as defined by the Final SRS. It must not weaken preliminary tool safety.

## 10. Evaluation and success metrics

Evaluate both individual capabilities and the end-to-end workflow on held-out, manually reviewed Indonesian consultations.

| Area | Metrics |
|---|---|
| State extraction | Per-field accuracy, exact complete-state match, correction accuracy |
| Missing facts | Missing/ambiguous recall, false-completion rate |
| Orchestration | Illegal transition count, premature tool-call count, stale-result reuse count |
| Pricing safety | Margin-floor violations, nondeterministic numerical outputs |
| Writing | Unsupported numerical claims, engine-status faithfulness, clarity review |
| Conversation | Turns to confirmed state, successful-consultation rate, out-of-domain handling |
| Operations | P50/P95 latency, startup time, model failures, memory use |

Compare at minimum:

1. direct base-model chatbot with one domain prompt;
2. the same base model inside the HargaTurun workflow.

This isolates the value of adaptation through orchestration. Report actual results only.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| “Chatbot” appears generic | Demonstrate explicit actions, state, tool traces, and baseline improvement |
| Model silently changes facts | Patch validation, visible cards, revision number, explicit confirmation |
| Too many turns | Extract all supplied facts and group missing questions |
| Hallucinated arithmetic | Model never computes; writer is checked against allowed numbers |
| Scope creep | Fixed intent/action allowlist and out-of-domain redirect |
| Model outage | Preserve state; form fallback and numbers-only result for confirmed structured input |
| Competition ambiguity | Preserve written organizer clarification and describe implementation honestly |

## 12. Delivery order

1. Freeze conversation-state and action contracts.
2. Implement deterministic state merge and transition guards.
3. Wrap `pricing.compute` behind a typed tool interface.
4. Implement schema-constrained extraction and writing calls.
5. Add trace events and safe repair/fallback behavior.
6. Build chat plus confirmation/result cards and form fallback.
7. Build held-out evaluation and direct-chat baseline.
8. Package and test the full preliminary Docker Compose path.
9. Update proposal and record videos from the verified build.

See the authoritative acceptance detail in `HargaTurun_Penyisihan_SRS.md` and the evidence plan in `HargaTurun_Agentic_Workflow_Plan.md`.
