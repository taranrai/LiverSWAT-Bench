"""YAML model configuration.

A model config pins everything needed to reproduce a run: the exact model
identifier and revision, backend, prompt template, system prompt and
generation parameters. Credentials are never stored in configs; the
OpenAI-compatible backend reads its API key from a named environment variable.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

#: A Hugging Face commit SHA, or an Ollama content digest.
PINNED_REVISION = re.compile(r"^([0-9a-f]{40}|sha256:[0-9a-f]{64})$")
QUESTION_PLACEHOLDER = "{question}"
FORBIDDEN_OPTION_KEYS = {"api_key", "token", "password", "secret"}


class ConfigError(ValueError):
    """Raised when a model config cannot be loaded or is invalid."""


class Backend(StrEnum):
    MOCK = "mock"
    TRANSFORMERS = "transformers"
    VLLM = "vllm"
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"


class _Strict(BaseModel):
    # No whitespace stripping: prompts, system prompts and stop sequences must be
    # stored exactly as written, or runs are not reproducible.
    model_config = ConfigDict(extra="forbid")


class GenerationParams(_Strict):
    temperature: float = Field(default=0.0, ge=0.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
    max_new_tokens: int = Field(default=512, gt=0)
    #: Base seed. Trial ``t`` uses ``seed + t``. ``None`` means unseeded.
    seed: int | None = 0
    stop: list[str] = Field(default_factory=list)


class ModelConfig(_Strict):
    config_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    model_name: str = Field(min_length=1)
    #: Exact revision (a 40-character commit SHA for Hugging Face models).
    model_revision: str | None = None
    #: Must be set explicitly to run with an unpinned revision such as ``main``.
    allow_unpinned_revision: bool = False
    backend: Backend
    licence: str | None = None
    #: Weights are publicly downloadable.
    open_weight: bool | None = None
    #: Licence is OSI-approved open source. Distinct from open_weight.
    osi_approved_licence: bool | None = None
    parameter_count: str | None = None
    quantisation: str | None = None
    system_prompt: str | None = None
    prompt_template: str = QUESTION_PLACEHOLDER
    generation: GenerationParams = Field(default_factory=GenerationParams)
    backend_options: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    @property
    def revision_pinned(self) -> bool:
        return bool(self.model_revision and PINNED_REVISION.match(self.model_revision))

    @model_validator(mode="after")
    def _check(self) -> ModelConfig:
        if self.prompt_template.count(QUESTION_PLACEHOLDER) != 1:
            raise ValueError("prompt_template must contain {question} exactly once")
        leaked = FORBIDDEN_OPTION_KEYS & {k.lower() for k in self.backend_options}
        if leaked:
            raise ValueError(
                f"credentials must not be stored in configs (found {sorted(leaked)}); "
                "use backend_options.api_key_env to name an environment variable"
            )
        if self.backend in (Backend.TRANSFORMERS, Backend.VLLM, Backend.OLLAMA):
            if not self.model_revision:
                raise ValueError(f"{self.backend} configs require model_revision")
            if not self.revision_pinned and not self.allow_unpinned_revision:
                raise ValueError(
                    f"model_revision {self.model_revision!r} is not a 40-character commit SHA "
                    "or an Ollama 'sha256:<64 hex>' digest; pin it, or set "
                    "allow_unpinned_revision: true (recorded in outputs)"
                )
        if self.backend == Backend.OPENAI_COMPATIBLE and not self.backend_options.get("base_url"):
            raise ValueError("openai_compatible configs require backend_options.base_url")
        return self

    def render_prompt(self, question: str) -> str:
        return self.prompt_template.replace(QUESTION_PLACEHOLDER, question)

    def build_messages(self, question: str) -> list[dict[str, str]]:
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": self.render_prompt(question)})
        return messages


def load_model_config(path: Path) -> ModelConfig:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read model config {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"model config {path} must be a YAML mapping")
    try:
        return ModelConfig.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '<config>'}: {e['msg']}" for e in exc.errors()
        )
        raise ConfigError(f"invalid model config {path}: {details}") from exc


def resolve_model_config(model: str, configs_dir: Path) -> Path:
    """Accept either a path to a YAML file or a config ID in ``configs_dir``."""
    candidate = Path(model)
    if candidate.suffix in {".yaml", ".yml"} or candidate.exists():
        return candidate
    for suffix in (".yaml", ".yml"):
        path = configs_dir / f"{model}{suffix}"
        if path.exists():
            return path
    raise ConfigError(f"no model config found for {model!r} (looked in {configs_dir})")
