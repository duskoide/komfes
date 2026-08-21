from __future__ import annotations

import os

import uvicorn

from .api import create_app

app = create_app()


def run() -> None:
    uvicorn.run(
        "hargaturun.main:app",
        host=os.getenv("HARGATURUN_HOST", "0.0.0.0"),
        port=int(os.getenv("HARGATURUN_PORT", "8000")),
        reload=os.getenv("HARGATURUN_RELOAD") == "1",
    )


if __name__ == "__main__":
    run()
