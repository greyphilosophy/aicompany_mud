"""
Dream command: close your eyes and imagine in the room.

Usage:
  dream <text>      — dream or imagine something while in the room
  dream              — close your eyes and observe

A whimsical command for literary and atmospheric expressions.
When you dream, your words appear as italicized, ethereal text
visible to others in the room — perfect for daydreams, memories,
or poetic observations.

Examples:
  dream The sun paints golden streaks across the desk
  dream I remember the first day — all noise and new faces
  dream
"""

from evennia import Command


class CmdDream(Command):
    """
    Dream or imagine something in the current room.

    Usage:
      dream <text>      — dream or imagine something
      dream             — close your eyes and observe

    Dreaming is visible to others in the room as an ethereal,
    italicized text — a soft overlay of imagination on reality.
    """
    key = "dream"
    aliases = ["imagine", "fantasize"]
    locks = "cmd:all()"
    help_category = "Social"

    DREAM_PROMPTS = [
        "You close your eyes. The room fades to a soft blur...",
        "You let the world fall away, drifting into thought...",
        "Your eyes close. The sounds of the room soften...",
        "Stillness. You breathe, and the room dissolves...",
        "You look inward, letting the moment stretch...",
    ]

    def func(self):
        caller = self.caller
        room = caller.location
        args = (self.args or "").strip()

        if not args:
            prompt = self._random_choice(self.DREAM_PROMPTS)
            caller.msg(prompt)
            return

        dream_text = args.strip()
        caller.msg(
            "You close your eyes and imagine: " + dream_text
        )

        # Broadcast to others in the room
        for obj in room.contents:
            if obj != caller:
                obj.msg(
                    f"  *{caller.key} dreams: {dream_text}*"
                )

    def _random_choice(self, items):
        """Simple random selection without importing random."""
        import random
        return random.choice(items)
