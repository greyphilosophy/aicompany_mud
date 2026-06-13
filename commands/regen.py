# commands/regen.py
"""
Regenerate an AI image for a room or object.

Usage:
  regen            - Regenerate image for current room
  regen name       - Regenerate image for a named object
  regen #dbref     - Regenerate image for an object by dbref
"""

from evennia import Command


class CmdRegen(Command):
    """
    Regenerate an AI image for the current room or a named object.

    Usage:
      regen           - Generate image for current room
      regen name      - Generate image for an object by name
      regen #dbref    - Generate image for an object by dbref

    Examples:
      regen
      regen keycard
      regen #42
    """
    key = "regen"
    aliases = ["regenerate"]
    locks = "cmd:all()"
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
            # Build prompt from room key + description
            desc = getattr(room, "description", None)
            if desc:
                desc = desc.split("\n\n")[0] if "\n\n" in desc else desc
            else:
                desc = room.key
            prompt = f"{room.key}: {desc}"

            result = generate_room_image(prompt)
            if result:
                return f"Room image generated for {room.key}! URL: {result}"
            else:
                return "Image was generated but the URL came back empty."
        except Exception as e:
            return f"Generation failed: {e}"

    def _generate_object(self, obj_ref: str):
        """Generate an image for an object (by name or #dbref)."""
        backend = self._get_backend()
        if not backend:
            return "FLUX.2 server is not running or the backend is down."

        # Resolve: #dbref is direct, otherwise search by name
        if obj_ref.startswith("#") and obj_ref[1:].isdigit():
            from evennia.utils.search import search_object
            results = search_object(obj_ref)
            if not results:
                return f"No object found for dbref {obj_ref}."
            obj = results[0]
        else:
            room = self.caller.location
            if not room:
                return "You are nowhere (no current room)."
            # Search in room contents first, then global
            obj = room.search(obj_ref)
            if not obj:
                from evennia.utils.search import search_object
                results = search_object(obj_ref, typeclass="typeclasses.objects.Object")
                if results:
                    obj = results[0]
                else:
                    return f"No object named '{obj_ref}' found."

        try:
            from utils.image_generation import generate_object_image
            result = generate_object_image(obj.key, obj.key)
            if result:
                return f"Image generated for {obj.key} ({obj.dbref})! URL: {result}"
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

        # Argument provided: try it as an object reference
        if args.startswith("#") and args[1:].isdigit():
            # Direct dbref
            result = self._generate_object(args)
            self.caller.msg(result)
            return

        # Plain name — search for it
        result = self._generate_object(args)
        self.caller.msg(result)
