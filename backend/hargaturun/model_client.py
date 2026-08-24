from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .schemas import (
    PARSE_REQUIRED_FIELDS,
    PARSE_SYSTEM_PROMPT,
    MULTIMODAL_PARSE_SYSTEM_PROMPT,
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
    base_url: str = "http://127.0.0.1:8080/v1"
    model: str = "hargaturun-qwen3.5-4b"
    timeout: float = 20.0
    max_output_tokens: int = 350

    def parse(self, free_text: str) -> dict:
        output = _normalize_parse_bookkeeping(
            self._complete(PARSE_SYSTEM_PROMPT, free_text)
        )
        errors = validate_parse_output(output)
        if errors:
            repair_payload = json.dumps(
                {
                    "original_input": free_text,
                    "invalid_output": output,
                    "contract_violations": errors,
                    "instruction": (
                        "Perbaiki JSON agar semua pelanggaran kontrak hilang. "
                        "Jangan menebak fakta baru. Keluarkan JSON saja."
                    ),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            output = _normalize_parse_bookkeeping(
                self._complete(PARSE_SYSTEM_PROMPT, repair_payload)
            )
            errors = validate_parse_output(output)
        if errors:
            raise ModelContractError("; ".join(errors))
        return output

    def parse_multimodal(self, text: str, image_data_uri: str) -> dict:
        output = _normalize_parse_bookkeeping(
            self._complete_multimodal(MULTIMODAL_PARSE_SYSTEM_PROMPT, text, image_data_uri)
        )
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
        allowed_numbers = allowed_numbers_for(normalized_input, engine_result)
        errors = validate_write_output(output, allowed_numbers, engine_result.get("status"))
        if errors:
            repair_payload = json.dumps(
                {
                    "authoritative_input": {
                        "normalized_input": normalized_input,
                        "engine_result": engine_result,
                    },
                    "invalid_output": output,
                    "contract_violations": errors,
                    "instruction": (
                        "Perbaiki JSON agar semua pelanggaran kontrak hilang. "
                        "Jangan menambah atau mengubah angka. Keluarkan JSON saja."
                    ),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            output = self._complete(WRITE_SYSTEM_PROMPT, repair_payload)
            errors = validate_write_output(output, allowed_numbers, engine_result.get("status"))
        if errors:
            raise ModelContractError("; ".join(errors))
        return output


    def _complete_multimodal(self, system: str, text: str, image_data_uri: str) -> dict:
        return self._complete(
            system,
            [
                {"type": "text", "text": text or "Ekstrak fakta eksplisit saja."},
                {"type": "image_url", "image_url": {"url": image_data_uri}},
            ],
        )

    def _complete(self, system: str, user: object) -> dict:
        content = user
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                "temperature": 0,
                "top_p": 1,
                "seed": 42,
                "max_tokens": self.max_output_tokens,
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


def _normalize_parse_bookkeeping(output: dict) -> dict:
    """Derive confirmation metadata from null required fields.

    The bookkeeping is deterministic and contains no extracted facts. Normalizing
    it prevents a base model from treating optional ``shop_name`` as required,
    while leaving every parsed value untouched for strict validation.
    """
    parsed = output.get("parsed_input")
    if not isinstance(parsed, dict):
        return output
    normalized = dict(output)
    missing = [field for field in PARSE_REQUIRED_FIELDS if parsed.get(field) is None]
    normalized["missing_fields"] = missing
    normalized["needs_confirmation"] = bool(missing)
    return normalized


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
