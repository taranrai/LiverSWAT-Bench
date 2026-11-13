"""Model adapters and configuration.

Backends with heavy dependencies (transformers, vllm) are imported only when
they are actually requested, so the core package needs neither.
"""

from __future__ import annotations

from liverswat_bench.models.base import AdapterError, GenerationResult, ModelAdapter
from liverswat_bench.models.config import (
    Backend,
    ConfigError,
    GenerationParams,
    ModelConfig,
    load_model_config,
    resolve_model_config,
)


def create_adapter(config: ModelConfig) -> ModelAdapter:
    if config.backend == Backend.MOCK:
        from liverswat_bench.models.mock import MockAdapter

        return MockAdapter(config)
    if config.backend == Backend.OPENAI_COMPATIBLE:
        from liverswat_bench.models.openai_compatible import OpenAICompatibleAdapter

        return OpenAICompatibleAdapter(config)
    if config.backend == Backend.OLLAMA:
        from liverswat_bench.models.ollama import OllamaAdapter

        return OllamaAdapter(config)
    if config.backend == Backend.TRANSFORMERS:
        from liverswat_bench.models.hf_transformers import TransformersAdapter

        return TransformersAdapter(config)
    if config.backend == Backend.VLLM:
        from liverswat_bench.models.vllm_backend import VLLMAdapter

        return VLLMAdapter(config)
    raise ConfigError(f"unsupported backend {config.backend!r}")  # pragma: no cover


__all__ = [
    "AdapterError",
    "Backend",
    "ConfigError",
    "GenerationParams",
    "GenerationResult",
    "ModelAdapter",
    "ModelConfig",
    "create_adapter",
    "load_model_config",
    "resolve_model_config",
]
