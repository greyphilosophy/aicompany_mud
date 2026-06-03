# utils/image_mixin.py
"""
ImageMixin for Evennia typeclasses.

Centralized image display: any room or object that inherits this mixin
automatically appends its generated image URL to its description.

Image generation is triggered by shorthand helpers that delegate to
utils/image_generation.py so all backend configuration lives in one place.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ImageMixin:
    """
    Evennia typeclass mixin for AI-generated images.

    Attributes:
        image_url: str | None — the URL of the most recent generated image
        image_generating: bool — whether a generation is in-flight
        image_generation_cooldown: float — seconds between room image generations
        _image_generation_last_ts: float — timestamp of last generation trigger

    Subclass hooks:
        _trigger_room_image(): called when a room image should be generated
        _trigger_object_image(obj): called when an object image should be generated

    The actual generation is done via utils/image_generation.py.
    """

    # Image generation settings
    image_enabled: bool = True
    image_generation_cooldown: float = 5.0  # seconds between triggers

    def at_object_creation(self):
        super().at_object_creation()
        # Initialize image state
        if not hasattr(self, "db"):
            return
        self.db.image_url = None
        self.db.image_generating = False
        self.db._image_generation_last_ts = 0.0

    def _is_image_generating(self) -> bool:
        return getattr(self.db, "image_generating", False)

    def _can_trigger_image(self) -> bool:
        """Check if we're past the cooldown."""
        import time
        last = self.db._image_generation_last_ts
        if last is None:
            last = 0.0
        return (time.time() - last) >= self.image_generation_cooldown

    def _trigger_image_generation(self, prompt: str, subject_type: str = "room") -> None:
        """
        Trigger asynchronous image generation via utils/image_generation.py.

        Delegates to the central helper so all backend configuration
        lives in one place.
        """
        if not self.image_enabled:
            return

        if not self._can_trigger_image():
            return

        import time
        self.db._image_generation_last_ts = time.time()

        from twisted.internet.threads import deferToThread

        def _generate():
            try:
                from utils.image_generation import generate_room_image

                result = generate_room_image(prompt)
                if result is not None:
                    self.db.image_url = result

                self.db.image_generating = False
                return result

            except Exception as e:
                logger.warning(f"[ImageMixin] Generation failed: {e}")
                self.db.image_generating = False
                return None

        self.db.image_generating = True
        deferToThread(_generate)

    def _trigger_object_image(self, obj) -> None:
        """
        Trigger an image for a child object (prop, creature, etc.).

        Delegates to utils/image_generation.py so backend configuration
        is centralized.
        """
        if not self._can_trigger_image():
            return

        import time
        self.db._image_generation_last_ts = time.time()

        from twisted.internet.threads import deferToThread

        def _generate():
            try:
                from utils.image_generation import generate_object_image

                shortdesc = getattr(obj.db, "shortdesc", "")
                result = generate_object_image(
                    object_key=obj.key,
                    object_desc=getattr(obj.db, "desc", ""),
                    shortdesc=shortdesc,
                )
                if result is not None:
                    obj.db.image_url = result

                return result

            except Exception as e:
                logger.warning(f"[ImageMixin] Object image failed: {e}")
                return None

        deferToThread(_generate)

    def get_image_html(self) -> str:
        """
        Return HTML image tag (for webclient) or plain URL for telnet.
        Subclasses can override this for different display formats.
        """
        url = getattr(self.db, "image_url", None)
        if url:
            return f'<img src="{url}" width="600" style="border-radius: 8px;">'
        return ""

    def get_description_with_image(self) -> str:
        """
        Get the object/room description with the image appended.

        Default: appends image URL. Override for custom formatting.
        """
        desc = getattr(self.db, "desc", "")
        if getattr(self.db, "image_generating", False):
            return f"{desc}\n\n|yImage: generating...|n"
        url = getattr(self.db, "image_url", None)
        if url:
            return f"{desc}\n\n|yImage: {url}|n"
        return desc or ""
