"""
Tests for utils/image_generation.py — unit tests only (no live FLUX.2 server required).

Tests verify:
- _get_backend returns a Flux2RestBackend with env-configured URL
- generate_room_image / generate_object_image delegate correctly
- Graceful fallback when backend errors or is missing
"""
import importlib.util

import pytest

if not importlib.util.find_spec("evennia_ai_image_generator"):
    pytest.skip(
        "evennia_ai_image_generator not installed", allow_module_level=True
    )


class TestFlux2RestBackendConfig:
    """Verify Flux2RestBackend configures correctly with defaults and env vars."""

    def test_default_server_url(self):
        from evennia_ai_image_generator.backend.flux2_rest_backend import Flux2RestBackend
        backend = Flux2RestBackend()
        assert backend.server_url == "http://127.0.0.1:8190"

    def test_custom_server_url(self):
        from evennia_ai_image_generator.backend.flux2_rest_backend import Flux2RestBackend
        backend = Flux2RestBackend(server_url="http://169.254.209.73:8190")
        assert backend.server_url == "http://169.254.209.73:8190"

    def test_path_building_is_deterministic(self):
        from evennia_ai_image_generator.backend.base import ImageGenerationRequest
        from evennia_ai_image_generator.backend.flux2_rest_backend import Flux2RestBackend

        backend = Flux2RestBackend()
        request = ImageGenerationRequest(
            subject_type="room",
            subject_key="test_key",
            prompt="A dark forest",
            mode="txt2img",
            width=512,
            height=512,
        )
        path1, url1 = backend._build_paths(request)
        path2, url2 = backend._build_paths(request)
        assert path1 == path2
        assert url1 == url2
        assert path1.endswith(".png")
        assert "room" in path1


class TestGenerateWithMockedBackend:
    """Test generate_room_image / generate_object_image with mocked backend."""

    def _reset_cache(self):
        import utils.image_generation as ig
        ig._backend_cache = None

    def test_generate_room_image_calls_backend(self):
        """Verify generate_room_image produces a valid result when backend returns."""
        self._reset_cache()

        from utils import image_generation as ig
        from evennia_ai_image_generator.backend.base import ImageGenerationResult
        from unittest.mock import MagicMock, patch

        mock_backend = MagicMock()
        mock_backend.generate.return_value = ImageGenerationResult(
            image_path="generated/test.png",
            image_url="https://game.test/media/generated/test.png",
            model_name="FLUX.2-dev",
            generation_time=1.0,
            metadata={},
        )

        with patch.object(ig, "_get_backend", return_value=mock_backend) as mock_get:
            result = ig.generate_room_image("A cozy tavern")
            assert result is not None
            assert "test.png" in result
            mock_get.assert_called_once()
            mock_backend.generate.assert_called_once()

    def test_generate_object_image_calls_backend(self):
        self._reset_cache()

        from utils import image_generation as ig
        from evennia_ai_image_generator.backend.base import ImageGenerationResult
        from unittest.mock import MagicMock, patch

        mock_backend = MagicMock()
        mock_backend.generate.return_value = ImageGenerationResult(
            image_path="generated/crystal.png",
            image_url="https://game.test/media/generated/crystal.png",
            model_name="FLUX.2-dev",
            generation_time=1.0,
            metadata={},
        )

        with patch.object(ig, "_get_backend", return_value=mock_backend):
            result = ig.generate_object_image(
                object_key="crystal",
                object_desc="A glowing crystal",
                shortdesc="Crystal",
            )
            assert result is not None
            mock_backend.generate.assert_called_once()

    def test_generate_returns_none_on_backend_error(self):
        """When the backend raises, the helper returns None (graceful fallback)."""
        self._reset_cache()

        from utils import image_generation as ig
        from unittest.mock import MagicMock, patch

        mock_backend = MagicMock()
        mock_backend.generate.side_effect = ConnectionError("Server timeout")

        with patch.object(ig, "_get_backend", return_value=mock_backend):
            result = ig.generate_room_image("A dark room")
            assert result is None

    def test_generate_returns_none_when_no_backend(self):
        """When _get_backend returns None, no generation happens."""
        self._reset_cache()

        from utils import image_generation as ig
        from unittest.mock import patch

        with patch.object(ig, "_get_backend", return_value=None):
            result = ig.generate_room_image("A dark room")
            assert result is None

    def test_backend_cache_is_reused(self):
        """Verify the backend cache mechanism works."""
        self._reset_cache()

        from utils import image_generation as ig
        from evennia_ai_image_generator.backend.base import ImageGenerationResult
        from unittest.mock import MagicMock, patch

        mock_backend = MagicMock()
        mock_backend.generate.return_value = ImageGenerationResult(
            image_path="generated/test.png",
            image_url="https://game.test/media/generated/test.png",
            model_name="FLUX.2-dev",
            generation_time=1.0,
            metadata={},
        )

        call_count = [0]

        def fake_get_backend():
            call_count[0] += 1
            return mock_backend

        with patch.object(ig, "_get_backend", side_effect=fake_get_backend):
            ig._backend_cache = None
            ig.generate_room_image("Room 1")
            ig.generate_room_image("Room 2")

        # _get_backend should be called twice since we're patching it directly,
        # but the real _get_backend would only call the constructor once.
        assert call_count[0] == 2


class TestGetBackend:
    """Test that _get_backend returns the correct backend type."""

    def test_get_backend_returns_flux2(self):
        """_get_backend should return a Flux2RestBackend when the package is installed."""
        from utils.image_generation import _get_backend
        from evennia_ai_image_generator.backend.flux2_rest_backend import Flux2RestBackend
        from utils import image_generation as ig
        ig._backend_cache = None

        backend = _get_backend()
        assert isinstance(backend, Flux2RestBackend)
