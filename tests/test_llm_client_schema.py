# tests/test_llm_client_schema.py
# Tests for LLMClient JSON extraction and schema validation behavior.

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

import django
django.setup()

import pytest
import utils.llm_client as llm


class TestLLMClientDefaults:
    """Verify LLMClient default parameter values."""

    def test_default_max_attempts_is_2(self):
        c = llm.LLMClient()
        assert c.max_attempts == 2

    def test_default_temperature_is_0_6(self):
        c = llm.LLMClient()
        assert c.temperature == 0.6

    def test_default_timeout_is_30(self):
        c = llm.LLMClient()
        assert c.timeout_s == 30.0


class TestLLMClientJSONExtraction:
    """Test that LLMClient correctly extracts JSON from model responses."""

    def test_extract_json_from_clean_dict(self):
        c = llm.LLMClient()
        result = c._extract_json_from_text('{"key": "Telescope", "desc": "A brass telescope"}', label="test")
        assert result is not None
        assert result["key"] == "Telescope"

    def test_extract_json_from_text_with_wrapping(self):
        """Extract JSON embedded in surrounding text."""
        c = llm.LLMClient()
        result = c._extract_json_from_text("Here is the JSON:\n{\"key\": \"Candle\"}\nEnd.", label="test")
        assert result is not None
        assert result["key"] == "Candle"

    def test_extract_json_returns_none_for_array(self):
        c = llm.LLMClient()
        result = c._extract_json_from_text('[1, 2, 3]', label="test")
        assert result is None

    def test_extract_json_returns_none_for_plain_text(self):
        c = llm.LLMClient()
        result = c._extract_json_from_text("just plain text", label="test")
        assert result is None

    def test_extract_json_handles_thinking_tags(self):
        """Strip <thinking> tags before JSON extraction."""
        c = llm.LLMClient()
        text = "<thinking>Let's see...</thinking>\n{\"key\": \"Rock\", \"desc\": \"a stone\"}"
        result = c._extract_json_from_text(text, label="test")
        assert result is not None
        assert result["key"] == "Rock"


class TestLLMClientSchemaBehavior:
    """Verify schema validation behavior at the extraction layer."""

    def test_affordance_only_response_has_no_required_fields(self):
        """A model returning only affordance fields is missing key/desc."""
        c = llm.LLMClient()
        text = '{"weight": 5, "immovable": false}'
        result = c._extract_json_from_text(text, label="test")
        assert result is not None
        assert "key" not in result
        assert "desc" not in result
        # The caller checks for required fields — LLMClient just extracts.

    def test_complete_response_has_all_fields(self):
        """A well-formed response passes field checks."""
        c = llm.LLMClient()
        text = '{"key": "Telescope", "shortdesc": "a brass telescope", "desc": "A brass telescope on a table."}'
        result = c._extract_json_from_text(text, label="test")
        assert result is not None
        assert "key" in result
        assert "desc" in result
        assert "shortdesc" in result


class TestBuildDefaultClient:
    """Test build_default_client_from_env."""

    def test_build_default_client_with_env_vars(self, monkeypatch):
        monkeypatch.setenv("LLM_TIMEOUT_S", "60")
        monkeypatch.setenv("LLM_MAX_ATTEMPTS", "3")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.8")
        monkeypatch.setenv("LLM_NO_TEMPERATURE_MODELS", "gpt-5-mini")

        c = llm.build_default_client_from_env()
        assert c.timeout_s == 60.0
        assert c.max_attempts == 3
        assert c.temperature == 0.8
