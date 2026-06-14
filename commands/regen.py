# commands/regen.py
"""
Regenerate an AI image for a room or object.

Usage:
  regen          - Regenerate image for current room
  regen name     - Regenerate image for a named object (current room only)

Requires builder lock. Does not accept dbref arguments (local search only).
"""
import concurrent.futures
import threading

from evennia import Command


class CmdRegen(Command):
    """
    Regenerate an AI image for the current room or a named object.

    Only searches for objects in the current room. Requires builder
    privilege to avoid resource burn from unprivileged players.

    Usage:
      regen          - Generate image for current room
      regen keycard  - Generate image for an object by name

    Examples:
      regen
      regen keycard
    """
    key = "regen"
    aliases = ["regenerate"]
    locks = "cmd:all()"
    help_category = "Building"

    @staticmethod
    def _generate_image(prompt: str, subject_type: str, subject_key: str):
        """Pure HTTP call to FLUX.2 server. Thread-safe, no Evennia state needed."""
        from evennia_ai_image_generator.backend.base import ImageGenerationRequest
        from utils.image_generation import _get_backend

        backend = _get_backend()
        if not backend:
            return None

        result = backend.generate(
            ImageGenerationRequest(
                subject_type=subject_type,
                subject_key=subject_key,
                prompt=prompt,
                mode="txt2img",
                width=1536,
                height=1024,
            )
        )
        return result.image_url

    def _on_room_done(self, room, prompt, future):
        """Callback: runs on reactor thread after image is generated."""
        try:
            url = future.result()
            if url:
                room.db.image_url = url
                self.caller.msg(f"Room image regenerated. [Image]({url})")
            else:
                self.caller.msg("FLUX.2 server is not reachable or returned no image.")
        except Exception as e:
            self.caller.msg(f"Generation failed: {e}")

    def _on_object_done(self, obj, future):
        """Callback: runs on reactor thread after image is generated."""
        try:
            url = future.result()
            if url:
                obj.db.image_url = url
                self.caller.msg(f"Image regenerated for {obj.key}. [Image]({url})")
            else:
                self.caller.msg("FLUX.2 server is not reachable or returned no image.")
        except Exception as e:
            self.caller.msg(f"Generation failed: {e}")

    def func(self):
        args = (self.args or "").strip()

        if not args:
            # No argument: target the current room
            room = self.caller.location
            if not room:
                self.caller.msg("You are nowhere.")
                return

            desc = getattr(room.db, "desc", None)
            if desc:
                desc = desc.split("\n\n")[0] if "\n\n" in desc else desc
            else:
                desc = room.key
            prompt = f"{room.key}: {desc}"

            self.caller.msg("Generating room image... please hold (up to 2 minutes).")
            # Offload the blocking HTTP call to a thread; callback runs on reactor thread
            future = _executor.submit(
                self._generate_image, prompt, "room", f"regen_room_{room.dbid}"
            )
            future.add_done_callback(lambda _: self._on_room_done(room, prompt, future))
            return

        # Argument provided: search in current room only
        room = self.caller.location
        if not room:
            self.caller.msg("You are nowhere (no current room).")
            return

        obj = room.search(args)
        if not obj:
            self.caller.msg(f"No object named '{args}' found in this room.")
            return

        self.caller.msg(f"Generating image for {obj.key}... please hold (up to 2 minutes).")
        future = _executor.submit(
            self._generate_image, obj.key, "object", f"regen_{obj.dbid}"
        )
        future.add_done_callback(lambda _: self._on_object_done(obj, future))


# Shared thread pool for FLUX.2 HTTP calls (bounded so they don't starve the reactor)
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
