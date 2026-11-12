"""vLLM offline-inference backend (optional: ``pip install -e '.[vllm]'``).

For a vLLM *server*, use the ``openai_compatible`` backend instead.
"""

from __future__ import annotations

import contextlib
from importlib import metadata
from typing import Any

from liverswat_bench.models.base import (
    AdapterError,
    GenerationResult,
    Messages,
    ModelAdapter,
)
from liverswat_bench.models.config import GenerationParams, ModelConfig


class VLLMAdapter(ModelAdapter):
    """Options (``backend_options``): ``quantization``, ``dtype``,
    ``tensor_parallel_size``, ``gpu_memory_utilization``, ``max_model_len``,
    ``trust_remote_code``. They are passed straight to ``vllm.LLM``.
    """

    _LLM_OPTIONS = (
        "quantization",
        "dtype",
        "tensor_parallel_size",
        "gpu_memory_utilization",
        "max_model_len",
        "trust_remote_code",
    )

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        self.llm, self.sampling_params_cls = self._load_engine()

    def _load_engine(self) -> tuple[Any, Any]:
        try:
            from vllm import LLM, SamplingParams
        except ImportError as exc:
            raise AdapterError(
                "the vllm backend needs optional dependencies: pip install -e '.[vllm]'"
            ) from exc
        opts = {k: v for k, v in self.config.backend_options.items() if k in self._LLM_OPTIONS}
        try:
            llm = LLM(
                model=self.config.model_name,
                revision=self.config.model_revision,
                tokenizer_revision=self.config.model_revision,
                **opts,
            )
        except Exception as exc:
            raise AdapterError(f"failed to load {self.config.model_name}: {exc}") from exc
        return llm, SamplingParams

    def generate(self, messages: Messages, params: GenerationParams) -> GenerationResult:
        sampling = self.sampling_params_cls(
            temperature=params.temperature,
            top_p=params.top_p,
            max_tokens=params.max_new_tokens,
            seed=params.seed,
            stop=params.stop or None,
        )
        outputs = self.llm.chat(messages, sampling_params=sampling, use_tqdm=False)
        request = outputs[0]
        completion = request.outputs[0]
        return GenerationResult(
            text=completion.text,
            finish_reason=completion.finish_reason,
            prompt_tokens=len(request.prompt_token_ids or []),
            completion_tokens=len(completion.token_ids),
            served_model_id=self.config.model_name,
        )

    def runtime_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"backend": "vllm"}
        for lib in ("vllm", "torch"):
            with contextlib.suppress(metadata.PackageNotFoundError):
                info[f"{lib}_version"] = metadata.version(lib)
        return info
