"""Hugging Face Transformers backend (optional: ``pip install -e '.[hf]'``).

Heavy imports happen in :meth:`_load_components`, so importing this module never
requires ``torch`` or ``transformers``. Tests override that method with stubs.
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


class TransformersAdapter(ModelAdapter):
    """Options (``backend_options``): ``device_map`` (default "auto"),
    ``torch_dtype`` (default "auto"), ``trust_remote_code`` (default false),
    ``load_in_4bit`` / ``load_in_8bit`` (bitsandbytes quantisation).
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        self.tokenizer, self.model, self.torch = self._load_components()

    def _load_components(self) -> tuple[Any, Any, Any]:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise AdapterError(
                "the transformers backend needs optional dependencies: "
                "pip install -e '.[hf]' (and a suitable torch build)"
            ) from exc

        opts = self.config.backend_options
        kwargs: dict[str, Any] = {
            "revision": self.config.model_revision,
            "device_map": opts.get("device_map", "auto"),
            "torch_dtype": opts.get("torch_dtype", "auto"),
            "trust_remote_code": bool(opts.get("trust_remote_code", False)),
        }
        if opts.get("load_in_4bit") or opts.get("load_in_8bit"):
            from transformers import BitsAndBytesConfig

            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=bool(opts.get("load_in_4bit")),
                load_in_8bit=bool(opts.get("load_in_8bit")),
            )
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_name,
                revision=self.config.model_revision,
                trust_remote_code=kwargs["trust_remote_code"],
            )
            model = AutoModelForCausalLM.from_pretrained(self.config.model_name, **kwargs)
        except Exception as exc:  # surface any loading failure with context
            raise AdapterError(f"failed to load {self.config.model_name}: {exc}") from exc
        model.eval()
        return tokenizer, model, torch

    def generate(self, messages: Messages, params: GenerationParams) -> GenerationResult:
        torch = self.torch
        if params.seed is not None:
            torch.manual_seed(params.seed)
        input_ids = self.tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        ).to(self.model.device)
        do_sample = params.temperature > 0
        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": params.max_new_tokens,
            "do_sample": do_sample,
        }
        if do_sample:
            gen_kwargs.update(temperature=params.temperature, top_p=params.top_p)
        if params.stop:
            gen_kwargs["stop_strings"] = params.stop
            gen_kwargs["tokenizer"] = self.tokenizer
        with torch.no_grad():
            output = self.model.generate(input_ids, **gen_kwargs)
        new_tokens = output[0][input_ids.shape[-1] :]
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        n_new = int(new_tokens.shape[-1])
        return GenerationResult(
            text=text,
            finish_reason="length" if n_new >= params.max_new_tokens else "stop",
            prompt_tokens=int(input_ids.shape[-1]),
            completion_tokens=n_new,
            served_model_id=self.config.model_name,
        )

    def runtime_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {"backend": "transformers"}
        for lib in ("torch", "transformers", "accelerate", "bitsandbytes"):
            with contextlib.suppress(metadata.PackageNotFoundError):
                info[f"{lib}_version"] = metadata.version(lib)
        torch = self.torch
        try:
            if torch.cuda.is_available():
                info["cuda_version"] = torch.version.cuda
                info["gpus"] = [
                    torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())
                ]
            info["model_device"] = str(self.model.device)
        except AttributeError:
            pass
        return info
