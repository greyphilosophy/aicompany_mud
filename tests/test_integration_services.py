"""
Integration tests for external service connectivity.

Tests that the MUD can reach:
- Ollama (LLM provider)
- ComfyUI (image generation backend)

Run with:
    pytest tests/test_integration_services.py -v
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

import django
django.setup()

import httpx
import pytest

from django.conf import settings
from utils.llm_client import LLMClient, LLMProvider


@pytest.fixture
def local_provider():
    """Build LOCAL provider from settings."""
    return LLMProvider(
        label="LOCAL",
        base_url=getattr(settings, "LOCAL_BASE_URL", None),
        model=getattr(settings, "LOCAL_MODEL", None),
        api_key=None,
    )


@pytest.fixture
def llm_client():
    """Client with higher timeout for integration tests."""
    return LLMClient(timeout_s=120, max_attempts=2)


def test_local_base_url_configured():
    url = getattr(settings, "LOCAL_BASE_URL", None)
    assert url is not None, "LOCAL_BASE_URL not set in settings"
    assert "127.0.0.1" in url or "localhost" in url


def test_local_model_configured():
    model = getattr(settings, "LOCAL_MODEL", None)
    assert model is not None, "LOCAL_MODEL not set in settings"


def test_image_backend_configured():
    backend = getattr(settings, "IMAGE_BACKEND", None)
    assert backend is not None, "IMAGE_BACKEND not set in settings"
    assert backend.get("backend") == "comfyui"


class TestOllamaConnectivity:
    """Direct connectivity to Ollama."""

    def test_ollama_health(self):
        base = getattr(settings, "LOCAL_BASE_URL", "")
        # Use /v1/models endpoint (OpenAI-compatible API)
        models_url = base.rstrip("/") + "/models"
        resp = httpx.get(models_url, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0

    def test_ollama_chat_completion(self, local_provider):
        providers = [local_provider]
        client = LLMClient(timeout_s=60, max_attempts=2)
        messages = [
            {"role": "system", "content": 'Return JSON: {"status":"ok"}'},
            {"role": "user", "content": "Test ping"},
        ]
        result = client.chat_json(providers, messages)
        assert "status" in result
        assert result["status"] == "ok"


class TestComfyUIConnectivity:
    """Connectivity to ComfyUI."""

    def test_comfyui_reachable(self):
        backend = getattr(settings, "IMAGE_BACKEND", {})
        server_url = backend["options"]["server_url"]
        resp = httpx.get(server_url + "/system_stats", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "system" in data

    def test_comfyui_backend_loads(self):
        from evennia_ai_image_generator.backend.loader import load_backend
        backend = load_backend(getattr(settings, "IMAGE_BACKEND"))
        assert backend is not None


class TestComputerLLM:
    """End-to-end test of Computer class LLM calls."""

    def test_generate_prop_json(self, llm_client, local_provider):
        import json
        from utils.computer_payloads import build_prop_create_payload
        from utils.computer_prompts import prop_create_system_prompt

        payload = build_prop_create_payload(
            player="Tester",
            instruction="Create a brass telescope on a table",
            room_desc="A warm tavern.",
            anchors=[],
            recent_memory="",
        )

        messages = [
            {"role": "system", "content": prop_create_system_prompt()},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        result = llm_client.chat_json([local_provider], messages)
        assert "key" in result, f"Missing 'key' in response: {result}"
        assert "desc" in result, f"Missing 'desc' in response: {result}"

    def test_predict_intent(self, llm_client, local_provider):
        import json
        from utils.computer_payloads import build_intent_payload
        from utils.computer_prompts import intent_router_system_prompt

        payload = build_intent_payload(
            player="Tester",
            utterance="computer, make a wooden chair",
            room_desc="A warm tavern.",
            anchors=[],
            recent_memory="",
        )

        messages = [
            {"role": "system", "content": intent_router_system_prompt()},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        result = llm_client.chat_json([local_provider], messages)
        assert "intent" in result, f"Missing 'intent': {result}"
