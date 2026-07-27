# HargaTurun

**AI-powered surplus-food markdown assistant for Indonesian food UMKM.**
Built for COMPFEST 18 — AI Innovation Challenge (theme: *AI for the Backbone of the Economy* → Smart Commerce).

A warung, bakery, or small café owner has stock that will expire. HargaTurun answers two questions in one interaction:
**should I discount this, and by how much?** — then writes the Indonesian explanation and the promo copy for it.

The system is deliberately **hybrid**:

| Component | Owns |
|---|---|
| Fine-tuned Qwen3.5-4B (local, llama.cpp, `temp=0`) | Parsing colloquial Indonesian input → structured fields; writing the explanation and promo copy |
| `pricing.py` (pure Python oracle) | Every number: discount %, price, timing, projections, bounds, margin floor |

The model never does arithmetic. Python never writes prose.

> **Document status:** This repository currently contains specifications only (`docs/`). The flows below are the
> contract that the implementation must satisfy. Setup/`docker compose` instructions belong in this file once the
> code lands.

---

## Scope: two rounds, two different products

| | Penyisihan (preliminary) | Final (10-hour hackathon) |
|---|---|---|
| Spec | [`docs/HargaTurun_Penyisihan_SRS.md`](docs/HargaTurun_Penyisihan_SRS.md) | [`docs/HargaTurun_Final_SRS.md`](docs/HargaTurun_Final_SRS.md) |
| User flow | Vendor asks → vendor gets a recommendation. **Nothing is published.** | Vendor publishes → consumer browses → consumer claims → vendor redeems |
| Persistence | None | SQLite (`deals`, `claims`) |
| Consumer | Static deal-card **preview** only | Real `/deals` route |

Everything below is marked **[P]** (built in penyisihan) or **[F]** (added in the final round).

---

## Actors

| Actor | Who | Where |
|---|---|---|
| **Vendor** | UMKM food owner/manager — Bu Sari (warung), Mas Dimas (café), Mbak Rina (home-based) | `/business` |
| **Consumer** | Price-sensitive buyer — student, budget household. No account, ever. | `/deals` **[F]** |
| **Frontend** | Browser SPA — validation, confirmation state, result screen | — |
| **API** | FastAPI — orchestration only, never a pricing authority | — |
| **Model server** | Local fine-tuned model, static params, `temperature=0` | — |
| **Pricing engine** | `pricing.py`, pure function, no I/O | — |

---

## The whole journey at a glance

```mermaid
flowchart LR
    A["Vendor has<br/>expiring stock"] --> B["Types free text<br/>or fills form"]
    B --> C{"Enough<br/>info?"}
    C -- no --> D["Confirm prefilled<br/>fields"] --> E
    C -- yes --> E["Pricing engine<br/>computes"]
    E --> F{"Outcome"}
    F --> G["Recommendation<br/>+ explanation + promo"]
    F --> H["No action needed"]
    F --> I["Safety warning"]
    G --> J["Publikasikan"]:::final
    J --> K["Consumer browses<br/>/deals"]:::final
    K --> L["Klaim → HT-XXXX"]:::final
    L --> M["Vendor redeems<br/>at the shop"]:::final

    classDef final stroke-dasharray: 5 5;
```

Solid boxes are the preliminary MVP **[P]**. Dashed boxes are the final-round extension **[F]**.

---

## Flow 1 — Vendor gets a recommendation **[P]**

The core interaction. One input, one synchronous response, one screen.

```mermaid
sequenceDiagram
    autonumber
    actor V as Vendor
    participant FE as Frontend
    participant API as FastAPI
    participant M as Model server
    participant PE as pricing.py

    V->>FE: Types "roti tawar 10 biji exp 2 hari harga 15rb modal 10rb"
    FE->>FE: Basic validation, disable button, show loading
    FE->>API: POST /api/recommend { free_text }

    API->>M: system prompt + user input (temp=0, max 350 tok)
    M-->>API: { parsed_input, explanation, promo_copy }
    Note over M,API: Model returns fields and prose only.<br/>No discount, no price, no projections.

    API->>API: Validate JSON, check required fields present

    alt Required field, daily_sales, or shelf-life choice missing
        API-->>FE: 422 { status: needs_confirmation, parsed_input, missing_fields }
        FE-->>V: Prefilled form — "lengkapi data ini"
        Note over V,FE: See Flow 2. The engine is NOT called yet.
    else All confirmed
        API->>PE: compute(category, price, cost, stock, days_remaining,<br/>total_shelf_life, daily_sales)
        PE->>PE: pressure → urgency → category bias → margin ceiling<br/>→ clamp 5-70% → round to 5% → round price to Rp500
        PE-->>API: discount, price, timing, sell-through, revenue, loss, confidence
        API->>API: Inject computed figures into promo_copy
        API-->>FE: 200 { status, normalized_input, recommendation,<br/>explanation, promo_copy, preview }
        FE-->>V: Result screen + static deal-card preview
    end
```

**Target:** under 10 seconds end-to-end on 1× 8 GB VRAM GPU. Same confirmed input → byte-identical numbers.

### The four outcomes

Every call to `POST /api/recommend` ends in exactly one of these:

```mermaid
flowchart TD
    S["Confirmed input"] --> X{"Checks"}
    X -- "cost >= price<br/>or days_remaining <= 0<br/>or invalid numbers" --> W["422 invalid_input<br/>Safety warning, no recommendation"]
    X -- "pressure <= 1.0 AND urgency < 0.7" --> N["200 no_action<br/>'Belum perlu diskon. Cek lagi dalam X hari.'"]
    X -- "missing / ambiguous fields" --> C["422 needs_confirmation<br/>Prefilled form"]
    X -- "otherwise" --> R["200 recommendation<br/>Discount, price, timing, projections,<br/>explanation, promo, preview"]
```

| Outcome | What the vendor sees |
|---|---|
| **Recommendation** | `Rp10.500 (30% off)` · timing · `8 dari 10 pcs terjual` · revenue vs. loss · 2–4 sentence explanation · promo preview |
| **No action** | *"Belum perlu diskon. Item ini kemungkinan terjual normal sebelum kadaluarsa. Cek lagi dalam X hari."* |
| **Needs confirmation** | Prefilled fields with the gaps highlighted. The system never invents `cost`, `daily_sales`, or shelf life. |
| **Safety warning** | *"Harga modal ≥ harga jual. Mohon cek input Anda."* or *"Item sudah kadaluarsa."* No numbers issued. |

Plus one failure mode: `502 model_unavailable` when the model server is down.

---

## Flow 2 — Free text is incomplete **[P]**

The single most common real-world path, because `daily_sales` and `total_shelf_life` are almost never in a
colloquial one-liner. **The backend must ask, not guess.**

```mermaid
sequenceDiagram
    autonumber
    actor V as Vendor
    participant FE as Frontend
    participant API as FastAPI
    participant M as Model server
    participant PE as pricing.py

    V->>FE: "kue lapis 5 loyang exp besok harga 25rb"
    FE->>API: POST /api/recommend { free_text }
    API->>M: parse
    M-->>API: parsed_input with cost=null, daily_sales absent
    API-->>FE: 422 needs_confirmation, missing_fields: ["cost","daily_sales"]
    FE-->>V: Form prefilled — item, stock 5, exp 1 hari, harga 25000<br/>Empty: modal, rata-rata terjual per hari
    Note over FE,V: Category default shelf life is shown and<br/>disclosed, e.g. "Bakery = 4 hari", editable.

    V->>FE: Fills modal 18000, ~4 per hari, confirms
    FE->>API: POST /api/recommend { full structured payload }
    API->>PE: compute(...)
    PE-->>API: numbers
    API-->>FE: 200 recommendation
    FE-->>V: Result screen
```

Second call skips the model entirely when the payload is fully structured — the model is only needed for
parsing and prose.

### Category shelf-life defaults

Used when the vendor does not supply `total_shelf_life`; always disclosed in the result.

| Bakery | Prepared Food | Dairy | Beverage | Produce | Snack | Canned | Other |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 d | 3 d | 14 d | 5 d | 7 d | 90 d | 365 d | 30 d |

---

## Flow 3 — Vendor publishes a deal **[F]**

Only a successful, validated recommendation can become a deal. The client is never trusted as the pricing
authority — the server revalidates every number.

```mermaid
sequenceDiagram
    autonumber
    actor V as Vendor
    participant FE as Frontend
    participant API as FastAPI
    participant PE as pricing.py
    participant DB as SQLite

    Note over V,FE: Vendor is looking at a valid recommendation<br/>from Flow 1. "Publikasikan" is now enabled.
    V->>FE: Taps "Publikasikan"
    FE->>API: POST /api/deals { item, shop, prices, discount,<br/>days_remaining, initial_stock, promo_copy }
    API->>PE: Revalidate discount/price consistency + margin floor
    alt Price below cost + Rp500 or discount inconsistent
        PE-->>API: violation
        API-->>FE: 4xx rejected
        FE-->>V: "Harga tidak valid" — nothing published
    else Valid
        API->>DB: INSERT deal (status=active, remaining_stock=initial_stock)
        DB-->>API: deal_id
        API-->>FE: 201 { deal_id, created_at }
        FE-->>V: Deal appears in "Active Deals" list
    end
```

The vendor may remove a deal at any time (`DELETE /api/deals/{id}` → `204`, status becomes `removed`).
**There is no automatic expiry** — that would require background work, which is out of scope. The UI may display
a time-remaining hint but must not promise an automatic status change.

---

## Flow 4 — Consumer browses and claims **[F]**

No login. No geolocation. No payment. Just today's deals.

```mermaid
sequenceDiagram
    autonumber
    actor C as Consumer
    participant FE as Frontend (/deals)
    participant API as FastAPI
    participant DB as SQLite

    C->>FE: Opens /deals on a phone browser
    FE->>API: GET /api/deals?status=active
    API->>DB: SELECT active, non-removed deals
    DB-->>API: rows with remaining_stock, status
    API-->>FE: deal list
    FE-->>C: Cards — item, shop, Rp10.500 (was Rp15.000, 30% OFF),<br/>sisa 2 hari, stok 8, promo text

    C->>FE: Taps "Klaim"
    FE->>API: POST /api/deals/{id}/claims

    rect rgb(240, 240, 240)
        Note over API,DB: One SQLite transaction
        API->>DB: BEGIN
        API->>DB: Verify status=active AND remaining_stock > 0
        API->>DB: remaining_stock = remaining_stock - 1
        API->>DB: INSERT claim (code HT-XXXX, status=claimed)
        API->>DB: If remaining_stock = 0 then status = sold_out
        API->>DB: COMMIT (rollback everything on any failure)
    end

    alt Stock was available
        API-->>FE: 201 { claim_code: "HT-4821" }
        FE-->>C: "Kode klaim Anda: HT-4821.<br/>Tunjukkan di Toko Sari Bakery."
    else Sold out or removed
        API-->>FE: 409
        FE-->>C: Card switches to "Habis", claim disabled
    end
```

**Invariant:** `remaining_stock` can never go negative, and no claim is ever issued after sellout — even under
simultaneous local taps. The conditional check and the decrement live in the same transaction.

---

## Flow 5 — Redemption at the shop **[F]**

```mermaid
sequenceDiagram
    autonumber
    actor C as Consumer
    actor V as Vendor
    participant FE as Frontend (/business)
    participant API as FastAPI
    participant DB as SQLite

    C->>V: Shows "HT-4821" at the counter, pays the normal way
    V->>FE: Enters or selects the code
    FE->>API: POST /api/claims/HT-4821/redeem
    API->>DB: Look up claim

    alt Unknown code
        API-->>FE: 404
        FE-->>V: "Kode tidak ditemukan"
    else Already redeemed
        API-->>FE: 409
        FE-->>V: "Kode sudah digunakan" — nothing changes
    else Valid, status = claimed
        API->>DB: status = redeemed, redeemed_at = now
        API-->>FE: 200 { status: "redeemed" }
        FE-->>V: Marked "Digunakan"
    end
```

**Stock is reserved at claim time, not at redemption.** Redemption confirms collection and must never decrement
stock a second time.

---

## Deal lifecycle **[F]**

```mermaid
stateDiagram-v2
    [*] --> active: POST /api/deals
    active --> sold_out: last unit claimed
    active --> removed: DELETE /api/deals/{id}
    sold_out --> removed: DELETE /api/deals/{id}
    removed --> [*]

    note right of removed
        Removing a deal never deletes
        existing claim records.
    end note
```

Claim: `claimed` → `redeemed`. One-way, once. Claims made before removal stay redeemable until the vendor
manually rejects them.

---

## How the recommendation is actually computed

Full derivation in [`docs/HargaTurun_Project_Spec.md`](docs/HargaTurun_Project_Spec.md) §9.5. The shape of it:

```
1. days_of_supply = stock / daily_sales
   pressure       = days_of_supply / days_remaining      → >1 means surplus exists
2. life_consumed  = 1 - days_remaining / total_shelf_life
   urgency        = life_consumed ^ 1.5                  → non-linear near expiry
3. category bias  Bakery 1.3 … Canned 0.7                → soft elasticity prior
4. raw_discount   = pressure_factor × urgency × bias × 80
5. max_discount   = min(70, margin% - Rp500-per-unit guard)
6. discount       = round_to_5(clamp(raw, 5, max_discount))
7. price          = max(round_to_500(price × (1-d)), cost + 500)
8. projections    expected sell-through, revenue, loss if nothing is done
9. timing         "Belum perlu diskon" | "Bisa tunggu 1 hari" | "Mulai diskon hari ini"
10. confidence    "Cukup yakin" | "Prediksi kurang pasti"
```

**Hard guarantees the vendor can rely on:** discount stays within 5–70%; the recommended price is never below
`cost + Rp500`; prices round to Rp500 and discounts to 5% (Indonesian pricing convention).

Special cases short-circuit the formula: expires today → fire sale at the margin ceiling with *"HARI INI SAJA!"*;
stock ≤ 2 → minimal 5–15% discount, not worth the margin; already expired → discard/donate advice, no deal.

---

## API surface

| Method | Endpoint | Round | Purpose |
|---|---|---|---|
| `POST` | `/api/recommend` | **[P]** | The core interaction. Returns one of four outcomes. |
| `POST` | `/api/deals` | **[F]** | Publish a revalidated recommendation → `201 { deal_id }` |
| `GET` | `/api/deals?status=active` | **[F]** | Consumer feed |
| `DELETE` | `/api/deals/{id}` | **[F]** | Mark `removed` → `204` |
| `POST` | `/api/deals/{id}/claims` | **[F]** | Claim one unit → `201 { claim_code }` / `409` |
| `POST` | `/api/claims/{code}/redeem` | **[F]** | Redeem once → `200` / `404` / `409` |

## Deployment topology

```
Penyisihan [P]                          Final [F] adds SQLite
─────────────────────────               ─────────────────────────
Browser SPA                             Browser SPA
   │ HTTP                                  ├─ /business ──┐
   ▼                                       └─ /deals ─────┤
FastAPI ──HTTP──► local model server                      ▼
   │                                                   FastAPI ──► model server
   └──► pricing.py                                        ├──► pricing.py
                                                          └──► data/hargaturun.db
```

`docker compose up` starts frontend + API + model server (+ a mounted volume for the SQLite file in the final
round). No database *service*, no queue, no worker, no scheduled task — by design and by competition rule.

---

## Smoke tests

**Preliminary [P]**
```
structured input        → complete recommendation
colloquial free text    → parses, then completes after confirmation
missing cost            → needs_confirmation, never a fabricated number
far-expiry low-pressure → no_action
expires today           → bounded fire sale, margin floor still holds
cost >= price           → warning, no recommendation
same input twice        → identical numbers
```

**Final [F]**
```
recommend → publish → browse → claim → redeem → restart API → state persists
stock = 1: first claim 201, second claim 409, remaining_stock = 0
redeem the same code twice: 200 then 409
publish a price below the margin floor: rejected by the server
```

---

## Documents

| File | What it is |
|---|---|
| [`docs/HargaTurun_Project_Spec.md`](docs/HargaTurun_Project_Spec.md) | Problem, personas, the full oracle formula, model choice, business model, risks |
| [`docs/HargaTurun_Penyisihan_SRS.md`](docs/HargaTurun_Penyisihan_SRS.md) | **Authoritative** preliminary scope, API contract, acceptance criteria |
| [`docs/HargaTurun_Final_SRS.md`](docs/HargaTurun_Final_SRS.md) | Final-round marketplace loop, data model, phased cut line |
| [`docs/HargaTurun_FineTuning_Plan.md`](docs/HargaTurun_FineTuning_Plan.md) | QLoRA runbook — data generation, hyperparameters, eval, GGUF export |
| [`docs/AIC_Technical_Guide.md`](docs/AIC_Technical_Guide.md) | Competition rules, technical constraints only |
| [`docs/AI_Innovation_Challenge.md`](docs/AI_Innovation_Challenge.md) | Full rulebook |

Where the Project Spec and the SRS documents disagree on scope, **the SRS wins** — the Project Spec describes the
two-sided vision, the SRSs describe what each round actually ships.

---

*Licensed under the terms in [LICENSE](LICENSE).*
