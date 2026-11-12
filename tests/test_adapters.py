"""Adapter tests. No model weights are downloaded and no external network is used:
heavy backends are exercised through stubs, and the OpenAI-compatible adapter
talks to a local in-process HTTP server."""

from __future__ import annotations

import builtins
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from typing import ClassVar

import pytest

from liverswat_bench.models import (
    AdapterError,
    GenerationParams,
    ModelConfig,
    create_adapter,
)
from liverswat_bench.models.hf_transformers import TransformersAdapter
from liverswat_bench.models.mock import MOCK_PREFIX, SCRIPTED_PREFIX, MockAdapter
from liverswat_bench.models.vllm_backend import VLLMAdapter

SHA = "0123456789abcdef0123456789abcdef01234567"
MSGS = [{"role": "user", "content": "Hello?"}]


def config(**kw) -> ModelConfig:
    data = {"config_id": "t", "model_name": "org/model", "backend": "mock"}
    data.update(kw)
    return ModelConfig.model_validate(data)


# --------------------------------------------------------------------- mock


def test_mock_is_deterministic_and_seed_sensitive():
    adapter = MockAdapter(config())
    p0 = GenerationParams(seed=0)
    a, b = adapter.generate(MSGS, p0), adapter.generate(MSGS, p0)
    c = adapter.generate(MSGS, GenerationParams(seed=1))
    assert a.text == b.text
    assert a.text != c.text
    assert a.text.startswith(MOCK_PREFIX)
    assert a.finish_reason == "stop"
    assert a.completion_tokens == len(a.text.split())


def test_mock_truncates_to_max_new_tokens():
    result = MockAdapter(config()).generate(MSGS, GenerationParams(max_new_tokens=3))
    assert result.finish_reason == "length"
    assert result.completion_tokens == 3


def test_mock_failure_marker():
    adapter = MockAdapter(config(backend_options={"fail_if_prompt_contains": ["Hello"]}))
    with pytest.raises(AdapterError, match="mock failure"):
        adapter.generate(MSGS, GenerationParams())


def test_create_adapter_dispatches_mock():
    assert isinstance(create_adapter(config()), MockAdapter)


# --------------------------------------------------- OpenAI-compatible (local)


class _Handler(BaseHTTPRequestHandler):
    requests: ClassVar[list] = []
    reply: ClassVar[tuple[int, dict]] = (200, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests.append(
            {"path": self.path, "body": body, "auth": self.headers.get("Authorization")}
        )
        status, payload = type(self).reply
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # silence test output
        pass


@pytest.fixture
def server():
    _Handler.requests = []
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1", _Handler
    httpd.shutdown()


def openai_config(base_url, **opts):
    return config(backend="openai_compatible", backend_options={"base_url": base_url, **opts})


def test_openai_compatible_round_trip(server, monkeypatch):
    base_url, handler = server
    handler.reply = (
        200,
        {
            "model": "served-model",
            "choices": [{"message": {"content": "Answer."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        },
    )
    monkeypatch.setenv("TEST_LSB_KEY", "secret-value")
    adapter = create_adapter(openai_config(base_url, api_key_env="TEST_LSB_KEY"))
    result = adapter.generate(MSGS, GenerationParams(seed=7, stop=["\n\n"], max_new_tokens=20))

    assert result.text == "Answer."
    assert (result.prompt_tokens, result.completion_tokens) == (5, 2)
    assert result.served_model_id == "served-model"
    sent = handler.requests[0]
    assert sent["path"] == "/v1/chat/completions"
    assert sent["auth"] == "Bearer secret-value"
    assert sent["body"]["seed"] == 7
    assert sent["body"]["max_tokens"] == 20
    assert sent["body"]["stop"] == ["\n\n"]
    assert "secret-value" not in json.dumps(adapter.runtime_info())


def test_openai_compatible_http_error(server):
    base_url, handler = server
    handler.reply = (500, {"error": "boom"})
    adapter = create_adapter(openai_config(base_url))
    with pytest.raises(AdapterError, match="HTTP 500"):
        adapter.generate(MSGS, GenerationParams())


def test_openai_compatible_bad_shape(server):
    base_url, handler = server
    handler.reply = (200, {"choices": []})
    with pytest.raises(AdapterError, match="unexpected response shape"):
        create_adapter(openai_config(base_url)).generate(MSGS, GenerationParams())


def test_openai_compatible_unreachable():
    adapter = create_adapter(openai_config("http://127.0.0.1:9", timeout_s=2))
    with pytest.raises(AdapterError, match="cannot reach"):
        adapter.generate(MSGS, GenerationParams())


def test_openai_compatible_missing_key_env(monkeypatch):
    monkeypatch.delenv("TEST_LSB_MISSING", raising=False)
    with pytest.raises(AdapterError, match="TEST_LSB_MISSING"):
        create_adapter(openai_config("http://x", api_key_env="TEST_LSB_MISSING"))


# ------------------------------------------------- heavy backends via stubs


def _block_import(monkeypatch, *names):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.split(".")[0] in names:
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)


def test_transformers_missing_dependency_message(monkeypatch):
    _block_import(monkeypatch, "torch", "transformers")
    with pytest.raises(AdapterError, match=r"pip install -e '\.\[hf\]'"):
        create_adapter(config(backend="transformers", model_revision=SHA))


def test_vllm_missing_dependency_message(monkeypatch):
    _block_import(monkeypatch, "vllm")
    with pytest.raises(AdapterError, match=r"pip install -e '\.\[vllm\]'"):
        create_adapter(config(backend="vllm", model_revision=SHA))


class _Tensor:
    """Minimal stand-in for a 2-D token tensor."""

    def __init__(self, rows):
        self.rows = rows
        self.shape = (len(rows), len(rows[0]))

    def to(self, _device):
        return self

    def __getitem__(self, idx):
        row = self.rows[idx]
        return _Row(row)


class _Row(list):
    @property
    def shape(self):
        return (len(self),)

    def __getitem__(self, idx):
        result = list.__getitem__(self, idx)
        return _Row(result) if isinstance(idx, slice) else result


class _StubTorch:
    seeds: ClassVar[list] = []

    class cuda:
        @staticmethod
        def is_available():
            return False

    @classmethod
    def manual_seed(cls, seed):
        cls.seeds.append(seed)

    @staticmethod
    def no_grad():
        import contextlib

        return contextlib.nullcontext()


class _StubTokenizer:
    def apply_chat_template(self, messages, add_generation_prompt, return_tensors):
        assert add_generation_prompt and return_tensors == "pt"
        return _Tensor([[1, 2, 3]])

    def decode(self, tokens, skip_special_tokens):
        return " ".join(f"tok{t}" for t in tokens)


class _StubModel:
    device = "cpu"
    calls: ClassVar[list] = []

    def generate(self, input_ids, **kwargs):
        type(self).calls.append(kwargs)
        return _Tensor([[*input_ids.rows[0], 7, 8]])


class _StubTransformersAdapter(TransformersAdapter):
    def _load_components(self):
        return _StubTokenizer(), _StubModel(), _StubTorch


def test_transformers_generation_logic():
    _StubModel.calls, _StubTorch.seeds = [], []
    adapter = _StubTransformersAdapter(config(backend="transformers", model_revision=SHA))
    greedy = adapter.generate(MSGS, GenerationParams(temperature=0.0, seed=3))
    assert greedy.text == "tok7 tok8"
    assert (greedy.prompt_tokens, greedy.completion_tokens) == (3, 2)
    assert _StubModel.calls[0]["do_sample"] is False
    assert "temperature" not in _StubModel.calls[0]
    assert _StubTorch.seeds == [3]

    adapter.generate(MSGS, GenerationParams(temperature=0.7, top_p=0.9, seed=4))
    assert _StubModel.calls[1]["do_sample"] is True
    assert _StubModel.calls[1]["temperature"] == 0.7
    assert adapter.runtime_info()["backend"] == "transformers"


class _StubLLM:
    def __init__(self):
        self.calls = []

    def chat(self, messages, sampling_params, use_tqdm):
        self.calls.append((messages, sampling_params))
        completion = SimpleNamespace(text="vllm answer", finish_reason="stop", token_ids=[1, 2])
        return [SimpleNamespace(prompt_token_ids=[1, 2, 3, 4], outputs=[completion])]


class _StubVLLMAdapter(VLLMAdapter):
    def _load_engine(self):
        return _StubLLM(), lambda **kw: SimpleNamespace(**kw)


def test_vllm_generation_logic():
    adapter = _StubVLLMAdapter(config(backend="vllm", model_revision=SHA))
    result = adapter.generate(MSGS, GenerationParams(temperature=0.5, seed=9, max_new_tokens=50))
    assert result.text == "vllm answer"
    assert (result.prompt_tokens, result.completion_tokens) == (4, 2)
    _, sampling = adapter.llm.calls[0]
    assert (sampling.seed, sampling.max_tokens, sampling.temperature) == (9, 50, 0.5)
    assert sampling.stop is None


def test_mock_scripted_responses(tmp_path):
    script = tmp_path / "script.jsonl"
    script.write_text(json.dumps({"prompt_contains": "Hello", "response": "Scripted."}) + "\n")
    adapter = MockAdapter(config(backend_options={"script_path": str(script)}))
    hit = adapter.generate(MSGS, GenerationParams())
    assert hit.text == f"{SCRIPTED_PREFIX}\nScripted."
    miss = adapter.generate([{"role": "user", "content": "Other"}], GenerationParams())
    assert miss.text.startswith(MOCK_PREFIX)


def test_mock_bad_script_path(tmp_path):
    with pytest.raises(AdapterError, match="cannot load mock script"):
        MockAdapter(config(backend_options={"script_path": str(tmp_path / "missing.jsonl")}))
