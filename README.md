# HargaTurun

**Conversational inventory-rescue copilot for Indonesian food UMKM.**
Built for COMPFEST 18 — AI Innovation Challenge, *AI for the Backbone of the Economy / Smart Commerce*.

A vendor describes at-risk food stock in everyday Indonesian. HargaTurun gathers only the missing facts, confirms what it understood, calls a deterministic pricing tool, and explains the resulting action. It is a **bounded, tool-backed chatbot**, not a general-purpose assistant.

> **Implementation status:** the deterministic pricing oracle, strict model contracts, FastAPI/SQLite service, HTTP-backed Flutter web/PWA, and local Qwen llama.cpp baseline are implemented. The bounded multi-turn orchestrator, `POST /api/chat`, conversational chat UI, agent traces, and comparative agentic evaluation described below remain the next implementation target. The included base Qwen3.5-4B setup is for infrastructure validation; no fine-tuned artifact is claimed.

## Product promise

> **Ceritakan stokmu seperti biasa. HargaTurun membantu melengkapi datanya, menghitung tindakan yang aman, dan menjelaskan apa yang harus dilakukan.**

The selling point is not “a chatbot.” It is a governed decision workflow for merchants who do not want to fill a complex pricing form:

- understands colloquial Indonesian such as `15rb`, `lusa expired`, and corrections in later turns;
- asks for missing economic facts instead of inventing them;
- lets the vendor review an editable confirmation card;
- calls a deterministic pricing engine that enforces margin and expiry rules;
- explains the result and drafts promotional copy;
- supports corrections and recalculation without restarting the consultation.

## Hybrid agentic architecture

```text
Vendor message
    |
    v
Conversation orchestrator
    |-- model: extract a proposed state patch from Indonesian text
    |-- code: validate and merge only allowed fields
    |-- code: choose ASK / CONFIRM / CALCULATE / EXPLAIN / OUT_OF_SCOPE
    |
    +-- incomplete ----------> ask for all missing/ambiguous facts
    |
    +-- complete ------------> show editable confirmation card
                                  |
                           explicit confirmation
                                  |
                                  v
                         PricingTool.compute()
                         (deterministic authority)
                                  |
                                  v
                     model: explanation + promo copy
                                  |
                                  v
                    output validator / one repair attempt
                                  |
                                  v
                       recommendation card + chat
```

| Component | Responsibility |
|---|---|
| Qwen3.5-4B, local llama.cpp | Understand a message as a proposed field update; phrase concise questions, explanations, and promo copy |
| Conversation orchestrator | Own allowed actions, state transitions, confirmation, tool invocation, repair limits, and trace events |
| `pricing.py` | Every number: discount, price, timing, projections, bounds, and margin floor |
| Validators | Reject unknown fields, impossible values, unsupported numerical claims, and unsafe transitions |
| Chat UI | Conversation plus structured confirmation/recommendation cards and a form fallback |

**The model never owns conversation truth and never calculates a price.** Backend state is authoritative. The deterministic tool is the only pricing authority.

## Bounded chatbot behavior

HargaTurun supports one consultation for one item at a time:

1. describe an item;
2. answer missing-field questions;
3. correct a previously captured value;
4. confirm the normalized data;
5. calculate or recalculate a recommendation;
6. ask for an explanation or revised promo wording.

Out-of-domain requests receive a short redirect. The preliminary MVP does not provide generic business advice, customer service, product search, persistent chat history, background agents, or autonomous actions.

## Two rounds

| | Penyisihan | Final extension |
|---|---|---|
| Authoritative spec | [`docs/HargaTurun_Penyisihan_SRS.md`](docs/HargaTurun_Penyisihan_SRS.md) | [`docs/HargaTurun_Final_SRS.md`](docs/HargaTurun_Final_SRS.md) |
| Core flow | Bounded chat → confirmation → pricing-tool result | Publish result → browse → claim → redeem |
| Persistence | None; consultation state is request/response data | SQLite for deals and claims |
| Consumer | Static promo preview only | Real deal feed |

The penyisihan build must expose only the bounded vendor consultation. Marketplace, authentication, analytics, and other final-round functionality must not appear in the preliminary demo.

## Conversation state

The model proposes patches; application code owns this structure:

```json
{
  "item_name": "Roti Tawar",
  "category": "Bakery",
  "original_price": 15000,
  "cost": 10000,
  "stock": 20,
  "days_remaining": 2,
  "daily_sales": 4,
  "total_shelf_life": null,
  "shop_name": "Toko Sari Bakery",
  "confirmed": false,
  "revision": 3
}
```

Any accepted correction invalidates prior confirmation and prior results. The pricing tool runs only after all required fields are present and the vendor explicitly confirms them.

## Example interaction

> **Vendor:** Aku punya 20 roti tawar, lusa expired. Harga normal 15rb, modal 10rb. Biasanya laku 4 sehari.
> **HargaTurun:** Aku mencatat 20 roti, sisa 2 hari, harga Rp15.000, modal Rp10.000, dan penjualan 4/hari. Berapa total masa simpannya sejak diproduksi?
> **Vendor:** 5 hari.
> **HargaTurun:** *Shows editable confirmation card.*
> **Vendor:** Hitung rekomendasi.
> **HargaTurun:** *Calls `PricingTool.compute`, then shows the recommendation and explanation.*
> **Vendor:** Stoknya ternyata 24.
> **HargaTurun:** *Updates stock, invalidates the old result, asks for confirmation, and recalculates only after confirmation.*

## AI-customization position

The organizer clarification permits advanced adaptation methods—including agentic workflows—instead of requiring parameter fine-tuning in every project. HargaTurun therefore uses the **agentic workflow** route:

- domain-specific task decomposition;
- explicit state and allowed actions;
- deterministic pricing-tool use;
- human confirmation before consequential calculation;
- schema and numerical-faithfulness validation;
- bounded validator-guided repair;
- evaluation against a direct zero-shot chatbot baseline.

This is more than a raw zero-shot API call. See [`docs/HargaTurun_Agentic_Workflow_Plan.md`](docs/HargaTurun_Agentic_Workflow_Plan.md). Parameter fine-tuning remains an optional later optimization and must never be claimed unless artifacts and measured results exist.

## Current code

| Path | Status |
|---|---|
| `backend/hargaturun/pricing.py` | Implemented deterministic pricing authority |
| `backend/hargaturun/api.py` | Implemented one-shot recommendation, demo auth/shop, deal, claim, and redemption API |
| `backend/hargaturun/model_client.py` | Implemented validated OpenAI-compatible parse/write client with one repair attempt |
| `backend/hargaturun/schemas.py` | Implemented strict one-shot parse/write contracts; must evolve into conversational patch/write contracts |
| `frontend/` | Implemented Flutter web/PWA baseline using HTTP-backed repositories and structured cards |
| `scripts/run-llama-server.sh` | Implemented local CUDA llama.cpp launcher for the temporary base GGUF |
| Multi-turn chat orchestrator, `POST /api/chat`, and chat UI | Planned |
| Full application Docker Compose | Planned |
| Agentic evaluation report | Planned |

For a complete CUDA-enabled local stack, install Docker Compose and the NVIDIA
Container Toolkit, then run:

```bash
docker compose up --build
```

The first run downloads and verifies the temporary base Qwen GGUF when it is
absent, builds the FastAPI and release Flutter containers with their pinned
dependencies, and serves the app at `http://127.0.0.1:3000`. Model and SQLite
data persist in named volumes. See [`backend/README.md`](backend/README.md) for
configuration, native-development commands, and the base-model caveat.

Run the implemented backend suite:

```bash
cd backend
uv sync --extra dev
uv run pytest -q
```

See [`backend/README.md`](backend/README.md) for the model/API runbook and fast Flutter preview commands.

## Required submission evidence

Before calling the MVP competition-ready, the repository must contain:

- a public, runnable repository with one documented `docker compose up --build` path;
- an architecture/state diagram and tool contract;
- representative execution traces showing ask, confirm, tool call, correction, and safe failure;
- a held-out comparison of direct base-model chat versus the customized workflow;
- prompt/config/model identity and reproducible test commands;
- a proposal accurately describing the workflow and preprocessing;
- proof-of-work and innovation videos made from the exact submission build.

No document should describe a planned model, result, dataset, or metric as completed.

## Documents

| File | Purpose |
|---|---|
| [`docs/HargaTurun_Project_Spec.md`](docs/HargaTurun_Project_Spec.md) | Product vision, value proposition, architecture, requirements, and metrics |
| [`docs/HargaTurun_Penyisihan_SRS.md`](docs/HargaTurun_Penyisihan_SRS.md) | **Authoritative preliminary MVP contract** |
| [`docs/HargaTurun_Agentic_Workflow_Plan.md`](docs/HargaTurun_Agentic_Workflow_Plan.md) | AI customization, implementation, evaluation, and evidence plan |
| [`docs/HargaTurun_FineTuning_Plan.md`](docs/HargaTurun_FineTuning_Plan.md) | Superseded LoRA plan retained as optional historical material |
| [`docs/HargaTurun_Final_SRS.md`](docs/HargaTurun_Final_SRS.md) | Final-round marketplace extension |
| [`docs/HargaTurun_LLM_Server_Setup.md`](docs/HargaTurun_LLM_Server_Setup.md) | Local llama.cpp serving profile |
| [`docs/AIC_Technical_Guide.md`](docs/AIC_Technical_Guide.md) | Competition constraints plus recorded clarification |
| [`docs/HargaTurun_Implementation_Handoff.md`](docs/HargaTurun_Implementation_Handoff.md) | Current implementation status and next steps |

Where documents conflict, the Penyisihan SRS controls preliminary scope; the Final SRS controls final-round additions.

*Licensed under the terms in [LICENSE](LICENSE).*
