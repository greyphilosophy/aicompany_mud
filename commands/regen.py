# commands/regen.py
"""
Regenerate an AI image for a room or object.

Usage:
  regen          - Regenerate image for current room
  regen name     - Regenerate image for a named object (current room only)

Requires builder lock. Does not accept dbref arguments (local search only).
"""

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
    locks = "cmd:builder()"
    help_category = "Building"

    def _get_backend(self):
        """Get the image generation backend."""
        try:
            from utils.image_generation import _get_backend
            return _get_backend()
        except ImportError:
            return None

    def _generate_room(self):
        """Generate an image for the current room."""
        backend = self._get_backend()
        if not backend:
            return "FLUX.2 server is not running or the backend is down."

        room = self.caller.location
        if not room:
            return "You are nowhere."

        try:
            from utils.image_generation import generate_room_image
            # Build prompt from room key + db.desc
            desc = getattr(room.db, "desc", None)
            if desc:
                desc = desc.split("\n\n")[0] if "\n\n" in desc else desc
            else:
                desc = room.key
            prompt = f"{room.key}: {desc}"

            result = generate_room_image(prompt)
            if result:
                room.db.image_url = result
                return f"Room image regenerated. [Image]({result})"
            else:
                return "Image was generated but the URL came back empty."
        except Exception as e:
            return f"Generation failed: {e}"

    def _generate_object(self, obj_ref: str):
        """Generate an image for an object in the current room."""
        backend = self._get_backend()
        if not backend:
            return "FLUX.2 server is not running or the backend is down."

        room = self.caller.location
        if not room:
            return "You are nowhere (no current room)."

        # Search only in the current room (avoid global dbref resolution)
        obj = room.search(obj_ref)
        if not obj:
            return f"No object named '{obj_ref}' found in this room."

        try:
            from utils.image_generation import generate_object_image
            result = generate_object_image(obj.key, obj.key)
            if result:
                obj.db.image_url = result
                return f"Image regenerated for {obj.key}. [Image]({result})"
            else:
                return "Image was generated but the URL came back empty."
        except Exception as e:
            return f"Generation failed: {e}"

    def func(self):
        args = (self.args or "").strip()

        if not args:
            # No argument: target the current room
            result = self._generate_room()
            self.caller.msg(result)
            return

        # Argument provided: search in current room only
        result = self._generate_object(args)
        self.caller.msg(result)
