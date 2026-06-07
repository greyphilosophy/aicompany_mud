"""
Clap command: applaud or cheer for someone (or something) in the room.

Usage:
  clap <character>      — clap for a character
  clap <text>            — clap with a reason (e.g., "clap brilliant speech")
  clap all              — clap for everyone in the room
  clap                  — clap in general (e.g., for an event)

This adds a light social interaction for showing appreciation,
celebrating achievements, or acknowledging someone's action.

Examples:
  clap Elara
  clap Elara for that brilliant speech
  clap all
  clap

Clapping is broadcast to the room so others can share in the moment.
"""

from evennia import Command


class CmdClap(Command):
    """
    Clap or cheer for someone in the room.

    Usage:
      clap <character>      — clap for a character
      clap <text>          — clap with a custom message
      clap all             — clap for everyone in the room
      clap                 — clap in general

    Examples:
      clap Elara
      clap Elara for saving the kingdom
      clap all
      clap
    """
    key = "clap"
    aliases = ["applaud", "cheer"]
    locks = "cmd:all()"
    help_category = "Social"

    CHEER_MESSAGES = [
        "claps enthusiastically.",
        "gives a warm round of applause.",
        "claps with genuine appreciation.",
        "breaks into enthusiastic applause.",
        "claps slowly, deliberately.",
        "applauds with a smile.",
        "gives three sharp, approving claps.",
    ]

    def func(self):
        caller = self.caller
        room = caller.location
        args = (self.args or "").strip()

        if not args:
            # General clap — no target, just applause in the room
            self._do_general_clap(caller, room)
            return

        parts = args.split(None, 1)
        target_name = parts[0].lower()
        custom_text = parts[1] if len(parts) > 1 else None

        # Clap for everyone in the room
        if target_name == "all":
            targets = [o for o in room.contents if o != caller and o.name]
            if not targets:
                caller.msg("You are alone in the room — clap for yourself instead.")
                self._do_general_clap(caller, room)
                return
            for target in targets:
                self._do_clap_for(caller, target, custom_text)
            caller.msg("You applaud everyone in the room.")
            return

        # Search for a single character in the room
        matches = [o for o in room.contents if o != caller and o.name.lower() == target_name]
        if not matches:
            # If not found, treat the whole args as a general clap with reason
            self._do_general_clap(caller, room, args)
            return

        target = matches[0]
        self._do_clap_for(caller, target, custom_text)
        caller.msg(f"You applaud {target.key}.")

    def _do_general_clap(self, caller, room, reason=None):
        """Broadcast a general clap/applause to the room."""
        import random
        action = random.choice(self.CHEER_MESSAGES)

        if reason:
            msg = f"{caller.key} claps — {reason}."
        else:
            msg = f"{caller.key} {action}"

        for obj in room.contents:
            if obj != caller:
                obj.msg(msg)

    def _do_clap_for(self, caller, target, reason=None):
        """Send a clap/applause directed at a specific character."""
        import random
        room = caller.location
        action = random.choice(self.CHEER_MESSAGES)

        if reason:
            msg = f"{caller.key} applauds {target.key} — {reason}."
        else:
            msg = f"{caller.key} {action} {target.key}."

        target.msg(f"{caller.key} applauds you!" + (f" — {reason}" if reason else ""))
        for obj in room.contents:
            if obj != caller and obj != target:
                obj.msg(msg)
