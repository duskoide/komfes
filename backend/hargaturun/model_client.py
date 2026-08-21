from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .schemas import (
    PARSE_SYSTEM_PROMPT,
    WRITE_SYSTEM_PROMPT,
    allowed_numbers_for,
    validate_parse_output,
    validate_write_output,
)


class ModelUnavailable(RuntimeError):
    pass


class ModelContractError(RuntimeError):
    pass


class TextModel(Protocol):
    def parse(self, free_text: str) -> dict: ...

    def write(self, normalized_input: dict, engine_result: dict) -> dict: ...


@dataclass(frozen=True)
class OpenAICompatibleModel:
    base_url: str = os.getenv("HARGATURUN_MODEL_URL", "http://127.0.0.1:8080/v1")
    model: str = os.getenv("HARGATURUN_MODEL_NAME", "hargaturun-qwen3.5-4b")
    timeout: float = float(os.getenv("HARGATURUN_MODEL_TIMEOUT", "20"))

    def parse(self, free_text: str) -> dict:
        output = self._complete(PARSE_SYSTEM_PROMPT, free_text)
        errors = validate_parse_output(output)
        if errors:
            raise ModelContractError("; ".join(errors))
        return output

    def write(self, normalized_input: dict, engine_result: dict) -> dict:
        payload = json.dumps(
            {"normalized_input": normalized_input, "engine_result": engine_result},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        output = self._complete(WRITE_SYSTEM_PROMPT, payload)
        errors = validate_write_output(
            output,
            allowed_numbers_for(normalized_input, engine_result),
            engine_result.get("status"),
        )
        if errors:
            raise ModelContractError("; ".join(errors))
        return output

    def _complete(self, system: str, user: str) -> dict:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "top_p": 1,
                "seed": 42,
                "max_tokens": 350,
            },
            ensure_ascii=False,
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                envelope = json.load(response)
            content = envelope["choices"][0]["message"]["content"]
            return _decode_json_object(content)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ModelUnavailable("model server unavailable") from error
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ModelContractError("model returned malformed JSON") from error


def _decode_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
        if text.startswith("json"):
            text = text[4:].lstrip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("model output is not an object")
    return value
