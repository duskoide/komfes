# HargaTurun — AI-Powered Surplus Food Marketplace for Indonesian UMKM

> **Project Specification & Pre-Technical Document**
> Theme alignment: *AI for the Backbone of the Economy* → Smart Commerce
> Competition: COMPFEST 18 — AI Innovation Challenge (AIC)
> Version: 2.0 — Two-sided platform framing

---

## 1. Problem Statement

### 1.1 The Core Problem

Indonesian micro, small, and medium enterprises (UMKM) in the food sector — warungs, small
restaurants, cafés, bakeries, catering services, food stalls (warung makan, kedai, rumah makan)
— operate on razor-thin margins (5–20%) while routinely losing **20–40% of perishable
inventory** to expiration or spoilage.

Unlike supermarket chains and franchise brands that employ dedicated revenue management teams
and enterprise markdown software (Wasteless, Yieldigo, Smartway), UMKM owners make pricing
and markdown decisions purely on gut feeling — if they make them at all.

The result is a **three-way loss**:

- **Business loses revenue:** Unsold expired goods are total loss (purchase cost + preparation
  labor + storage). A small bakery losing 15 breads/day at Rp8.000 cost = Rp3.6M/month wasted.
- **Consumer loses access:** Affordable near-expiry food is thrown away instead of reaching
  price-sensitive buyers (students, low-income families, budget-conscious workers) who would
  gladly purchase quality food at a discount.
- **Environment suffers:** Indonesia ranks among the top food-wasting nations globally
  (~300 kg/capita/year, BAPPENAS). UMKM food service waste is a significant and growing
  contributor as the sector expands.

### 1.2 The Missing Middle

Enterprise markdown platforms exist for large retailers. Consumer-facing surplus food apps
exist in Europe/US (Too Good To Go, $1.5B valuation; Flashfood; Karma). But in Indonesia:

| Existing solution | Why it fails Indonesian UMKM |
|---|---|
| Enterprise markdown platforms (Wasteless, Yieldigo, Smartway) | Require POS integration, thousands of SKUs, cloud infra; priced for chains (USD $thousands/month) |
| Digital kasir/POS apps (Kulaku, KasirinAja, BukuWarung, Moka) | Track sales & stock but have **zero pricing intelligence** — no expiry-aware recommendations, no markdown optimization |
| Consumer surplus food apps (Too Good To Go model) | **Do not exist in Indonesia.** No local equivalent connects UMKM surplus food to budget consumers |
| Manual discount (shouting "turun harga!", stickers) | Vendor guesses the discount %, often too little (item still expires) or too much (margin destroyed). No visibility to consumers beyond walk-by traffic |
| Doing nothing | Default behavior — vendor absorbs the loss or throws the product away |

**There is no platform in Indonesia that:**
1. **Uses AI to tell UMKM the optimal markdown price** (not just "discount something"), AND
2. **Connects that discounted surplus to consumers who want it** (broadcast/marketplace layer)

HargaTurun fills both gaps in a single, lightweight product.

### 1.3 The Insight

The problem has two halves that are trivially connected:

- **Supply side (business):** *"Given X units of product Y expiring in Z days, what discount
  maximizes revenue while ensuring sell-through?"* — an optimization problem.
- **Demand side (consumer):** *"Where can I get good food cheaply today?"* — a discovery
  problem.

Enterprise solutions over-engineer the supply side. Consumer apps ignore the supply side
entirely (vendors set their own prices). **Nobody combines AI-optimized pricing with consumer
discovery at UMKM scale.**

A fine-tuned **Qwen3.5-4B** language model handles the parts that need language: parsing
free-text input, generating explanations, and writing promotional copy. A deterministic Python pricing
engine (the same oracle formula used to generate training data) handles the arithmetic:
discount calculation, revenue/loss projection, and deal JSON assembly. The model never does
math — it extracts meaning and produces words; Python produces numbers. The consumer side is
then a lightweight read-only page that renders the assembled output.

---

## 2. Target Users

### 2.1 Supply Side: UMKM Food Business Owner/Manager

**Primary persona — "Bu Sari" (Warung/Kedai Owner):**
- Ages 30–55, runs a small food shop (warung sembako, toko kue, warung makan, kedai kopi).
- Sells perishables daily: bread, dairy, eggs, snacks, prepared meals, beverages.
- Tech literacy: low-to-moderate. Uses WhatsApp, basic smartphone apps. Unlikely to use
  complex dashboards or English interfaces.
- Solo operator or family-run. Makes all purchasing, pricing, and discounting decisions alone.
- **Pain:** Knows she loses money on expired/unsold goods but doesn't know *how much* or
  *what price to set*. Discounts are ad-hoc or not done at all.

**Secondary persona — "Mas Dimas" (Small Café/Restaurant Manager):**
- Ages 25–40, manages a small café, restaurant, or catering service (2–10 employees).
- Sells prepared food with very short shelf life (pastries, meals, desserts, fresh juices).
- Tech literacy: moderate. Uses POS apps, social media for marketing.
- **Pain:** End-of-day surplus is common (unsold pastries, prepped ingredients). Currently
  either thrown away or given to staff. Wants a systematic way to recover value.

**Tertiary persona — "Mbak Rina" (Home-based Food Seller / Online UMKM):**
- Ages 25–45, sells batch-cooked food (keripik, sambal, kue kering, frozen food) via
  Instagram, WhatsApp, or Shopee from home.
- Tech literacy: moderate-to-high.
- **Pain:** Overproduction per batch; items expire before selling out. Limited marketing
  reach for last-minute discounts.

### 2.2 Demand Side: Price-Sensitive Consumers

**Primary persona — "Andi" (University Student):**
- Ages 18–24, tight budget (Rp1–2M/month living cost).
- Actively seeks affordable food options near campus/kos.
- Tech-native: checks phone constantly, uses WhatsApp/Instagram.
- **Pain:** Good food is expensive; cheap food is often low quality. Wants a way to find
  quality food at reduced prices.

**Secondary persona — "Pak Joko" (Budget-Conscious Worker/Family):**
- Ages 30–50, manages household food budget for a family.
- Willing to buy near-expiry items if quality is assured and price is right.
- **Pain:** No systematic way to know which shops have markdowns today.

### 2.3 Anti-Users (Out of Scope)

- Supermarket chains, convenience store franchises (Indomaret, Alfamart) — they have enterprise
  solutions and are not UMKM.
- Non-food retailers (electronics, clothing) — the perishability problem doesn't apply.
- Fine-dining restaurants — surplus food model doesn't fit their brand/positioning.
- Consumers expecting delivery/ecommerce logistics — this is a discovery + claim-in-store model.

---

## 3. User Pain Points & Jobs-to-Be-Done

### 3.1 Business Side

| # | Pain Point | Job-to-Be-Done |
|---|---|---|
| B1 | "I don't know which items will expire soon or how much I'm losing" | Help me **identify** at-risk inventory and quantify the loss |
| B2 | "I don't know how much to discount" | Tell me the **optimal discount %** that balances sell-through vs. margin |
| B3 | "I discount too late and it still expires" | Tell me **when** to start discounting (timing) |
| B4 | "I discount too much and destroy my margin" | Ensure I **never discount more than necessary** |
| B5 | "Even if I discount, walk-by traffic isn't enough to sell it all" | Help me **reach more buyers** beyond foot traffic |
| B6 | "I don't have time to write promotional messages" | **Generate** the promotional copy for me |
| B7 | "I can't explain to my partner/employee why this price" | Give me a **clear reason** I can communicate |

### 3.2 Consumer Side

| # | Pain Point | Job-to-Be-Done |
|---|---|---|
| C1 | "I don't know which shops have discounts today" | Show me **available deals** near me / from shops I follow |
| C2 | "I'm not sure if discounted food is still good" | Show me **time remaining** and item condition so I can judge |
| C3 | "I don't want to create accounts everywhere" | Let me browse deals **without registration** |
| C4 | "I want to act fast before items sell out" | Show me **stock remaining** and let me **claim/reserve** quickly |

---

## 4. Solution Overview

**HargaTurun** is a two-sided, AI-powered surplus food platform for Indonesian UMKM:

> **For businesses:** "AI tells you the exact price to set, writes the promo for you, and
> broadcasts it to nearby buyers — in one step."
>
> **For consumers:** "See today's food deals from local shops. Good food, lower price,
> less waste."

### 4.1 Platform Flow

```
╔══════════════════════════════════════════════════════════════╗
║                    BUSINESS SIDE (AI Core)                    ║
║                                                              ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │  INPUT: item name, category, expiry, stock, price,     │  ║
║  │         cost (via form OR free-text)                    │  ║
║  └───────────────────────┬────────────────────────────────┘  ║
║                          ▼                                   ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │  AI ENGINE — Hybrid (Model + Python Pricing Engine)    │  ║
║  │                                                        │  ║
║  │  Step 1: Fine-tuned Qwen3.5-4B model (single inference) │  ║
║  │    → parses input (structured or free-text)            │  ║
║  │    → generates explanation (why this price)            │  ║
║  │    → generates promotional copy                        │  ║
║  │                                                        │  ║
║  │  Step 2: Python pricing engine (deterministic, ~50 LOC)│  ║
║  │    → computes discount %, recommended price, timing    │  ║
║  │    → projects sell-through, revenue vs. loss           │  ║
║  │    → assembles final deal JSON for consumer page       │  ║
║  │    → enforces margin floor + bounds (5–70%)            │  ║
║  └───────────────────────┬────────────────────────────────┘  ║
║                          ▼                                   ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │  VENDOR CONFIRMS → deal goes live                      │  ║
║  │  (one-tap "Publikasikan" button)                       │  ║
║  └───────────────────────┬────────────────────────────────┘  ║
╚══════════════════════════╪═══════════════════════════════════╝
                           │
                           ▼
╔══════════════════════════════════════════════════════════════╗
║              CONSUMER SIDE (Read-Only Deals Page)             ║
║                                                              ║
║  ┌────────────────────────────────────────────────────────┐  ║
║  │  "HargaTurun — Deals Hari Ini"                         │  ║
║  │                                                        │  ║
║  │  ┌──────────────────────────────────────────────┐      │  ║
║  │  │ 🍞 Roti Tawar — Toko Sari Bakery            │      │  │
║  │  │ Rp10.500 (was Rp15.000) · 30% OFF           │      │  │
║  │  │ Sisa 2 hari · Stok: 8 pcs                   │      │  │
║  │  │ [Klaim]                                    │      │  │
║  │  └──────────────────────────────────────────────┘      │  ║
║  │                                                        │  ║
║  │  ┌──────────────────────────────────────────────┐      │  ║
║  │  │ ☕ Iced Latte — Kedai Dimas                  │      │  │
║  │  │ Rp12.000 (was Rp22.000) · 45% OFF           │      │  │
║  │  │ Hari ini saja · Stok: 4 cups                │      │  │
║  │  │ [Klaim]                                    │      │  │
║  │  └──────────────────────────────────────────────┘      │  ║
║  │                                                        │  ║
║  │  No login. No geolocation. Just today's deals.         │  ║
║  └────────────────────────────────────────────────────────┘  ║
║                                                              ║
║  CLAIM FLOW:                                                 ║
║  Consumer taps [Klaim] → gets a simple claim code            ║
║  → shows code at shop → vendor marks as redeemed             ║
║  (No payment integration. Pay at shop as normal.)            ║
╚══════════════════════════════════════════════════════════════╝
```

### 4.2 Core Value Proposition

**For businesses:**
1. **Reduce waste** — items sell before expiry instead of being thrown away.
2. **Protect margin** — AI finds the *minimum* discount needed, not a blanket 50% off.
3. **Reach more buyers** — deal is broadcast beyond foot traffic, increasing sell-through.
4. **Zero effort marketing** — AI writes the promotional copy; vendor just confirms.
5. **Explainable** — every recommendation has a reason the vendor can trust and communicate.

**For consumers:**
1. **Save money** — quality food at 20–50% off.
2. **No friction** — no account, no app install, just a web page.
3. **Transparency** — see exactly what's discounted, how fresh it is, how much is left.
4. **Feel good** — actively reducing food waste with every purchase.

**For the ecosystem:**
1. **Food waste reduction** — direct SDG 12 (Responsible Consumption & Production) impact.
2. **Food affordability** — increases access to quality food for budget consumers.
3. **UMKM resilience** — recovers revenue that would otherwise be lost.

---

## 5. Functional Requirements

### 5.1 AI Core — Pricing Engine (MUST-HAVE)

| ID | Requirement | Description |
|---|---|---|
| FR-1 | **Item input (structured)** | Business user provides: item name, category (bakery/dairy/produce/prepared-food/beverage/snack/other), expiry date or days remaining, stock quantity, current selling price, purchase/production cost per unit. |
| FR-2 | **Item input (free-text)** | Business user types naturally: "roti tawar 10 biji exp 2 hari harga 15rb modal 10rb" → system parses into structured fields. |
| FR-3 | **Markdown recommendation** | System outputs: optimal discount %, recommended selling price, recommended timing ("mulai hari ini" vs. "tunggu 1 hari"). |
| FR-4 | **Impact projection** | System outputs: expected units sold, expected revenue at recommended price, expected loss if no action taken (items expire unsold). |
| FR-5 | **Explanation (business-facing)** | System outputs: 2–4 sentences in plain Bahasa Indonesia explaining *why* this specific discount, referencing shelf life, stock, and category behavior. |
| FR-6 | **Promotional copy (consumer-facing)** | System outputs: a short, catchy deal description (1–2 sentences) suitable for display on the deals page. Includes urgency framing. |
| FR-7 | **Structured deal data** | System outputs: JSON with all fields needed to render a deal card (item, prices, discount, expiry, stock, shop name, promo text). |
| FR-8 | **Single-interaction flow** | One input → one output containing all three outputs above. No multi-step wizard. |

### 5.2 Business-Side Features (MUST-HAVE)

| ID | Requirement | Description |
|---|---|---|
| FR-9 | **Publish deal** | After receiving recommendation, vendor taps "Publikasikan" → deal appears on consumer page. One-tap confirmation. |
| FR-10 | **View active deals** | Vendor can see their currently published deals and remaining claimed/unclaimed stock. |
| FR-11 | **Mark redeemed** | When consumer shows claim code, vendor marks it as redeemed (decrement stock). |
| FR-12 | **Remove deal** | Vendor can unpublish a deal at any time (item sold out, changed mind). |
| FR-13 | **Margin floor enforcement** | System NEVER recommends a price below cost. If vendor manually overrides below cost, show a warning. |
| FR-14 | **"No action needed" response** | If item has ample shelf life relative to typical sell-through, system says: "Belum perlu diskon. Cek lagi dalam X hari." |

### 5.3 Consumer-Side Features (MUST-HAVE)

| ID | Requirement | Description |
|---|---|---|
| FR-15 | **Browse deals** | Consumer sees a list of all active deals (today's deals). No login required. |
| FR-16 | **Deal card display** | Each deal shows: item name, shop name, original price, deal price, discount %, time remaining, stock remaining, promo text. |
| FR-17 | **Claim deal** | Consumer taps "Klaim" → receives a unique claim code (simple alphanumeric). No payment. |
| FR-18 | **Claim code display** | Consumer can show the code at the shop (text is sufficient; QR optional). |
| FR-19 | **Stock decrement** | When claimed, available stock decreases. When stock = 0, deal shows "Habis" and is unclaimable. |

### 5.4 Model Behavior Requirements

| ID | Requirement | Description |
|---|---|---|
| FR-20 | **Deterministic output** | Same input → same output. Static parameters, greedy decoding (temp=0). Competition rule: "parameter statis." |
| FR-21 | **Category-aware pricing** | Different categories have different elasticity + perishability profiles. Bakery ≠ canned goods. |
| FR-22 | **Shelf-life sensitivity** | 1 day left vs. 5 days left → very different recommendations. Urgency scales non-linearly. |
| FR-23 | **Stock quantity awareness** | 3 units vs. 50 units → different discount depth and urgency. |
| FR-24 | **Reasonable bounds** | Discount bounded 5%–70%. No absurd outputs. |
| FR-25 | **Promo copy tone** | Consumer-facing text is friendly, urgent but not desperate. No misleading claims. |
| FR-26 | **Confidence indication** | Output includes certainty level: "Prediksi cukup yakin" vs. "Prediksi kurang pasti." |

### 5.5 System / Integration Requirements

| ID | Requirement | Description |
|---|---|---|
| FR-27 | **Synchronous API** | Single request → single response. No background jobs, no queue. |
| FR-28 | **Docker Compose deployment** | Entire system (model + backend + frontend) runs via `docker compose up`. |
| FR-29 | **Local execution** | Must run fully on localhost. No external API calls at inference time. |
| FR-30 | **README setup guide** | Clear instructions for a non-team-member to run the app locally. |
| FR-31 | **Two views, one app** | Business view and consumer view are routes in the same web app. Not separate deployments. |

---

## 6. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | **Inference latency** | < 10 seconds end-to-end (input → all outputs displayed) |
| NFR-2 | **Hardware ceiling** | Must run on: 1× GPU 8GB VRAM + 20GB system RAM. No multi-GPU. |
| NFR-3 | **Model size** | Qwen3.5-4B (4B parameters, 4-bit quantized for inference). ~2.5 GB VRAM at inference, ~4–5 GB for QLoRA training. Fits 8GB GPU with headroom. |
| NFR-4 | **Offline capability** | No internet required at inference time. Model weights bundled or pre-downloaded. |
| NFR-5 | **Reproducibility** | Same input → same output (static parameters, greedy decoding). |
| NFR-6 | **Modular architecture** | Clear separation: model layer / API layer / frontend layer. |
| NFR-7 | **Startup time** | Cold start (model load) < 60s. Warm inference < 10s. |
| NFR-8 | **Concurrent users** | MVP: small-scale demo (≤5 concurrent). No multi-tenant requirement. |
| NFR-9 | **Data persistence** | Active deals + claim codes persist across app restarts (simple file/SQLite). No distributed DB. |
| NFR-10 | **Mobile-friendly UI** | Consumer page must be usable on a phone browser (responsive). Business page can be desktop-first. |

---

## 7. User Stories

### US-1: Get Pricing Recommendation (Business — Primary Flow)

> **As a** café owner with 8 unsold pastries expiring tomorrow,
> **I want to** input the item details and get an AI recommendation,
> **So that** I know the exact price to set to sell them before they expire.

**Acceptance criteria:**
- Input form accepts: item name, category, expiry, stock, price, cost.
- Output shows: recommended price, discount %, timing, expected sell-through, revenue vs. loss.
- Output includes: business explanation (2–4 sentences) + consumer promo copy + deal JSON.
- Response time < 10 seconds.

### US-2: Natural Language Input (Business)

> **As a** warung owner who doesn't like filling forms,
> **I want to** type "kue lapis 5 loyang exp besok harga 25rb modal 18rb",
> **So that** the system understands and gives me the same recommendation.

**Acceptance criteria:**
- System parses free-text into structured fields correctly.
- If ambiguous, system asks ONE clarifying question.
- Output format identical to US-1.

### US-3: Publish a Deal (Business → Consumer)

> **As a** vendor who just received a recommendation,
> **I want to** publish it as a deal in one tap,
> **So that** nearby consumers can see it and come buy.

**Acceptance criteria:**
- "Publikasikan" button appears with the recommendation.
- On tap, deal appears on consumer page within 2 seconds.
- Deal card shows: item, prices, discount, time left, stock, promo text.
- Vendor can see it in their "Active Deals" list.

### US-4: Browse and Claim a Deal (Consumer)

> **As a** student looking for cheap lunch,
> **I want to** see today's food deals and claim one,
> **So that** I can show the code at the shop and get the discounted price.

**Acceptance criteria:**
- Consumer page loads a list of active deals without login.
- Each deal shows all relevant info (item, shop, prices, discount, time, stock).
- Tapping "Klaim" generates a unique code (e.g., "HT-4821").
- Stock decrements by 1. If stock hits 0, deal shows "Habis."

### US-5: Redeem at Shop (Consumer ↔ Business)

> **As a** consumer at the shop,
> **I want to** show my claim code,
> **So that** the vendor verifies it and gives me the discounted item.

**Acceptance criteria:**
- Vendor sees claim code in their dashboard.
- Vendor marks it "Redeemed."
- Consumer's code status changes to "Digunakan."

### US-6: No Action Needed (Business — Edge Case)

> **As a** vendor who inputs an item with 30 days remaining and normal stock,
> **I want** the system to tell me "no action needed yet",
> **So that** I don't unnecessarily discount items that will sell normally.

**Acceptance criteria:**
- Output: "Belum perlu diskon. Item ini kemungkinan terjual normal sebelum kadaluarsa. Cek lagi dalam X hari."
- No deal is published.

### US-7: Critical / Already Expiring (Business — Edge Case)

> **As a** vendor with 20 meals expiring TODAY,
> **I want** an aggressive recommendation,
> **So that** I recover at least some value instead of total loss.

**Acceptance criteria:**
- Discount approaches upper bound (50–70%).
- Explanation: "Waktu sangat terbatas. Lebih baik untung kecil daripada rugi total."
- Promo copy conveys urgency: "HARI INI SAJA!"
- Still respects margin floor.

### US-8: Deal Expires / Sold Out (Consumer)

> **As a** consumer browsing deals,
> **I want to** clearly see when a deal is no longer available,
> **So that** I don't waste a trip to the shop.

**Acceptance criteria:**
- Expired deals (past expiry time) show "Kadaluarsa" and are unclaimable.
- Sold-out deals show "Habis" and are unclaimable.
- Both are visually distinct from active deals (greyed out or moved to bottom).

---

## 8. Scope Boundaries (Competition MVP Alignment)

### 8.1 IN SCOPE (Penyisihan)

**AI Core:**
- ✅ Single-input → single-output AI interaction (FR-1 through FR-8)
- ✅ Structured form + free-text input (FR-1, FR-2)
- ✅ Pricing recommendation + impact projection + explanation (FR-3, FR-4, FR-5)
- ✅ Promotional copy generation (FR-6)
- ✅ Static model parameters, deterministic output (FR-20)
- ✅ Fine-tuned Qwen3.5-4B model (4B params, within competition 4–9B range)

**Business Side:**
- ✅ Publish/unpublish deal (FR-9, FR-12)
- ✅ View active deals (FR-10)
- ✅ Mark redeemed (FR-11)
- ✅ Margin floor enforcement (FR-13)

**Consumer Side:**
- ✅ Browse deals (no login) (FR-15)
- ✅ Deal card display (FR-16)
- ✅ Claim deal → get code (FR-17, FR-18)
- ✅ Stock decrement (FR-19)

**System:**
- ✅ Docker Compose deployment (FR-28)
- ✅ Local execution (FR-29)
- ✅ README setup guide (FR-30)
- ✅ Single web app, two views (FR-31)
- ✅ Simple persistence (SQLite/file) (NFR-9)

### 8.2 OUT OF SCOPE (Penyisihan)

- ❌ User authentication / accounts (both sides)
- ❌ Geolocation / map / "near me" filtering
- ❌ Push notifications / reminders
- ❌ Payment integration (pay at shop)
- ❌ Multi-item batch processing ("check all my expiring items")
- ❌ Photo/OCR input (product label scanning)
- ❌ Voice input
- ❌ Analytics dashboard / history / trends
- ❌ Multi-language (Bahasa Indonesia only)
- ❌ Mobile native app (web-only, responsive)
- ❌ Background jobs / scheduled tasks
- ❌ Multi-tenant / multi-shop marketplace routing

### 8.3 HACKATHON (Final) Upgrade Candidates

If the team advances to the 10-hour hackathon, priority upgrades:

1. **Photo/OCR input** — photograph product label → auto-extract item + expiry
2. **Voice input** — Whisper-based, for hands-free vendor operation
3. **Multi-item batch** — "check all my expiring items" in one query
4. **Simple history** — track past deals, redemption rate, revenue recovered
5. **Share via WhatsApp** — one-tap share deal link to WhatsApp groups/contacts
6. **Consumer "follow shop"** — lightweight (cookie-based, no account) to see favorite shop's deals first

---

## 9. AI Model Specification (Generic)

### 9.1 Model Requirements

| Attribute | Specification |
|---|---|
| **Base model** | **Qwen3.5-4B** (`Qwen/Qwen3.5-4B`) |
| **Architecture** | Transformer-based causal language model (decoder-only), multimodal (vision + text) |
| **Parameters** | 4 billion (within competition 4–9B range) |
| **Languages** | 201 languages, including Bahasa Indonesia |
| **Quantization (inference)** | 4-bit (GGUF Q4_K_M via llama.cpp) → ~2.5 GB VRAM |
| **Quantization (training)** | QLoRA via Unsloth → ~4–5 GB VRAM |
| **Context window** | 262,144 tokens (256K) — far exceeds the ~1K needed per interaction |
| **Fine-tuning method** | QLoRA via Unsloth (LoRA rank 16–64, target: q/k/v/o/gate/up/down projections) |
| **Fine-tuning data** | Custom dataset: pricing scenarios → dual output: NLU + NLG (see §10) |
| **Inference mode** | Deterministic (temperature=0, greedy decoding) for reproducibility |
| **Serving** | llama.cpp / vLLM via Docker container |
| **Max output tokens** | 350 (sufficient for parsed_input + explanation + promo) |
| **Vision capability** | Built-in (accepts image input) — not used in MVP, available for hackathon OCR upgrade |

> **Why Qwen3.5-4B?**
> - **Indonesian fluency:** 201-language pre-training with strong Indonesian coverage.
>   The model's entire job is parsing colloquial Indonesian and generating natural
>   Bahasa Indonesia text — this is the #1 selection criterion.
> - **Right-sized:** 4B parameters fits the competition range (4–9B) and the 8GB VRAM
>   budget with headroom. The task is narrow NLU + NLG; 7B+ adds latency without
>   meaningful quality gain after domain fine-tuning.
> - **Mature tooling:** Full Unsloth support (fine-tuning), standard llama.cpp / vLLM
>   support (serving). No custom forks needed.
> - **Free vision upgrade path:** Qwen3.5-4B is multimodal. The hackathon OCR upgrade
>   (photograph product label → extract fields) can use the model's built-in vision
>   instead of a separate OCR tool. No architecture change needed.
> - **Fallback:** If Indonesian quality disappoints after fine-tuning, swap to
>   **Qwen3.5-9B** (same pipeline, one-line model ID change, ~8–10 GB QLoRA VRAM).
>
> **Candidates evaluated and rejected:**
> | Model | Why rejected |
> |---|---|
> | Nanbeige4.2-3B | English + Chinese only, no Indonesian. Custom Looped Transformer architecture breaks standard QLoRA tooling. 3B below competition range. |
> | Ternary Bonsai 27B | 27B params = 3× competition ceiling. QLoRA training needs ~14 GB VRAM. Requires PrismML's custom forks for serving. Overkill for NLU + NLG. |
> | Qwen3.5-9B | Viable fallback, but ~8–10 GB QLoRA VRAM is tight on 8GB GPU. Start with 4B, upgrade only if needed. |
> | Qwen2.5-7B-Instruct | Mature and reliable, but Qwen3.5-4B is newer with better per-parameter performance and built-in vision. |

### 9.2 Hybrid Architecture: Fine-Tuned Model + Deterministic Pricing Engine

The system splits responsibilities by what each component does best:

| Component | Responsibility | Why |
|---|---|---|
| **Fine-tuned Qwen3.5-4B** | Parse input (structured + free-text), generate explanation, generate promo copy | Language understanding and generation — what LLMs excel at |
| **Python pricing engine** | Compute discount %, recommended price, timing, sell-through, revenue/loss projections, assemble deal JSON, enforce bounds | Deterministic arithmetic — what code excels at. Uses the same oracle formula that generates training data (§10) |

The model outputs parsed fields + natural language text. Python computes all numbers and
assembles the final JSON. The model never performs arithmetic.

**Why not have the model do everything (pricing + text)?**

| Concern | Model-does-everything | Hybrid (chosen) |
|---|---|---|
| Numerical accuracy | ~90%, needs post-processing clamping | **100% exact** — formula is deterministic |
| Fine-tuning complexity | Must learn math + language simultaneously | **Language only** — smaller dataset, faster convergence |
| Post-processing layer | ~50 lines of validation/clamping | **Mostly unnecessary** — numbers are correct by construction |
| Competition rule ("model wajib di-fine tune") | ✅ | ✅ — model is still fine-tuned for NLU + NLG |
| Latency | 1 model call | 1 model call + ~1ms Python — negligible |
| Debuggability | Pricing errors buried in model output | Pricing logic is readable, testable Python code |

**Why not a separate ML model (XGBoost etc.) for pricing?**
Over-engineered for MVP. The oracle formula is already a well-defined function. Wrapping it
in a separate ML model adds a second model to serve, a second container, and integration
complexity — for zero accuracy gain.

**Model size constraints:**
- Larger model (13B+) → doesn't fit 8GB VRAM for QLoRA training.
- Smaller model (<3B) → insufficient capacity for reliable Indonesian NLU + NLG.
- **Qwen3.5-4B** → 4B params, ~4–5 GB QLoRA VRAM, 201-language pre-training.
  Sweet spot for this task. Fallback to Qwen3.5-9B if Indonesian quality is insufficient.

### 9.3 Model Input/Output Contract

**Input (as prompt, from structured form):**
```
Item: Roti Tawar
Kategori: Bakery
Harga Jual Saat Ini: Rp15.000
Harga Beli/Modal: Rp10.000
Stok: 10 pcs
Kadaluarsa: 2 hari lagi
Nama Toko: Toko Sari Bakery
```

**Input (as prompt, from free-text):**
```
roti tawar 10 biji exp 2 hari harga 15rb modal 10rb toko sari bakery
```

#### Model Output (what the LLM produces)

The model outputs **parsed fields + natural language** — no arithmetic:

```json
{
  "parsed_input": {
    "item_name": "Roti Tawar",
    "category": "Bakery",
    "original_price": 15000,
    "cost": 10000,
    "stock": 10,
    "days_remaining": 2,
    "shop_name": "Toko Sari Bakery"
  },
  "explanation": "Roti tawar punya shelf life pendek dan pembeli sangat sensitif harga. Dengan sisa 2 hari dan stok 10 pcs, diskon agresif dibutuhkan agar tidak terbuang. Tanpa aksi, sebagian besar stok akan hangus.",
  "promo_copy": "🍞 Roti Tawar Fresh — diskon spesial! Buruan sebelum habis, sisa 2 hari saja!"
}
```

#### Python Pricing Engine Output (assembled by backend)

The Python engine takes `parsed_input`, runs the oracle formula, and produces the final
response sent to the frontend:

```json
{
  "recommendation": {
    "discount_percent": 30,
    "recommended_price": 10500,
    "timing": "Mulai diskon hari ini",
    "expected_sell_through": "8 dari 10 pcs",
    "expected_revenue": 84000,
    "expected_loss_no_action": 70000,
    "confidence": "Cukup yakin"
  },
  "explanation": "Roti tawar punya shelf life pendek...",
  "promo_copy": "🍞 Roti Tawar Fresh — 30% OFF! Cuma Rp10.500 (dari Rp15.000). Sisa 2 hari, stok terbatas 10 pcs. Buruan sebelum habis!",
  "deal_data": {
    "item_name": "Roti Tawar",
    "shop_name": "Toko Sari Bakery",
    "original_price": 15000,
    "deal_price": 10500,
    "discount_percent": 30,
    "days_remaining": 2,
    "stock": 10,
    "category": "Bakery"
  }
}
```

> **Note:** The Python engine injects the computed numbers into the promo copy template
> (e.g., replacing the generic "diskon spesial" with "30% OFF! Cuma Rp10.500") before
> sending the final response. The model's promo copy serves as the base text; Python
> enriches it with exact figures.

### 9.4 Validation Layer

With the hybrid architecture, most numerical validation is **unnecessary** — the Python
pricing engine produces correct numbers by construction. The remaining validation is minimal:

| Check | Action |
|---|---|
| Model JSON output unparseable | Retry once; if still invalid, extract fields via regex fallback |
| Model `parsed_input` has missing fields | Show structured form with pre-filled guesses; ask user to confirm |
| Promo copy > 200 chars (after Python enrichment) | Truncate at last complete sentence |

The pricing engine itself enforces all numerical constraints internally:
- Discount bounded 5–70% (clamped in formula)
- Recommended price never below cost (margin floor built into formula)
- All arithmetic is deterministic and testable

This layer is **not** a second model — it's ~30 lines of Python.

### 9.5 Pricing Engine (Oracle) Specification

The oracle is a deterministic Python function that computes **all numerical outputs**.
It serves dual purpose:
- **Production:** the pricing engine in the hybrid architecture (§9.2)
- **Training:** the ground-truth generator for synthetic fine-tuning data (§10)

Write it once, use it in both places.

#### Inputs

| Field | Type | Source | Example |
|---|---|---|---|
| `category` | enum | Model parses from input | `"Bakery"` |
| `original_price` | int (Rp) | Model parses from input | `15000` |
| `cost` | int (Rp) | Model parses from input | `10000` |
| `stock` | int (units/servings) | Model parses from input | `10` |
| `days_remaining` | float | Model parses from input | `2` |
| `total_shelf_life` | float (days) | Model parses from input, or category default | `4` |
| `daily_sales` | float | Model parses from input (vendor estimate or POS data) | `5` |
| `prev_stock` | int (optional) | SQLite — yesterday's record, if available | `13` |

> **Cafe / made-to-order note:** For items made from expiring ingredients (e.g., lattes
> from expiring milk), the owner converts ingredients → sellable servings before input.
> "2L milk ≈ 20 latte servings." The oracle operates on servings, not raw ingredients.
> No special handling needed — same formula, same inputs. The consumer sees a *drink*
> discount, not an ingredient discount.

#### Default shelf life per category

Used when the vendor doesn't provide total shelf life (common for fresh/prepared food):

| Category | Default `total_shelf_life` (days) |
|---|---|
| Bakery | 4 |
| Prepared Food | 3 |
| Dairy | 14 |
| Beverage (pre-made) | 5 |
| Produce | 7 |
| Snack (packaged) | 90 |
| Canned / Bottled | 365 |
| Other | 30 |

#### Core Formula (10 steps)

**Step 1 — Sell-through pressure:**
```
days_of_supply = stock / daily_sales
pressure = days_of_supply / days_remaining
```
- `pressure ≤ 1.0` → item will likely sell naturally before expiry
- `pressure > 1.0` → surplus exists, discount needed
- Higher pressure = deeper discount

**Step 2 — Expiry urgency (relative, not absolute):**
```
life_consumed = 1 - (days_remaining / total_shelf_life)
urgency = life_consumed ^ 1.5
```
The exponent makes urgency **non-linear** — it accelerates as the product approaches
end of life:

| `life_consumed` | `urgency` |
|---|---|
| 50% | 0.35 |
| 75% | 0.65 |
| 90% | 0.85 |
| 95% | 0.93 |

> **Why relative?** 30 days left on a 365-day canned good (92% consumed) is more urgent
> than 30 days left on a 60-day snack (50% consumed). Absolute days alone would treat
> them identically.

**Step 3 — Category bias (soft starting prior):**
```python
CATEGORY_BIAS = {
    "Bakery":        1.3,   # discount stimulates demand strongly
    "Prepared Food": 1.3,
    "Dairy":         1.1,
    "Beverage":      1.0,   # baseline
    "Produce":       1.1,
    "Snack":         0.9,
    "Canned":        0.7,   # low elasticity, small discount suffices
    "Other":         1.0,
}
```
This is **not** a precise elasticity coefficient — it's a rough starting bias. The daily
re-run loop (§9.5 "Daily re-run behavior") empirically refines the effective discount
over successive days, reducing reliance on this prior.

**Step 4 — Raw discount:**
```
pressure_factor = min(1.0, (pressure - 1.0) / 4.0)   # maps pressure 1→5 to 0→1
raw_discount = pressure_factor × urgency × CATEGORY_BIAS[category] × 80
```
- `pressure_factor`: 0 when no surplus, scales to 1.0 at 5× oversupply
- `× 80`: base scale so that high pressure + high urgency approaches the 70% cap
- Result is a percentage (e.g., 32.5)

**Step 5 — Margin ceiling (hard constraint):**
```
margin_percent = ((original_price - cost) / original_price) × 100
max_discount = min(70, margin_percent - (500 / original_price × 100))
```
Ensures at least **Rp500 profit per unit** remains. An item with 20% margin can never
be discounted more than ~17%.

**Step 6 — Final discount:**
```
discount = round_to_5(clamp(raw_discount, 5, max_discount))
```
Bounded 5–70%, rounded to nearest 5% (Indonesian pricing convention: 5%, 10%, 15%…).

**Step 7 — Recommended price:**
```
recommended_price = round_to_500(original_price × (1 - discount / 100))
recommended_price = max(recommended_price, cost + 500)   # absolute floor
```
All prices rounded to nearest Rp500 (Indonesian convention).

**Step 8 — Impact projections:**
```
# With discount: demand increases roughly proportional to discount depth
expected_sell_through = min(stock, daily_sales × days_remaining × (1 + discount / 50))
expected_revenue = expected_sell_through × recommended_price

# Without discount: natural sell-through
baseline_sell_through = min(stock, daily_sales × days_remaining)
expected_loss_no_action = max(0, (stock - baseline_sell_through)) × cost
```

**Step 9 — Timing recommendation:**
```
if pressure ≤ 1.0 and urgency < 0.7:
    timing = "Belum perlu diskon"
elif pressure ≤ 1.5:
    timing = "Bisa tunggu 1 hari, cek lagi besok"
else:
    timing = "Mulai diskon hari ini"
```

**Step 10 — Confidence level:**
```
if daily_sales is vendor estimate (not POS data):
    confidence = "Cukup yakin"
if daily_sales < 1 or data very sparse:
    confidence = "Prediksi kurang pasti"
if pressure > 3 and urgency > 0.8:
    confidence = "Cukup yakin"   # clear-cut situation regardless of data quality
```

#### Special Cases

| Case | Condition | Behavior |
|---|---|---|
| **No action needed** | `pressure ≤ 1.0` AND `urgency < 0.7` | Output: *"Belum perlu diskon. Item ini kemungkinan terjual normal sebelum kadaluarsa. Cek lagi dalam X hari."* No deal published. |
| **Fire sale (expires today)** | `days_remaining < 1` | Override: discount = `min(70%, margin ceiling)`. Timing = *"HARI INI SAJA!"* Max urgency regardless of ratio. |
| **Already expired** | `days_remaining ≤ 0` | Output: *"Item sudah kadaluarsa. Pertimbangkan untuk dibuang atau didonasikan."* No deal published. |
| **Very low stock (1–2 pcs)** | `stock ≤ 2` | Minimal discount (5–15%). Aggressive markdown on 1–2 units isn't worth the margin loss. |
| **Zero / negative margin** | `cost ≥ original_price` | Warning: *"Harga modal ≥ harga jual. Mohon cek input Anda."* No recommendation issued. |
| **Ambiguous / missing input** | Model flags low parse confidence | Show structured form with pre-filled guesses; ask vendor to confirm before computing. |

#### Daily Re-Run Behavior

The system is designed to be run **daily** by the vendor. This creates a natural feedback
loop that empirically handles elasticity without hardcoding it:

```
Day 3 left:  10 units → oracle: 20% off
Day 2 left:   7 units (3 sold) → pressure increased → oracle: 35% off
Day 1 left:   5 units (2 sold) → pressure critical → oracle: 55% off
```

The oracle never needed to know the exact elasticity coefficient. It observed that
yesterday's discount moved 3 units, the pressure ratio worsened, and escalated accordingly.

**Implementation:**
- System stores `prev_stock` per item in SQLite (one integer per active deal)
- On re-run: `sold_yesterday = prev_stock - current_stock`
- If `sold_yesterday < expected` → pressure increased → deeper discount (natural escalation)
- If `sold_yesterday ≥ expected` → pressure decreased → shallower discount or "no action"
- Explanation references yesterday's data when available:
  *"Kemarin diskon 20%, terjual 3 dari 10. Sisa 7 pcs, waktu tinggal 1 hari.
  Perlu diskon lebih dalam untuk menghabiskan stok."*

**One-day lag caveat:** The loop learns "yesterday's discount wasn't enough" only after
a full day. For items expiring *tomorrow*, there's no retry — the first recommendation
must be reasonable. The category bias (§9.5 Step 3) provides this starting prior.

#### Worked Example

**Input:** Roti Tawar, Bakery, Rp15.000, cost Rp10.000, stock 10, expires in 2 days,
shelf life 4 days, sells ~5/day, yesterday's stock was 13.

```
Step 1:  days_of_supply = 10/5 = 2.0;  pressure = 2.0/2 = 1.0
         → borderline (just at the edge)
Step 2:  life_consumed = 1 - 2/4 = 0.5;  urgency = 0.5^1.5 = 0.35
Step 3:  category_bias = 1.3 (Bakery)
Step 4:  pressure_factor = (1.0 - 1.0)/4.0 = 0.0
         → hmm, pressure exactly 1.0 means "barely enough time"
         → but yesterday: sold 3 of 13 = slower than expected 5/day
         → adjusted pressure using yesterday's rate: 10/3 × 1/2 = 1.67
         → pressure_factor = (1.67 - 1.0)/4.0 = 0.17
         raw_discount = 0.17 × 0.35 × 1.3 × 80 = 6.2%
Step 5:  margin = (15000-10000)/15000 = 33%;  max_discount = min(70, 33-3.3) = 29.7%
Step 6:  discount = clamp(6.2, 5, 29.7) → round_to_5 → 5%

         → but 5% feels too low for bread expiring in 2 days.
         → the vendor re-runs tomorrow: stock still high, days=1
         → pressure = 10/3/1 = 3.3, urgency = (1-1/4)^1.5 = 0.65
         → raw = (2.3/4) × 0.65 × 1.3 × 80 = 30% → discount = 30% ✓

Step 7:  recommended_price = round_to_500(15000 × 0.70) = Rp10.500
Step 8:  expected_sell = min(10, 5×1×(1+30/50)) = min(10, 8) = 8
         revenue = 8 × 10500 = Rp84.000
         baseline = min(10, 5×1) = 5;  loss_no_action = 5 × 10000 = Rp50.000
Step 9:  pressure 3.3 > 1.5 → "Mulai diskon hari ini"
Step 10: vendor estimate → "Cukup yakin"
```

> **Note on the worked example:** Day 1 (2 days left) produces a conservative 5% because
> the pressure ratio is borderline. The daily loop naturally escalates to 30% on Day 2
> (1 day left) when the situation is clearly urgent. This is by design — the oracle
> avoids over-discounting early and lets observed sell-through drive escalation.

#### Parameter Tuning

The following constants may need adjustment after evaluating on real-world scenarios:

| Parameter | Default | Role | Tuning approach |
|---|---|---|---|
| Exponent in urgency (`^1.5`) | 1.5 | How aggressively urgency ramps near expiry | Test 1.2–2.0 on sample scenarios |
| Base scale (`×80`) | 80 | Maps raw score to discount % range | Adjust so typical scenarios land in 10–50% |
| Pressure divisor (`/4.0`) | 4.0 | How quickly pressure saturates | Lower = more sensitive to oversupply |
| `CATEGORY_BIAS` values | 0.7–1.3 | Starting elasticity prior | Refine after observing real sell-through data |
| `MIN_MARGIN_RP` | 500 | Minimum Rp profit per unit | May vary by price tier |
| Sell-through discount factor (`discount/50`) | /50 | How much discount boosts demand | Crude linear model; replace with observed data if available |

These are **starting values**, not final. Generate synthetic data across a range of
parameter settings, evaluate output reasonableness, and lock before training.

---

## 10. Data Strategy

### 10.1 Fine-Tuning Dataset

The model learns **input parsing (NLU) + explanation generation + promo copywriting (NLG)**.
Pricing arithmetic is handled by the deterministic Python engine (§9.2), not the model.

**Data generation approach:**

1. **Synthetic scenario generation (primary):**
   - Generate pricing scenarios programmatically with randomized inputs:
     - All 8 categories (Bakery, Prepared Food, Dairy, Beverage, Produce, Snack, Canned, Other)
     - Realistic Indonesian UMKM price ranges (Rp2.000 – Rp150.000/unit)
     - Realistic cost-to-price ratios (margin 10–50%)
     - Stock quantities (1–100 units)
     - Days remaining (0–60 days) and total shelf life per category (§9.5 defaults)
     - Daily sales estimates (1–50/day, correlated with category and price)
     - Shop names (varied: "Toko X", "Kedai Y", "Café Z", "Warung W", "Bakery Q")
     - Optional `prev_stock` to simulate daily re-run scenarios with sell-through history

2. **Oracle formula (ground truth):**
   For each scenario, compute the "correct" answer using the full oracle specification
   in **§9.5** (10-step formula: pressure → urgency → category bias → margin ceiling →
   final discount → price → projections → timing → confidence).
   The oracle is the **same function** used in production — no separate training-only logic.

3. **Dual output generation (model learns NLU + NLG only):**
   - **Model output (training target):** `parsed_input` (structured fields) +
     `explanation` (natural language, references scenario context but NOT computed
     numbers) + `promo_copy` (generic urgency text, no specific discount figures)
   - **Python output (NOT in training data):** `recommendation` (all numbers) +
     `deal_data` (assembled JSON) — these are computed by the oracle at inference time,
     not learned by the model
   - Explanation: template + variation (LLM-augmented for diversity)
   - Promo copy: template + variation (different tones: urgent, friendly, playful)

4. **Free-text input augmentation:**
   - Paraphrase each structured input into 2–3 colloquial variants
   - Include abbreviations (rb, pcs, exp, kadaluarsa→kadaluwarsa→exp)
   - Include incomplete inputs (missing field → model should ask or infer)

5. **Edge case injection (10–15% of dataset):**
   - `pressure ≤ 1.0` AND `urgency < 0.7` → "no action needed" (§9.5 special case)
   - Already expired (`days_remaining ≤ 0`) → "cut loss / discard advice"
   - Fire sale (`days_remaining < 1`) → max discount, "HARI INI SAJA!"
   - Very low stock (1–2 pcs) → minimal discount (5–15%)
   - Very high stock (100+) with low daily sales → aggressive discount
   - Zero/negative margin (`cost ≥ price`) → warning, no recommendation
   - Cafe/ingredient scenario → owner inputs servings, same formula applies
   - Daily re-run scenario (with `prev_stock`) → explanation references yesterday's data
   - Ambiguous free-text → clarifying question

**Target dataset size:** 5,000–8,000 examples.

### 10.2 Data Sources (Public/Synthetic)

| Source | Use |
|---|---|
| Synthetic (oracle formula) | Core training data (80%) |
| BPS / PIHPS (Indonesian price statistics) | Realistic price ranges per category |
| Food science shelf-life tables | Realistic expiry timelines |
| Published FMCG price elasticity studies | Elasticity parameters per category |
| Self-generated colloquial paraphrases | Input diversity |
| Indonesian food marketing copy (scraped) | Promo copy style reference |

### 10.3 Preprocessing Pipeline

1. Generate structured scenarios (randomized inputs across all categories + edge cases)
2. Run each scenario through the oracle (§9.5) → get ground-truth numbers
3. Generate model training targets: `parsed_input` + `explanation` + `promo_copy`
   (numbers from oracle are used to *inform* explanation context, but the model
   output does NOT contain computed values — those are added by Python at inference)
4. Generate free-text input variants (2–3 colloquial paraphrases per scenario)
5. Format as instruction-response pairs:
   - System prompt: role definition + output format spec (JSON schema for model output)
   - User message: structured or free-text input
   - Assistant message: JSON with `parsed_input` + `explanation` + `promo_copy` only
6. Validate: parsed fields match input, JSON valid, explanations coherent
7. Split: 90% train / 10% eval
8. Tokenize and pack for QLoRA training

---

## 11. Product & Interaction Design

### 11.1 Business View — Layout

```
┌─────────────────────────────────────────────────────────┐
│  HargaTurun — Panel Bisnis                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─── Input Section ───────────────────────────────┐    │
│  │  [Form fields]  OR  [Free-text box]             │    │
│  │  [Dapatkan Rekomendasi] button                  │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─── Recommendation Section (appears after) ─────┐    │
│  │  💡 Rekomendasi: Rp10.500 (30% off)           │    │
│  │  📊 Prediksi: 8/10 terjual, untung Rp24.000   │    │
│  │  ⚠️ Tanpa aksi: rugi Rp70.000                 │    │
│  │  📝 Penjelasan: "..."                         │    │
│  │  📢 Promo: "..."                              │    │
│  │                                                 │    │
│  │  [Publikasikan Deal]  [Ubah Manual]  [Batal]   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─── Active Deals Section ───────────────────────┐    │
│  │  Deal 1: Roti Tawar — 8/10 remaining — [Hapus] │    │
│  │  Deal 2: Iced Latte — 2/4 remaining — [Hapus]  │    │
│  │  Claimed: HT-4821 (Andi) — [✓ Redeem]         │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 11.2 Consumer View — Layout

```
┌─────────────────────────────────────────────────────────┐
│  HargaTurun — Deals Hari Ini 🏷️                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─── Deal Card ──────────────────────────────────┐    │
│  │  🍞 Roti Tawar                                 │    │
│  │  Toko Sari Bakery                              │    │
│  │  Rp10.500  ~~Rp15.000~~  (30% OFF)            │    │
│  │  ⏰ Sisa 2 hari · 📦 Stok: 8 pcs              │    │
│  │  "Roti tawar fresh, diskon karena mendekati    │    │
│  │   tanggal kadaluarsa. Kualitas tetap bagus!"   │    │
│  │                                                │    │
│  │  [Klaim Deal Ini]                              │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─── Deal Card ──────────────────────────────────┐    │
│  │  ☕ Iced Latte                                  │    │
│  │  Kedai Dimas                                   │    │
│  │  Rp12.000  ~~Rp22.000~~  (45% OFF)            │    │
│  │  ⏰ Hari ini saja · 📦 Stok: 4 cups           │    │
│  │  "Iced latte fresh made today, harus habis     │    │
│  │   sebelum tutup. Harga spesial!"               │    │
│  │                                                │    │
│  │  [Klaim Deal Ini]                              │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─── Claimed (after tapping Klaim) ─────────────┐    │
│  │  ✅ Kode klaim Anda: HT-4821                  │    │
│  │  Tunjukkan kode ini di Toko Sari Bakery        │    │
│  │  Berlaku hari ini.                             │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 11.3 Interaction Principles

1. **Minimal clicks:** Vendor gets recommendation in 1 action. Publishes in 1 more. Consumer claims in 1 tap.
2. **No jargon:** All UI text in simple Bahasa Indonesia. No "markdown optimization" or "price elasticity" visible to users.
3. **Transparency:** Consumer sees *why* the item is discounted (near expiry) — builds trust, not suspicion.
4. **No dark patterns:** No fake urgency, no inflated "original prices." The AI recommendation is honest.
5. **Forgiving:** Wrong input? System asks to clarify. Changed mind? Unpublish anytime.

---

## 12. Business Model (For Proposal — Bonus Criterion)

### 12.1 Revenue Model (Post-Competition Vision)

| Stream | Mechanism | Pricing |
|---|---|---|
| Freemium SaaS | Free: 5 deals/day. Premium: unlimited + analytics + WhatsApp broadcast | Rp29.000–99.000/month |
| Commission | Small % on claimed deals (only when vendor actually sells) | 3–5% per redeemed deal |
| Promoted listings | Shops pay to appear at top of consumer deals page | Rp5.000–10.000/day |

### 12.2 Why This Is Viable

- **Willingness to pay:** Vendors already lose Rp500K–5M/month on waste. Saving even 30% of that = clear ROI.
- **Low CAC:** Consumer side grows organically (word-of-mouth, WhatsApp sharing, shop QR codes).
- **Network effects:** More shops → more deals → more consumers → more reason for shops to join.
- **Precedent:** Too Good To Go ($1.5B valuation, 80M+ users) proves the model in Western markets. No Indonesian equivalent exists.

### 12.3 Governance & Ethics (Bonus Criterion)

| Principle | Implementation |
|---|---|
| **Explainability** | Every AI recommendation includes a human-readable reason. No black-box pricing. |
| **Fairness** | AI never recommends exploitative pricing. Margin floor protects vendors. Consumers get honest info. |
| **Transparency** | Consumers see *why* an item is discounted (near expiry). No deception about freshness. |
| **Data minimization** | MVP requires no personal data. No accounts, no tracking, no cookies (beyond session). |
| **Responsible AI** | Reduces food waste (SDG 12), improves food access (SDG 2), supports UMKM livelihoods (SDG 8). |
| **Human override** | Vendor always has final say. AI recommends, human decides. Can override or reject. |

---

## 13. Success Metrics

### 13.1 Model Quality (Eval Set)

| Metric | Target | How Measured |
|---|---|---|
| Discount accuracy | Within ±5% of oracle | Compare model output to ground-truth formula |
| Margin floor compliance | 100% | Automated check: recommended_price ≥ cost |
| Explanation coherence | >90% "clear" | Manual eval on 50 samples |
| Promo copy quality | >85% "would click" | Manual eval on 50 samples |
| Free-text parsing accuracy | >85% fields correct | Automated extraction check |
| JSON schema compliance | >95% valid | Schema validation |
| "No action" correctness | >90% on far-expiry inputs | Automated check |

### 13.2 System Quality (Demo)

| Metric | Target |
|---|---|
| End-to-end response time | < 10 seconds |
| Deal publish → consumer page visible | < 2 seconds |
| Claim flow (tap → code shown) | < 1 second |
| Docker compose up → app ready | < 3 minutes (excl. model download) |
| Works offline after initial setup | Yes |

### 13.3 Competition Scoring Alignment

| Criterion | How HargaTurun scores |
|---|---|
| **Originality & Social Impact** | First AI-optimized surplus food platform for Indonesian UMKM. Double-sided impact: vendor income + consumer access + waste reduction. No direct competitor. |
| **Technology & Architecture** | Proportional model choice (Qwen3.5-4B, not overkill). Clean 3-layer separation (model/API/frontend). Fine-tuned, not just API-called. Hybrid architecture: model for language, deterministic Python for pricing. |
| **MVP Readiness** | Right-sized scope: core AI + two views + claim flow. Extensible (OCR, voice, batch as hackathon upgrades). Clear upgrade path without rearchitecture. |
| **Video Promosi** | Strong storytelling: open with vendor throwing away bread → "what if AI could prevent this?" → show platform → consumer gets cheap food → win-win. Emotional + logical. |
| **Proposal Quality** | Clear methodology: oracle formula → synthetic data → QLoRA → eval. Decision-making documented (why hybrid model+Python, why Qwen3.5-4B, why not larger/smaller). |
| **Theme Relevance** | Directly Smart Commerce: AI optimizes commercial transactions, connects supply and demand, improves UMKM operations. Not forced. |
| **Business Value (bonus)** | Clear monetization path (freemium + commission). Precedent (Too Good To Go). Scalable network effects. |
| **Governance (bonus)** | Explainable AI, data minimization, human override, SDG alignment, no dark patterns. |

---

## 14. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | ~~LLM outputs numerically wrong discount~~ | ~~Medium~~ → **Eliminated** | ~~High~~ → **N/A** | Pricing math is done by the deterministic Python engine (§9.2), not the model. The model never computes discounts, revenue, or loss — it only parses input and generates text. Numerical accuracy is 100% by construction. |
| R2 | 8GB VRAM insufficient for QLoRA training | Low | High | QLoRA 4-bit + rank-16 + gradient checkpointing + batch=1 with accumulation. Tested: 7B QLoRA fits ~6GB. |
| R3 | Inference too slow for live demo | Low | Medium | 4-bit quantized inference; max 350 output tokens; model pre-loaded at startup; GPU warmup on boot. |
| R4 | Synthetic data doesn't generalize to real pricing intuition | Medium | Medium | Ground oracle in published elasticity/shelf-life research. Include diverse categories + Indonesian price ranges. Manual review of 100 samples. |
| R5 | Free-text parsing fails on very colloquial/slang input | Medium | Low | Include colloquial variants in training. Fallback: if parse confidence low, show structured form with pre-filled guesses. |
| R6 | Two-sided scope feels "too much" for MVP to judges | Low | Medium | Consumer page is intentionally minimal (read-only list + claim). Emphasize in video: "the AI is the core; the consumer page is just a render of AI output." |
| R7 | Docker image too large / model download too slow for panitia | Medium | Medium | Provide pre-built image on GHCR with model baked in. Or: download script with progress bar + clear README instructions. |
| R8 | Claim code system feels "toy" | Low | Low | Acknowledge in proposal as MVP simplification. Explain upgrade path (QR, payment integration) for production. |
| R9 | Judges don't emotionally connect with the problem | Low | High | Video promosi MUST open with visceral imagery: vendor counting expired bread, money literally in the trash. 30 seconds of pain before showing solution. |

---

## 15. Assumptions

| # | Assumption | Basis |
|---|---|---|
| A1 | UMKM owners know their purchase/production cost per item | Standard for any business operator |
| A2 | Expiry dates are knowable (printed on packaging, or estimated for fresh food) | Most packaged goods have printed dates; fresh food estimated by vendor experience |
| A3 | A fine-tuned Qwen3.5-4B can reliably parse colloquial Indonesian input and generate explanation + promo copy, while a deterministic Python engine handles all pricing arithmetic | Qwen3.5-4B has 201-language pre-training including Indonesian; QLoRA on NLU + NLG tasks is well within 4B capability; pricing math is a known formula that doesn't need a neural network |
| A4 | Indonesian FMCG/food price elasticity can be approximated from published studies | BPS data + academic FMCG elasticity papers exist |
| A5 | 5,000–8,000 training examples suffice for QLoRA | Domain-specific instruction tuning typically needs far fewer than general tuning |
| A6 | Consumers will actually visit a deals page and claim deals | Precedent: Too Good To Go adoption; Indonesian consumers are highly price-sensitive and deal-seeking |
| A7 | A simple claim code (no payment) is sufficient for MVP demo | Competition scope is MVP, not production. Demonstrates the flow without payment complexity. |
| A8 | Deterministic inference (temp=0) produces stable, useful outputs | Standard for factual/structured generation tasks |
| A9 | The two-sided framing stays within MVP scope rules | Consumer page is a passive render of AI output, not a separate complex system. No auth, no feed algorithm, no background jobs. |

---

## 16. Glossary

| Term | Definition |
|---|---|
| **Markdown** | Strategic price reduction to accelerate sale of time-sensitive inventory |
| **Sell-through** | Percentage of stock sold within a given period |
| **Price elasticity** | How much demand changes in response to price change (high = buyers very price-sensitive) |
| **Shelf life** | Remaining time before product expires / becomes unsellable |
| **Margin floor** | Minimum acceptable price (= cost). Selling below = losing money on the transaction |
| **QLoRA** | Quantized Low-Rank Adaptation; fine-tune large models on limited VRAM |
| **Oracle** | Hand-crafted formula producing "ground truth" for training data generation |
| **UMKM** | Usaha Mikro, Kecil, dan Menengah — Indonesian micro, small, medium enterprises |
| **Surplus food** | Prepared/perishable food that will go unsold before expiry without intervention |
| **Claim code** | Simple alphanumeric code issued to consumer as proof of deal reservation |
| **Two-sided platform** | Product serving both supply (business) and demand (consumer) simultaneously |

---

## 17. Competitive Landscape & Differentiation

| Competitor / Similar | What they do | HargaTurun's differentiation |
|---|---|---|
| Too Good To Go (EU/US) | Consumer marketplace for surplus food; vendor sets own price | **AI sets the optimal price**, not the vendor. No Indonesian equivalent exists. |
| Wasteless / Yieldigo / Smartway | Enterprise markdown optimization for supermarket chains | UMKM-accessible, no POS integration needed, no enterprise pricing |
| Kulaku / BukuWarung / Moka | POS + kasbon + stock tracking for UMKM | **Zero pricing intelligence.** They track; we recommend. |
| Generic "AI chatbot for UMKM" | General Q&A / content generation | Narrow, deep, measurable: one problem (markdown pricing), solved optimally |
| Manual discount (stickers, shouting) | Vendor guesses | Data-driven, explainable, consumer-visible |

---

## 18. Next Steps (Post-This-Document)

Once this specification is approved, technical execution begins:

1. ~~**Select specific 4–9B base model**~~ — **Done: Qwen3.5-4B** (evaluated Nanbeige4.2-3B, Ternary Bonsai 27B, Qwen2.5-7B; see §9.1)
2. **Build the oracle formula** — pricing logic ground-truth generator (Python)
3. **Generate synthetic dataset** — target: 5,000+ examples with triple output
4. **Set up QLoRA training pipeline** — Unsloth or HuggingFace TRL
5. **Fine-tune and evaluate** — iterate until eval targets met (§13.1)
6. **Build API layer** — FastAPI, single endpoint for AI inference + CRUD for deals/claims
7. **Build frontend** — two views (business + consumer), single web app
8. **Integration test** — docker compose up → full flow works end-to-end
9. **Write README** — setup guide for panitia (clear, step-by-step)
10. **Record videos** — proof of work (7 min) + video promosi (5 min)
11. **Write proposal** — 20 pages, methodology-heavy

---

*Dokumen ini adalah living document. Update seiring keputusan teknis diambil.*
