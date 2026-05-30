"""
LLM client utilities for Evennia.

Goals:
- Thread-safe: these functions do not touch Evennia/Django objects.
- OpenAI-compatible: works with LM Studio /v1 and OpenAI /v1 endpoints.
- Robust: retries, backoff, JSON extraction, model-parameter quirks.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

# Evennia logger is safe to import; we only log strings.
from evennia.utils import logger


JsonDict = Dict[str, Any]
Messages = List[Dict[str, str]]


@dataclass(frozen=True)
class LLMProvider:
    label: str
    base_url: str
    model: str
    api_key: Optional[str] = None


class LLMClient:
    """
    Small reusable client for OpenAI-compatible /chat/completions.

    Usage:
        client = LLMClient(timeout_s=30, max_attempts=2)
        result = client.chat_json([local_provider, openai_provider], messages)
    """

    def __init__(
        self,
        timeout_s: float = 30.0,
        max_attempts: int = 2,
        temperature: float = 0.6,
        no_temperature_models: Optional[set[str]] = None,
    ):
        self.timeout_s = float(timeout_s)
        self.max_attempts = int(max_attempts)
        self.temperature = float(temperature)
        self.no_temperature_models = no_temperature_models or {"gpt-5-mini"}

    def chat_json(self, providers: List[LLMProvider], messages: Messages) -> JsonDict:
        """
        Try providers in order; return first successful JSON object.
        Raises RuntimeError if all fail.
        """
        logger.log_info(
            "[LLM] Provider order: "
            + ", ".join(
                f"{p.label}(model={p.model!r}, base_url={p.base_url!r}, api_key={'set' if p.api_key else 'unset'})"
                for p in providers
            )
        )

        last_exc: Optional[Exception] = None
        for provider in providers:
            try:
                out = self._call_chat_completions_json(provider, messages)
                if out is None:
                    raise RuntimeError("Provider returned no JSON (None)")
                return out
            except Exception as exc:
                last_exc = exc
                logger.log_err(
                    f"[LLM:{provider.label}] Provider-level exception: {exc!r}\n{traceback.format_exc()}"
                )

        raise RuntimeError(f"All LLM providers failed. Last exception: {last_exc!r}")

    # -------------------------
    # Internal
    # -------------------------

    def _call_chat_completions_json(self, provider: LLMProvider, messages: Messages) -> Optional[JsonDict]:
        """
        Returns parsed JSON dict or None on exhaustion.
        """
        url = f"{provider.base_url.rstrip('/')}/chat/completions"

        headers = {"Content-Type": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"

        payload: JsonDict = {
            "model": provider.model,
            "messages": messages,
            "max_tokens": 2048,
        }

        # Temperature quirks: omit if model rejects non-default temperature.
        if provider.model not in self.no_temperature_models:
            payload["temperature"] = self.temperature

        last_err = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                with httpx.Client(timeout=self.timeout_s) as client:
                    r = client.post(url, headers=headers, json=payload)

                if r.status_code >= 400:
                    body_snip = (r.text or "")[:1200]
                    logger.log_err(
                        f"[LLM:{provider.label}] HTTP {r.status_code} attempt {attempt}. "
                        f"Model={provider.model!r} Temp={'(omitted)' if 'temperature' not in payload else payload.get('temperature')!r}. "
                        f"Body: {body_snip!r}"
                    )
                    last_err = f"HTTP {r.status_code}"
                else:
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = self._extract_json_from_text(content, label=provider.label)
                    if parsed is not None:
                        # Validate that responses to prop_create and prop_edit prompts
                        # contain the required schema fields. Retry on partial responses.
                        if self._is_required_fields_missing(parsed, messages):
                            logger.log_warn(
                                f"[LLM:{provider.label}] Response missing required fields (attempt {attempt}/{self.max_attempts}): {parsed}"
                            )
                            last_err = "Missing required fields"
                            continue
                        return parsed
                    last_err = "JSON parse failed"

            except Exception as exc:
                last_err = repr(exc)
                logger.log_err(
                    f"[LLM:{provider.label}] Exception attempt {attempt}: {exc!r}\n{traceback.format_exc()}"
                )

            # small backoff + jitter
            time.sleep(0.25 + random.random() * 0.5 + attempt * 0.2)

        logger.log_err(f"[LLM:{provider.label}] Exhausted attempts. Last error: {last_err}")
        return None

    def _strip_thinking_tags(self, text: str) -> str:
        """Strip <thinking>...</thinking> blocks from reasoning-model outputs (Qwen3, etc.)."""
        return re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)

    def _is_required_fields_missing(self, response: JsonDict, messages: Messages) -> bool:
        """Check if a response is missing required schema fields based on the prompt.
        Returns True if the response looks incomplete (e.g., only affordance fields)."""
        # Check if any message contains prop_create or prop_edit prompts
        is_prop_prompt = False
        is_intent_prompt = False
        for msg in messages:
            content = msg.get("content", "")
            if "key is REQUIRED" in content:
                is_prop_prompt = True
            if "intent_router" in content or '"intent"' in content:
                is_intent_prompt = True

        # Prop create/edit requires key, shortdesc, and desc
        if is_prop_prompt:
            missing = {"key", "desc", "shortdesc"} - set(response.keys())
            if missing:
                return True

        # Intent router requires 'intent'
        if is_intent_prompt:
            if "intent" not in response:
                return True

        # Fallback: if response only has affordance-like fields, it's incomplete
        if set(response.keys()) <= {"weight", "immovable"} and "key" not in response:
            return True

        return False

    def _extract_json_from_text(self, text: Any, label: str) -> Optional[JsonDict]:
        if text is None:
            return None

        t = str(text).strip()

        # Strip <thinking>...</thinking> blocks from reasoning-model outputs
        t = self._strip_thinking_tags(t)

        # Try parsing the entire text as JSON first (handles nested objects)
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        # Try greedy match on the whole text for nested JSON
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass

        # If the full greedy parse returned a dict with a nested object key,
        # unpack one level (e.g., {"object": {...}} or {"result": {...}})
        # and return the innermost dict that has the schema fields.
        candidates: list[tuple[int, JsonDict]] = []
        for match in re.finditer(r"\{[^{}]*\}", t):
            try:
                obj = json.loads(match.group(0))
                if isinstance(obj, dict):
                    candidates.append((match.start(), obj))
            except Exception:
                continue

        if candidates:
            return candidates[-1][1]

        # Last resort: try to find JSON-like patterns in the text
        for pattern in [r'"desc"\s*:\s*"([^"]+)"', r'"key"\s*:\s*"([^"]+)":', r'"shortdesc"\s*:\s*"([^"]+)"']:
            m = re.search(pattern, t)
            if m:
                break

        logger.log_err(f"[LLM:{label}] No JSON object found. Raw (first 800): {t[:800]!r}")
        return None


def build_default_client_from_env() -> LLMClient:
    """
    Build a client with env-configurable knobs.
    """
    timeout_s = float(os.getenv("LLM_TIMEOUT_S", "120"))
    max_attempts = int(os.getenv("LLM_MAX_ATTEMPTS", "2"))
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.6"))
    # Comma-separated model IDs that should omit temperature
    raw = os.getenv("LLM_NO_TEMPERATURE_MODELS", "gpt-5-mini")
    no_temp = {m.strip() for m in raw.split(",") if m.strip()}
    return LLMClient(timeout_s=timeout_s, max_attempts=max_attempts, temperature=temperature, no_temperature_models=no_temp)
