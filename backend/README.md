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
- `HARGATURUN_CORS_ORIGINS=http://localhost:...` (comma-separated)

The current `Qwen3.5-4B Q4_K_M` is an infrastructure baseline, not the final
fine-tuned competition artifact. The model client validates every parse/write
response. It deterministically normalizes confirmation bookkeeping and performs
one validator-guided repair attempt for other contract violations.

Structured recommendations always use `pricing.compute()`. If the local model is
unavailable only the prose fields degrade to empty strings; all numeric output
still comes from the oracle. Free-text parsing requires the model server.

## Test

```bash
cd backend
uv run pytest -q
```

The suite covers deterministic pricing/model contracts and the API flow:
recommend → publish → browse → claim → redeem → restart.
