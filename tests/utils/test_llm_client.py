# tests/utils/test_llm_client.py
import os
from dataclasses import replace

import utils.llm_client as llm


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON")
        return self._json_data


class FakeHTTPXClient:
    """
    A fake httpx.Client that returns a scripted sequence of responses.
    Captures post() calls for assertions.
    """
    def __init__(self, responses, timeout=None):
        self._responses = list(responses)
        self.timeout = timeout
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        self.posts.append({"url": url, "headers": headers or {}, "json": json})
        if not self._responses:
            return FakeResponse(status_code=500, text="No scripted responses")
        return self._responses.pop(0)


def patch_logger(monkeypatch, sink):
    def fake_log_err(msg):
        sink.append(str(msg))
    monkeypatch.setattr(llm.logger, "log_err", fake_log_err)


def patch_sleep_and_random(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda *_args, **_kw: None)
    monkeypatch.setattr(llm.random, "random", lambda: 0.0)


def patch_httpx_client(monkeypatch, fake_client):
    # llm.httpx.Client(timeout=...) -> fake_client instance
    monkeypatch.setattr(llm.httpx, "Client", lambda timeout=None: fake_client)


def test_extract_json_strict_dict(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)

    c = llm.LLMClient()
    out = c._extract_json_from_text('{"a": 1}', label="t")
    assert out == {"a": 1}
    assert logs == []


def test_extract_json_strict_non_dict_returns_none(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)

    c = llm.LLMClient()
    out = c._extract_json_from_text('["a", 1]', label="t")
    assert out is None


def test_extract_json_embedded_object(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)

    c = llm.LLMClient()
    out = c._extract_json_from_text("hello\n{\n  \"x\": 2\n}\nbye", label="t")
    assert out == {"x": 2}
    assert logs == []


def test_extract_json_none_logs_and_returns_none(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)

    c = llm.LLMClient()
    assert c._extract_json_from_text(None, label="t") is None
    assert any("No content to parse" in m for m in logs)


def test_extract_json_no_object_logs(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)

    c = llm.LLMClient()
    assert c._extract_json_from_text("no braces here", label="t") is None
    assert any("No JSON object found" in m for m in logs)


def test_extract_json_bad_candidate_logs(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)

    c = llm.LLMClient()
    # Has braces, but invalid JSON (single quotes)
    assert c._extract_json_from_text("{'a': 1}", label="t") is None
    assert any("JSON extraction parse failed" in m for m in logs)


def test_build_default_client_from_env(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_S", "12.5")
    monkeypatch.setenv("LLM_MAX_ATTEMPTS", "7")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.9")
    monkeypatch.setenv("LLM_NO_TEMPERATURE_MODELS", "gpt-5-mini,foo, bar  ")

    c = llm.build_default_client_from_env()
    assert c.timeout_s == 12.5
    assert c.max_attempts == 7
    assert c.temperature == 0.9
    assert c.no_temperature_models == {"gpt-5-mini", "foo", "bar"}


def test_call_omits_temperature_for_no_temperature_model(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    # Response returns valid JSON dict content
    resp = FakeResponse(
        status_code=200,
        json_data={"choices": [{"message": {"content": '{"ok": true}'}}]},
        text="",
    )
    fake_http = FakeHTTPXClient([resp])
    patch_httpx_client(monkeypatch, fake_http)

    provider = llm.LLMProvider(label="p", base_url="http://x/v1", model="gpt-5-mini", api_key=None)
    c = llm.LLMClient(max_attempts=1, temperature=0.7, no_temperature_models={"gpt-5-mini"})

    out = c._call_chat_completions_json(provider, [{"role": "user", "content": "hi"}])
    assert out == {"ok": True}

    # Ensure request payload did NOT include temperature
    sent = fake_http.posts[0]["json"]
    assert "temperature" not in sent


def test_call_includes_temperature_for_other_models(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    resp = FakeResponse(
        status_code=200,
        json_data={"choices": [{"message": {"content": '{"ok": true}'}}]},
    )
    fake_http = FakeHTTPXClient([resp])
    patch_httpx_client(monkeypatch, fake_http)

    provider = llm.LLMProvider(label="p", base_url="http://x/v1", model="some-model", api_key=None)
    c = llm.LLMClient(max_attempts=1, temperature=0.33, no_temperature_models={"gpt-5-mini"})

    out = c._call_chat_completions_json(provider, [{"role": "user", "content": "hi"}])
    assert out == {"ok": True}

    sent = fake_http.posts[0]["json"]
    assert sent["temperature"] == 0.33


def test_retry_then_success(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    # 1st attempt: HTTP 500, 2nd attempt: success with JSON
    r1 = FakeResponse(status_code=500, text="nope")
    r2 = FakeResponse(
        status_code=200,
        json_data={"choices": [{"message": {"content": '{"a": 1}'}}]},
        text="",
    )
    fake_http = FakeHTTPXClient([r1, r2])
    patch_httpx_client(monkeypatch, fake_http)

    provider = llm.LLMProvider(label="p", base_url="http://x/v1", model="m", api_key=None)
    c = llm.LLMClient(max_attempts=3)

    out = c._call_chat_completions_json(provider, [{"role": "user", "content": "hi"}])
    assert out == {"a": 1}

    # We should have posted twice (failed once, then succeeded)
    assert len(fake_http.posts) == 2
    assert any("HTTP 500 attempt 1" in m for m in logs)


def test_chat_json_tries_providers_in_order(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    # Provider A: always 500 and exhaust (max_attempts=1)
    # Provider B: success
    r_fail = FakeResponse(status_code=500, text="nope")
    r_ok = FakeResponse(
        status_code=200,
        json_data={"choices": [{"message": {"content": '{"win": true}'}}]},
    )

    # We need two different fake clients, one per provider call.
    fake_a = FakeHTTPXClient([r_fail])
    fake_b = FakeHTTPXClient([r_ok])

    # Patch httpx.Client to return fake_a first time, fake_b second time
    clients = [fake_a, fake_b]
    monkeypatch.setattr(llm.httpx, "Client", lambda timeout=None: clients.pop(0))

    a = llm.LLMProvider(label="a", base_url="http://a/v1", model="m", api_key=None)
    b = llm.LLMProvider(label="b", base_url="http://b/v1", model="m", api_key=None)

    c = llm.LLMClient(max_attempts=1)
    out = c.chat_json([a, b], [{"role": "user", "content": "hi"}])
    assert out == {"win": True}

def test_chat_json_logs_provider_level_exception_and_raises(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)

    class BoomClient(llm.LLMClient):
        def _call_chat_completions_json(self, provider, messages):
            raise RuntimeError("boom")

    c = BoomClient(max_attempts=1)

    p = llm.LLMProvider(label="p", base_url="http://x/v1", model="m")
    try:
        c.chat_json([p], [{"role": "user", "content": "hi"}])
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "All LLM providers failed" in str(e)

    assert any("Provider-level exception" in m for m in logs)

def test_call_handles_response_json_failure(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    # status 200 but .json() raises => should retry then exhaust -> None
    bad = FakeResponse(status_code=200, json_data=None, text="not json")
    fake_http = FakeHTTPXClient([bad])
    patch_httpx_client(monkeypatch, fake_http)

    provider = llm.LLMProvider(label="p", base_url="http://x/v1", model="m")
    c = llm.LLMClient(max_attempts=1)

    out = c._call_chat_completions_json(provider, [{"role": "user", "content": "hi"}])
    assert out is None
    assert any("Exception attempt 1" in m for m in logs)

def test_call_sets_authorization_header_when_api_key_present(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    resp = FakeResponse(
        status_code=200,
        json_data={"choices": [{"message": {"content": '{"ok": true}'}}]},
    )
    fake_http = FakeHTTPXClient([resp])
    patch_httpx_client(monkeypatch, fake_http)

    provider = llm.LLMProvider(label="p", base_url="http://x/v1", model="m", api_key="sk-123")
    c = llm.LLMClient(max_attempts=1)

    out = c._call_chat_completions_json(provider, [{"role": "user", "content": "hi"}])
    assert out == {"ok": True}

    sent_headers = fake_http.posts[0]["headers"]
    assert sent_headers["Authorization"] == "Bearer sk-123"


def test_call_sets_last_err_json_parse_failed_when_extraction_returns_none(monkeypatch):
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    # HTTP 200, JSON is present, but content has no JSON object -> _extract_json returns None.
    resp = FakeResponse(
        status_code=200,
        json_data={"choices": [{"message": {"content": "no json here"}}]},
        text="",
    )
    fake_http = FakeHTTPXClient([resp])
    patch_httpx_client(monkeypatch, fake_http)

    provider = llm.LLMProvider(label="p", base_url="http://x/v1", model="m")
    c = llm.LLMClient(max_attempts=1)

    out = c._call_chat_completions_json(provider, [{"role": "user", "content": "hi"}])
    assert out is None

    # This proves we hit the "JSON parse failed" branch and then exhausted.
    assert any("Exhausted attempts. Last error: JSON parse failed" in m for m in logs)
