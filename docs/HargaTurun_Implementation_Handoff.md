# HargaTurun — Implementation Handoff

> **Document type:** living implementation-status + handoff document
> **Last updated:** 2026-08-17
> **Branch:** `feat/pricing-engine` (pushed to `origin`; compare with `main` for the current commit count)
> **Author of code so far:** `buahkol <illonanasywa710@gmail.com>`
> **Purpose:** give anyone picking this up the full context — what the repo is,
> what has been built and *why it behaves the way it does*, the constraints
> discovered along the way, the findings that affect the demo, and exactly what
> comes next in what order.

If you read only one section, read **§3 (what's built)**, **§5 (findings that
change the demo)**, and **§7 (what's next)**.

---

## 1. Where the project stands in one paragraph

At this branch's starting point the shared repository was **specification only**.
This branch adds the first two engineering deliverables from the Fine-Tuning
Plan's execution order (§9 of `HargaTurun_FineTuning_Plan.md`): the
**deterministic pricing oracle** (`pricing.py`, every number in the system) and
the **frozen model I/O contracts** (`schemas.py`, the parse/write tasks the
training data and the API both agree on). Both are pure-stdlib and fully tested.
The model itself, FastAPI layer, dataset generator, and gold test set are **not
started on this branch** — see §7. A separate `frontend` branch contains the
Flutter UI; it is not integrated with this deterministic core yet.

---

## 2. Repository map

```
komfes/
├── README.md                    # product/flow overview (READ THIS for the vision)
├── UIUX_HANDOVER.md             # per-screen UI/UX requirements (see §5 caveat)
├── compose.llm.yml              # standalone llama.cpp CUDA model server (pre-existing)
├── flake.nix                    # dev shell — currently ONLY flutter (see §5 caveat)
├── .envrc                       # direnv: `use flake`
├── models/                      # .gitignored — GGUF artifacts live here, not in git
├── docs/
│   ├── HargaTurun_Project_Spec.md       # problem, personas, oracle formula §9.5, model choice
│   ├── HargaTurun_Penyisihan_SRS.md     # AUTHORITATIVE preliminary scope + API contract
│   ├── HargaTurun_Final_SRS.md          # final-round marketplace loop + data model
│   ├── HargaTurun_FineTuning_Plan.md    # BF16 LoRA runbook + deliverable order (§9)
│   ├── HargaTurun_LLM_Server_Setup.md   # RTX 4060 CUDA serving setup
│   ├── AIC_Technical_Guide.md           # competition rules (technical)
│   └── HargaTurun_Implementation_Handoff.md   # ← THIS FILE
└── backend/                     # ← NEW, all code so far lives here
    ├── pyproject.toml           # dependency-free core package metadata
    ├── README.md                # how to run the backend tests
    ├── .gitignore               # python artifacts
    ├── hargaturun/
    │   ├── __init__.py
    │   ├── pricing.py           # THE ORACLE — every number
    │   └── schemas.py           # frozen parse/write model contracts
    └── tests/
        ├── test_pricing.py      # oracle regressions + 20k-iteration fuzz
        └── test_schemas.py      # strict parse/write contract tests
```

**Doc precedence rule (from README):** where the Project Spec and an SRS
disagree on scope, **the SRS wins**. The Project Spec is the two-sided vision;
the SRSs are what each round actually ships.

---

## 3. What has been built (this branch)

Five small commits currently make up the committed branch history; the fixes
listed in §5.5 are the next merge-preparation change:

| Commit | What |
|---|---|
| `cd9c374` | scaffold the `hargaturun` package (pyproject, gitignore, README) |
| `0bca52f` | `pricing.py` — the deterministic oracle (Project Spec §9.5) |
| `a7035d1` | 26 oracle tests incl. a 20k-iteration margin-floor fuzz |
| `f436b68` | `schemas.py` — frozen parse/write model contracts (FT Plan §2) |
| `862200e` | this living implementation handoff |

### 3.1 `hargaturun/pricing.py` — the oracle

The single source of truth for **every number** in HargaTurun. Pure functions,
no I/O, no model, no network → the same input always yields the same output
(competition rule: *parameter statis*, reproducible). It is used in two places,
written once: the production pricing authority behind `POST /api/recommend`, and
the ground-truth generator for the fine-tuning dataset.

**Public surface:**

- `PricingInput` (frozen dataclass): `category, original_price, cost, stock,
  days_remaining, daily_sales, total_shelf_life=None`. Inputs must already be
  confirmed — the oracle never invents a value.
- `compute(inp: PricingInput) -> OracleResult` — runs the 10-step §9.5 formula.
- `OracleResult` (frozen dataclass): carries `status` plus outcome fields, and
  helpers `sell_through_text(unit)` → `"8 dari 10 pcs"` and
  `recommendation_dict(unit)` → the API `recommendation` object.
- Constants exposed for reuse: `CATEGORIES`, `DEFAULT_SHELF_LIFE`,
  `CATEGORY_BIAS`, bounds, and status strings.

**The three outcomes** `compute()` can return (`status` field):

| `status` | When | Key fields |
|---|---|---|
| `recommendation` | a markdown is warranted | `discount_percent`, `recommended_price`, `timing`, `expected_sell_through_units`, `expected_revenue`, `expected_loss_no_action`, `confidence`, `is_fire_sale` |
| `no_action` | low pressure & low urgency | `message`, `reassess_in_days` |
| `invalid_input` | bad economics / expired | `message`, `expired` (bool) |

> Note: the API's fourth outcome, **`needs_confirmation`**, is *not* an oracle
> concern — it happens earlier, in the API layer, before `compute()` is ever
> called. The oracle only ever sees confirmed input.

**Special-case evaluation order** (documented in the code because §9.5 leaves
the overlaps implicit):

1. invalid economics / numbers (`price<=0`, `stock<=0`, `daily_sales<=0`,
   `cost>=price`) → `invalid_input`
2. already expired (`days_remaining<=0`) → `invalid_input` (`expired=True`)
3. **fire sale** (`0 < days_remaining < 1`); if no 5% margin-safe markdown fits,
   return `invalid_input`, otherwise recommend at the margin ceiling
4. **no action** (`pressure<=1.0 AND urgency<0.7`) → `no_action`, even when the
   margin is too thin for a future markdown
5. insufficient room for a needed 5% discount plus Rp500 margin → `invalid_input`
6. **very low stock** (`stock<=2`) → discount capped at 15%
7. normal formula

**Hard guarantees (enforced by construction + asserted + fuzz-tested):**

- `recommended_price >= cost + Rp500` for every recommendation; when the
  minimum viable markdown cannot preserve this floor, the outcome is
  `invalid_input` instead.
- discount ∈ [5, 70], a multiple of 5, for every recommendation.
- recommended price never exceeds the original price.
- the *displayed* discount never exceeds the margin ceiling (see §5.3).
- prices are multiples of Rp500 (Indonesian pricing convention), except the rare
  `cost + Rp500` floor value itself.

### 3.2 `hargaturun/schemas.py` — frozen model contracts

Deliverable #2. The one place the **training data, the model, and the API**
agree on the parse/write task shapes, so they can't drift.

- **Field contracts:** `PARSE_REQUIRED_FIELDS` (8 fields; `shop_name` optional),
  numeric-field lists, allowed categories.
- **Frozen system prompts:** `PARSE_SYSTEM_PROMPT` / `WRITE_SYSTEM_PROMPT`, each
  with a version string (`parse-v2`, `write-v2`). Keep these stable — FT Plan
  §4.1 records the prompt version with every eval run; changing a prompt
  invalidates prior results.
- **`to_engine_result(result, unit)`** — the *single* adapter turning an
  `OracleResult` into the write task's authoritative `engine_result`. It owns the
  only status translation: the oracle's internal `invalid_input` becomes the
  model-facing `warning` (FT Plan §2.2 vocabulary: `recommendation` / `no_action`
  / `warning`).
- **Stdlib validators** enforcing FT Plan §3.6 gates, reused by tests and (later)
  the dataset generator:
  - `validate_parse_output` — enforces the exact JSON shape, field types and
    numeric domains, leaked-field rejection, and exact consistency among null
    required values, `missing_fields`, and `needs_confirmation`.
  - `validate_write_output(obj, allowed_numbers, engine_status)` — enforces the
    exact output shape, sentence counts, status-appropriate promo behavior, and
    rejects numerical claims absent from the engine input. Number extraction
    distinguishes decimal claims from Indonesian Rupiah thousands separators.
  - `allowed_numbers_for(normalized_input, engine_result)` — the legitimate
    numeric set for a write output.

### 3.3 Tests — all green, zero runtime dependencies

Because the code is pure-stdlib, the tests run with nothing installed:

```bash
cd backend
python3 -m unittest discover -s tests -v      # NOTE: python3, not python
```

Highlights worth knowing:

- `TestInvariantsFuzz` runs **20,000 seeded random inputs** and asserts the
  margin floor, true-markdown requirement, and discount bounds hold for every
  accepted recommendation.
- `TestCanonicalExample` pins the surprising-but-correct finding in §5.1.
- `TestSurplusRecommendation` regression-locks a hand-derived example
  (Bakery, Rp20 000, cost 10 000, 30 units, 1 day, shelf 4, 5/day) → **45% off,
  Rp11 000**, so future formula edits can't silently drift.

---

## 4. Environment constraints discovered (important for whoever runs this)

The machine this was built on has an unusual Python setup. Know these before you
try to run or extend things:

| Constraint | Detail | Consequence |
|---|---|---|
| **Python** | `python3` = 3.12.3. There is **no `python`** alias. | Always invoke `python3`. |
| **No `pip` / `ensurepip` / `uv`** | Cannot install packages the normal way. | The oracle + schemas + tests are deliberately **stdlib-only** so they run anyway. **FastAPI cannot be installed/run here** without bootstrapping pip (`get-pip.py`) first. |
| **`venv` exists but is pip-less** | `python3 -m venv` works but won't get pip (needs ensurepip). | A venv alone doesn't unblock FastAPI. |
| **Internet: available** | `pypi.org` reachable. | Bootstrapping pip via `get-pip.py` is *possible*, just not yet done. |
| **git identity was unset** | Set repo-locally to `buahkol <illonanasywa710@gmail.com>`. | Commits are authored as buahkol. **Team decision on record: no "Claude"/co-author trace in commits.** Keep it that way. |

**Testing tooling:** tests use stdlib `unittest`; `pytest` is an optional
`dev` extra and collects the same suite when installed. FastAPI dependencies
belong to the separate backend-integration branch.

---

## 5. Findings that change the demo / need attention

These came out of reading the whole spec set against the actual formula. None are
blockers for the code already written, but they affect the demo and the docs.

### 5.1 The docs' headline example resolves to `no_action`, not a 30% discount

The canonical roti-tawar input everyone quotes — Rp15 000, cost 10 000, stock 10,
**2 days** left, shelf 4, sells 5/day — has `pressure` **exactly 1.0** and
`urgency` 0.35 (< 0.7). Under the base penyisihan formula that is the
**`no_action`** branch. The famous "30% off, Rp10 500" figure in the spec's
example JSON actually comes from the **daily re-run scenario** (yesterday's
slower sell-through bumps pressure), which is **explicitly out of scope for
penyisihan** (`Penyisihan SRS` §5.5: no `prev_stock`, no re-run loop).

**Action for the demo:** the hero example must use genuinely-surplus inputs
(e.g. 30 units, 1 day left) so a recommendation actually appears. This is pinned
as a test (`test_canonical_roti_tawar_is_no_action`) so nobody "fixes" the oracle
to match the doc by mistake. Consider correcting the example JSON in the specs.

### 5.2 The SRS "successful recommendation" example numbers are internally inconsistent

In `Penyisihan SRS` §6.1 the success example lists `days_remaining: 2` but its
`expected_sell_through: "8 dari 10 pcs"` and `expected_loss_no_action: 50000`
are the arithmetic for `days_remaining = 1`. With `days=2` the formula yields
sell-through 10 and loss 0. **The formula is authoritative** (it's the
deterministic source of truth by design); the tests follow the formula, not the
illustrative JSON. Worth correcting the doc so reviewers aren't confused.

### 5.3 Margin-ceiling vs rounding — a documented deviation from the literal §9.5

§9.5 Step 6 literally says `round_to_5(clamp(raw, 5, max_discount))`. But a
ceiling like 47.5% would naively round **up** to 50%, pushing the displayed
discount past the margin ceiling and disagreeing with the (margin-protected)
price. Because the margin ceiling is a stated **hard** constraint, `pricing.py`
rounds **down** to the nearest 5% when naive rounding would overshoot. In the
common case (e.g. the 30% worked example) this is byte-identical to the literal
formula. Documented in `_finalize_discount`'s docstring.

### 5.4 Pre-existing product-spec defects still open (from the earlier repo review)

These live in the *specs*, not in the code yet, and should be resolved before or
during the API/frontend work:

1. **Margin floor unverifiable at publish time (Final round).** `POST /api/deals`
   and the `deals` table don't carry `cost`, yet the Final SRS requires the
   server to reject a price below `cost + Rp500`. → Bring `cost` into the publish
   payload (server-side only, never shown to the consumer).
2. **`502 model_unavailable` kills the whole flow** even though a structured form
   + Python can still produce the numbers. → Add a "numbers-only, no prose"
   degradation path so a live demo survives a model hiccup.
3. **`daily_sales` almost never parses from free text** → the "type naturally"
   headline path nearly always detours to the confirmation form. → Frame the flow
   honestly as "first capture, then confirm", or lower the expectation.
4. **Native-app vs web tension.** `UIUX_HANDOVER.md` is written as a native app
   (SMS-OTP autofill, haptics, portrait-lock, `dp` units) while the original
   penyisihan SRS expects `docker compose up` → a browser. The separate frontend
   branch currently chooses Flutter. → Before integration, decide whether the
   deliverable is Flutter web/PWA or a native app and align deployment and
   breakpoint requirements accordingly.
5. **OTP auth** has no backend contract and adds heavy infra, while the rules
   disqualify "complex authentication systems". → Drop auth from penyisihan
   (it's already out of scope) or stub it.
6. **Minor:** `days_remaining` typed as int in some places, REAL/float in
   others; `422` is used both for `needs_confirmation` (a *normal* branch — a
   `200` + status discriminator is cleaner) and for `invalid_input`.

---

### 5.5 Merge-preparation hardening completed

The oracle now rejects non-finite or structurally invalid numeric input. If the
margin cannot support the minimum 5% markdown while retaining Rp500 profit, it
returns `invalid_input` instead of a misleading 0% "recommendation" or a price
above the original. Low-price Rp500 rounding also falls downward when nearest
rounding would erase the markdown.

The parse/write validators now enforce the frozen contracts rather than only a
subset of their keys: exact shapes, types and ranges, exact missing-field
bookkeeping, sentence limits, status-aware promo behavior, and decimal-safe
number faithfulness. Regression tests cover each case.

---

## 6. How the pieces fit (mental model for the next dev)

```
                          ┌───────────────────────────────────────────┐
Free text ───▶ model(parse)│  parsed_input + missing_fields +          │
                          │  needs_confirmation   (schemas.PARSE_*)    │
                          └───────────────┬───────────────────────────┘
                                          │ any required field missing?
                            yes ──────────┤────────── no
                                          ▼            ▼
                            API returns confirmation   confirmed normalized_input
                            (no engine call)                    │
                                                                ▼
Structured input ─────────────────────────────────────▶ pricing.compute()
                                                                │  OracleResult
                                                                ▼
                                        schemas.to_engine_result()  →  engine_result
                                                                │
                                                                ▼
                              model(write)  ← WRITE_SYSTEM_PROMPT + normalized_input + engine_result
                                                                │  explanation + promo_copy
                                                                ▼
                              schemas.validate_write_output(...)  (no fabricated numbers)
                                                                ▼
                                             assembled POST /api/recommend response
```

- **The model never does arithmetic.** It only parses text and writes prose.
- **Python never writes prose.** It only produces numbers.
- `schemas.py` is the contract seam between the two.

---

## 7. What comes next (in order)

Following `HargaTurun_FineTuning_Plan.md` §9 "Deliverables and execution order".
Done: #1 (pricing) and #2 (schemas). Remaining, in dependency order:

| # | Deliverable | Can it be built+verified on *this* machine? | Notes / decisions needed |
|---|---|---|---|
| 3 | **Gold test set** — ≥200 hand-authored/verified examples (`data/gold_test.jsonl`) | Format + validator: yes. The 200 examples: **no — human curation** (FT Plan §3.2 forbids generator provenance). | Team must own authoring/verification; it's the *primary* quality claim. Code can scaffold the format + a small seed. |
| 4 | **Dataset generator + validator** (`scripts/generate_training_data.py`, `validate_training_data.py`) | **Yes, fully (stdlib).** | Needs reversible text-normalization (`render_rupiah`, `render_days` + round-trip parsers, FT Plan §3.3) first. Prose = template v1; **Indonesian quality needs native-speaker review** (§3.5). Must pass all §3.6 gates. |
| 5 | **Baseline eval reports** (`scripts/eval_model.py`) — base Q8_0 + Q4_K_M on the gold set | Partial — needs a running llama.cpp model server (`compose.llm.yml`) + the GGUFs in `models/`. | Requires GPU + model files, not present here. |
| 6 | **BF16 LoRA smoke run** (10 steps, save/reload/export) | No — needs ≥12 GB VRAM training GPU + Unsloth. | Cloud/Colab GPU. QLoRA is explicitly rejected for Qwen3.5. |
| 7 | **Full training run** | No — same as #6. | Record env, logs, adapters, hashes. |
| 8 | **Adapter / Q8_0 / Q4_K_M eval reports** | No. | All §4 gates must pass; don't claim percentages until measured. |
| 9 | **Final local server smoke test** | Needs the 8 GB laptop + fine-tuned GGUF. | Record artifact hash + API result. |

**In parallel with the data/model track**, the app can be built (needed for the
penyisihan MVP regardless of model progress):

- **API layer** — FastAPI `POST /api/recommend` wiring `pricing.compute` +
  `schemas` + a model-client seam (with the §5.4.2 degradation path). *Writable
  here, but not runnable until pip/FastAPI is bootstrapped.* The **structured-input
  path needs no model** and is fully demoable on its own.
- **Frontend integration** — replace the Flutter branch's mock recommendation
  repository with the eventual API and align float/default-confirmation fields.

### Suggested immediate next step

Build **#4 the dataset generator** (critical path, most likely to slip over the
12-day window, and the one big thing fully verifiable on this machine), starting
with the reversible text-normalization module it depends on. Scaffold **#3's
format + a seed** alongside so the team can begin curating the gold set early.
The API/frontend can proceed in parallel once the stack + pip questions are
settled.

---

## 8. Key dates & scope reminders

- **Penyisihan deadline: 2026-08-25** (~12 days from this doc). The long pole is
  fine-tuning (deliverables #4–#8); start the data generator now.
- **Penyisihan ships:** vendor asks → vendor gets a recommendation. **Nothing is
  published.** No consumer marketplace, no persistence, no auth. (`Penyisihan
  SRS` §1.2 exclusions.)
- **Final round (10-hour hackathon) adds:** publish → browse → claim → redeem,
  with SQLite. Deliberately absent from penyisihan.
- **Model:** Qwen3.5-4B (real; Alibaba released the Qwen3.5 Small family
  0.8B–9B, multimodal, 262K context, on 2026-03-02). Q4_K_M for the 8 GB laptop;
  BF16 LoRA training on a separate ≥12 GB GPU.

---

## 9. How to verify what's here right now

```bash
git checkout feat/pricing-engine
cd backend
python3 -m unittest discover -s tests -v      # expect: all tests pass
```

Then read, in order: `hargaturun/pricing.py` (the formula), `tests/test_pricing.py`
(the behavior contract, including the fuzz), `hargaturun/schemas.py` (the model
seam). Everything else in this document is context around those three files.
