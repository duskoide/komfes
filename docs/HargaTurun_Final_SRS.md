# HargaTurun — Software Requirements Specification: Final-Round Extension

> **Status:** Planned enhancement after a completed, working [Penyisihan MVP](HargaTurun_Penyisihan_SRS.md)
> **Scope:** Minimal vendor-to-consumer deal lifecycle
> **Not an organizer-mandated feature list:** AIC defines the final as a 10-hour iterative hackathon. This document is the team's proposed, prioritized expansion—not a claim that all features are required by the organizer.
> **Companion documents:** [Penyisihan SRS](HargaTurun_Penyisihan_SRS.md), [Project Spec](HargaTurun_Project_Spec.md), [Agentic Workflow Plan](HargaTurun_Agentic_Workflow_Plan.md)

## 1. Purpose and delivery rule

The final extension turns a validated business-owner recommendation into a minimal local marketplace loop:

```text
Vendor receives recommendation -> publishes it -> consumer browses it
-> consumer claims one unit -> vendor redeems the claim
```

It starts only from the preliminary MVP's existing, verified core: bounded conversational intake, explicit confirmation, deterministic pricing-tool use, and the business recommendation screen. The final must remain locally demoable and synchronous. The organizer's final has a 10-hour hackathon constraint, so each phase below is independently demonstrable; do not start a later phase until the prior phase works.

## 2. Scope

### 2.1 Included

- Vendor publishes a previously calculated recommendation as a live deal.
- Vendor sees active deals, remaining stock, and claim codes; vendor can remove a deal.
- Consumer browses active deals without an account.
- Consumer claims one available unit and receives a unique claim code.
- Vendor redeems a valid claim exactly once.
- SQLite persists deals and claims across API restarts.
- Stock changes are atomic enough for the local demo: claim creation succeeds only while stock remains positive.

### 2.2 Still excluded

- Authentication, payments, delivery, maps/geolocation, consumer profiles, shop routing, notifications, analytics, or history dashboards.
- Background jobs, scheduled expiry scans, automatic logging, daily feedback loops, model auto-tuning, and bulk evaluation tools.
- Real-time sockets, distributed databases, multi-instance scaling, and cloud deployment.
- OCR, voice, multi-item batch operations, and native mobile apps.

A deal may be manually removed by the vendor. Time-based automatic expiration is deferred because it would introduce background work; the UI can calculate/display an expiry hint but must not promise automatic status transitions.

## 3. Final-round priorities

| Phase | Goal | Demonstrable outcome |
|---|---|---|
| 0 | Preserve preliminary core | Vendor can still request a recommendation and view a preview. |
| 1 | Publish and browse | Vendor publishes a computed preview; consumer `/deals` immediately lists it. |
| 2 | Claim safely | One consumer claim returns a code and decrements remaining stock without going below zero. |
| 3 | Redeem and manage | Vendor sees a claim, redeems it once, and can remove a deal. |
| 4 | Harden only if time remains | Validation, empty/error states, responsive polish, final smoke test, README/video updates. |

**Cut line:** Phase 1 is the minimum final expansion. Phases 2–3 are valuable only after publish/browse works end-to-end. Do not add planned upgrades if the core recommendation or publish/browse loop is broken.

## 4. Users and flows

### 4.1 Vendor: recommend and publish

1. Vendor completes the existing preliminary recommendation flow.
2. The result includes a static preview plus **Publikasikan**.
3. Vendor may optionally adjust permitted display data before publishing, but price must remain at or above the engine's margin floor.
4. The API stores the computed deal and returns an ID.
5. The deal appears in the vendor active-deals list and on the consumer route.
6. Vendor may remove a deal. Removed deals no longer appear in the active consumer list.

### 4.2 Consumer: browse and claim

1. Consumer opens `/deals`; no account or login is requested.
2. The page lists active deals with item, shop, original/deal prices, discount, time remaining, remaining stock, and promo text.
3. Consumer taps **Klaim** for one unit.
4. If stock exists, the page displays a unique claim code. If not, the API returns a conflict and the UI shows **Habis**.

### 4.3 Vendor: redeem

1. Consumer presents the claim code in person.
2. Vendor enters/selects the code in the business view.
3. A valid unredeemed code becomes `redeemed`; a repeated redemption returns a clear conflict.

Claims reserve stock at claim time. Redemption confirms collection; it must not decrement stock a second time.

## 5. Architecture

```text
Browser SPA
  |-- /business --> FastAPI --> local model server
  |                    |             (constrained conversational agent)
  |                    +--> conversation state/validators
  |                    +--> PricingTool -> pricing.py
  |                    +--> SQLite file
  |
  +-- /deals -----> FastAPI --> SQLite file
```

The conversational workflow and pricing engine retain exactly the preliminary responsibility split:

- Local model: propose structured state patches and generate faithful Indonesian language.
- Orchestrator: own state, confirmation, transition guards, tool routing, validation, and bounded repair.
- Python pricing tool: own all arithmetic, bounds, timing, projections, and computed deal data.

SQLite is the only new persistent dependency. It is accessed through Python's standard `sqlite3`; no separate database service is required. The application remains local and uses Docker Compose to run the frontend, API, and model server.

## 6. Components

### 6.1 Existing preliminary components

- **Business consultation screen:** preserves the chat, state correction, confirmation, safety, and no-action behavior from the Penyisihan SRS.
- **Model/orchestrator:** unchanged constrained inference, static parameters, explicit state, and tool gates.
- **Pricing tool:** unchanged pure calculation authority. Publication only receives already-computed, validated deal data.

### 6.2 New API/deal module

Owns SQLite initialization, deal CRUD, claim creation, redemption, and transactional stock changes. It must not invoke the model during claim or redemption.

### 6.3 Business additions

- Publish control shown only for a valid recommendation.
- Active-deals list: item, price, remaining stock, status, removal action.
- Claim/redeem view: code and status, with a redeem action.

### 6.4 Consumer route

A simple mobile-friendly active-deal list. It is a local view, not a personalized or location-based marketplace.

## 7. API contracts

The existing `POST /api/recommend` behavior remains governed by the Penyisihan SRS.

### 7.1 `POST /api/deals`

Publishes an already-computed recommendation. The server revalidates all numerical fields; the client is never trusted as the pricing authority.

```json
{
  "item_name": "Roti Tawar",
  "shop_name": "Toko Sari Bakery",
  "category": "Bakery",
  "original_price": 15000,
  "deal_price": 10500,
  "discount_percent": 30,
  "days_remaining": 2,
  "initial_stock": 10,
  "promo_copy": "Roti tawar fresh..."
}
```

Response: `201 { "deal_id": "uuid", "created_at": "ISO-8601" }`.

### 7.2 `GET /api/deals?status=active`

Returns active, non-removed deals. A deal contains `remaining_stock` and `status`; a stock-zero deal may be shown as `sold_out` but cannot be claimed.

### 7.3 `DELETE /api/deals/{id}`

Marks a deal `removed`. Response `204`. Removing a deal must not delete existing claim records.

### 7.4 `POST /api/deals/{id}/claims`

Claims exactly one unit and creates a unique code.

Response: `201 { "claim_code": "HT-XXXX" }`.

Response `409` when the deal is removed, sold out, or otherwise unavailable.

**Atomicity requirement:** in one SQLite transaction, verify the deal is active with `remaining_stock > 0`, decrement it once, generate/insert a collision-free claim code, and mark the deal sold out if stock reaches zero. Roll back everything if any step fails.

### 7.5 `POST /api/claims/{code}/redeem`

Response: `200 { "status": "redeemed" }` for a valid claimed code.

Responses: `404` for unknown code; `409` for already redeemed, or a code belonging to a removed/invalid deal where policy disallows redemption. The implementation must select and document one policy; the recommended simple policy is that claims made before removal remain redeemable until the vendor rejects them manually.

## 8. Data model

SQLite file: `data/hargaturun.db`, mounted as a Docker volume so data survives API restarts.

### 8.1 `deals`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT primary key | UUID |
| `item_name` | TEXT | Required |
| `shop_name` | TEXT | May be blank if preliminary input omitted it |
| `category` | TEXT | Allowed pricing category |
| `original_price` | INTEGER | Rupiah |
| `deal_price` | INTEGER | Validated engine value |
| `discount_percent` | INTEGER | Validated engine value |
| `days_remaining` | REAL | Display information from recommendation |
| `initial_stock` | INTEGER | Positive whole number |
| `remaining_stock` | INTEGER | Decremented at claim time, never negative |
| `promo_copy` | TEXT | Generated/reviewed preview text |
| `status` | TEXT | `active`, `sold_out`, or `removed` |
| `created_at` | TEXT | ISO-8601 timestamp |

### 8.2 `claims`

| Column | Type | Notes |
|---|---|---|
| `code` | TEXT primary key | Unique claim code, e.g. `HT-4821` |
| `deal_id` | TEXT | Foreign key to `deals.id` |
| `status` | TEXT | `claimed` or `redeemed` |
| `created_at` | TEXT | ISO-8601 timestamp |
| `redeemed_at` | TEXT | Nullable ISO-8601 timestamp |

There is intentionally no `daily_stock_log`, customer table, analytics table, or automatic expiry tracker.

## 9. Functional requirements

| ID | Requirement |
|---|---|
| F-FR-1 | The completed Penyisihan recommendation flow remains usable without regression. |
| F-FR-2 | Only a successful, validated recommendation can be published as a deal. |
| F-FR-3 | Publishing makes the deal visible through `GET /api/deals` and `/deals` without a background process. |
| F-FR-4 | Consumers can browse active deals without authentication. |
| F-FR-5 | Each deal card displays complete, truthful computed pricing and remaining-stock information. |
| F-FR-6 | A successful claim reserves one unit, returns a unique code, and decrements stock once. |
| F-FR-7 | Concurrent local claim attempts never make `remaining_stock` negative or issue a claim after sellout. |
| F-FR-8 | A vendor can redeem a valid claim once; duplicate redemption returns `409` and changes nothing. |
| F-FR-9 | A vendor can remove a deal; it is no longer claimable or listed as active. |
| F-FR-10 | Deal and claim data survive an API restart. |
| F-FR-11 | All deal lifecycle actions are synchronous; no queue, timer, or worker is required. |

## 10. Non-functional requirements and validation

| Requirement | Validation |
|---|---|
| Local operation | `docker compose up` starts all required services and a browser can complete the flow. |
| Reproducible core inference | Repeat the same preliminary confirmed input; numerical recommendation remains identical. |
| Persistence | Publish/claim, restart API, then verify deal/claim records remain. |
| Stock correctness | Start with stock 1; first claim succeeds, second returns `409`; remaining stock is 0. |
| Redemption correctness | Redeem the same code twice; first succeeds and second returns `409`. |
| Pricing safety | Server rejects a publish attempt whose price violates the margin floor or has inconsistent discount data. |
| Scope discipline | Repository contains no scheduled task, daily logging pipeline, auth/payment flow, or distributed database. |

Minimum final smoke test:

```text
recommend -> publish -> browse -> claim -> redeem -> restart API -> verify persisted state
```

## 11. Risks and decisions

| Risk | Mitigation / decision |
|---|---|
| 10-hour final time limit | Implement in phases; publish/browse precedes claims/redemption; cut optional polish. |
| Marketplace scope dilutes the AI core | Reuse the completed preliminary recommendation flow and demonstrate it first. |
| Overselling under simultaneous claims | Use a single SQLite transaction with a conditional stock check. |
| Claim-code collision | Use a sufficiently random code and rely on the primary-key constraint; retry on the rare collision. |
| Automatic expiry adds operational complexity | Do not automate it. Vendor removal is the final-MVP control. |
| Consumer trust in near-expiry goods | Always display time remaining and honest promo wording; never fabricate urgency. |

## 12. Deferred work

Only after the final MVP is stable: QR display, payment, maps, notifications, account/authentication, multi-shop routing, automatic expiry, histories/analytics, daily inventory feedback, OCR, voice, and bulk item processing. None is prerequisite to proving the vendor-to-consumer marketplace loop.
