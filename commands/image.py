# commands/image.py
"""
Image generation command — generates a new FLUX.2 image for a room or object.

Usage:
  imgen room                    Generate image for current room
  imgen room "a cozy tavern..." Generate image with custom prompt
  imgen object [name]          Generate image for a named object
  imgen object [name] "desc.." Generate image for an object with custom prompt
"""

from evennia import Command


class CmdImgGen(Command):
    """
    Generate a new AI image for a room or object.

    Usage:
      imgen room                - Generate from current room's description
      imgen room "prompt..."    - Generate from custom prompt
      imgen object [name]       - Generate from object's description
      imgen object [name] "prompt..." - Generate with custom prompt

    Examples:
      imgen room
      imgen room "spacious library with warm lighting, rows of bookshelves"
      imgen object keycard
      imgen object keycard "metal keycard with glowing blue LED"
    """
    key = "imgen"
    aliases = ["generate_image", "genimage"]
    locks = "cmd:all()"
    help_category = "Building"

    def _get_backend(self):
        """Get the image generation backend."""
        try:
            from utils.image_generation import _get_backend
            return _get_backend()
        except ImportError:
            return None

    def _generate_room(self, prompt: str) -> str:
        """Generate an image for the current room."""
        backend = self._get_backend()
        if not backend:
            return "FLUX.2 server is not running or the backend is down."

        try:
            from utils.image_generation import generate_room_image
            result = generate_room_image(prompt)
            if result:
                return f"Room image generated! URL: {result}"
            else:
                return "Image was generated but the URL came back empty."
        except Exception as e:
            return f"Generation failed: {e}"

    def _generate_object(self, obj_key: str, prompt: str) -> str:
        """Generate an image for a named object."""
        backend = self._get_backend()
        if not backend:
            return "FLUX.2 server is not running or the backend is down."

        # Find the object
        room = self.caller.location
        if not room:
            return "You are nowhere (no current room)."

        # Search in room contents first, then global
        obj = room.search(obj_key)
        if not obj:
            # Try searching more broadly
            from evennia.utils.search import search_object
            results = search_object(obj_key, typeclass="typeclasses.objects.Object")
            if results:
                obj = results[0]
            else:
                return f"No object named '{obj_key}' found here."

        try:
            from utils.image_generation import generate_object_image
            result = generate_object_image(obj.key, prompt)
            if result:
                return f"Image generated for {obj.key}! URL: {result}"
            else:
                return "Image was generated but the URL came back empty."
        except Exception as e:
            return f"Generation failed: {e}"

    def func(self):
        if not self.args:
            self.caller.msg(
                "Usage:\n"
                "  imgen room                (from room description)\n"
                "  imgen room \"prompt...\"    (custom prompt)\n"
                "  imgen object [name]       (from object description)\n"
                '  imgen object [name] "prompt..."  (custom prompt)'
            )
            return

        args = self.args.strip()
        parts = args.split(None, 1)

        if parts[0].lower() == "room":
            if len(parts) > 1:
                prompt = parts[1]
            else:
                room = self.caller.location
                if not room:
                    self.caller.msg("You are nowhere.")
                    return
                # Use the room's key and description as the prompt
                desc = getattr(room, "description", None)
                if desc:
                    # Remove image tags for a cleaner prompt
                    desc = desc.split("\n\n")[0] if "\n\n" in desc else desc
                else:
                    desc = room.key
                prompt = f"{room.key}: {desc}"
            
            self.caller.msg(f"Generating room image with prompt: {prompt}")
            result = self._generate_room(prompt)
            self.caller.msg(result)

        elif parts[0].lower() == "object":
            if len(parts) == 1:
                self.caller.msg("Usage: imgen object [name] [\"prompt...\"]")
                return
            
            rest = parts[1]
            # Split into object name and optional prompt
            # If there's a quoted string, use it as the prompt
            import shlex
            try:
                parsed = shlex.split(rest)
            except ValueError:
                parsed = rest.split()

            if not parsed:
                self.caller.msg("Object name is missing.")
                return

            if len(parsed) >= 2:
                obj_name = parsed[0]
                # Reconstruct the prompt from remaining parts
                # Try to find quoted portion
                if '"' in rest:
                    import re
                    match = re.search(r'"([^"]*)"', rest)
                    prompt = match.group(1) if match else " ".join(parsed[1:])
                else:
                    prompt = " ".join(parsed[1:])
            else:
                obj_name = parsed[0]
                # Find the object and use its key as prompt
                room = self.caller.location
                if room:
                    obj = room.search(obj_name)
                    if obj:
                        prompt = obj.key
                    else:
                        prompt = obj_name
                else:
                    prompt = obj_name

            self.caller.msg(f"Generating image for '{obj_name}': {prompt}")
            result = self._generate_object(obj_name, prompt)
            self.caller.msg(result)

        else:
            self.caller.msg(
                "Usage:\n"
                "  imgen room [\"prompt...\"]\n"
                "  imgen object [name] [\"prompt...\"]"
            )
