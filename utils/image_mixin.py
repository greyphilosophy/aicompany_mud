# utils/image_mixin.py
"""
ImageMixin for Evennia typeclasses.

Centralized image display: any room or object that inherits this mixin
automatically appends its generated image URL to its description.

Image generation is triggered by subclass overrides (e.g., SmartRoom
triggers on description rewrites and prop creation).
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

    The actual generation is done via the evennia_ai_image_generator package.
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
        # Evennia's db handler returns None for missing attributes (not raising
        # AttributeError), so getattr(..., default) doesn't fire. Check both
        # missing and None explicitly.
        last = self.db._image_generation_last_ts
        if last is None:
            last = 0.0
        return (time.time() - last) >= self.image_generation_cooldown

    def _trigger_image_generation(self, prompt: str, subject_type: str = "room") -> None:
        """
        Trigger asynchronous image generation via the image generator backend.

        This is the main hook — subclasses call this when they want an image.
        The image URL gets stored in self.db.image_url and is automatically
        appended to descriptions.
        """
        if not self.image_enabled:
            return

        if not self._can_trigger_image():
            return  # Still in cooldown

        import time
        self.db._image_generation_last_ts = time.time()

        # Generate asynchronously on a thread
        from twisted.internet.threads import deferToThread

        def _generate():
            try:
                # Lazy import — allows graceful fallback when package is missing
                try:
                    from evennia_ai_image_generator.backend.comfyui_backend import (
                        ComfyUIBackend,
                    )
                except ImportError:
                    logger.debug("evennia_ai_image_generator not installed, skipping image gen")
                    self.db.image_generating = False
                    return None

                backend = ComfyUIBackend(
                    server_url="http://127.0.0.1:8188",
                    scheduler="karras",
                    sampler_name="euler",
                    default_steps=20,
                    default_cfg=7.5,
                    output_dir="generated",
                    media_url_base="https://game.test/media/generated",
                    timeout_s=120.0,
                    max_wait_s=600.0,
                )

                from evennia_ai_image_generator.backend.base import ImageGenerationRequest
                result = backend.generate(
                    ImageGenerationRequest(
                        subject_type=subject_type,
                        subject_key=self.key,
                        prompt=prompt,
                        negative_prompt="blurry, low-res, cartoon, text, watermark",
                        mode="txt2img",
                        width=1024,
                        height=1024,
                    )
                )

                # Store the result
                self.db.image_url = result.image_url
                self.db.image_generating = False
                return result.image_url

            except Exception as e:
                logger.warning(f"[ImageMixin] Generation failed: {e}")
                self.db.image_generating = False
                return None

        # Mark as in-flight
        self.db.image_generating = True
        deferToThread(_generate)

    def _trigger_object_image(self, obj) -> None:
        """
        Trigger an image for a child object (prop, creature, etc.).

        The image is generated and stored on the *object*, not the room.
        Uses the room's cooldown to avoid hammering ComfyUI.
        """
        if not self._can_trigger_image():
            return

        import time
        self.db._image_generation_last_ts = time.time()

        from twisted.internet.threads import deferToThread

        def _generate():
            try:
                try:
                    from evennia_ai_image_generator.backend.comfyui_backend import ComfyUIBackend
                except ImportError:
                    logger.debug("evennia_ai_image_generator not installed, skipping object image")
                    return None

                backend = ComfyUIBackend(
                    server_url="http://127.0.0.1:8188",
                    scheduler="karras",
                    sampler_name="euler",
                    default_steps=20,
                    default_cfg=7.5,
                    output_dir="generated",
                    media_url_base="https://game.test/media/generated",
                    timeout_s=120.0,
                    max_wait_s=600.0,
                )

                prompt = getattr(obj.db, "shortdesc", "") or obj.key
                from evennia_ai_image_generator.backend.base import ImageGenerationRequest
                result = backend.generate(
                    ImageGenerationRequest(
                        subject_type="object",
                        subject_key=obj.key,
                        prompt=prompt,
                        negative_prompt="blurry, low-res, cartoon, text, watermark",
                        mode="txt2img",
                        width=1024,
                        height=1024,
                    )
                )

                obj.db.image_url = result.image_url
                return result.image_url

            except Exception as e:
                logger.warning(f"[ImageMixin] Object image failed for #{obj.dbref}: {e}")
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
