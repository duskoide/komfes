# HargaTurun — Agentic Workflow Plan & Evidence Runbook

> **Version:** 1.0
> **Status:** Authoritative AI-customization plan for the conversational pivot
> **Selected adaptation route:** constrained agentic workflow with deterministic tool use
> **Not a completion claim:** implementation and measured reports are still required

## 1. Compliance thesis

The organizer clarification states that the intent of the model-customization rule is to prevent teams from submitting an unmodified zero-shot API call. It permits advanced adaptations including RAG, agentic workflows, tool/function calling, and integrated trained supporting models in addition to LoRA/QLoRA.

HargaTurun selects **agentic workflow** because it directly fits the product:

- conversation is decomposed into explicit domain actions;
- validated state is maintained outside the model;
- a deterministic pricing tool owns consequential arithmetic;
- the user confirms facts before calculation;
- model output is schema- and number-validated;
- invalid output receives one bounded repair attempt;
- behavior is evaluated against a direct-chat baseline.

The compliance claim is the implemented system and evidence—not the word “agent,” a chat UI, or a long prompt.

### 1.1 Organizer evidence

Before submission, archive outside or inside the submission evidence package:

- the original clarification text;
- announcement date and channel;
- Discord message link/ID or screenshot;
- any written organizer answer confirming this specific architecture.

Recommended confirmation question:

> Apakah workflow berikut memenuhi kategori “Agentic Workflow” tanpa parameter fine-tuning: model melakukan ekstraksi/update state percakapan, backend memvalidasi state, meminta konfirmasi pengguna, menjalankan deterministic pricing tool, lalu memanggil model untuk penjelasan dengan output validation dan bounded repair? Kami akan menyertakan execution trace dan evaluasi terhadap direct zero-shot baseline.

Only the organizer can guarantee eligibility. This runbook defines the engineering evidence for that review.

## 2. Product boundary

The workflow handles one item per transient consultation. It can:

- capture facts;
- request missing facts;
- accept corrections;
- show confirmation;
- call the pricing tool;
- explain a result;
- revise promo wording;
- reject out-of-domain requests.

It cannot browse the web, access arbitrary tools, publish automatically, contact customers, alter inventory, run in the background, or act without a current user request.

## 3. Workflow design

```text
USER_MESSAGE
   |
   v
EXTRACT_PATCH (model, schema constrained)
   |
   v
VALIDATE_PATCH (code)
   |
   v
MERGE_STATE (code, revisioned)
   |
   +-- missing/ambiguous --> ASK_FOR_MISSING_FIELDS
   |
   +-- complete ----------> SHOW_CONFIRMATION
                                  |
                           user confirms revision
                                  |
                                  v
                         CALL_PRICING_TOOL
                                  |
                                  v
                         VALIDATE_TOOL_RESULT
                                  |
                                  v
                         WRITE_RESPONSE (model)
                                  |
                                  v
                         VALIDATE_LANGUAGE
                           |             |
                          valid       invalid
                           |             v
                           |        ONE_REPAIR_ATTEMPT
                           |             |
                           +------> RESULT or SAFE_FALLBACK
```

### 3.1 Deterministic action policy

The orchestrator exposes an allowlist:

| Action | Preconditions | Effect |
|---|---|---|
| `ASK_FOR_MISSING_FIELDS` | State incomplete or ambiguous | Ask a grouped question; no tool call |
| `SHOW_CONFIRMATION` | Required state complete | Show editable card; no tool call |
| `CALL_PRICING_TOOL` | Current revision explicitly confirmed | Call typed pricing tool once |
| `EXPLAIN_RESULT` | Valid current result exists | Generate/return faithful explanation |
| `REVISE_PROMO_COPY` | Recommendation exists | Rewrite words only; preserve values/status |
| `OUT_OF_SCOPE` | Unsupported intent | Redirect; preserve state |
| `SAFE_FAILURE` | Model/tool contract failure | Preserve state; return recoverable error |

The model may classify intent, but code enforces preconditions. The model cannot invent an action outside the allowlist.

### 3.2 Conversation state

Use a typed immutable-or-copy-on-write state object:

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
  "revision": 0,
  "result_revision": null
}
```

Invariant examples:

- `confirmed=true` implies all required fields are valid;
- `result_revision == revision` is required before explaining/reusing a result;
- accepted changes increment `revision`, set `confirmed=false`, and clear the current result;
- a rejected/ambiguous patch changes nothing;
- every result records the exact state revision and tool version.

## 4. Tool contract

Expose the existing engine through a narrow adapter:

```python
class PricingTool(Protocol):
    name = "calculate_markdown_recommendation"

    def compute(self, confirmed: ConfirmedItemState) -> OracleResult:
        ...
```

The adapter must:

1. accept only the confirmed typed state;
2. map exactly to `PricingInput`;
3. call `pricing.compute` once;
4. serialize the complete `OracleResult`;
5. emit start/success/failure trace events;
6. never call the model, database, or network.

Do not label this “native function calling” unless the chosen model API actually emits a validated tool-call object. The qualifying claim remains agentic orchestration and tool use.

## 5. Model contracts

### 5.1 Extract patch

Input:

- latest user message;
- current structured state;
- allowed categories/fields;
- compact recent context if needed.

Output JSON:

```json
{
  "intent": "provide_or_correct_data",
  "patch": {
    "stock": 24
  },
  "ambiguous_fields": [],
  "evidence": {
    "stock": "stoknya ternyata 24"
  }
}
```

Rules:

- output only fields explicitly supported by the message;
- no pricing or recommendation fields;
- `evidence` quotes short source spans for validation/debugging;
- ambiguity is reported, not guessed;
- an empty patch is valid for non-data intents.

Application code independently validates normalization and domain rules. Evidence is not chain-of-thought.

### 5.2 Write response

Input:

- confirmed state;
- authoritative pricing-tool result;
- requested response kind;
- allowed numerical set.

Output JSON:

```json
{
  "explanation": "...",
  "promo_copy": "..."
}
```

Rules:

- tool status and values are authoritative;
- numerical claims must occur in the allowed set;
- no discount promo for no-action/warning;
- concise Bahasa Indonesia;
- no claims of food safety or guaranteed sales.

### 5.3 Inference profile

Record and freeze:

- model repository/name and file SHA-256;
- llama.cpp image digest/build;
- chat template;
- extraction/writer prompt versions;
- JSON schemas;
- temperature, seed, token limit, and thinking controls.

Static settings support reproducibility but do not make generated wording byte-identical. Numerical determinism comes from the pricing tool.

## 6. Validation and repair

### 6.1 Patch validation

Reject or flag:

- unknown keys;
- wrong types or booleans used as numbers;
- non-finite, non-positive, or impossible domains;
- unsupported categories;
- values not grounded in the user message;
- ambiguous units that cannot be normalized reversibly;
- a model attempt to set `confirmed`, `revision`, or result fields.

### 6.2 Language validation

Check:

- exact output shape;
- engine-status consistency;
- allowed numerical claims;
- no recommendation claims in warning/no-action states;
- length and sentence limits;
- no hidden tool/result mutation.

### 6.3 Repair policy

On a model contract violation:

1. issue one repair call containing the invalid output and machine-readable violations;
2. validate again;
3. on second failure, use a safe deterministic question/template or numbers-only result;
4. record the failure in the sanitized trace.

Never loop repairs indefinitely.

## 7. Sanitized execution trace

Each request should produce a trace record suitable for tests and proof of work:

```json
{
  "trace_id": "...",
  "prompt_version": "extract-v1",
  "state_revision_before": 2,
  "events": [
    {"type": "model_call", "operation": "extract_patch", "status": "valid"},
    {"type": "state_patch", "accepted_fields": ["stock"]},
    {"type": "transition", "from": "recommendation", "to": "ready_to_confirm"}
  ],
  "state_revision_after": 3
}
```

For a calculation, include tool name, argument hash or redacted typed arguments, tool-result status, elapsed time, and result revision. Do not store or display hidden reasoning, secrets, full private prompts where inappropriate, or unnecessary personal data.

## 8. Evaluation design

### 8.1 Systems compared

Use the same base model and held-out cases:

- **Baseline A — direct chat:** one HargaTurun system prompt; model receives conversation and directly answers.
- **System B — customized workflow:** patch extraction, validated state, confirmation, pricing tool, validated writing, bounded repair.

Optionally report a structured-form oracle ceiling, but do not confuse it with an AI baseline.

### 8.2 Held-out suite

Create manually authored or manually verified multi-turn cases covering:

- all categories;
- complete and incomplete first messages;
- `rb/ribu/k`, dates, relative days, quantities, and colloquial spelling;
- multiple facts per message;
- corrections and negations;
- ambiguous values;
- no-action, recommendation, expired, and invalid-margin outcomes;
- out-of-domain requests;
- prompt-injection-like attempts to override price or skip confirmation;
- model output contract failures via test doubles.

Split evaluation cases by underlying scenario so paraphrases/corrections from one scenario do not leak across development and held-out sets. Preserve provenance and reviewer decisions.

### 8.3 Metrics

| Capability | Metric |
|---|---|
| Extraction | Valid schema; per-field accuracy; complete-state exact match |
| Missing facts | Recall; false-completion rate |
| Corrections | Corrected-field accuracy; unrelated-field preservation |
| State safety | Unauthorized field mutations; stale-result reuse |
| Tool policy | Premature calls; missed valid calls; duplicate calls |
| Pricing | Margin/safety violations; numerical nondeterminism |
| Writing | Unsupported numbers; status faithfulness; clarity rubric |
| Scope | Out-of-domain redirect accuracy; state preservation |
| Product | Task completion; median turns to confirmation |
| Runtime | P50/P95 latency; failures; peak memory |

Report counts, denominators, raw failures, configuration, and commit SHA. Do not publish target percentages as results.

### 8.4 Minimum decision rule

The workflow is ready for submission only if:

- it produces zero premature pricing-tool calls in the held-out suite;
- it produces zero accepted recommendations that violate deterministic engine rules;
- corrections cannot reuse a stale result;
- unsupported numerical claims are zero after validation/fallback;
- it materially improves task completion and/or state accuracy over direct chat;
- every result is reproducible from the recorded state and tool version.

If direct chat performs similarly on language metrics, the workflow still must demonstrate safety/tool-policy benefits. Be transparent about mixed results.

## 9. Test plan

### 9.1 Unit tests

- state merge and revision invalidation;
- missing-field derivation;
- allowed-action preconditions;
- pricing-tool argument mapping;
- unsupported-number extraction;
- repair limit;
- out-of-domain no-op behavior.

### 9.2 Integration tests

Use fake model responses to prove:

- complete first message → confirmation, not immediate tool call;
- incomplete message → grouped question;
- correction → state update and stale-result invalidation;
- confirm → one exact tool call;
- malformed patch → repair/fallback;
- malformed writer output → numbers-only safe result;
- model unavailable → state preserved.

### 9.3 End-to-end tests

Run against the actual local model for representative consultations, save traces, and manually review failures. Repeat fixed inputs to validate state/tool determinism and measure wording variance separately.

## 10. Repository evidence layout

Planned artifacts:

```text
configs/
  agentic-workflow.yaml
  prompts/
    extract-v1.txt
    write-v1.txt
data/
  eval/
    consultations.jsonl
    reviewer_rubric.md
reports/
  direct-chat-baseline.json
  agentic-workflow.json
  comparison.md
  traces/
scripts/
  eval_agentic_workflow.py
  validate_eval_data.py
docs/
  AI_CUSTOMIZATION_EVIDENCE.md
```

Large model files remain ignored. Store artifact identities, download instructions, licenses, and hashes.

## 11. Implementation sequence

| Order | Deliverable | Exit condition |
|---:|---|---|
| 1 | State/action schemas | Reviewed against Penyisihan SRS |
| 2 | Pure state reducer | Unit tests cover updates, corrections, invalidation |
| 3 | Typed pricing tool | Exact argument/result mapping tests pass |
| 4 | Extract/write model clients | JSON schemas and validators pass with fakes |
| 5 | Orchestrator and trace | Illegal transitions/tool calls impossible in tests |
| 6 | Chat UI + cards + form fallback | Primary flow works without marketplace features |
| 7 | Direct-chat and workflow evaluator | Same held-out suite/config produces raw reports |
| 8 | Full Compose packaging | Clean-clone smoke succeeds locally |
| 9 | Evidence/proposal/video update | All claims map to committed artifacts |

## 12. Optional parameter fine-tuning

Fine-tuning is no longer the selected compliance dependency. Consider it only if evaluation identifies persistent extraction or Indonesian-language failures that prompts/workflow cannot solve economically.

If pursued:

- keep the agentic workflow unchanged;
- freeze an evaluation suite first;
- train only on leakage-safe data;
- compare base and tuned models in the same workflow;
- retain configs, logs, adapters, hashes, licenses, and raw reports;
- never call a base GGUF “fine-tuned.”

The former LoRA runbook is retained at `HargaTurun_FineTuning_Plan.md` as superseded historical material.

## 13. Definition of done

The AI-customization work is done only when:

- source code implements the documented action/state/tool boundaries;
- the actual local model artifact is identified honestly;
- all unit/integration tests pass;
- direct-chat and workflow reports exist with raw cases and failures;
- representative traces can be replayed;
- full Docker Compose setup works from a clean clone;
- proposal and videos describe only implemented behavior;
- organizer clarification evidence is archived.
