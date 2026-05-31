# tests/test_object_image_display.py
"""
Tests for object image display — objects should show their generated image
when examined (looked at) in-game.

Tests cover:
- Object inherits ImageMixin and has image state
- Object get_display_desc includes image URL when present
- Object image display works independently of room images
"""

import time
import pytest

from utils.image_mixin import ImageMixin


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


def _make_test_obj(**db_kwargs):
    """
    Create a standalone ImageMixin-based object with a mock db.

    Avoids defining `db = None` as a class attribute (which would shadow
    the instance-level `self.db` set in __init__).
    """
    class _TestObj:
        def __init__(self, **kw):
            self.db = FakeDb(**kw)
            self.key = kw.get("key", "test_obj")
            self.image_enabled = True
            self.image_generation_cooldown = 5.0

        def at_object_creation(self):
            pass

        def _is_image_generating(self):
            return getattr(self.db, "image_generating", False)

        def _can_trigger_image(self):
            return ImageMixin._can_trigger_image(self)

        def get_image_html(self):
            return ImageMixin.get_image_html(self)

        def get_description_with_image(self):
            return ImageMixin.get_description_with_image(self)

    return _TestObj(**db_kwargs)


class TestObjectImageMixinInheritance:
    """Verify that the Object typeclass inherits ImageMixin."""

    def test_object_inherits_image_mixin(self):
        """Object should inherit ImageMixin."""
        from typeclasses.objects import Object
        assert issubclass(Object, ImageMixin)

    def test_objectparent_inherits_image_mixin(self):
        """ObjectParent should inherit ImageMixin so all entities get it."""
        from typeclasses.objects import ObjectParent
        assert issubclass(ObjectParent, ImageMixin)


class TestObjectImageDisplay:
    """Test that objects display their image in descriptions."""

    def test_object_get_display_desc_shows_image_url(self):
        """get_description_with_image should include the image URL when set."""
        obj = _make_test_obj(
            desc="A shiny brass cat idol.",
            image_url="http://127.0.0.1:8188/generated/cat.png",
            image_generating=False,
        )
        desc = obj.get_description_with_image()
        assert "cat.png" in desc
        assert "brass cat" in desc

    def test_object_get_display_desc_generating(self):
        """get_description_with_image should show 'generating...' when in-flight."""
        obj = _make_test_obj(
            desc="A mysterious orb.",
            image_url=None,
            image_generating=True,
        )
        desc = obj.get_description_with_image()
        assert "generating..." in desc

    def test_object_get_display_desc_no_image(self):
        """get_description_with_image should return just the desc when no image."""
        obj = _make_test_obj(
            desc="A wooden chair.",
            image_url=None,
            image_generating=False,
        )
        desc = obj.get_description_with_image()
        assert desc == "A wooden chair."

    def test_object_has_image_url_attribute(self):
        """Object instances should have db.image_url settable."""
        obj = _make_test_obj(desc="A stone.")
        obj.db.image_url = "http://example.com/stone.png"
        assert obj.db.image_url == "http://example.com/stone.png"

    def test_object_cooldown_blocks_recent_triggers(self):
        """Cooldown should block triggers within the cooldown window."""
        obj = _make_test_obj(
            desc="Blocked.",
            _image_generation_last_ts=time.time() - 1,
            image_generating=False,
        )
        assert not obj._can_trigger_image()

    def test_get_image_html_returns_image_tag(self):
        """get_image_html should return a proper <img> tag."""
        obj = _make_test_obj(
            desc="A prop.",
            image_url="http://example.com/prop.png",
            image_generating=False,
        )
        html = obj.get_image_html()
        assert "<img" in html
        assert "http://example.com/prop.png" in html


class TestObjectImageIntegration:
    """Integration-style tests: object images don't interfere with room images."""

    def test_object_image_does_not_require_room(self):
        """Object images work independently — no room needed."""
        obj = _make_test_obj(
            desc="A standalone object.",
            image_url="http://test.obj",
            image_generating=False,
        )
        desc = obj.get_description_with_image()
        assert "http://test.obj" in desc

    def test_image_mixin_safe_on_object_without_desc(self):
        """Should handle objects with empty/None desc gracefully."""
        obj = _make_test_obj(
            desc="",
            image_url=None,
            image_generating=False,
        )
        desc = obj.get_description_with_image()
        assert desc == ""
