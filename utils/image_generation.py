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
    """Return a configured FLUX.2 backend (or ``None`` if missing)."""
    global _backend_cache
    if _backend_cache is not None:
        return _backend_cache

    try:
        from evennia_ai_image_generator.backend.flux2_rest_backend import Flux2RestBackend

        # Build absolute path for the generated media directory
        import os
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        game_dir = os.path.dirname(utils_dir)
        media_dir = os.path.join(game_dir, "server", ".static", "media", "generated")

        backend = Flux2RestBackend(
            server_url=os.getenv("FLUX2_SERVER_URL", "http://169.254.209.73:8190"),
            media_url_base="/media/generated",
            output_dir=media_dir,
            default_steps=28,
            timeout_s=600.0,
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
