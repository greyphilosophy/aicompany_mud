"""
Whisper command — private messaging between characters in the same room.

Usage:
  whisper <character> <message>
  w <character> <message>

Example:
  whisper Alice I'll meet you at the tavern at noon
  w Bob pass the salt

Features:
- Private messages to characters sharing your room
- Auto-detects the only other character in the room (if just one other)
- Messages appear as styled whispers for the target
- Integrates with room speech buffer for LLM context

Aliases: w
Help category: Social
"""

from evennia import Command


class CmdWhisper(Command):
    """
    Whisper a private message to another character in the room.

    Usage:
      whisper <character> <message>
      w <character> <message>

    If there is only one other character in the room, you can omit the
    target name:

      whisper Hi there

    Whispers are delivered privately — only the target character sees the
    message text.
    """

    key = "whisper"
    aliases = ["w"]
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            caller.msg("You're nowhere — there's no one to whisper to.")
            return

        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: whisper <character> <message>")
            return

        # Get other characters in the room
        others = [
            obj for obj in room.contents
            if obj is not caller
            and hasattr(obj, "is_character") and obj.is_character
        ]

        if not others:
            caller.msg("You're alone here — no one to whisper to.")
            return

        # If only one other character, treat the whole args as the message
        if len(others) == 1:
            target = others[0]
            message = args
        else:
            # First token is the target name, rest is the message
            parts = args.split(None, 1)
            target_name = parts[0]
            message = parts[1] if len(parts) > 1 else ""

            # Try to find the target
            target = self._find_character(room, target_name, caller)

            if target is None:
                # Maybe the user just typed a message and there's only one other char
                # Try matching against the one other character by first token as partial match
                match = None
                for o in others:
                    if (o.name or "").lower().startswith(target_name.lower()):
                        if match is not None:
                            match = None  # ambiguous
                            break
                        match = o

                if match is not None:
                    # Treat the original args as the message
                    target = match
                    message = args
                else:
                    caller.msg(
                        f"No character named '{target_name}' in the room.\n"
                        f"Characters here: {', '.join(o.name for o in others)}"
                    )
                    return

        # Send the whisper to the target
        target.msg(
            f"\x1b[36m{caller.name} whispers to you: {message}\x1b[0m"
        )

        # Confirmation to sender
        caller.msg(f"You whisper to {target.name}: {message}")

        # Notify the room's LLM context about this social interaction
        if hasattr(room, "handle_speech"):
            try:
                room.handle_speech(
                    caller,
                    f"[whispers to {target.name}: {message}]"
                )
            except Exception:
                pass

    def _find_character(self, room, name, caller):
        """Find a character in the room by name (case-insensitive exact match)."""
        low = name.lower()
        for obj in room.contents:
            if obj is not caller and hasattr(obj, "is_character") and obj.is_character:
                if (obj.name or "").lower() == low:
                    return obj
        return None
