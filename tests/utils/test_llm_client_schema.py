# tests/utils/test_llm_client_schema.py
# Tests for schema validation, retry on missing fields, and default parameters.

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


def test_is_required_fields_missing_catches_affordance_only():
    """Model returns {'weight': 5, 'immovable': False} — classic bug response."""
    c = llm.LLMClient()
    bad_response = {"weight": 5, "immovable": False}
    assert c._is_required_fields_missing(bad_response, []) is True


def test_is_required_fields_missing_catches_missing_key():
    """Catch a response that has 'desc' but no 'key'."""
    c = llm.LLMClient()
    messages = [{"role": "system", "content": "key is REQUIRED: ..."}]
    bad_response = {"desc": "A glass", "shortdesc": "a glass"}
    assert c._is_required_fields_missing(bad_response, messages) is True


def test_is_required_fields_missing_passes_complete():
    """A response with all required fields should pass."""
    c = llm.LLMClient()
    messages = [{"role": "system", "content": "key is REQUIRED: ..."}]
    good_response = {
        "key": "Glass of Soda",
        "shortdesc": "a tall glass of soda",
        "desc": "A tall glass filled with clear soda.",
        "affordance": {"weight": 2, "immovable": False},
    }
    assert c._is_required_fields_missing(good_response, messages) is False


def test_is_required_fields_missing_catches_missing_intent():
    """Intent router response missing 'intent' field."""
    c = llm.LLMClient()
    messages = [{"role": "system", "content": "\"intent\": str, \"normalized\": str"}]
    bad_response = {"normalized": "create something", "question": "what?"}
    assert c._is_required_fields_missing(bad_response, messages) is True


def test_retry_on_missing_fields_then_success(monkeypatch):
    """Model returns partial JSON on attempt 1, full JSON on attempt 2."""
    from tests.utils.test_llm_client import patch_logger, patch_sleep_and_random
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    bad_content = '{"weight": 5, "immovable": false}'
    bad = FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": bad_content}}]})

    good_content = '{"key": "Brass Telescope", "shortdesc": "a brass telescope", "desc": "A brass telescope on a table."}'
    good = FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": good_content}}]})

    fake_http = FakeHTTPXClient([bad, good])
    def fake_client(timeout=None):
        return fake_http
    monkeypatch.setattr(llm.httpx, "Client", fake_client)

    provider = llm.LLMProvider(label="p", base_url="http://x/v1", model="m", api_key=None)
    c = llm.LLMClient(max_attempts=2)

    out = c._call_chat_completions_json(provider, [])
    assert out is not None
    assert "key" in out
    assert "desc" in out
    # Should have made 2 HTTP calls
    assert len(fake_http.posts) == 2


def test_retry_on_missing_fields_exhausts_and_returns_none(monkeypatch):
    """If both attempts return incomplete JSON, it should exhaust."""
    from tests.utils.test_llm_client import patch_logger, patch_sleep_and_random
    logs = []
    patch_logger(monkeypatch, logs)
    patch_sleep_and_random(monkeypatch)

    bad_content = '{"weight": 5, "immovable": false}'
    bad1 = FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": bad_content}}]})
    bad_content2 = '{"weight": 3, "immovable": true}'
    bad2 = FakeResponse(status_code=200, json_data={"choices": [{"message": {"content": bad_content2}}]})

    fake_http = FakeHTTPXClient([bad1, bad2])
    def fake_client(timeout=None):
        return fake_http
    monkeypatch.setattr(llm.httpx, "Client", fake_client)

    provider = llm.LLMProvider(label="p", base_url="http://x/v1", model="m", api_key=None)
    c = llm.LLMClient(max_attempts=2)

    out = c._call_chat_completions_json(provider, [])
    assert out is None
    # Both attempts were used
    assert len(fake_http.posts) == 2


def test_default_max_attempts_is_2():
    c = llm.LLMClient()
    assert c.max_attempts == 2


def test_default_temperature_is_0_3():
    c = llm.LLMClient()
    assert c.temperature == 0.6
