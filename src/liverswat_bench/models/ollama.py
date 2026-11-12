"""Native Ollama backend (local inference through the Ollama HTTP API).

Uses ``/api/chat`` so that the context window (``num_ctx``), seed and other
options are set explicitly. At load time, the adapter reads ``/api/tags`` and
checks that the installed model has the digest given in ``model_revision``
(``sha256:<64 hex>``). A different or missing model stops the run, so results
are tied to exact model weights. Standard library only.

Options (``backend_options``): ``base_url`` (default ``http://localhost:11434``),
``num_ctx`` (default 8192), ``format`` (for example ``json``), ``timeout_s``
(default 600), ``keep_alive``.
"""

from __future__ import annotations

import json
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


class OllamaAdapter(ModelAdapter):
    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        opts = config.backend_options
        self.base_url = str(opts.get("base_url", "http://localhost:11434")).rstrip("/")
        self.num_ctx = int(opts.get("num_ctx", 8192))
        self.format = opts.get("format")
        self.timeout_s = float(opts.get("timeout_s", 600))
        self.keep_alive = opts.get("keep_alive")
        self.installed = self._check_model()

    def _request(self, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if body is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise AdapterError(f"HTTP {exc.code} from Ollama {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise AdapterError(f"cannot reach Ollama at {self.base_url}: {exc.reason}") from exc
        except (TimeoutError, json.JSONDecodeError) as exc:
            raise AdapterError(f"bad response from Ollama {path}: {exc}") from exc

    def _check_model(self) -> dict[str, Any]:
        tags = self._request("/api/tags").get("models", [])
        match = next((m for m in tags if m.get("name") == self.config.model_name), None)
        if match is None:
            raise AdapterError(
                f"model {self.config.model_name!r} is not installed in Ollama "
                f"(run: ollama pull {self.config.model_name})"
            )
        digest = f"sha256:{match.get('digest')}"
        expected = self.config.model_revision
        if expected and expected != digest:
            raise AdapterError(
                f"installed {self.config.model_name} has digest {digest}, but the config "
                f"pins {expected}; refusing to run with different weights"
            )
        return {"digest": digest, "details": match.get("details", {})}

    def generate(self, messages: Messages, params: GenerationParams) -> GenerationResult:
        options: dict[str, Any] = {
            "temperature": params.temperature,
            "top_p": params.top_p,
            "num_predict": params.max_new_tokens,
            "num_ctx": self.num_ctx,
        }
        if params.seed is not None:
            options["seed"] = params.seed
        if params.stop:
            options["stop"] = params.stop
        body: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if self.format:
            body["format"] = self.format
        if self.keep_alive is not None:
            body["keep_alive"] = self.keep_alive
        payload = self._request("/api/chat", body)
        try:
            text = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise AdapterError("unexpected response shape from Ollama /api/chat") from exc
        prompt_tokens = payload.get("prompt_eval_count")
        if prompt_tokens is not None and prompt_tokens >= self.num_ctx:
            raise AdapterError(
                f"prompt used {prompt_tokens} tokens, the full context window ({self.num_ctx}); "
                "the prompt may have been truncated"
            )
        return GenerationResult(
            text=text,
            finish_reason=payload.get("done_reason"),
            prompt_tokens=prompt_tokens,
            completion_tokens=payload.get("eval_count"),
            served_model_id=payload.get("model"),
            extra={
                "total_duration_ns": payload.get("total_duration"),
                "eval_duration_ns": payload.get("eval_duration"),
            },
        )

    def runtime_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "backend": "ollama",
            "base_url": self.base_url,
            "num_ctx": self.num_ctx,
            "format": self.format,
            "installed_digest": self.installed["digest"],
            "model_details": self.installed["details"],
        }
        try:
            info["ollama_version"] = self._request("/api/version").get("version")
        except AdapterError:
            info["ollama_version"] = None
        return info
