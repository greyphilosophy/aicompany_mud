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
        client = LLMClient(timeout_s=30, max_attempts=4)
        result = client.chat_json([local_provider, openai_provider], messages)
    """

    def __init__(
        self,
        timeout_s: float = 30.0,
        max_attempts: int = 4,
        temperature: float = 0.4,
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

    def _extract_json_from_text(self, text: Any, label: str) -> Optional[JsonDict]:
        """
        Try strict json.loads, then extract first {...} block.
        """
        if text is None:
            logger.log_err(f"[LLM:{label}] No content to parse.")
            return None

        t = str(text).strip()

        # strict
        try:
            obj = json.loads(t)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

        # extract first JSON object
        m = re.search(r"\{.*\}", t, flags=re.DOTALL)
        if not m:
            logger.log_err(f"[LLM:{label}] No JSON object found. Raw (first 800): {t[:800]!r}")
            return None

        candidate = m.group(0)
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else None
        except Exception as exc:
            logger.log_err(
                f"[LLM:{label}] JSON extraction parse failed: {exc!r}. "
                f"Candidate (first 800): {candidate[:800]!r}. Raw (first 800): {t[:800]!r}"
            )
            return None


def build_default_client_from_env() -> LLMClient:
    """
    Build a client with env-configurable knobs.
    """
    timeout_s = float(os.getenv("LLM_TIMEOUT_S", "30"))
    max_attempts = int(os.getenv("LLM_MAX_ATTEMPTS", "4"))
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
    # Comma-separated model IDs that should omit temperature
    raw = os.getenv("LLM_NO_TEMPERATURE_MODELS", "gpt-5-mini")
    no_temp = {m.strip() for m in raw.split(",") if m.strip()}
    return LLMClient(timeout_s=timeout_s, max_attempts=max_attempts, temperature=temperature, no_temperature_models=no_temp)
