#!/usr/bin/env python3
"""Development stub for the local model server.

Speaks just enough of the OpenAI-compatible ``/v1/chat/completions`` surface
for the API to run the consultation flow without a GPU or a multi-gigabyte
GGUF download. Useful for looking at the chat UI, and for reviewing the
orchestration on a machine that cannot host the real model.

**This is not a substitute for the model and must never be used for
evaluation or in a proof-of-work recording.** It fakes only the two language
tasks: reading Indonesian free text into fields, and writing prose. Every
number still comes from ``pricing.compute`` on the API side, so what you see
on screen is the real oracle output, not invented figures.

Parsing here is a handful of regexes, not language understanding. It handles
the documented demo phrasing and leaves anything it cannot read as ``null``,
which is the same "never guess" rule the real contract enforces.

Usage:
    python scripts/dev_stub_model.py [--port 8080]

Then point the API at it:
    HARGATURUN_MODEL_URL=http://127.0.0.1:8080/v1
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Category keywords -> the contract's English category values.
_CATEGORY_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("roti", "kue", "donat", "bolu", "bakery"), "Bakery"),
    (("nasi", "ayam", "lauk", "katering", "masakan"), "Prepared Food"),
    (("susu", "yogurt", "keju", "yoghurt"), "Dairy"),
    (("kopi", "teh", "jus", "minuman", "latte"), "Beverage"),
    (("sayur", "buah", "tomat", "pisang", "cabai"), "Produce"),
    (("snack", "keripik", "biskuit", "wafer"), "Snack"),
    (("kaleng", "sardines", "kalengan"), "Canned"),
]

_RUPIAH = r"(\d+(?:[.,]\d+)?)\s*(rb|ribu|k|jt|juta)?"


def _to_rupiah(number: str, suffix: str | None) -> int:
    value = float(number.replace(".", "").replace(",", "."))
    if suffix in {"rb", "ribu", "k"}:
        value *= 1_000
    elif suffix in {"jt", "juta"}:
        value *= 1_000_000
    return int(round(value))


def _first(pattern: str, text: str) -> re.Match[str] | None:
    return re.search(pattern, text, re.IGNORECASE)


def parse_free_text(text: str) -> dict:
    """Extract what the demo phrasing states outright. Never infers."""
    lower = text.lower()

    price = cost = None
    if m := _first(r"harga\s*" + _RUPIAH, lower):
        price = _to_rupiah(m.group(1), m.group(2))
    if m := _first(r"(?:modal|hpp)\s*" + _RUPIAH, lower):
        cost = _to_rupiah(m.group(1), m.group(2))

    stock = None
    if m := _first(r"(\d+)\s*(?:biji|pcs|buah|porsi|gelas|bungkus|botol)", lower):
        stock = int(m.group(1))

    days = None
    if m := _first(r"(?:exp|kadaluarsa|kadaluwarsa)\s*(\d+)\s*hari", lower):
        days = int(m.group(1))
    elif "hari ini" in lower:
        days = 0
    elif "besok" in lower:
        days = 1

    daily_sales = None
    if m := _first(r"(?:sehari|per hari|tiap hari)\s*(?:laku\s*)?(\d+)", lower):
        daily_sales = int(m.group(1))
    elif m := _first(r"(?:laku|terjual)\s*(\d+)\s*(?:per hari|sehari|/hari)", lower):
        daily_sales = int(m.group(1))

    category = None
    for keywords, value in _CATEGORY_HINTS:
        if any(word in lower for word in keywords):
            category = value
            break

    # Only offer an item name when the sentence actually describes an item.
    # Without this guard a later correction like "sehari laku 2" would have its
    # leading words read as a new name and overwrite the real one — which is
    # exactly the "never guess" rule the contract exists to enforce.
    describes_item = any(
        marker in lower
        for marker in ("harga", "modal", "exp", "kadaluarsa", "biji", "pcs", "porsi")
    )
    item_name = None
    if describes_item:
        cut = re.search(r"\d", text)
        candidate = (text[: cut.start()] if cut else text).strip(" ,.")
        if candidate:
            item_name = candidate.title()

    shop_name = None
    if m := _first(r"toko\s+([a-z\s]+)$", lower):
        shop_name = "Toko " + m.group(1).strip().title()

    parsed = {
        "item_name": item_name,
        "category": category,
        "original_price": price,
        "cost": cost,
        "stock": stock,
        "days_remaining": days,
        "daily_sales": daily_sales,
        "total_shelf_life": None,
        "shop_name": shop_name,
    }
    if shop_name is None:
        del parsed["shop_name"]

    # missing_fields must mirror the nulls exactly, in contract order.
    required = (
        "item_name",
        "category",
        "original_price",
        "cost",
        "stock",
        "days_remaining",
        "daily_sales",
        "total_shelf_life",
    )
    missing = [f for f in required if parsed.get(f) is None]
    return {
        "task": "parse",
        "parsed_input": parsed,
        "missing_fields": missing,
        "needs_confirmation": bool(missing),
    }


def write_prose(payload: dict) -> dict:
    """Prose that quotes only numbers the engine already produced.

    The writer validator rejects any figure outside the allowed set, so this
    deliberately mentions none of them and lets the numbers stay in the
    structured fields where they belong.
    """
    return {
        "task": "write",
        "explanation": (
            "Stok yang tersisa lebih banyak daripada perkiraan penjualan normal "
            "sampai tanggal kedaluwarsa. Menurunkan harga sekarang membuat barang "
            "lebih cepat terserap dan menekan potensi kerugian."
        ),
        "promo_copy": "Stok terbatas, harga turun hari ini. Buruan sebelum habis!",
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self._send(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid json"})
            return

        messages = request.get("messages", [])
        system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
        user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")

        if "parse" in system.lower():
            payload = parse_free_text(user)
        else:
            payload = write_prose(request)

        self._send(
            200,
            {
                "id": "stub",
                "object": "chat.completion",
                "model": "dev-stub",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(payload, ensure_ascii=False),
                        },
                    }
                ],
            },
        )

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._send(200, {"status": "ok", "note": "development stub, not a model"})

    def log_message(self, fmt: str, *args: object) -> None:
        # One short line per call; never echo message bodies.
        print(f"[stub] {self.command} {self.path}")

    def _send(self, status: int, body: dict) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    print("*** DEVELOPMENT STUB — not the model. Do not use for evaluation. ***")
    print(f"serving http://{args.host}:{args.port}/v1/chat/completions")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
