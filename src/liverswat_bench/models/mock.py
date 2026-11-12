"""Deterministic mock model for testing without a GPU, model download or API."""

from __future__ import annotations

import hashlib
import json

from liverswat_bench.models.base import (
    AdapterError,
    GenerationResult,
    Messages,
    ModelAdapter,
)
from liverswat_bench.models.config import GenerationParams

MOCK_PREFIX = "[MOCK RESPONSE - NOT A REAL MODEL]"


class MockAdapter(ModelAdapter):
    """Returns a fixed-format response derived from a hash of the inputs.

    The same messages, parameters and model name always produce the same text.
    ``backend_options.fail_if_prompt_contains`` (list of strings) makes the mock
    raise for matching prompts, to exercise error handling.
    """

    def generate(self, messages: Messages, params: GenerationParams) -> GenerationResult:
        prompt = messages[-1]["content"]
        for marker in self.config.backend_options.get("fail_if_prompt_contains", []):
            if marker in prompt:
                raise AdapterError(f"mock failure triggered by marker {marker!r}")

        payload = json.dumps(
            {
                "model": self.config.model_name,
                "messages": messages,
                "params": params.model_dump(),
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        text = (
            f"{MOCK_PREFIX} digest={digest}. This placeholder text is generated "
            "deterministically for software testing and contains no medical information."
        )
        words = text.split()
        if len(words) > params.max_new_tokens:
            text = " ".join(words[: params.max_new_tokens])
            finish = "length"
        else:
            finish = "stop"
        return GenerationResult(
            text=text,
            finish_reason=finish,
            prompt_tokens=sum(len(m["content"].split()) for m in messages),
            completion_tokens=len(text.split()),
            served_model_id=self.config.model_name,
        )

    def runtime_info(self) -> dict[str, object]:
        return {"backend": "mock", "device": "cpu"}
