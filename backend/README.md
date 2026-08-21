# HargaTurun backend

FastAPI orchestration around the deterministic pricing oracle, plus the minimal
SQLite marketplace used by the current Flutter UI.

## Run

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
