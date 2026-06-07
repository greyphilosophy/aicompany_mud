"""
Greet command: socially greet another character in the room.

Usage:
  greet <character>        — greet a character with a default greeting
  greet <character> <text> — greet with a custom message

This command adds a warm, structured social interaction for characters
sharing a room. It's more specific than |wemote|n and more personal
than |wshout|n.

Examples:
  greet Elara
  greet Elara Welcome, traveler!
  greet All
"""

from evennia import Command


class CmdGreet(Command):
    """
    Greet another character in the room.

    Usage:
      greet <character>        — send a default greeting
      greet <character> <text> — send a custom greeting
      greet all                — greet everyone in the room

    Examples:
      greet Elara
      greet Elara Welcome, traveler!
      greet all
    """
    key = "greet"
    aliases = ["salute", "welcome"]
    locks = "cmd:all()"
    help_category = "Social"

    DEFAULT_GREETINGS = [
        "'Hello there!",
        "gives a warm smile. 'How do you do?",
        "nods respectfully. 'Greetings!",
        "raises a hand. 'Well met!",
        "offers a bright smile. 'Welcome!",
    ]

    def _get_greeting(self):
        """Pick a random default greeting."""
        import random
        return random.choice(self.DEFAULT_GREETINGS)

    def func(self):
        caller = self.caller
        room = caller.location
        args = (self.args or "").strip()

        if not args:
            caller.msg("Greet whom? Use |wgreet <character>|n or |wgreet <character> <message>|n")
            return

        parts = args.split(None, 1)
        target_name = parts[0].lower()
        custom_text = parts[1] if len(parts) > 1 else None

        # Find the target in the room
        if target_name == "all":
            targets = [o for o in room.contents if o != caller and o.name]
            if not targets:
                caller.msg("You are alone in the room.")
                return
            for target in targets:
                self._do_greet(caller, target, custom_text)
            caller.msg(f"You greet everyone in the room.")
            return

        # Search for a single character
        matches = [o for o in room.contents if o != caller and o.name.lower() == target_name]
        if not matches:
            room_names = [o.name for o in room.contents if o != caller]
            if room_names:
                caller.msg(f"No one named '{target_name}' is here. I see: {', '.join(room_names)}")
            else:
                caller.msg("You are alone in the room — no one to greet.")
            return

        target = matches[0]
        self._do_greet(caller, target, custom_text)
        caller.msg(f"You greet {target.key}.")

    def _do_greet(self, caller, target, custom_text):
        """Send the greeting messages to the involved characters and onlookers."""
        if custom_text:
            msg = f"{caller.key} greets {target.key}: '{custom_text}'"
        else:
            greeting = self._get_greeting()
            msg = f"{caller.key} {greeting}"

        # Notify the target
        target.msg(f"{caller.key} greets you!")
        if custom_text:
            target.msg(f"They say: '{custom_text}'")

        # Broadcast to the rest of the room
        room = caller.location
        for obj in room.contents:
            if obj != caller and obj != target:
                obj.msg(msg)
