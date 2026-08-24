"""Explicit opt-in Compose configuration smoke tests.

Validates compose.yml and compose.llm.yml structure using the local container runtime
(Podman or Docker).

Never runs by default. Opt in via:
    HARGATURUN_TEST_COMPOSE=1 pytest -m compose
or:
    python scripts/run_dev_tests.py --compose
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import pytest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_compose(text: str) -> dict:
    """Parse the service keys needed by this static security contract."""
    services: dict[str, dict[str, object]] = {}
    in_services = False
    current: str | None = None
    for line in text.splitlines():
        if line == "services:":
            in_services = True
            continue
        if not in_services or not line.strip() or line.lstrip().startswith("#"):
            continue
        if line and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            current = line.strip()[:-1]
            services[current] = {}
            continue
        if current and line.startswith("    ") and not line.startswith("      "):
            key, _, value = line.strip().partition(":")
            services[current][key] = value.strip()
    return {"services": services}


class ComposeSmokeTest(unittest.TestCase):
    compose_cmd: list[str] | None = None

    @classmethod
    def setUpClass(cls):
        if os.getenv("HARGATURUN_TEST_COMPOSE", "").strip().lower() not in ("1", "true", "yes"):
            return
        cls.compose_cmd = next(
            (
                command
                for command in (["docker", "compose"], ["podman-compose"], ["podman", "compose"])
                if shutil.which(command[0])
            ),
            None,
        )

    @classmethod
    def _require_runtime(cls) -> list[str]:
        if cls.compose_cmd is not None:
            return cls.compose_cmd
        if os.getenv("HARGATURUN_STRICT_MODE", "").strip().lower() in ("1", "true", "yes"):
            raise AssertionError("Neither Docker nor Podman container runtime found on PATH.")
        raise unittest.SkipTest("Neither Docker nor Podman container runtime found on PATH.")

    def test_static_security_contract_without_runtime(self):
        for name in ("compose.yml", "compose.llm.yml"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            document = _load_compose(text)
            llm_service = document["services"]["llm-server"]
            self.assertNotIn("ports", llm_service)
            image = llm_service["image"]
            image = re.sub(r"^\$\{[^:}]+:-([^}]+)\}$", r"\1", image)
            self.assertRegex(
                image,
                r"^ghcr\.io/ggml-org/llama\.cpp:[^\s]+@sha256:[0-9a-f]{64}$",
            )

    def test_static_contract_catches_hypothetical_llm_port(self):
        text = (REPO_ROOT / "compose.yml").read_text(encoding="utf-8")
        prefix, llm = text.split("  llm-server:\n", 1)
        llm = llm.replace(
            "    command:\n",
            '    ports:\n      - "127.0.0.1:8080:8080"\n    command:\n',
            1,
        )
        document = _load_compose(prefix + "  llm-server:\n" + llm)
        self.assertIn("ports", document["services"]["llm-server"])

    def test_compose_yml_syntax(self):
        compose_file = REPO_ROOT / "compose.yml"
        self.assertTrue(compose_file.exists(), "compose.yml not found")
        res = subprocess.run(
            [*self._require_runtime(), "-f", str(compose_file), "config"],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
        )
        if res.returncode != 0:
            pytest.fail(f"compose.yml validation failed:\n{res.stderr}")

    def test_compose_llm_yml_syntax(self):
        compose_llm_file = REPO_ROOT / "compose.llm.yml"
        self.assertTrue(compose_llm_file.exists(), "compose.llm.yml not found")
        res = subprocess.run(
            [*self._require_runtime(), "-f", str(compose_llm_file), "config"],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
        )
        if res.returncode != 0:
            pytest.fail(f"compose.llm.yml validation failed:\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
