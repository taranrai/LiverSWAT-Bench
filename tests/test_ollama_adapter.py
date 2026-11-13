"""Native Ollama adapter, tested against a local stub server (no Ollama, no download)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pytest

from liverswat_bench.models import AdapterError, GenerationParams, ModelConfig, create_adapter
from liverswat_bench.models.ollama import OllamaAdapter

DIGEST = "a" * 64


class _Ollama(BaseHTTPRequestHandler):
    chats: ClassVar[list] = []
    chat_reply: ClassVar[dict] = {}
    models: ClassVar[list] = [
        {"name": "test:1b", "digest": DIGEST, "details": {"quantization_level": "Q4_K_M"}}
    ]

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send(200, {"models": type(self).models})
        elif self.path == "/api/version":
            self._send(200, {"version": "0.0-test"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).chats.append(body)
        code, payload = type(self).chat_reply
        self._send(code, payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def ollama():
    _Ollama.chats = []
    _Ollama.chat_reply = (
        200,
        {"model": "test:1b", "message": {"role": "assistant", "content": "Answer."},
         "done_reason": "stop", "prompt_eval_count": 12, "eval_count": 3,
         "total_duration": 1000, "eval_duration": 500},
    )  # fmt: skip
    httpd = HTTPServer(("127.0.0.1", 0), _Ollama)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def config(base_url, revision=f"sha256:{DIGEST}", **opts) -> ModelConfig:
    return ModelConfig.model_validate(
        {"config_id": "t", "model_name": "test:1b", "backend": "ollama",
         "model_revision": revision, "backend_options": {"base_url": base_url, **opts}}
    )  # fmt: skip


def test_digest_is_a_pinned_revision(ollama):
    assert config(ollama).revision_pinned
    with pytest.raises(ValueError, match="model_revision"):
        ModelConfig.model_validate({"config_id": "t", "model_name": "m", "backend": "ollama"})


def test_generation_sends_explicit_options(ollama):
    adapter = create_adapter(config(ollama, num_ctx=4096, format="json"))
    assert isinstance(adapter, OllamaAdapter)
    result = adapter.generate(
        [{"role": "user", "content": "Hi"}],
        GenerationParams(temperature=0.0, seed=7, max_new_tokens=50, stop=["\n\n"]),
    )
    assert result.text == "Answer."
    assert (result.prompt_tokens, result.completion_tokens) == (12, 3)
    sent = _Ollama.chats[0]
    assert sent["options"] == {"temperature": 0.0, "top_p": 1.0, "num_predict": 50,
                               "num_ctx": 4096, "seed": 7, "stop": ["\n\n"]}  # fmt: skip
    assert sent["format"] == "json" and sent["stream"] is False
    info = adapter.runtime_info()
    assert info["installed_digest"] == f"sha256:{DIGEST}"
    assert info["ollama_version"] == "0.0-test"


def test_digest_mismatch_refuses_to_run(ollama):
    with pytest.raises(AdapterError, match="refusing to run with different weights"):
        create_adapter(config(ollama, revision=f"sha256:{'b' * 64}"))


def test_missing_model_is_reported(ollama):
    cfg = config(ollama).model_copy(update={"model_name": "absent:7b"})
    with pytest.raises(AdapterError, match="not installed"):
        OllamaAdapter(cfg)


def test_full_context_window_is_treated_as_possible_truncation(ollama):
    _Ollama.chat_reply = (200, {"message": {"content": "x"}, "prompt_eval_count": 4096})
    adapter = create_adapter(config(ollama, num_ctx=4096))
    with pytest.raises(AdapterError, match="truncated"):
        adapter.generate([{"role": "user", "content": "Hi"}], GenerationParams())


def test_http_error_and_unreachable(ollama):
    _Ollama.chat_reply = (500, {"error": "model failed to load"})
    adapter = create_adapter(config(ollama))
    with pytest.raises(AdapterError, match="HTTP 500"):
        adapter.generate([{"role": "user", "content": "Hi"}], GenerationParams())
    with pytest.raises(AdapterError, match="cannot reach Ollama"):
        create_adapter(config("http://127.0.0.1:9", timeout_s=2))
