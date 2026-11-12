"""Adapter for any server exposing the OpenAI-compatible ``/chat/completions`` API.

Works with local servers (e.g. ``vllm serve``, llama.cpp server, Ollama) and
with hosted providers. Uses only the standard library. The API key, if needed,
is read from the environment variable named in ``backend_options.api_key_env``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from liverswat_bench.models.base import (
    AdapterError,
    GenerationResult,
    Messages,
    ModelAdapter,
)
from liverswat_bench.models.config import GenerationParams, ModelConfig


class OpenAICompatibleAdapter(ModelAdapter):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        opts = config.backend_options
        self.base_url: str = str(opts["base_url"]).rstrip("/")
        self.timeout_s: float = float(opts.get("timeout_s", 120))
        self.api_key: str | None = None
        key_env = opts.get("api_key_env")
        if key_env:
            self.api_key = os.environ.get(key_env)
            if not self.api_key:
                raise AdapterError(
                    f"environment variable {key_env!r} (backend_options.api_key_env) is not set"
                )

    def _request_body(self, messages: Messages, params: GenerationParams) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "max_tokens": params.max_new_tokens,
        }
        if params.seed is not None:
            body["seed"] = params.seed
        if params.stop:
            body["stop"] = params.stop
        return body

    def generate(self, messages: Messages, params: GenerationParams) -> GenerationResult:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(self._request_body(messages, params)).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise AdapterError(f"HTTP {exc.code} from {self.base_url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise AdapterError(f"cannot reach {self.base_url}: {exc.reason}") from exc
        except (TimeoutError, json.JSONDecodeError) as exc:
            raise AdapterError(f"bad response from {self.base_url}: {exc}") from exc

        try:
            choice = payload["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(f"unexpected response shape from {self.base_url}") from exc
        if not isinstance(text, str):
            raise AdapterError("response message content is not a string")
        usage = payload.get("usage") or {}
        return GenerationResult(
            text=text,
            finish_reason=choice.get("finish_reason"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            served_model_id=payload.get("model"),
            extra={"system_fingerprint": payload.get("system_fingerprint")},
        )

    def runtime_info(self) -> dict[str, Any]:
        # The base URL is recorded, never the key.
        return {"backend": "openai_compatible", "base_url": self.base_url}
