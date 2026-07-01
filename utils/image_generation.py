# utils/image_generation.py
"""
Lightweight helpers for triggering image generation from
SmartRoom and prop objects — no Evennia typeclass coupling required.

Tries FLUX.2 REST server first; falls back to OpenAI Images API
if the FLUX.2 server is down or unreachable.

Uses the evennia_ai_image_generator package (must be installed).
"""
from __future__ import annotations

import hashlib
import httpx
import logging
import os
from typing import Any

from utils.image_paths import get_generated_media_dir, get_media_url_base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend caching (lazy init so the MUD runs even when backends are absent)
# ---------------------------------------------------------------------------

_flux2_backend: Any | None = None
_openai_backend: Any | None = None


def _get_flux2_backend() -> Any | None:
    """Return a configured FLUX.2 backend (or ``None`` if missing)."""
    global _flux2_backend
    if _flux2_backend is not None:
        return _flux2_backend

    try:
        from evennia_ai_image_generator.backend.flux2_rest_backend import Flux2RestBackend

        _flux2_backend = Flux2RestBackend(
            server_url=os.getenv("FLUX2_SERVER_URL", "http://169.254.209.73:8190"),
            media_url_base=get_media_url_base(),
            output_dir=get_generated_media_dir(),
            default_steps=8,
            timeout_s=120.0,
        )
        return _flux2_backend
    except ImportError:
        logger.info("FLUX.2 backend not found (package missing)")
        _flux2_backend = None
        return None


def _get_openai_backend() -> Any | None:
    """Return a configured OpenAI image backend (or ``None`` if missing)."""
    global _openai_backend
    if _openai_backend is not None:
        return _openai_backend

    try:
        from evennia_ai_image_generator.backend.openai_image_backend import OpenAIImageBackend

        _openai_backend = OpenAIImageBackend(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            media_url_base=get_media_url_base(),
            output_dir=get_generated_media_dir(),
        )
        return _openai_backend
    except ImportError:
        logger.info("OpenAI backend not found (package missing)")
        _openai_backend = None
        return None


def _has_any_backend() -> bool:
    """Check whether at least one backend is available."""
    return _get_flux2_backend() is not None or _get_openai_backend() is not None


def _flux2_generate_ok() -> bool:
    """Quick check: can the FLUX2 server accept a minimal generation request?

    Uses a tiny 64x64 image to avoid burning a full GPU pass. Returns
    True within ~3 seconds if the server is responsive.
    """
    backend = _get_flux2_backend()
    if not backend:
        return False
    server_url = backend.server_url
    try:
        with httpx.Client(timeout=5.0) as client:
            # POST to /generate with a minimal payload — the same endpoint
            # that Flux2RestBackend uses, so it's the real test.
            r = client.post(
                f"{server_url}/generate",
                json={"prompt": "test", "width": 64, "height": 64, "steps": 1},
            )
            return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Image generation (FLUX2 → OpenAI fallback)
# ---------------------------------------------------------------------------


def _generate_image_with_fallback(
    subject_type: str,
    subject_key: str,
    prompt: str,
) -> str | None:
    """Generate an image, trying FLUX.2 first, then OpenAI.

    Quick check: if FLUX.2 /generate doesn't respond, skip to OpenAI
    immediately instead of waiting for the full generation timeout.
    """
    flux2 = _get_flux2_backend()

    # Only try FLUX2 if the server's /generate endpoint actually responds
    if flux2 is not None and _flux2_generate_ok():
        try:
            from evennia_ai_image_generator.backend.base import ImageGenerationRequest

            result = flux2.generate(
                ImageGenerationRequest(
                    subject_type=subject_type,
                    subject_key=subject_key,
                    prompt=prompt,
                    mode="txt2img",
                    width=1536,
                    height=1024,
                )
            )
            return result.image_url
        except Exception as exc:
            logger.warning(
                "FLUX.2 backend failed for %s %s: %s",
                subject_type, subject_key, exc,
            )
            return None

    logger.info(
        "FLUX.2 not available for %s %s, falling back to OpenAI",
        subject_type, subject_key,
    )
    openai_backend = _get_openai_backend()
    if openai_backend is not None:
        try:
            from evennia_ai_image_generator.backend.base import ImageGenerationRequest

            result = openai_backend.generate(
                ImageGenerationRequest(
                    subject_type=subject_type,
                    subject_key=subject_key,
                    prompt=prompt,
                    mode="txt2img",
                    width=1024,
                    height=1024,
                )
            )
            return result.image_url
        except Exception as exc:
            logger.warning(
                "OpenAI backend failed for %s %s: %s",
                subject_type, subject_key, exc,
            )
            return None

    return None


def generate_room_image(room_description: str) -> str | None:
    """Generate a room image from a text description.

    Tries FLUX.2 REST server first (with health check); falls back to
    OpenAI if FLUX.2 is down. Returns the image URL on success, or
    ``None`` on failure/silence.
    """
    if not _has_any_backend():
        return None

    try:
        digest = hashlib.sha256(room_description.encode("utf-8")).hexdigest()[:12]
        subject_key = f"room_desc_{digest}"
        return _generate_image_with_fallback("room", subject_key, room_description)
    except Exception as exc:
        logger.warning("generate_room_image failed: %s", exc)
        return None


def generate_object_image(
    object_key: str,
    object_desc: str,
    shortdesc: str = "",
) -> str | None:
    """Generate an image for a scene object.

    Tries FLUX.2 REST server first (with health check); falls back to
    OpenAI if FLUX.2 is down. Returns the image URL on success, or
    ``None`` on failure/silence.
    """
    if not _has_any_backend():
        return None

    try:
        prompt = shortdesc or object_key or object_desc
        return _generate_image_with_fallback("object", object_key, prompt)
    except Exception as exc:
        logger.warning("generate_object_image failed: %s", exc)
        return None
