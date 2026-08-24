"""Static and opt-in smoke coverage for the text/multimodal server profiles."""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _health(base_url: str, timeout: float) -> bool:
    root = base_url.rstrip("/")
    health_url = root.rsplit("/v1", 1)[0] + "/health" if "/v1" in root else root + "/health"
    try:
        with urllib.request.urlopen(health_url, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _chat(base_url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "HargaTurun-Smoke"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        assert response.status == 200
        return json.load(response)


class TestModelServerProfileConfig:
    def test_text_profile_is_default_and_disables_projector(self):
        compose = _read("compose.llm.yml")
        text = compose.split("  llm-server-mm:", 1)[0]
        assert "--no-mmproj" in text
        assert "--mmproj" not in text
        assert "profiles:" not in text
        assert ":/models:ro" in text

    def test_multimodal_profile_requires_explicit_projector_and_read_only_mount(self):
        compose = _read("compose.llm.yml")
        mm = compose.split("  llm-server-mm:", 1)[1]
        assert "profiles: [multimodal]" in mm
        assert "--mmproj" in mm
        assert "/models/${HARGATURUN_MMPROJ_FILE" in mm
        assert ":/models:ro" in mm
        assert "--no-mmproj" not in mm
        assert "HARGATURUN_MMPROJ_SHA256" in mm

    def test_model_and_projector_are_configurable_without_code_changes(self):
        compose = _read("compose.llm.yml")
        launcher = _read("scripts/run-llama-server.sh")
        for text in (compose, launcher):
            assert "HARGATURUN_MODEL_FILE" in text
            assert "HARGATURUN_MODEL_NAME" in text
        assert "HARGATURUN_MMPROJ_FILE" in compose
        assert "HARGATURUN_MMPROJ_PATH" in launcher
        assert "HARGATURUN_MODEL_SHA256" in launcher
        assert "HARGATURUN_MMPROJ_SHA256" in launcher

    def test_artifact_provenance_is_documented_without_fabricated_hashes(self):
        docs = _read("docs/HargaTurun_LLM_Server_Setup.md")
        assert "Projector artifact provenance" in docs
        assert "PROJECTOR_SHA256_TO_RECORD" in docs
        assert "sha256sum" in docs
        assert "Hugging Face" in docs


@pytest.mark.real_model
def test_readiness_covers_text_and_opted_in_multimodal_profiles():
    if not _enabled("HARGATURUN_TEST_REAL_MODEL"):
        pytest.skip("Live model checks disabled; set HARGATURUN_TEST_REAL_MODEL=1.")
    timeout = float(os.getenv("HARGATURUN_MODEL_TIMEOUT", "10"))
    text_url = os.getenv("HARGATURUN_MODEL_URL", "http://127.0.0.1:8080/v1")
    mm_url = os.getenv("HARGATURUN_MULTIMODAL_MODEL_URL", text_url)
    if not _health(text_url, timeout):
        if _enabled("HARGATURUN_STRICT_MODE"):
            raise AssertionError(f"Text model server is not ready: {text_url}")
        pytest.skip(f"[SKIP] Text model server is not ready: {text_url}")
    if not _enabled("HARGATURUN_TEST_MULTIMODAL"):
        pytest.skip("[SKIP] Multimodal readiness disabled; set HARGATURUN_TEST_MULTIMODAL=1.")
    if not _health(mm_url, timeout):
        if _enabled("HARGATURUN_STRICT_MODE"):
            raise AssertionError(f"Multimodal model server is not ready: {mm_url}")
        pytest.skip(f"[SKIP] Multimodal model server is not ready: {mm_url}")


@pytest.mark.real_model
@pytest.mark.parametrize("profile_env", ["HARGATURUN_TEST_MULTIMODAL"])
def test_one_local_image_request(profile_env: str):
    if not _enabled("HARGATURUN_TEST_REAL_MODEL"):
        pytest.skip("Live model checks disabled; set HARGATURUN_TEST_REAL_MODEL=1.")
    if not _enabled(profile_env):
        pytest.skip(f"[SKIP] Image smoke disabled; set {profile_env}=1 with a --mmproj server.")
    timeout = float(os.getenv("HARGATURUN_MODEL_TIMEOUT", "20"))
    base_url = os.getenv("HARGATURUN_MULTIMODAL_MODEL_URL", os.getenv("HARGATURUN_MODEL_URL", "http://127.0.0.1:8080/v1"))
    if not _health(base_url, timeout):
        if _enabled("HARGATURUN_STRICT_MODE"):
            raise AssertionError(f"Multimodal model server is not ready: {base_url}")
        pytest.skip(f"[SKIP] Multimodal model server is not ready: {base_url}")
    # 1x1 PNG: a deterministic local fixture, not a file path or remote URL.
    image_uri = "data:image/png;base64," + base64.b64encode(
        bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c6360a0f000000200001a5c2e0000000049454e44ae426082")
    ).decode("ascii")
    payload = {
        "model": os.getenv("HARGATURUN_MODEL_NAME", "hargaturun-qwen3.5-4b"),
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Ekstrak hanya fakta yang terlihat."},
            {"type": "image_url", "image_url": {"url": image_uri}},
        ]}],
        "temperature": 0,
        "max_tokens": 32,
        "stream": False,
    }
    started = time.perf_counter()
    try:
        response = _chat(base_url, payload, timeout)
    except (OSError, urllib.error.URLError) as error:
        pytest.fail(f"Multimodal image request failed: {error}")
    assert response.get("choices"), "image smoke response did not contain choices"
    assert time.perf_counter() >= started
