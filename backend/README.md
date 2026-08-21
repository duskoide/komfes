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
- FastAPI: `http://127.0.0.1:8000`
- llama.cpp: `http://127.0.0.1:8080/v1`
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

The model endpoint defaults to `http://127.0.0.1:8080/v1`; the API defaults to
`http://127.0.0.1:8000`. Useful environment values:

- `HARGATURUN_DB=data/hargaturun.db`
- `HARGATURUN_MODEL_URL=http://127.0.0.1:8080/v1`
- `HARGATURUN_MODEL_NAME=hargaturun-qwen3.5-4b`
- `HARGATURUN_DEMO_OTP=123456` (demo-only OTP; no SMS provider)
- `HARGATURUN_TOKEN_SECRET=...` (set outside local demo use)
- `HARGATURUN_CORS_ORIGINS=http://localhost:...` (comma-separated). Defaults to
  the local dev origins, never `*` — state production origins explicitly.
- `HARGATURUN_MODEL_TIMEOUT=20` (seconds per inference call)
- `HARGATURUN_MAX_BODY_BYTES=65536` (requests above this get `413`)
- `HARGATURUN_RATE_LIMIT=30` / `HARGATURUN_RATE_WINDOW=60` (per client address,
  applied to `/api/chat` and `/api/recommend` only; health probes are never
  throttled, and exceeding it returns `429`)

The current `Qwen3.5-4B Q4_K_M` is an infrastructure baseline, not the final
fine-tuned competition artifact. The model client validates every parse/write
response. It deterministically normalizes confirmation bookkeeping and performs
one validator-guided repair attempt for other contract violations.

Structured recommendations always use `pricing.compute()`. If the local model is
unavailable only the prose fields degrade to empty strings; all numeric output
still comes from the oracle. Free-text parsing requires the model server.

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

```bash
cd backend
uv run pytest -q
```

The suite covers deterministic pricing/model contracts and the API flow:
recommend → publish → browse → claim → redeem → restart.
