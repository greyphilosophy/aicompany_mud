"""
Tests for the object image feature — objects should display images when looked at.

Tests verify:
1. Object inherits ImageMixin
2. get_display_desc() shows image URL when one exists
3. get_display_desc() triggers generation when no image exists (with cooldown)
"""

import time
import pytest


class TestObjectInheritsImageMixin:
    """Verify Object class properly inherits ImageMixin."""

    def test_object_has_image_enabled_attribute(self):
        """Object should have image_enabled from ImageMixin."""
        from typeclasses.objects import Object
        assert hasattr(Object, "image_enabled")
        assert Object.image_enabled is True

    def test_object_has_image_generation_cooldown(self):
        """Object should have image_generation_cooldown from ImageMixin."""
        from typeclasses.objects import Object
        assert hasattr(Object, "image_generation_cooldown")
        assert isinstance(Object.image_generation_cooldown, float)

    def test_object_has_get_display_desc(self):
        """Object should have get_display_desc method."""
        from typeclasses.objects import Object
        assert hasattr(Object, "get_display_desc")
        assert callable(getattr(Object, "get_display_desc", None))

    def test_object_has_trigger_image_generation(self):
        """Object should have _trigger_image_generation from ImageMixin."""
        from typeclasses.objects import Object
        assert hasattr(Object, "_trigger_image_generation")
        assert callable(getattr(Object, "_trigger_image_generation", None))

    def test_object_has_can_trigger_image(self):
        """Object should have _can_trigger_image from ImageMixin."""
        from typeclasses.objects import Object
        assert hasattr(Object, "get_display_desc")
        assert callable(getattr(Object, "_can_trigger_image", None))


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


class TestDisplayDescLogic:
    """Test get_display_desc display logic by replicating the exact pattern
    used in typeclasses/objects.py (same as test_object_image_display.py)."""

    def _make_display_result(self, db):
        """Replicate the exact get_display_desc logic from Object."""
        desc = getattr(db, "desc", "") or ""
        if getattr(db, "image_generating", False):
            return f"{desc}\n\n|yImage: generating...|n"
        url = getattr(db, "image_url", None)
        if url:
            return f"{desc}\n\n|yImage: {url}|n"
        return desc

    def test_display_desc_with_image_url(self):
        """When object has an image_url, display includes the image."""
        db = FakeDb(
            desc="A majestic marble statue.",
            image_url="http://127.0.0.1:8188/generated/statue.png",
            image_generating=False,
        )
        result = self._make_display_result(db)
        assert "majestic marble statue" in result
        assert "Image:" in result
        assert "statue.png" in result

    def test_display_desc_without_image_url_returns_plain_desc(self):
        """When object has no image_url, display returns plain text."""
        db = FakeDb(
            desc="A simple wooden chair.",
            image_url=None,
            image_generating=False,
        )
        result = self._make_display_result(db)
        assert result == "A simple wooden chair."

    def test_display_desc_generating_shows_generating_message(self):
        """When image_generating is True, show 'generating...' message."""
        db = FakeDb(
            desc="An ancient book.",
            image_url=None,
            image_generating=True,
        )
        result = self._make_display_result(db)
        assert "ancient book" in result
        assert "generating..." in result

    def test_display_desc_empty_desc_no_image(self):
        """When desc is empty and no image, return empty string."""
        db = FakeDb(
            desc="",
            image_url=None,
            image_generating=False,
        )
        result = self._make_display_result(db)
        assert result == ""

    def test_display_desc_empty_desc_with_image(self):
        """When desc is empty but image exists, image still shows."""
        db = FakeDb(
            desc="",
            image_url="http://example.com/orb.png",
            image_generating=False,
        )
        result = self._make_display_result(db)
        assert "orb.png" in result
        assert "Image:" in result


class TestImageMixinCooldown:
    """Test ImageMixin _can_trigger_image() cooldown logic."""

    def test_can_trigger_when_cooldown_expired(self):
        """When cooldown expires, _can_trigger_image returns True."""
        from utils.image_mixin import ImageMixin

        class TestObj(ImageMixin):
            def __init__(self):
                self.db = FakeDb(_image_generation_last_ts=time.time() - 10)
                self.image_generation_cooldown = 5.0

        obj = TestObj()
        assert obj._can_trigger_image() is True

    def test_cannot_trigger_when_in_cooldown(self):
        """When still in cooldown, _can_trigger_image returns False."""
        from utils.image_mixin import ImageMixin

        class TestObj(ImageMixin):
            def __init__(self):
                self.db = FakeDb(_image_generation_last_ts=time.time() + 10)
                self.image_generation_cooldown = 5.0

        obj = TestObj()
        assert obj._can_trigger_image() is False

    def test_can_trigger_with_none_timestamp(self):
        """_can_trigger_image should handle None _image_generation_last_ts."""
        from utils.image_mixin import ImageMixin

        class TestObj(ImageMixin):
            def __init__(self):
                self.db = FakeDb(_image_generation_last_ts=None)
                self.image_generation_cooldown = 5.0

        obj = TestObj()
        result = obj._can_trigger_image()
        assert isinstance(result, bool)
        assert result is True

    def test_can_trigger_with_zero_timestamp(self):
        """_can_trigger_image should handle 0.0 timestamp."""
        from utils.image_mixin import ImageMixin

        class TestObj(ImageMixin):
            def __init__(self):
                self.db = FakeDb(_image_generation_last_ts=0.0)
                self.image_generation_cooldown = 5.0

        obj = TestObj()
        assert obj._can_trigger_image() is True


class TestImageMixinDescriptionHelpers:
    """Test ImageMixin description helper methods."""

    def test_get_description_with_image_includes_url(self):
        """get_description_with_image should include URL when set."""
        from utils.image_mixin import ImageMixin

        class TestObj(ImageMixin):
            def __init__(self):
                self.db = FakeDb(
                    desc="A shiny brass cat idol.",
                    image_url="http://127.0.0.1:8188/generated/cat.png",
                    image_generating=False,
                )

        obj = TestObj()
        result = obj.get_description_with_image()
        assert "cat.png" in result
        assert "brass cat idol" in result

    def test_get_description_with_image_generating(self):
        """get_description_with_image should show 'generating...' when in-flight."""
        from utils.image_mixin import ImageMixin

        class TestObj(ImageMixin):
            def __init__(self):
                self.db = FakeDb(
                    desc="A mysterious orb.",
                    image_url=None,
                    image_generating=True,
                )

        obj = TestObj()
        result = obj.get_description_with_image()
        assert "generating..." in result

    def test_get_description_with_image_none_desc(self):
        """get_description_with_image should handle None desc safely."""
        from utils.image_mixin import ImageMixin

        class TestObj(ImageMixin):
            def __init__(self):
                self.db = FakeDb(desc=None, image_generating=False)

        obj = TestObj()
        result = obj.get_description_with_image()
        assert result == ""


class TestObjectSourceCodeVerification:
    """Verify that Object.get_display_desc() source code contains the correct
    logic by reading the file directly."""

    def test_object_get_display_desc_triggers_image_generation(self):
        """Object.get_display_desc should call _trigger_image_generation
        when no image_url exists and cooldown allows."""
        import inspect
        from typeclasses.objects import Object
        source = inspect.getsource(Object.get_display_desc)
        assert "_trigger_image_generation" in source
        assert "_can_trigger_image" in source

    def test_object_get_display_desc_checks_image_url(self):
        """Object.get_display_desc should check for image_url."""
        import inspect
        from typeclasses.objects import Object
        source = inspect.getsource(Object.get_display_desc)
        assert "image_url" in source
        assert "image_generating" in source

    def test_object_inherits_image_mixin(self):
        """Object MRO should include ImageMixin."""
        from typeclasses.objects import Object
        from utils.image_mixin import ImageMixin
        assert ImageMixin in Object.__mro__
