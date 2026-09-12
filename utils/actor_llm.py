"""Shared local-first provider selection for Brain and legacy speech."""

import os
from utils.llm_client import LLMProvider


def get_actor_providers():
    try:
        from django.conf import settings as dj_settings
    except Exception:
        dj_settings = None

    base_url = os.getenv("LOCAL_LLM_BASE_URL")
    if not base_url and dj_settings is not None:
        base_url = getattr(dj_settings, "LOCAL_BASE_URL", None)
    if not base_url:
        base_url = "http://127.0.0.1:1234/v1"

    model = os.getenv("LOCAL_LLM_MODEL")
    if not model and dj_settings is not None:
        model = getattr(dj_settings, "LOCAL_MODEL", None)
    if not model:
        model = "gpt-oss-120b"

    providers = [LLMProvider(label="LOCAL", base_url=base_url, model=model)]

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key and dj_settings is not None:
        api_key = getattr(dj_settings, "OPENAI_API_KEY", None)
    if api_key:
        openai_base_url = os.getenv("OPENAI_BASE_URL")
        openai_model = os.getenv("OPENAI_MODEL")
        if dj_settings is not None:
            openai_base_url = openai_base_url or getattr(
                dj_settings, "OPENAI_BASE_URL", None
            )
            openai_model = openai_model or getattr(dj_settings, "OPENAI_MODEL", None)
        providers.append(
            LLMProvider(
                label="OPENAI",
                base_url=openai_base_url or "https://api.openai.com/v1",
                model=openai_model or "gpt-5-mini",
                api_key=api_key,
            )
        )
    return providers
