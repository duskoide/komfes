# HargaTurun backend

FastAPI orchestration around the deterministic pricing oracle, plus the minimal
SQLite marketplace used by the current Flutter UI.

## Run

```bash
cd backend
uv sync --extra dev
uv run hargaturun-api
```

The API listens on `http://127.0.0.1:8000` by default. Useful environment values:

- `HARGATURUN_DB=data/hargaturun.db`
- `HARGATURUN_MODEL_URL=http://127.0.0.1:8080/v1`
- `HARGATURUN_MODEL_NAME=hargaturun-qwen3.5-4b`
- `HARGATURUN_DEMO_OTP=123456` (demo-only OTP; no SMS provider)
- `HARGATURUN_TOKEN_SECRET=...` (set outside local demo use)
- `HARGATURUN_CORS_ORIGINS=http://localhost:...` (comma-separated)

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
