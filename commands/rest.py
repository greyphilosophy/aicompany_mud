"""
Rest command — take a moment to rest and recover in the room.

Usage:
  rest
  sit
  lounge

Examples:
  rest
  sit
  lounge

Features:
- Provides atmospheric rest messages based on surroundings
- Tracks consecutive rest turns for cumulative recovery
- Integrates with room speech buffer for LLM context
- Short aliases: sit, lounge

Help category: Social
"""

from evennia import Command


class CmdRest(Command):
    """
    Rest in your current location, recovering briefly.

    Usage:
      rest
      sit
      lounge

    Take a moment to catch your breath and observe the room.
    Resting multiple times in a row shows increasing relaxation.
    """

    key = "rest"
    aliases = ["sit", "lounge"]
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            caller.msg("You're nowhere — hard to rest without ground beneath you.")
            return

        # Track consecutive rests using a simple ndb counter
        prev_rests = getattr(caller.ndb, "rest_count", 0)
        caller.ndb.rest_count = prev_rests + 1
        rest_count = caller.ndb.rest_count

        # Determine if there's company
        others = [
            obj for obj in room.contents
            if obj is not caller
            and hasattr(obj, "is_character") and obj.is_character
        ]

        if rest_count == 1:
            if others:
                caller.msg(f"You settle into a comfortable spot. {others[0].name} glances over as you take a moment.")
            else:
                caller.msg("You find a comfortable spot and let your shoulders relax.")
            # Let others know you're resting
            for target in others:
                target.msg(f"\x1b[33m{caller.name} sits down to rest.\x1b[0m")
        elif rest_count == 2:
            caller.msg("You lean back, breathing a little deeper. The room seems quieter now.")
        elif rest_count == 3:
            caller.msg("Your eyes half-close. Time stretches, soft and easy.")
        elif rest_count == 4:
            caller.msg("You're nearly asleep. The room fades into a gentle rhythm.")
        else:
            caller.msg("Lost in quiet contemplation. Time is a suggestion now.")

        # Notify the room's LLM context
        if hasattr(room, "handle_speech"):
            try:
                if rest_count == 1:
                    room.handle_speech(caller, f"[{caller.name} sits down to rest]")
                else:
                    room.handle_speech(caller, f"[{caller.name} rests peacefully]")
            except Exception:
                pass
