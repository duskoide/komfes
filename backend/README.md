# HargaTurun backend

FastAPI orchestration around the deterministic pricing oracle, plus the minimal
SQLite marketplace used by the current Flutter UI.

## Full-stack Compose (recommended)

Prerequisites: Docker Engine, Docker Compose v2, the NVIDIA Container Toolkit,
and enough free space for the approximately 2.6 GB base GGUF. Then run:

```bash
docker compose up --build
```

The first run creates Docker volumes, downloads the temporary base
`Qwen3.5-4B Q4_K_M` GGUF only when absent, verifies its pinned SHA-256, starts
the CUDA llama.cpp server, installs/builds the backend and Flutter dependencies,
and waits for health checks before exposing the UI.

- Flutter web: `http://127.0.0.1:3000`
- FastAPI: `http://127.0.0.1:8000` (loopback)
- llama.cpp: `http://llm-server:8080/v1` (Compose network only)
- demo OTP: `123456`

The model and SQLite database persist in named volumes. Rebuilding containers
does not redownload the model. To stop the stack, use `docker compose down`.
Do **not** add `-v` unless you intentionally want to delete both persisted
volumes. Override ports, the public API URL, model URL/hash, or secrets through
the `HARGATURUN_*` variables documented in `compose.yml`.

## Native development

Start the local base-model server from the repository root. The launcher detects
LM Studio's bundled CUDA llama.cpp runtime and uses the ignored GGUF under
`models/`:

```bash
./scripts/run-llama-server.sh
```

Then start the API in a second terminal:

```bash
cd backend
uv sync --extra dev
uv run hargaturun-api
```

The model endpoint defaults to `http://127.0.0.1:8080/v1` for native loopback
development; the Compose API uses `http://llm-server:8080/v1`. The API defaults
to `http://127.0.0.1:8000`. Useful environment values:

- `HARGATURUN_DB=data/hargaturun.db`
- `HARGATURUN_MODEL_URL=http://127.0.0.1:8080/v1`
- `HARGATURUN_MODEL_NAME=hargaturun-qwen3.5-4b`
- `HARGATURUN_MODEL_FILE=hargaturun-qwen3.5-4b-q4_k_m.gguf` (or another configured 2B/4B candidate)
- `HARGATURUN_MODEL_SHA256=<64-hex-digest>` (optional native/Compose verification)
- `HARGATURUN_LLM_PROFILE=text` (native launcher default; set `multimodal` only with a matching projector)
- `HARGATURUN_MMPROJ_FILE=hargaturun-qwen3.5-mmproj-f16.gguf`
- `HARGATURUN_MMPROJ_SHA256=<64-hex-digest>` (optional projector verification)
- `HARGATURUN_DEMO_OTP=123456` (demo-only OTP; no SMS provider)
- `HARGATURUN_TOKEN_SECRET=...` (set outside local demo use)
- `HARGATURUN_CORS_ORIGINS=http://localhost:...` (comma-separated). Defaults to
  the local dev origins, never `*` — state production origins explicitly.
- `HARGATURUN_MODEL_TIMEOUT=20` (seconds per inference call)
- `HARGATURUN_INFERENCE_TIMEOUT_SECONDS=20` (cancellable `/api/chat` inference budget)
- `HARGATURUN_MAX_BODY_BYTES=65536` (requests above this get `413` while streaming)
- `HARGATURUN_MAX_TURNS=20` / `HARGATURUN_MAX_CONTEXT_CHARS=12000` (per-session chat budget)
- `HARGATURUN_IMAGE_MAX_BYTES=5242880` (image bytes, before decode)
- `HARGATURUN_IMAGE_MAX_PIXELS=12000000`, `HARGATURUN_IMAGE_MAX_WIDTH=6000`,
  `HARGATURUN_IMAGE_MAX_HEIGHT=6000`, `HARGATURUN_IMAGE_MAX_FRAMES=1`,
  `HARGATURUN_IMAGE_MAX_DECODED_BYTES=50331648`
- `HARGATURUN_IMAGE_TEMP_DIR` (optional private operator path) and
  `HARGATURUN_IMAGE_TEMP_TTL_SECONDS=300`
- `HARGATURUN_RATE_LIMIT=30` / `HARGATURUN_RATE_WINDOW=60` (per client address,
  applied to `/api/chat`, `/api/chat/image`, and `/api/recommend`; health probes
  are never throttled, and exceeding it returns `429`)
- Default logs contain only event/action metadata; message text, image data,
  personal data, prompts, and provider errors are never logged. Enable any
  local debug instrumentation explicitly and keep it out of production.

The current `Qwen3.5-4B Q4_K_M` is an infrastructure baseline, not the final
fine-tuned competition artifact. The model client validates every parse/write
response. It deterministically normalizes confirmation bookkeeping and performs
one validator-guided repair attempt for other contract violations.

Structured recommendations always use `pricing.compute()`. If the local model is
unavailable only the prose fields degrade to empty strings; all numeric output
still comes from the oracle. Free-text parsing requires the model server.

## Operational hardening

`POST /api/chat` is bounded by a streaming request-body limit, a cancellable
inference timeout, a maximum turn count and context-character budget per
session, and a bounded model output-token setting. Synchronous provider calls
run in disposable `spawn` workers; Linux and macOS are supported, while
Windows fails clearly because this cancellation boundary is not supported
there. Invalid environment values fall back to conservative defaults. Oversized/budget-exhausted requests return
generic `413`/`429` responses; model failures and timeouts preserve validated
state and return `SAFE_FAILURE` without provider details.

The primary frontend route is `/vendor/chat`. `/vendor/manual-form` remains a
manual outage/accessibility fallback. The obsolete `/vendor/check-item`,
`/confirm`, and `/processing` paths redirect to chat.

## Consultation chat — `POST /api/chat`

One synchronous turn per request; there is no streaming and no persisted chat
history. Sessions live in memory and disappear with the process, which the
preliminary round requires.

Request:

```json
{ "session_id": null, "action": "message", "text": "roti tawar 20 biji exp 2 hari", "patch": null }
```

`action` is one of `message`, `confirm`, `calculate`, `explain`, `revise_promo`,
`reset`. Omit `session_id` on the first turn; the response returns one to reuse.
`confirm` may carry a `patch` of the fields the vendor edited on the
confirmation card — the server validates and merges, and never accepts a whole
state object from the client.

The response reports the action the orchestrator actually took, drawn from the
allowlist in `docs/HargaTurun_Agentic_Workflow_Plan.md` §3.1:

```json
{
  "session_id": "…",
  "action": "ASK_FOR_MISSING_FIELDS",
  "assistant_message": "Tinggal beberapa ini: harga modal per barang, rata-rata terjual per hari.",
  "state": { "…": "§3.2 shape, plus confirmed / revision / result_revision" },
  "missing_fields": ["cost", "daily_sales"],
  "ambiguous_fields": [],
  "result": null
}
```

What the boundaries actually guarantee:

- the model only *proposes* field patches; unknown keys, booleans posing as
  numbers, negative or non-finite economics and unknown categories are dropped,
  so a hostile turn changes nothing;
- `calculate` on an unconfirmed or incomplete state performs **zero** pricing
  tool calls and answers with what is still needed;
- an accepted change bumps `revision`, clears `confirmed` and invalidates the
  current result, so a stale recommendation cannot be reused after a correction;
- a result is only returned while its revision still matches `state.revision`;
- assistant copy is deterministic per action rather than model-authored, so no
  unsupported number can appear in the prose.

Failure shapes: `404` unknown or expired session, `422` malformed request or
unknown action, `413` oversized body, `429` rate limited. A model outage is
**not** an error status — it returns `200` with `action: "SAFE_FAILURE"` and the
validated state intact, so the vendor's facts survive.

Known limitation: `ambiguous_fields` is always empty. The contract carries it,
but populating it needs the model to report its own uncertainty, which the
current parse contract does not express.

## Test

### Unified Developer Test Suite Runner

From the repository root:

```bash
# Tier 1 (Default): Fast deterministic backend unit tests + eval safety replay (< 3s)
python scripts/run_dev_tests.py

# Tier 2: Backend + Frontend Flutter unit & widget tests
python scripts/run_dev_tests.py --tier 2

# Tier 3: Wire-level multi-turn integration tests (FastAPI + dev stub)
python scripts/run_dev_tests.py --tier 3

# Tier 4 (Opt-in): Live local-model server & Compose smoke tests
python scripts/run_dev_tests.py --real-model --compose

# Strict CI Mode: Fails if optional dependencies (Flutter, Docker/Podman, Model Server) are absent
python scripts/run_dev_tests.py --tier all --strict
```

### Direct Pytest Execution

```bash
cd backend
uv sync --extra dev

# Fast deterministic unit & contract tests (excludes integration/smoke markers)
uv run pytest -q -m "not (integration or real_model or compose)"

# Live wire integration tests (launches in-process dev stub server on loopback)
uv run pytest -q -m integration

# Opt-in live model server smoke test (requires running llama.cpp on :8080)
HARGATURUN_TEST_REAL_MODEL=1 uv run pytest -q -m real_model

# Opt-in Compose configuration smoke test (requires Docker or Podman)
HARGATURUN_TEST_COMPOSE=1 uv run pytest -q -m compose

# Run all test suites
uv run pytest -q
```

### Test Markers & Environment Overrides

- `pytest.mark.unit`: Fast in-memory unit tests (pricing oracle, schemas, consultation state, limits, model client, dev stub).
- `pytest.mark.integration`: Multi-turn wire integration with live HTTP dev stub on loopback.
- `pytest.mark.real_model`: Opt-in live model server checks (overridden via `HARGATURUN_MODEL_URL` and `HARGATURUN_TEST_REAL_MODEL=1`).
- `pytest.mark.compose`: Opt-in Compose configuration syntax tests (enabled via `HARGATURUN_TEST_COMPOSE=1`).
- `HARGATURUN_STRICT_MODE=1`: Forces tests to fail immediately with an error rather than skipping when optional services are absent.

The suite covers deterministic pricing/model contracts and the API flow:
recommend → publish → browse → claim → redeem → restart.
