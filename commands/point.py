"""
Point command — point at objects, characters, or exits in the room.

Usage:
  point [at] <object/character/exit>
  point <object/character/exit>

Examples:
  point the lantern
  point at the suspicious door
  point the guard
  point north

Features:
- Points at visible objects, characters, or exits in the current room
- Draws attention from nearby characters
- Supports partial name matching
- Integrates with room speech buffer for LLM context
- Aliases: point-at, indicate

Help category: Social
"""

from evennia import Command


class CmdPoint(Command):
    """
    Point at something in your current room.

    Usage:
      point [at] <object/character/exit>

    Point at objects, characters, or exits in your current room
    to draw attention to them. Nearby characters notice your gesture.
    """

    key = "point"
    aliases = ["point-at", "indicate"]
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            caller.msg("You're nowhere — hard to point at anything without surroundings.")
            return

        # Parse the target (handle "point at X" and "point X")
        args = self.args.strip()
        if not args:
            caller.msg("Point at what?")
            caller.msg("Usage: point [at] <object/character/exit>")
            return

        # Strip the optional "at" preposition
        args_lower = args.lower()
        if args_lower.startswith("at "):
            args = args[3:]
        elif args_lower == "at":
            caller.msg("Point at what?")
            return

        if not args:
            caller.msg("Point at what?")
            return

        # Search for the target among room contents and exits
        target = self._find_target(room, args, caller)

        if target:
            target_name = target.name or "it"
            caller.msg(f"You point toward {target_name}.\x1b[0m")
            # Let others know what you're pointing at
            others = [
                obj for obj in room.contents
                if obj is not caller
                and hasattr(obj, "is_character") and obj.is_character
            ]
            for target_char in others:
                target_char.msg(f"\x1b[33m{caller.name} points at {target_name}.\x1b[0m")
            # Notify the room's LLM context
            if hasattr(room, "handle_speech"):
                try:
                    room.handle_speech(caller, f"[{caller.name} points at {target_name}]")
                except Exception:
                    pass
        else:
            caller.msg(f"You gesture toward {args}, but nothing there seems to pay attention.")
            # Still broadcast the gesture — partial points are still social!
            others = [
                obj for obj in room.contents
                if obj is not caller
                and hasattr(obj, "is_character") and obj.is_character
            ]
            for target_char in others:
                target_char.msg(f"\x1b[33m{caller.name} gestures vaguely toward {args}.\x1b[0m")

    def _find_target(self, room, args, caller):
        """
        Search for a target among room contents and exits.
        Returns the matched object/exit or None.
        """
        args_lower = args.lower()
        args_lower_clean = args_lower.replace("the ", "").strip()

        # Search exits first (e.g., "point north")
        for exit in room.exits:
            exit_name = (exit.name or "").lower()
            if exit_name == args_lower_clean or exit_name == args_lower:
                return exit
            # Also check exit alias/key variations
            exit_aliases = [a.lower() for a in getattr(exit, "aliases", [])]
            if exit_name in exit_aliases:
                if args_lower_clean in exit_name:
                    return exit

        # Search room contents (objects and characters)
        for obj in room.contents:
            if obj is caller:
                continue
            obj_name = (obj.name or "").lower()
            if obj_name == args_lower_clean or obj_name == args_lower:
                return obj
            # Partial match (e.g., "lantern" matches "the rusty lantern")
            if args_lower_clean and args_lower_clean in obj_name:
                return obj
            # Check aliases
            obj_aliases = [a.lower() for a in getattr(obj, "aliases", [])]
            if args_lower_clean in obj_aliases:
                return obj

        return None
