"""Common interface for all model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from liverswat_bench.models.config import GenerationParams, ModelConfig

Messages = list[dict[str, str]]


class AdapterError(RuntimeError):
    """Raised when a backend cannot be loaded or a generation fails."""


@dataclass
class GenerationResult:
    text: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    #: Model identifier reported by the backend, if any (e.g. by an API server).
    served_model_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class ModelAdapter(ABC):
    """A model backend. Subclasses load lazily so optional deps stay optional."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    @abstractmethod
    def generate(self, messages: Messages, params: GenerationParams) -> GenerationResult:
        """Generate one response. ``params.seed`` is the per-trial seed."""

    def runtime_info(self) -> dict[str, Any]:
        """Backend-specific environment details (library versions, devices)."""
        return {}

    def close(self) -> None:  # noqa: B027 - optional hook
        """Release resources. Default: nothing to do."""
