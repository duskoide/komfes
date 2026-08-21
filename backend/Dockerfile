FROM ghcr.io/astral-sh/uv:0.8.15-python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY hargaturun ./hargaturun

RUN uv sync --frozen --no-dev

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uv", "run", "--frozen", "--no-dev", "hargaturun-api"]
