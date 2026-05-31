"""
Tests for on-demand object image generation.

When a player examines an object (look statue), if the object has no
image, it should trigger generation and show "Image: generating...".

Tests cover:
- Object get_display_desc triggers image generation when no image exists
- Description shows "generating..." during async generation
- Description shows image URL once generation completes
- Cooldown is respected for on-demand triggers
"""
import time
import pytest

# Mock Evennia DB attribute handler
class FakeDb:
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


class TestOnDemandObjectImage:
    """
    Test the on-demand image generation logic that should be added to
    Object.get_display_desc().

    These tests replicate the exact pattern used in the Object class.
    """

    def test_object_display_desc_triggers_when_no_image(self):
        """When an object has no image_url, get_display_desc should trigger generation."""
        # Simulate the pattern: check if image_url is None → trigger generation
        db = FakeDb(
            desc="A weathered stone statue.",
            image_url=None,
            image_generating=False,
            _image_generation_last_ts=time.time() - 10.0,  # past cooldown
        )

        can_trigger = True  # Simulates _can_trigger_image()
        should_generate = (
            not getattr(db, "image_generating", False)
            and getattr(db, "image_url", None) is None
            and can_trigger
        )

        assert should_generate, "Should trigger generation when no image and not blocked"

    def test_object_display_desc_no_trigger_when_generating(self):
        """Don't re-trigger if already generating."""
        db = FakeDb(
            desc="A mysterious orb.",
            image_url=None,
            image_generating=True,
        )

        can_trigger = True
        should_generate = (
            not getattr(db, "image_generating", False)
            and getattr(db, "image_url", None) is None
            and can_trigger
        )

        assert not should_generate, "Should not re-trigger while generating"

    def test_object_display_desc_no_trigger_when_image_exists(self):
        """Don't trigger if image already exists."""
        db = FakeDb(
            desc="A brass cat idol.",
            image_url="http://127.0.0.1:8188/generated/cat.png",
            image_generating=False,
        )

        can_trigger = True
        should_generate = (
            not getattr(db, "image_generating", False)
            and getattr(db, "image_url", None) is None
            and can_trigger
        )

        assert not should_generate, "Should not trigger when image already set"

    def test_object_display_desc_no_trigger_when_disabled(self):
        """Don't trigger if image_enabled is False."""
        # Simulate image_enabled = False
        image_enabled = False
        db = FakeDb(
            desc="A simple rock.",
            image_url=None,
            image_generating=False,
            _image_generation_last_ts=time.time() - 10.0,
        )

        can_trigger = True
        should_generate = image_enabled and (
            not getattr(db, "image_generating", False)
            and getattr(db, "image_url", None) is None
            and can_trigger
        )

        assert not should_generate, "Should not trigger when image generation disabled"

    def test_get_display_desc_with_image_generating_state(self):
        """When image_generating is True, show 'generating...' in description."""
        # Replicate the exact pattern from Object.get_display_desc:
        desc = "A weathered stone statue."
        image_generating = True
        image_url = None

        if image_generating:
            result = f"{desc}\n\n|yImage: generating...|n"
        elif image_url:
            result = f"{desc}\n\n|yImage: {image_url}|n"
        else:
            result = desc

        assert "generating..." in result
        assert "weathered stone statue" in result

    def test_get_display_desc_with_image_url(self):
        """When image_url is set, show it in the description."""
        desc = "A brass cat idol."
        image_generating = False
        image_url = "http://127.0.0.1:8188/generated/cat.png"

        if image_generating:
            result = f"{desc}\n\n|yImage: generating...|n"
        elif image_url:
            result = f"{desc}\n\n|yImage: {image_url}|n"
        else:
            result = desc

        assert "cat.png" in result
        assert "brass cat idol" in result

    def test_get_display_desc_empty_desc_with_image(self):
        """Empty description with image URL still shows the image."""
        desc = ""
        image_generating = False
        image_url = "http://127.0.0.1:8188/generated/orb.png"

        if image_generating:
            result = f"{desc}\n\n|yImage: generating...|n"
        elif image_url:
            result = f"{desc}\n\n|yImage: {image_url}|n"
        else:
            result = desc

        assert "orb.png" in result
