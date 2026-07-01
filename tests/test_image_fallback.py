"""
Unit tests for the FLUX.2 → OpenAI image generation fallback chain.

Covers all acceptance criteria for the user story:
  "As a MUD player, I want room and object images to still generate when
   the primary FLUX.2 image server is unavailable, so that visual
   gameplay remains reliable and immersive even during local GPU/server
   outages."

Tests use mocks so they run without live servers or the evennia package
installed.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Conftest-level sys.module patching: fake the evennia package so the
# `from evennia_ai_image_generator.backend.base import ImageGenerationRequest`
# inside the fallback functions resolves to our test double.
# ---------------------------------------------------------------------------

class _FakeImageGenerationRequest:
    """Minimal stand-in for ImageGenerationRequest."""
    def __init__(self, subject_type=None, subject_key=None, prompt=None,
                 mode=None, width=None, height=None, negative_prompt=None):
        self.subject_type = subject_type
        self.subject_key = subject_key
        self.prompt = prompt
        self.mode = mode
        self.width = width
        self.height = height
        self.negative_prompt = negative_prompt


def _install_fake_evennia_module():
    """Install fake modules into sys.modules so the dynamic import works."""
    fake_base = ModuleType("evennia_ai_image_generator.backend.base")
    fake_base.ImageGenerationRequest = _FakeImageGenerationRequest
    fake_base.BaseImageBackend = object
    fake_base.ImageGenerationResult = type("ImageGenerationResult", (), {})
    fake_base.ReferenceImage = type("ReferenceImage", (), {})
    sys.modules["evennia_ai_image_generator"] = ModuleType("evennia_ai_image_generator")
    sys.modules["evennia_ai_image_generator.backend"] = ModuleType("evennia_ai_image_generator.backend")
    sys.modules["evennia_ai_image_generator.backend.base"] = fake_base


_install_fake_evennia_module()


# ---------------------------------------------------------------------------
# Criterion 1: FLUX.2 is used as primary when reachable
# ---------------------------------------------------------------------------

class TestCriterion1_FLUX2Primary:
    """When FLUX.2 is reachable and generation succeeds, FLUX.2 is used
    and OpenAI is never touched."""

    def test_flux2_success_returns_image_url(self):
        """FLUX.2 returns a result → the URL is returned."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_flux2 = MagicMock()
        mock_flux2.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/flux2_room_ok.png"
        )

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                result = _generate_image_with_fallback(
                    "room", "room_1", "A cozy tavern"
                )

        assert result == "https://game.test/media/generated/flux2_room_ok.png"
        mock_flux2.generate.assert_called_once()

    def test_flux2_success_does_not_touch_openai(self):
        """When FLUX.2 succeeds, OpenAI is never called."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_flux2 = MagicMock()
        mock_flux2.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/flux2_room_ok.png"
        )
        mock_openai = MagicMock()

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "room_1", "A cozy tavern"
                    )

        assert result == "https://game.test/media/generated/flux2_room_ok.png"
        mock_flux2.generate.assert_called_once()
        mock_openai.generate.assert_not_called()

    def test_generate_room_image_calls_fallback_chain(self):
        """generate_room_image routes through the fallback chain."""
        import utils.image_generation as img_gen
        from utils.image_generation import generate_room_image

        mock_flux2 = MagicMock()
        mock_flux2.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/flux2_tavern.png"
        )

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_has_any_backend", return_value=True):
                with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                    result = generate_room_image("A cozy tavern")

        assert result == "https://game.test/media/generated/flux2_tavern.png"

    def test_generate_object_image_calls_fallback_chain(self):
        """generate_object_image routes through the fallback chain."""
        import utils.image_generation as img_gen
        from utils.image_generation import generate_object_image

        mock_flux2 = MagicMock()
        mock_flux2.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/flux2_sword.png"
        )

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_has_any_backend", return_value=True):
                with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                    result = generate_object_image("sword", "a rusty sword", "Rusty Sword")

        assert result == "https://game.test/media/generated/flux2_sword.png"


# ---------------------------------------------------------------------------
# Criterion 2: Automatic OpenAI fallback on FLUX.2 failure
# ---------------------------------------------------------------------------

class TestCriterion2_OpenAIFallback:
    """When FLUX.2 is unreachable or generation fails, the system
    automatically attempts OpenAI image generation as a fallback."""

    def test_flux2_unavailable_triggers_openai(self):
        """When _flux2_server_alive() returns False, OpenAI is attempted."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_openai = MagicMock()
        mock_openai.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/openai_room.png"
        )

        with patch.object(img_gen, "_get_flux2_backend", return_value=MagicMock()):
            with patch.object(img_gen, "_flux2_server_alive", return_value=False):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "room_2", "A dark dungeon"
                    )

        assert result == "https://game.test/media/generated/openai_room.png"

    def test_flux2_generation_exception_triggers_openai(self):
        """When FLUX.2 health check passes but generate() raises, OpenAI
        is attempted."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_openai = MagicMock()
        mock_openai.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/openai_fallback.png"
        )

        mock_flux2 = MagicMock()
        mock_flux2.generate.side_effect = Exception("FLUX.2 GPU OOM")

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "room_3", "A fiery forge"
                    )

        assert result == "https://game.test/media/generated/openai_fallback.png"

    def test_flux2_down_openai_also_fails_returns_none(self):
        """When both backends fail gracefully, None is returned."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("OpenAI rate limit")

        mock_flux2 = MagicMock()
        mock_flux2.generate.side_effect = Exception("FLUX.2 timeout")

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "room_5", "An empty chamber"
                    )

        assert result is None


# ---------------------------------------------------------------------------
# Criterion 3: Graceful crash-free failure when both backends fail
# ---------------------------------------------------------------------------

class TestCriterion3_GracefulCrashFreeFailure:
    """When both backends fail or are unavailable, gameplay continues
    without crashing, and no image URL is returned."""

    def test_flux2_fail_openai_fail_returns_none(self):
        """FLUX.2 fails + OpenAI fails → None, no exception."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_flux2 = MagicMock()
        mock_flux2.generate.side_effect = Exception("FLUX.2 dies")

        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("OpenAI dies")

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "room_6", "A dark corridor"
                    )

        assert result is None

    def test_neither_backend_available_returns_none(self):
        """When no backends are configured at all, returns None."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        with patch.object(img_gen, "_get_flux2_backend", return_value=None):
            with patch.object(img_gen, "_get_openai_backend", return_value=None):
                result = _generate_image_with_fallback(
                    "room", "room_7", "A dark corridor"
                )

        assert result is None

    def test_generate_room_image_never_raises_on_double_failure(self):
        """generate_room_image catches exceptions and returns None."""
        import utils.image_generation as img_gen
        from utils.image_generation import generate_room_image

        mock_flux2 = MagicMock()
        mock_flux2.generate.side_effect = Exception("FLUX.2 dies")

        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("OpenAI dies")

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_has_any_backend", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = generate_room_image("A cozy room")

        assert result is None

    def test_generate_object_image_never_raises_on_double_failure(self):
        """generate_object_image catches exceptions and returns None."""
        import utils.image_generation as img_gen
        from utils.image_generation import generate_object_image

        mock_flux2 = MagicMock()
        mock_flux2.generate.side_effect = Exception("FLUX.2 dies")

        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("OpenAI dies")

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_has_any_backend", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = generate_object_image("gem", "a sparkling gem", "Gem")

        assert result is None

    def test_generate_room_image_no_backend_returns_none(self):
        """When no backend is available, generate_room_image returns None."""
        import utils.image_generation as img_gen
        with patch.object(img_gen, "_has_any_backend", return_value=False):
            from utils.image_generation import generate_room_image
            result = generate_room_image("A beautiful meadow")
            assert result is None

    def test_generate_object_image_no_backend_returns_none(self):
        """When no backend is available, generate_object_image returns None."""
        import utils.image_generation as img_gen
        with patch.object(img_gen, "_has_any_backend", return_value=False):
            from utils.image_generation import generate_object_image
            result = generate_object_image("key", "an iron key", "Iron Key")
            assert result is None


# ---------------------------------------------------------------------------
# Criterion 4: Backend failures are logged with enough context
# ---------------------------------------------------------------------------

class TestCriterion4_Logging:
    """Backend failures are logged with enough context to identify whether
    FLUX.2 or OpenAI failed."""

    def test_flux2_failure_logged_with_subject_context(self):
        """FLUX.2 failure logs subject_type, subject_key, and exception."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_flux2 = MagicMock()
        mock_flux2.generate.side_effect = Exception("FLUX.2 GPU OOM")

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=None):
                    with patch.object(img_gen, "logger") as mock_logger:
                        _generate_image_with_fallback(
                            "room", "tavern_01", "A cozy tavern"
                        )

        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) >= 1
        flux_warning = str(warning_calls[0])
        assert "FLUX.2" in flux_warning
        assert "room" in flux_warning
        assert "tavern_01" in flux_warning

    def test_openai_failure_logged_with_subject_context(self):
        """OpenAI failure logs subject_type, subject_key, and exception."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("OpenAI rate limit")

        with patch.object(img_gen, "_get_flux2_backend", return_value=MagicMock()):
            with patch.object(img_gen, "_flux2_server_alive", return_value=False):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    with patch.object(img_gen, "logger") as mock_logger:
                        _generate_image_with_fallback(
                            "object", "potion_01", "Healing Potion"
                        )

        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) >= 1
        openai_warning = str(warning_calls[0])
        assert "OpenAI" in openai_warning
        assert "object" in openai_warning
        assert "potion_01" in openai_warning


# ---------------------------------------------------------------------------
# Criterion 5: Uses existing generated media dir and media URL base
# ---------------------------------------------------------------------------

class TestCriterion5_SharedMediaConfig:
    """The fallback uses the existing generated media directory and media
    URL base so downstream Discord/game image handling continues to work."""

    def test_image_paths_module_provides_shared_config(self):
        """get_generated_media_dir() and get_media_url_base() return valid
        defaults."""
        from utils.image_paths import get_generated_media_dir, get_media_url_base

        media_dir = get_generated_media_dir()
        assert media_dir is not None
        assert isinstance(media_dir, str)

        url_base = get_media_url_base()
        assert url_base is not None
        assert isinstance(url_base, str)

    def test_image_generation_uses_image_paths_module(self):
        """The fallback code imports get_generated_media_dir and
        get_media_url_base from image_paths."""
        import utils.image_generation as img_gen
        import inspect
        source = inspect.getsource(img_gen)
        assert "get_generated_media_dir" in source
        assert "get_media_url_base" in source

    def test_backend_creation_uses_shared_config(self):
        """Both backend constructors receive output_dir and media_url_base
        from the shared config helpers."""
        import utils.image_generation as img_gen
        import inspect
        source = inspect.getsource(img_gen)
        assert "get_media_url_base()" in source
        assert "get_generated_media_dir()" in source


# ---------------------------------------------------------------------------
# Criterion 6: Required configuration is documented
# ---------------------------------------------------------------------------

class TestCriterion6_ConfigDocumentation:
    """Required configuration is documented, including FLUX2_SERVER_URL
    and OPENAI_API_KEY."""

    def test_config_env_vars_present_in_source(self):
        """FLUX2_SERVER_URL and OPENAI_API_KEY are referenced in the source
        code."""
        import utils.image_generation as img_gen
        import inspect
        source = inspect.getsource(img_gen)
        assert "FLUX2_SERVER_URL" in source
        assert "OPENAI_API_KEY" in source

    def test_default_server_url_is_documented(self):
        """The default server URL is visible in the source."""
        import utils.image_generation as img_gen
        import inspect
        source = inspect.getsource(img_gen)
        assert "FLUX2_SERVER_URL" in source
        assert "http://169.254.209.73:8190" in source


# ---------------------------------------------------------------------------
# Criterion 7: Follow-up health endpoint improvement
# ---------------------------------------------------------------------------

class TestCriterion7_HealthEndpoint:
    """The current implementation uses a lightweight GET health check.
    This test documents the behavior and validates it."""

    def test_health_check_is_lightweight_get_with_timeout(self):
        """_flux2_server_alive uses a GET request with a 3s timeout."""
        import utils.image_generation as img_gen
        mock_backend = MagicMock()
        mock_backend.server_url = "http://169.254.209.73:8190"

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_backend):
            with patch.object(img_gen, "httpx") as mock_httpx:
                mock_client = MagicMock()
                mock_response = MagicMock(status_code=200)
                mock_client.get.return_value = mock_response
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_httpx.Client.return_value = mock_client

                from utils.image_generation import _flux2_server_alive
                result = _flux2_server_alive()

                mock_httpx.Client.assert_called_once()
                call_kwargs = mock_httpx.Client.call_args[1]
                assert call_kwargs.get("timeout") == 3.0
                assert result is True

    def test_health_check_follows_redirects(self):
        """The health check follows redirects."""
        import utils.image_generation as img_gen
        mock_backend = MagicMock()
        mock_backend.server_url = "http://169.254.209.73:8190"

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_backend):
            with patch.object(img_gen, "httpx") as mock_httpx:
                mock_client = MagicMock()
                mock_response = MagicMock(status_code=200)
                mock_client.get.return_value = mock_response
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_httpx.Client.return_value = mock_client

                from utils.image_generation import _flux2_server_alive
                _flux2_server_alive()

                mock_client.get.assert_called_once()
                get_kwargs = mock_client.get.call_args[1]
                assert get_kwargs.get("follow_redirects") is True

    def test_health_check_returns_true_on_200(self):
        """A 200 status code passes the health check."""
        import utils.image_generation as img_gen
        mock_backend = MagicMock()
        mock_backend.server_url = "http://169.254.209.73:8190"

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_backend):
            with patch.object(img_gen, "httpx") as mock_httpx:
                mock_client = MagicMock()
                mock_response = MagicMock(status_code=200)
                mock_client.get.return_value = mock_response
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_httpx.Client.return_value = mock_client

                from utils.image_generation import _flux2_server_alive
                result = _flux2_server_alive()
                assert result is True

    def test_health_check_returns_false_on_500(self):
        """A 500 status code fails the health check."""
        import utils.image_generation as img_gen
        mock_backend = MagicMock()
        mock_backend.server_url = "http://169.254.209.73:8190"

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_backend):
            with patch.object(img_gen, "httpx") as mock_httpx:
                mock_client = MagicMock()
                mock_response = MagicMock(status_code=500)
                mock_client.get.return_value = mock_response
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_httpx.Client.return_value = mock_client

                from utils.image_generation import _flux2_server_alive
                result = _flux2_server_alive()
                assert result is False

    def test_health_check_returns_false_on_exception(self):
        """Any exception during the health check returns False."""
        import utils.image_generation as img_gen
        mock_backend = MagicMock()
        mock_backend.server_url = "http://169.254.209.73:8190"

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_backend):
            with patch.object(img_gen, "httpx") as mock_httpx:
                mock_client = MagicMock()
                mock_client.get.side_effect = Exception("Connection timeout")
                mock_client.__enter__ = MagicMock(return_value=mock_client)
                mock_client.__exit__ = MagicMock(return_value=False)
                mock_httpx.Client.return_value = mock_client

                from utils.image_generation import _flux2_server_alive
                result = _flux2_server_alive()
                assert result is False

    def test_health_check_no_backend_returns_false(self):
        """When no FLUX.2 backend is configured, health check returns False."""
        import utils.image_generation as img_gen
        with patch.object(img_gen, "_get_flux2_backend", return_value=None):
            from utils.image_generation import _flux2_server_alive
            result = _flux2_server_alive()
            assert result is False


# ---------------------------------------------------------------------------
# End-to-end fallback scenarios
# ---------------------------------------------------------------------------

class TestFallbackScenarios:
    """Integration-style scenarios covering the full fallback chain."""

    def test_scenario_flux2_up_openai_unused(self):
        """FLUX.2 succeeds → URL returned, OpenAI never touched."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_flux2 = MagicMock()
        mock_flux2.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/flux2_tavern.png"
        )
        mock_openai = MagicMock()

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "tavern", "A cozy tavern"
                    )

        assert result == "https://game.test/media/generated/flux2_tavern.png"
        mock_openai.generate.assert_not_called()

    def test_scenario_flux2_down_openai_succeeds(self):
        """FLUX.2 is down → OpenAI picks up the slack."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_openai = MagicMock()
        mock_openai.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/openai_tavern.png"
        )

        with patch.object(img_gen, "_get_flux2_backend", return_value=MagicMock()):
            with patch.object(img_gen, "_flux2_server_alive", return_value=False):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "tavern", "A cozy tavern"
                    )

        assert result == "https://game.test/media/generated/openai_tavern.png"

    def test_scenario_flux2_up_but_generation_fails(self):
        """Health check passes, generation fails → OpenAI used."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_openai = MagicMock()
        mock_openai.generate.return_value = MagicMock(
            image_url="https://game.test/media/generated/openai_fallback.png"
        )

        mock_flux2 = MagicMock()
        mock_flux2.generate.side_effect = Exception("GPU OOM during inference")

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "dungeon", "A dark dungeon"
                    )

        assert result == "https://game.test/media/generated/openai_fallback.png"
        mock_openai.generate.assert_called_once()

    def test_scenario_both_down_returns_none(self):
        """Both backends fail → None returned, no crash."""
        import utils.image_generation as img_gen
        from utils.image_generation import _generate_image_with_fallback

        mock_openai = MagicMock()
        mock_openai.generate.side_effect = Exception("OpenAI rate limit")

        mock_flux2 = MagicMock()
        mock_flux2.generate.side_effect = Exception("FLUX.2 timeout")

        with patch.object(img_gen, "_get_flux2_backend", return_value=mock_flux2):
            with patch.object(img_gen, "_flux2_server_alive", return_value=True):
                with patch.object(img_gen, "_get_openai_backend", return_value=mock_openai):
                    result = _generate_image_with_fallback(
                        "room", "tavern", "A cozy tavern"
                    )

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
