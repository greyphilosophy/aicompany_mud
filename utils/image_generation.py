# utils/image_generation.py
"""
Lightweight helpers for triggering FLUX.2 image generation from
SmartRoom and prop objects — no Evennia typeclass coupling required.

Uses the evennia_ai_image_generator package (must be installed).
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

# Lazy import so the MUD runs even when the package is absent.
_backend_cache = None


def _get_backend() -> Any | None:
    """Return a configured FLUX.2 REST backend (or ``None`` if missing)."""
    global _backend_cache
    if _backend_cache is not None:
        return _backend_cache

    try:
        from evennia_ai_image_generator.backend.flux2_rest_backend import Flux2RestBackend

        backend = Flux2RestBackend(
            server_url=os.getenv("FLUX2_REST_URL", "http://127.0.0.1:8190"),
            output_dir="generated",
            media_url_base=os.getenv(
                "MEDIA_URL_BASE",
                "https://game.test/media/generated",
            ),
            timeout_s=120.0,
            default_steps=int(os.getenv("FLUX2_REST_STEPS", "28")),
            default_guidance_scale=float(os.getenv("FLUX2_REST_GUIDANCE", "7.0")),
            default_seed=int(os.getenv("FLUX2_REST_SEED", "42")),
            default_width=int(os.getenv("FLUX2_REST_WIDTH", "1024")),
            default_height=int(os.getenv("FLUX2_REST_HEIGHT", "1024")),
        )
        _backend_cache = backend
        return backend
    except ImportError:
        _backend_cache = None
        return None


def _generate_image(backend, subject_type: str, subject_key: str, prompt: str) -> str | None:
    """Shared image generation logic."""
    from evennia_ai_image_generator.backend.base import ImageGenerationRequest

    result = backend.generate(
        ImageGenerationRequest(
            subject_type=subject_type,
            subject_key=subject_key,
            prompt=prompt,
            negative_prompt="blurry, low-res, cartoon, text, watermark",
            mode="txt2img",
            width=1024,
            height=1024,
        )
    )
    return result.image_url


def generate_room_image(room_description: str) -> str | None:
    """Generate a room image from a text description.

    Returns the image URL on success, or ``None`` on failure/silence.
    """
    backend = _get_backend()
    if not backend:
        return None

    try:
        digest = hashlib.sha256(room_description.encode("utf-8")).hexdigest()[:12]
        subject_key = f"room_desc_{digest}"
        return _generate_image(backend, "room", subject_key, room_description)
    except Exception:
        return None


def generate_object_image(
    object_key: str,
    object_desc: str,
    shortdesc: str = "",
) -> str | None:
    """Generate an image for a scene object.

    Returns the image URL on success, or ``None`` on failure/silence.
    """
    backend = _get_backend()
    if not backend:
        return None

    try:
        prompt = shortdesc or object_key or object_desc
        return _generate_image(backend, "object", object_key, prompt)
    except Exception:
        return None
