"""Shared helpers for image media paths and public URLs.

These helpers keep the generated-image directory and public URL base in one
place so the MUD, tests, and gateway-facing code can agree on the same
configuration without hard-coding a personal dev path or hostname.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_GENERATED_MEDIA_DIR = _REPO_ROOT / "server" / ".static" / "media" / "generated"
_DEFAULT_MEDIA_URL_BASE = "/media/generated"


def _settings_value(name: str) -> str | None:
    """Return a game setting value if the settings module can be imported."""
    try:
        from server.conf import settings as game_settings
    except Exception:
        return None

    value = getattr(game_settings, name, None)
    if value is None:
        return None
    return str(value)


def get_generated_media_dir() -> str:
    """Return the directory where generated image files are stored."""
    return (
        os.getenv("MUD_MEDIA_DIR")
        or _settings_value("MUD_MEDIA_DIR")
        or str(_DEFAULT_GENERATED_MEDIA_DIR)
    )


def get_media_url_base() -> str:
    """Return the public media URL base used for generated images."""
    base = os.getenv("MEDIA_URL_BASE") or _settings_value("MEDIA_URL_BASE")
    return (base or _DEFAULT_MEDIA_URL_BASE).rstrip("/")


def get_generated_image_filename(source: str) -> str:
    """Derive a stable filename for a generated-image source string."""
    if source.startswith("data:image/"):
        digest = hashlib.md5(source.encode("utf-8")).hexdigest()[:12]
        return f"img_{digest}.png"

    if source.startswith(("http://", "https://")):
        name = Path(urlparse(source).path).name
        return name or "generated.png"

    name = Path(source).name
    return name or "generated.png"


def join_media_url_base(filename: str) -> str:
    """Join a filename to the configured public media URL base."""
    base = get_media_url_base()
    filename = filename.lstrip("/")

    if base.startswith(("http://", "https://")):
        return f"{base}/{filename}"

    if not base.startswith("/"):
        base = f"/{base}"
    return f"{base}/{filename}"


def build_generated_image_url(source: str) -> str:
    """Normalize a generated-image reference into a public URL/path.

    - Absolute HTTP(S) URLs are preserved.
    - `/media/...` paths are preserved.
    - Absolute filesystem paths are rewritten to the configured media base.
    - Data URLs are converted into deterministic generated filenames.
    - Bare filenames are joined to the configured media base.
    """
    if not source:
        return ""

    if source.startswith("data:image/"):
        return join_media_url_base(get_generated_image_filename(source))

    if source.startswith(("http://", "https://")):
        return source

    if source.startswith("/media/"):
        return source

    if source.startswith("media/"):
        return f"/{source}"

    if Path(source).is_absolute():
        return join_media_url_base(Path(source).name)

    return join_media_url_base(get_generated_image_filename(source))


def get_generated_image_path(source: str) -> Path:
    """Map a generated-image reference to the local filesystem path."""
    return Path(get_generated_media_dir()) / get_generated_image_filename(source)
