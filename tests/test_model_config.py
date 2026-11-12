from __future__ import annotations

from pathlib import Path

import pytest

from liverswat_bench.models import ConfigError, load_model_config, resolve_model_config
from liverswat_bench.models.config import ModelConfig
from tests.conftest import REPO_ROOT

CONFIG_DIR = REPO_ROOT / "configs" / "models"
SHA = "0123456789abcdef0123456789abcdef01234567"


def cfg(**kw) -> dict:
    data = {"config_id": "x", "model_name": "org/model", "backend": "mock"}
    data.update(kw)
    return data


@pytest.mark.parametrize("path", sorted(CONFIG_DIR.glob("*.yaml")), ids=lambda p: p.name)
def test_shipped_configs_load(path: Path):
    config = load_model_config(path)
    assert config.config_id == path.stem


def test_example_configs_flag_unpinned_revisions():
    for name in ("qwen2.5-0.5b-instruct-hf", "qwen2.5-0.5b-instruct-vllm"):
        config = load_model_config(CONFIG_DIR / f"{name}.yaml")
        assert not config.revision_pinned
        assert config.allow_unpinned_revision


@pytest.mark.parametrize("backend", ["transformers", "vllm"])
def test_local_backends_require_revision(backend):
    with pytest.raises(ValueError, match="require model_revision"):
        ModelConfig.model_validate(cfg(backend=backend))


def test_unpinned_revision_rejected_without_opt_in():
    with pytest.raises(ValueError, match="not a 40-character commit SHA"):
        ModelConfig.model_validate(cfg(backend="transformers", model_revision="main"))


def test_pinned_revision_accepted():
    c = ModelConfig.model_validate(cfg(backend="transformers", model_revision=SHA))
    assert c.revision_pinned


@pytest.mark.parametrize("key", ["api_key", "API_KEY", "token"])
def test_credentials_rejected(key):
    with pytest.raises(ValueError, match="credentials must not be stored"):
        ModelConfig.model_validate(cfg(backend_options={key: "sk-123"}))


def test_openai_compatible_requires_base_url():
    with pytest.raises(ValueError, match="base_url"):
        ModelConfig.model_validate(cfg(backend="openai_compatible"))


@pytest.mark.parametrize("template", ["no placeholder", "{question} {question}"])
def test_prompt_template_needs_one_placeholder(template):
    with pytest.raises(ValueError, match="exactly once"):
        ModelConfig.model_validate(cfg(prompt_template=template))


def test_build_messages_with_system_prompt_and_braces():
    c = ModelConfig.model_validate(
        cfg(system_prompt="Be careful.", prompt_template="Q: {question}\nA:")
    )
    msgs = c.build_messages("What is {x}?")
    assert msgs == [
        {"role": "system", "content": "Be careful."},
        {"role": "user", "content": "Q: What is {x}?\nA:"},
    ]


def test_invalid_generation_params():
    with pytest.raises(ValueError):
        ModelConfig.model_validate(cfg(generation={"temperature": -1}))
    with pytest.raises(ValueError):
        ModelConfig.model_validate(cfg(generation={"max_new_tokens": 0}))


def test_load_errors_are_config_errors(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("config_id: [unclosed")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_model_config(bad_yaml)
    not_mapping = tmp_path / "list.yaml"
    not_mapping.write_text("- a\n- b\n")
    with pytest.raises(ConfigError, match="mapping"):
        load_model_config(not_mapping)
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("config_id: x\nmodel_name: m\nbackend: nope\n")
    with pytest.raises(ConfigError, match="backend"):
        load_model_config(invalid)
    with pytest.raises(ConfigError, match="cannot read"):
        load_model_config(tmp_path / "missing.yaml")


def test_resolve_model_config():
    assert resolve_model_config("mock", CONFIG_DIR) == CONFIG_DIR / "mock.yaml"
    explicit = CONFIG_DIR / "mock.yaml"
    assert resolve_model_config(str(explicit), CONFIG_DIR) == explicit
    with pytest.raises(ConfigError, match="no model config"):
        resolve_model_config("does-not-exist", CONFIG_DIR)


def test_prompt_text_and_stop_sequences_are_not_stripped():
    c = ModelConfig.model_validate(
        cfg(
            system_prompt="  keep  ",
            prompt_template="Q: {question}\nA: ",
            generation={"stop": ["\n\n", " "]},
        )
    )
    assert c.system_prompt == "  keep  "
    assert c.prompt_template.endswith("A: ")
    assert c.generation.stop == ["\n\n", " "]
