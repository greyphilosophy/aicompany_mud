"""
Unit tests for ImageMixin and SmartRoom image generation integration.

Tests cover:
- ImageMixin basic state and cooldown logic
- Image display in room descriptions
- Graceful fallback when evennia_ai_image_generator is missing
"""
import importlib.util
import time
import unittest

import pytest

# Check if the image generator package is available
_image_pkg_available = importlib.util.find_spec("evennia_ai_image_generator") is not None


class TestImageMixinBasics:
    """Test ImageMixin core logic without Evennia typeclasses."""

    def test_image_mixin_import(self):
        """Import should work even if package is missing."""
        from utils.image_mixin import ImageMixin
        assert ImageMixin is not None

    def test_image_mixin_defaults(self):
        """ImageMixin should have correct defaults."""
        from utils.image_mixin import ImageMixin

        assert ImageMixin.image_enabled is True
        assert ImageMixin.image_generation_cooldown == 5.0


class TestImageDisplay:
    """Test that images are properly displayed in descriptions."""

    def test_get_image_html_returns_empty_when_no_image(self):
        """Should return empty string when no image URL."""
        from utils.image_mixin import ImageMixin

        class DB:
            image_url = None
            def __getattr__(self, name):
                return None
            def __setattr__(self, name, value):
                self.__dict__[name] = value

        class Dummy(ImageMixin):
            db = DB()
            key = "test"

        obj = Dummy()
        assert obj.get_image_html() == ""

    def test_get_image_html_returns_html_when_image_exists(self):
        """Should return an <img> tag when image_url is set."""
        from utils.image_mixin import ImageMixin

        class DB:
            image_url = "http://127.0.0.1:8188/output/test.png"
            def __getattr__(self, name):
                return None
            def __setattr__(self, name, value):
                self.__dict__[name] = value

        class Dummy(ImageMixin):
            db = DB()
            key = "test"

        obj = Dummy()
        html = obj.get_image_html()
        assert "http://127.0.0.1:8188/output/test.png" in html
        assert "<img" in html

    def test_get_description_with_image_shows_generating(self):
        """Should show 'generating...' when image is in-flight."""
        from utils.image_mixin import ImageMixin

        class DB:
            desc = "A test room."
            image_generating = True
            def __getattr__(self, name):
                return None
            def __setattr__(self, name, value):
                self.__dict__[name] = value

        class Dummy(ImageMixin):
            db = DB()
            key = "test"

        obj = Dummy()
        desc = obj.get_description_with_image()
        assert "generating..." in desc

    def test_get_description_with_image_shows_url(self):
        """Should show the image URL in description."""
        from utils.image_mixin import ImageMixin

        class DB:
            desc = "A test room."
            image_generating = False
            image_url = "http://example.com/img.png"
            def __getattr__(self, name):
                return None
            def __setattr__(self, name, value):
                self.__dict__[name] = value

        class Dummy(ImageMixin):
            db = DB()
            key = "test"

        obj = Dummy()
        desc = obj.get_description_with_image()
        assert "http://example.com/img.png" in desc


class TestImageMixinCooldownLogic:
    """Test the cooldown mechanism."""

    def test_cooldown_respects_time(self):
        """Cooldown should allow new triggers after the threshold."""
        from utils.image_mixin import ImageMixin

        class DB:
            _image_generation_last_ts = time.time() - 10.0  # 10 seconds ago
            def __getattr__(self, name):
                return None
            def __setattr__(self, name, value):
                self.__dict__[name] = value

        class Dummy(ImageMixin):
            image_enabled = True
            db = DB()
            key = "test"
            image_generation_cooldown = 5.0

        obj = Dummy()
        # Should be able to trigger (10s ago, cooldown is 5s)
        assert obj._can_trigger_image()

    def test_cooldown_blocks_recent_triggers(self):
        """Should block triggers within the cooldown window."""
        from utils.image_mixin import ImageMixin

        class DB:
            _image_generation_last_ts = time.time() - 1.0  # 1 second ago
            def __getattr__(self, name):
                return None
            def __setattr__(self, name, value):
                self.__dict__[name] = value

        class Dummy(ImageMixin):
            image_enabled = True
            db = DB()
            key = "test"
            image_generation_cooldown = 5.0

        obj = Dummy()
        # Should be blocked (only 1s ago, cooldown is 5s)
        assert not obj._can_trigger_image()

    def test_cooldown_allows_after_window(self):
        """After cooldown elapses, a new trigger should be allowed."""
        from utils.image_mixin import ImageMixin

        # Start at "now" — should be blocked immediately
        class DB1:
            _image_generation_last_ts = time.time() - 0.1
            def __getattr__(self, name):
                return None
            def __setattr__(self, name, value):
                self.__dict__[name] = value

        class Dummy1(ImageMixin):
            db = DB1()
            key = "test"
            image_generation_cooldown = 5.0

        obj1 = Dummy1()
        assert not obj1._can_trigger_image()

        # Move timestamp forward past cooldown
        class DB2:
            _image_generation_last_ts = time.time() - 6.0
            def __getattr__(self, name):
                return None
            def __setattr__(self, name, value):
                self.__dict__[name] = value

        class Dummy2(ImageMixin):
            db = DB2()
            key = "test"
            image_generation_cooldown = 5.0

        obj2 = Dummy2()
        assert obj2._can_trigger_image()
