# HargaTurun — Software Requirements Specification: Penyisihan MVP

> **Status:** Authoritative specification for COMPFEST 18 AIC penyisihan
> **Scope:** Business-owner recommendation flow only
> **Companion documents:** [Project Spec](HargaTurun_Project_Spec.md), [Fine-Tuning Plan](HargaTurun_FineTuning_Plan.md), [AIC Technical Guide](AIC_Technical_Guide.md)
> **Supersedes:** the mixed implementation scope formerly described in [HargaTurun_SRS.md](HargaTurun_SRS.md)

## 1. Purpose and scope

HargaTurun helps an Indonesian food UMKM owner decide whether and how much to discount a single at-risk item. In one synchronous interaction, the owner provides item data and receives a deterministic price recommendation plus Indonesian explanation and promotional-copy preview.

This specification deliberately implements only the preliminary-round core. The AIC rules require a UI for a single input/output AI interaction, synchronous processing, static inference parameters, local reproducibility through `docker compose`, and a genuinely fine-tuned model. They do **not** require a consumer marketplace, deal lifecycle, or operational feedback system. Those are planned separately in [HargaTurun_Final_SRS.md](HargaTurun_Final_SRS.md).

### 1.1 Goals

- Accept a structured form or colloquial Indonesian free-text item description.
- Use a fine-tuned local language model to parse free text and generate business explanation plus promo-copy preview.
- Use deterministic Python code—not the model—for discount, price, projections, and safety limits.
- Display one complete recommendation in Bahasa Indonesia in under 10 seconds under the target local setup.
- Run locally with static model settings and no inference-time internet dependency after model setup.

### 1.2 Explicit exclusions

The following must not be built for penyisihan:

- Publishing, unpublishing, active-deal management, consumer deal feed, claims, redemption, or stock reservation.
- Deal/claim database schema, historical usage pages, analytics, or automatic data logging.
- Daily feedback loops, scheduled work, background jobs, queues, auto-tuning, or bulk-testing features in the app/repository.
- Authentication, payments, geolocation, notifications, multi-shop tenancy, delivery, OCR, voice input, or mobile-native packaging.

A rendered deal-card **preview** is allowed because it is output from the core recommendation; it is not a live consumer listing.

## 2. Product flow

```text
Owner form or free text
        |
        v
Frontend validation / confirmation
        |
        v
POST /api/recommend (synchronous)
        |
        +--> Fine-tuned local model: parse + explanation + promo preview
        |
        +--> Python pricing engine: price + discount + projections + safety rules
        |
        v
Single business-owner result screen
```

The user receives one of four outcomes:

1. **Recommendation:** a safe discount, rounded price, timing, projections, explanation, and promo preview.
2. **No action:** stock is likely to sell before expiry; show when to reassess.
3. **Input confirmation:** required facts are missing or ambiguous; prefill the structured fields and require confirmation before calculating.
4. **Safety warning:** expired item or invalid economics, such as cost at or above selling price; no recommendation is issued.

## 3. Users and interface

### 3.1 Primary user

A food UMKM owner or manager who needs an immediate markdown recommendation for one expiring product. The UI is desktop-first, Bahasa Indonesia, and avoids pricing jargon.

### 3.2 Single-screen business flow

1. Owner either completes the structured form or types free text such as `roti tawar 10 biji exp 2 hari harga 15rb modal 10rb`.
2. Owner selects **Dapatkan Rekomendasi**.
3. If parsing is incomplete or ambiguous, the app shows prefilled fields and asks for confirmation; it does not guess an economic input silently.
4. The result appears on the same screen with **Ubah Input** and **Hitung Lagi** actions. There is no publish action in this round.

### 3.3 Structured input contract

| Field | Required | Source / rule |
|---|---:|---|
| `item_name` | Yes | Owner input or model parse, then confirmation |
| `category` | Yes | One of Bakery, Prepared Food, Dairy, Beverage, Produce, Snack, Canned, Other |
| `original_price` | Yes | Rupiah per sellable unit |
| `cost` | Yes | Rupiah cost per sellable unit |
| `stock` | Yes | Whole number of sellable units/servings |
| `days_remaining` | Yes | Number of days until the item can no longer be sold |
| `shop_name` | Recommended | Used only in promo preview; default may be omitted |
| `daily_sales` | Yes or confirmed default | Owner estimate of units/day. It is not safely inferable from the current free-text model schema. |
| `total_shelf_life` | Yes or category default | Owner value when known; otherwise use the category default below and disclose it in the result. |

The structured form must expose `daily_sales` and `total_shelf_life` (or their chosen defaults). Free text can omit them, but the backend must request confirmation rather than invent values.

| Category | Default total shelf life (days) |
|---|---:|
| Bakery | 4 |
| Prepared Food | 3 |
| Dairy | 14 |
| Beverage | 5 |
| Produce | 7 |
| Snack | 90 |
| Canned | 365 |
| Other | 30 |

## 4. Functional requirements

| ID | Requirement |
|---|---|
| P-FR-1 | The UI accepts one structured item input and validates required economic fields before calculation. |
| P-FR-2 | The UI accepts one free-text Indonesian input. The model extracts available fields into the same structured representation. |
| P-FR-3 | Missing or ambiguous required fields result in a confirmation form with prefilled values; the pricing engine is not called until confirmation. |
| P-FR-4 | A single synchronous request returns either a recommendation, no-action response, input-confirmation response, or safety warning. |
| P-FR-5 | The recommendation contains discount percent, recommended price, timing, expected sell-through, expected revenue, expected loss without action, and confidence wording. |
| P-FR-6 | The result contains a 2–4 sentence business explanation and 1–2 sentence promo-copy preview in Bahasa Indonesia. |
| P-FR-7 | The pricing engine is the sole authority for numerical values. The model must not supply discount, price, revenue, or loss values. |
| P-FR-8 | The engine never recommends a price below `cost + Rp500`; discount and price rounding obey the documented oracle rules. |
| P-FR-9 | Items already expired, items with zero/negative margin, and invalid numeric inputs produce a clear warning and no recommendation. |
| P-FR-10 | Low-pressure items return `no_action` with a reassessment message instead of a forced discount. |
| P-FR-11 | The result screen renders a static deal-card preview using the computed price and generated promo copy. It has no publish or claim control. |
| P-FR-12 | Same confirmed input and static inference configuration produce reproducible numerical output; model serving uses static parameters, including temperature `0`. |

## 5. Architecture and components

### 5.1 Deployment topology

```text
Browser SPA  --HTTP-->  FastAPI API  --HTTP-->  local model server
                              |
                              +--> pricing.py (pure Python)
```

`docker compose up` starts the frontend, API, and model server. A three-service deployment is justified only because local model serving is part of the required end-to-end inference; no database service is needed for penyisihan.

### 5.2 Frontend

A small React/Vite single-page application is acceptable, but any simple browser UI is valid. It owns form validation, free-text entry, confirmation state, loading/error state, and the result screen. It must not contain marketplace pages or deal history.

### 5.3 API

FastAPI exposes one core synchronous endpoint. It validates normalized structured values, invokes the model only when needed for parsing/text generation, invokes the pure pricing engine, and assembles the response.

### 5.4 Fine-tuned model server

The selected base model and serving format must be documented and verified during implementation. The project currently plans Qwen3.5-4B with BF16 LoRA through Unsloth and GGUF serving through llama.cpp. Current Unsloth guidance does not recommend QLoRA for Qwen3.5; BF16 LoRA training requires a GPU larger than the 8 GB inference laptop. This SRS does not claim availability or performance until the full pipeline is tested. The model is genuinely fine-tuned for HargaTurun's Indonesian parsing and text-generation tasks, then served locally with static settings.

The model responsibility is limited to:

- parse free text into allowed structured fields and identify missing required fields;
- after confirmed input is priced by the deterministic engine, generate a qualitative explanation;
- after confirmed input is priced by the deterministic engine, generate qualitative promo copy.

### 5.5 Pricing engine

`pricing.py` is a pure Python module with no database, model, or network dependency. It implements the product spec's oracle rules: supply pressure, relative expiry urgency, category bias, margin ceiling, bounded/rounded discount, rounded price, projections, timing, and confidence. Its inputs must already be confirmed.

No prior-stock argument, daily re-run adjustment, or learning loop belongs in this round.

## 6. API contract

### 6.1 `POST /api/recommend`

Request accepts exactly one input mode.

```json
{
  "free_text": "roti tawar 10 biji exp 2 hari harga 15rb modal 10rb toko sari bakery"
}
```

or:

```json
{
  "item_name": "Roti Tawar",
  "category": "Bakery",
  "original_price": 15000,
  "cost": 10000,
  "stock": 10,
  "days_remaining": 2,
  "daily_sales": 5,
  "total_shelf_life": 4,
  "shop_name": "Toko Sari Bakery"
}
```

Free text must return `422` with `needs_confirmation: true` and prefilled parsed fields when a required field, `daily_sales`, or a shelf-life choice is unavailable. It must not fabricate them.

Successful recommendation:

```json
{
  "status": "recommendation",
  "normalized_input": {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 10,
    "days_remaining": 2,
    "daily_sales": 5,
    "total_shelf_life": 4,
    "shop_name": "Toko Sari Bakery"
  },
  "recommendation": {
    "discount_percent": 30,
    "recommended_price": 10500,
    "timing": "Mulai diskon hari ini",
    "expected_sell_through": "8 dari 10 pcs",
    "expected_revenue": 84000,
    "expected_loss_no_action": 50000,
    "confidence": "Cukup yakin"
  },
  "explanation": "...",
  "promo_copy": "...",
  "preview": {
    "item_name": "Roti Tawar",
    "shop_name": "Toko Sari Bakery",
    "original_price": 15000,
    "deal_price": 10500,
    "discount_percent": 30,
    "days_remaining": 2,
    "stock": 10
  }
}
```

Alternative responses:

- `200 { "status": "no_action", "message": "Belum perlu diskon...", "reassess_in_days": 5 }`
- `422 { "status": "needs_confirmation", "parsed_input": { ... }, "missing_fields": ["daily_sales"] }`
- `422 { "status": "invalid_input", "message": "Harga modal ≥ harga jual..." }`
- `502 { "status": "model_unavailable", "message": "..." }`

## 7. Non-functional requirements

| ID | Requirement |
|---|---|
| P-NFR-1 | End-to-end confirmed-input response target is under 10 seconds on the declared local target hardware. |
| P-NFR-2 | The implementation runs locally through documented `docker compose` commands. |
| P-NFR-3 | After the one-time model setup, inference has no external API or internet dependency. |
| P-NFR-4 | Model parameters are static and documented; inference uses deterministic serving configuration. |
| P-NFR-5 | All core app text and model output are Bahasa Indonesia. |
| P-NFR-6 | The app persists no deals, claims, user accounts, or operational history in penyisihan. |
| P-NFR-7 | The README identifies required host prerequisites, model acquisition/setup, expected hardware, startup time, and a smoke-test request. |

## 8. Acceptance and validation

### 8.1 Required product checks

- Structured valid input returns a complete recommendation.
- Free text correctly parses a known colloquial example and returns a complete result after any required confirmation.
- Missing `cost`, `daily_sales`, or shelf-life choice produces confirmation, not a fabricated recommendation.
- A far-expiry, low-pressure item returns no action.
- An item expiring today returns the bounded fire-sale response while respecting the margin floor.
- An expired item and `cost >= original_price` return warnings with no recommendation.
- Every generated recommendation satisfies `recommended_price >= cost + 500`.
- Repeating a confirmed request produces identical numerical values.

### 8.2 Model evidence

Before fine-tuning, run the existing baseline evaluation against a real local model server. After fine-tuning, compare held-out parsing/JSON compliance results using a separate evaluation set. Record the actual results in an evaluation report or proposal; do not claim target percentages as achieved until measured.

### 8.3 Proof-of-work readiness

The recorded preliminary proof of work must show, without cuts:

1. terminal and browser running locally with timestamps;
2. the model/API startup path;
3. one structured or free-text recommendation flow;
4. one validation or no-action/safety case;
5. the actual generated result screen and its promo preview.

Every feature shown in the innovation video must exist in this runnable MVP.

## 9. Traceability and risks

| AIC expectation | HargaTurun response |
|---|---|
| Single core UI interaction | One business-owner input/result screen |
| Synchronous backend | One `POST /api/recommend` request, no queues/jobs |
| Fine-tuned model with static parameters | Local fine-tuned model restricted to language tasks, temperature `0` |
| Local reproducibility | Docker Compose plus documented model setup |
| Proportional technical scope | No marketplace, persistence, or automation in preliminary round |

Primary execution risks: model/toolchain availability, actual 8 GB VRAM fit, local cold-start/inference performance, and synthetic-data quality. Mitigate by validating the base-model path first, keeping the pricing engine pure and testable, evaluating the fine-tuned model on held-out examples, and using the structured form as the safe fallback.

## 10. Deferred final work

If the team advances, use [HargaTurun_Final_SRS.md](HargaTurun_Final_SRS.md) as the separate plan for publishing a computed preview, consumer browsing, claims, redemption, and minimal SQLite persistence. That work is deliberately absent from this MVP.
