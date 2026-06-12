"""Tests for shared image path/url helpers.

These tests keep the media path logic from regressing back to hard-coded
personal paths or hostnames.
"""

from __future__ import annotations

from pathlib import Path

from utils.image_paths import (
    build_generated_image_url,
    get_generated_image_path,
    get_generated_media_dir,
    get_media_url_base,
)


def test_defaults_use_repo_relative_generated_dir(monkeypatch):
    monkeypatch.delenv("MUD_MEDIA_DIR", raising=False)
    assert get_generated_media_dir().endswith("server/.static/media/generated")


def test_defaults_use_relative_media_url_base(monkeypatch):
    monkeypatch.delenv("MEDIA_URL_BASE", raising=False)
    assert get_media_url_base() == "/media/generated"


def test_relative_media_url_is_preserved(monkeypatch):
    monkeypatch.delenv("MEDIA_URL_BASE", raising=False)
    assert build_generated_image_url("/media/generated/cat.png") == "/media/generated/cat.png"


def test_bare_filename_joins_configured_media_url_base(monkeypatch):
    monkeypatch.setenv("MEDIA_URL_BASE", "https://example.com/media/generated")
    assert (
        build_generated_image_url("cat.png")
        == "https://example.com/media/generated/cat.png"
    )


def test_absolute_path_is_normalized_to_public_media_url(monkeypatch):
    monkeypatch.setenv("MEDIA_URL_BASE", "https://example.com/media/generated")
    assert (
        build_generated_image_url("/tmp/folder/cat.png")
        == "https://example.com/media/generated/cat.png"
    )


def test_data_url_is_normalized_to_generated_filename(monkeypatch):
    monkeypatch.setenv("MEDIA_URL_BASE", "https://example.com/media/generated")
    url = build_generated_image_url("data:image/png;base64,Zm9v")
    assert url.startswith("https://example.com/media/generated/img_")
    assert url.endswith(".png")


def test_generated_image_path_uses_configured_directory(monkeypatch):
    monkeypatch.setenv("MUD_MEDIA_DIR", "/tmp/generated-images")
    path = get_generated_image_path("/media/generated/cat.png")
    assert path == Path("/tmp/generated-images/cat.png")
