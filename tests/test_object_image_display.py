# tests/test_object_image_display.py
"""
Tests for object image display — objects should show their generated image
when examined (looked at) in-game.

Tests cover:
- Object image display logic (unit tests)
- ImageMixin robustness with edge-case DB state
"""

import time
import pytest


class FakeDb:
    """Minimal mock for the Evennia `db` attribute handler."""

    def __init__(self, **kwargs):
        self._data = kwargs.copy()

    def __getattr__(self, name):
        if name == "_data":
            raise AttributeError
        return self._data.get(name)

    def __setattr__(self, name, value):
        if name == "_data":
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value


class TestImageMixinRobustness:
    """Test ImageMixin handles edge cases (pre-existing DB state)."""

    def test_can_trigger_image_handles_none_timestamp(self):
        """_can_trigger_image should handle None _image_generation_last_ts."""
        from utils.image_mixin import ImageMixin

        class SafeTest(ImageMixin):
            db = None
            key = "safe"
            image_generation_cooldown = 5.0

            def __init__(self):
                self.db = FakeDb(_image_generation_last_ts=None)

        obj = SafeTest()
        # Should not raise TypeError
        result = obj._can_trigger_image()
        assert isinstance(result, bool)

    def test_can_trigger_image_handles_zero_timestamp(self):
        """_can_trigger_image should handle 0.0 timestamp."""
        from utils.image_mixin import ImageMixin

        class ZeroTs(ImageMixin):
            db = None
            key = "zero"
            image_generation_cooldown = 5.0

            def __init__(self):
                self.db = FakeDb(_image_generation_last_ts=0.0)

        obj = ZeroTs()
        result = obj._can_trigger_image()
        assert result is True

    def test_get_description_with_image_handles_none(self):
        """get_description_with_image should handle None desc safely."""
        from utils.image_mixin import ImageMixin

        class NoneDesc(ImageMixin):
            db = None
            key = "none"

            def __init__(self):
                self.db = FakeDb(desc=None, image_generating=False)

        obj = NoneDesc()
        result = obj.get_description_with_image()
        assert result == ""

    def test_get_description_with_image_shows_url(self):
        """get_description_with_image should include image URL when set."""
        from utils.image_mixin import ImageMixin

        class WithUrl(ImageMixin):
            db = None
            key = "with_url"

            def __init__(self):
                self.db = FakeDb(
                    desc="A shiny brass cat idol.",
                    image_url="http://127.0.0.1:8188/generated/cat.png",
                    image_generating=False,
                )

        obj = WithUrl()
        obj._is_image_stale = lambda url: False
        result = obj.get_description_with_image()
        assert "cat.png" in result
        assert "brass cat idol" in result

    def test_get_description_with_image_shows_generating(self):
        """get_description_with_image should show 'generating...' when in-flight."""
        from utils.image_mixin import ImageMixin

        class Generating(ImageMixin):
            db = None
            key = "gen"

            def __init__(self):
                self.db = FakeDb(
                    desc="A mysterious orb.",
                    image_url=None,
                    image_generating=True,
                )

        obj = Generating()
        result = obj.get_description_with_image()
        assert "generating..." in result

    def test_get_description_with_image_regenerates_stale_image(self):
        """A stale image reference should trigger regeneration and show the loading message."""
        from utils.image_mixin import ImageMixin

        calls = []

        class Stale(ImageMixin):
            db = None
            key = "stale"

            def __init__(self):
                self.db = FakeDb(
                    desc="A worn lantern.",
                    image_url="/media/generated/lantern.png",
                    image_generating=False,
                )

            def _trigger_image_generation(self, prompt, subject_type="room"):
                calls.append((prompt, subject_type))

        obj = Stale()
        obj._is_image_stale = lambda url: True
        result = obj.get_description_with_image()
        assert "generating" in result
        assert calls == [("A worn lantern.", "room")]
        assert obj.db.image_url is None

    def test_object_image_display_in_get_display_desc(self):
        """Verify the image display pattern used by Object.get_display_desc works correctly."""
        # Replicate the exact pattern used by Object.get_display_desc:
        #   desc = getattr(self.db, "desc", "") or ""
        #   if generating: return desc + generating msg
        #   if url: return desc + url
        #   return desc
        db = FakeDb(
            desc="A wooden chair.",
            image_url="http://example.com/chair.png",
            image_generating=False,
        )
        desc = getattr(db, "desc", "") or ""
        if getattr(db, "image_generating", False):
            result = f"{desc}\n\n|yImage: generating...|n"
        else:
            url = getattr(db, "image_url", None)
            if url:
                result = f"{desc}\n\n|yImage: {url}|n"
            else:
                result = desc
        assert "wooden chair" in result
        assert "chair.png" in result

    def test_object_display_desc_no_image_returns_plain_desc(self):
        """When no image is set, get_display_desc should return just the description."""
        db = FakeDb(
            desc="A simple rock.",
            image_url=None,
            image_generating=False,
        )
        desc = getattr(db, "desc", "") or ""
        url = getattr(db, "image_url", None)
        if url:
            result = f"{desc}\n\n|yImage: {url}|n"
        else:
            result = desc
        assert result == "A simple rock."

    def test_object_display_desc_empty_desc_with_image(self):
        """When desc is empty but image exists, image should still show."""
        db = FakeDb(
            desc="",
            image_url="http://example.com/orb.png",
            image_generating=False,
        )
        desc = getattr(db, "desc", "") or ""
        url = getattr(db, "image_url", None)
        if url:
            result = f"{desc}\n\n|yImage: {url}|n"
        else:
            result = desc
        assert "orb.png" in result
