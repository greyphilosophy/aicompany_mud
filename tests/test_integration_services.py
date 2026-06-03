"""
Integration tests for external service connectivity.

Tests that the MUD can reach:
- vLLM (LLM provider)
- FLUX.2 (image generation backend on spark-c8ad)

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
    config = getattr(settings, "EVENNIA_AI_IMAGE_GENERATOR_CONFIG", None)
    assert config is not None, "EVENNIA_AI_IMAGE_GENERATOR_CONFIG not set in settings"
    assert config.get("backend", {}).get("backend") == "flux2_rest"


class TestLLMConnectivity:
    """Direct connectivity to the LLM provider."""

    def test_llm_health(self):
        base = getattr(settings, "LOCAL_BASE_URL", "")
        models_url = base.rstrip("/") + "/models"
        resp = httpx.get(models_url, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0

    def test_chat_completion(self, local_provider):
        providers = [local_provider]
        client = LLMClient(timeout_s=60, max_attempts=2)
        messages = [
            {"role": "system", "content": 'Return JSON: {"status":"ok"}'},
            {"role": "user", "content": "Test ping"},
        ]
        result = client.chat_json(providers, messages)
        assert "status" in result
        assert result["status"] == "ok"


class TestFlux2Connectivity:
    """Connectivity to FLUX.2 REST server on spark-c8ad."""

    def test_flux2_health_endpoint(self):
        resp = httpx.get("http://169.254.209.73:8190/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "loaded"
