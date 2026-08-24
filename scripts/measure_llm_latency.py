#!/usr/bin/env python3
"""Measure warmed local llama.cpp text/image latency without inventing hardware data.

Examples:
    python scripts/measure_llm_latency.py --url http://127.0.0.1:8080/v1
    python scripts/measure_llm_latency.py --url http://127.0.0.1:8080/v1 --image

The script never writes a report. It prints measurements from this run only;
missing endpoints, image support, or nvidia-smi are reported as unavailable.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import threading
import time
import urllib.error
import urllib.request

# A valid 1x1 RGB PNG, kept local so this tool does not fetch or expose a file.
IMAGE_DATA_URI = "data:image/png;base64," + base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c6360a0f000000200001a5c2e0000000049454e44ae426082"
)).decode("ascii")


def request(url: str, payload: dict, timeout: float) -> float:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "HargaTurun-Benchmark"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        json.load(response)
    return (time.perf_counter() - started) * 1000


def sample_vram(stop: threading.Event, peak: list[int]) -> None:
    while not stop.is_set():
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL, text=True, timeout=2,
            )
            values = [int(line.strip()) for line in output.splitlines() if line.strip().isdigit()]
            if values:
                peak[0] = max(peak[0], sum(values))
        except (FileNotFoundError, OSError, subprocess.SubprocessError, ValueError):
            return
        stop.wait(0.1)


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * p
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def measure(kind: str, url: str, model: str, count: int, warmup: int, timeout: float) -> None:
    if kind == "image":
        content = [
            {"type": "text", "text": "Ekstrak hanya fakta yang terlihat."},
            {"type": "image_url", "image_url": {"url": IMAGE_DATA_URI}},
        ]
    else:
        content = "roti tawar 20 biji exp 2 hari harga 15rb modal 10rb"
    payload = {"model": model, "messages": [{"role": "user", "content": content}],
               "temperature": 0, "max_tokens": 64, "stream": False}
    try:
        for _ in range(warmup):
            request(url, payload, timeout)
        peak = [0]
        stop = threading.Event()
        sampler = threading.Thread(target=sample_vram, args=(stop, peak), daemon=True)
        sampler.start()
        values = [request(url, payload, timeout) for _ in range(count)]
        stop.set()
        sampler.join(timeout=1)
    except (OSError, urllib.error.URLError, TimeoutError, RuntimeError) as error:
        print(f"{kind}: unavailable ({error})")
        return
    print(f"{kind}: n={len(values)} p50_ms={percentile(values, 0.50):.1f} p95_ms={percentile(values, 0.95):.1f}")
    if peak[0]:
        print(f"{kind}: peak_vram_mib={peak[0] / 1_048_576:.1f} (nvidia-smi sum)")
    else:
        print(f"{kind}: peak_vram_mib=unavailable (nvidia-smi not available or returned no sample)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="hargaturun-qwen3.5-4b")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--image", action="store_true", help="Also measure the opt-in multimodal endpoint")
    args = parser.parse_args()
    if args.count < 1 or args.warmup < 0:
        parser.error("--count must be positive and --warmup cannot be negative")
    print("Measurements are from this run only; no values are recorded when unavailable.")
    measure("text", args.url, args.model, args.count, args.warmup, args.timeout)
    if args.image:
        measure("image", args.url, args.model, args.count, args.warmup, args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
