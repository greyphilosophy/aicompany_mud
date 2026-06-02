# commands/whispers.py
"""
Whispers Command

Shows the room's recent speech memory as atmospheric "whispers" —
helpful for catching up when you join a room mid-conversation.

Usage:
  whispers
  whisper
  wisp
"""
from evennia import Command


class CmdWhispers(Command):
    """
    Show recent speech in the current room.

    Displays the room's memory buffer as whispered echoes,
    so you can catch up on what was said before you arrived
    or during a distracted moment.

    Usage:
      whispers
      whisper
      wisp
    """
    key = "whispers"
    aliases = ["whisper", "wisp", "echoes"]
    locks = "cmd:all()"
    help_category = "World"

    MAX_DISPLAY = 10  # show last N memories

    def func(self):
        room = self.caller.location
        if not room:
            self.caller.msg("You are nowhere — no whispers to hear.")
            return

        # Try to get memory from the room's SmartRoom system
        if hasattr(room, "db") and room.db.memory:
            mem = room.db.memory
            if not isinstance(mem, list):
                mem = list(mem)
            recent = mem[-self.MAX_DISPLAY:]
            if not recent:
                self.caller.msg("The room is quiet. No recent whispers.")
                return

            lines = []
            lines.append("|m— Recent whispers from the room —|n")
            for entry in recent:
                who = entry.get("who", "unknown")
                msg = entry.get("msg", "")
                lines.append(f"  |y{who}|n: |c{msg}|n")

            self.caller.msg("\n".join(lines))
        else:
            self.caller.msg("The room is quiet — no recent whispers to catch.")
