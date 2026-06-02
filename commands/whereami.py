# commands/whereami.py
from evennia import Command


class CmdWhereami(Command):
    """
    Show a full overview of your current location.

    Usage:
      whereami

    Displays:
      - Room name and dbref
      - Room description
      - Exits
      - Notable objects in the room
      - Other characters present
    """
    key = "whereami"
    aliases = ["here", "survey"]
    locks = "cmd:all()"
    help_category = "Building"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("You are in the void — nowhere at all.")
            return

        lines = []
        lines.append(f"|w{room.key} (#{room.id})|n")
        desc = getattr(room.db, "desc", "") or "No description yet."
        lines.append(f"{desc}")

        # Exits
        exits = [ex for ex in room.exits if hasattr(ex, "destination") and ex.destination]
        if exits:
            exit_names = ", ".join(ex.key for ex in exits)
            lines.append(f"\n|yExits:|n {exit_names}")
        else:
            lines.append("\n|yExits:|n None (a dead end)")

        # Other characters
        characters = [
            c for c in room.contents
            if c != caller
            and not hasattr(c, "destination")  # not an exit
            and str(getattr(c, "__class__", None)) != "Object"
        ]
        if not characters:
            # Try a broader check: anything that inherits from Character
            from evennia.utils.utils import inherits_from
            characters = [
                c for c in room.contents
                if c != caller
                and inherits_from(c, "evennia.objects.objects.DefaultCharacter")
            ]

        if characters:
            char_names = ", ".join(c.key for c in characters)
            lines.append(f"|yOthers here:|n {char_names}")

        # Notable objects (not exits, not characters)
        from evennia.utils.utils import inherits_from
        objects = [
            c for c in room.contents
            if c != caller
            and not inherits_from(c, "evennia.objects.objects.DefaultExit")
            and not inherits_from(c, "evennia.objects.objects.DefaultCharacter")
        ]
        if objects:
            obj_names = ", ".join(c.key for c in objects)
            lines.append(f"|yObjects:|n {obj_names}")
        else:
            lines.append("|yObjects:|n The room is sparsely furnished.")

        # Memory (recent speech)
        memory = getattr(room.db, "memory", [])
        if memory:
            lines.append("\n|cRecent whispers:|n")
            for entry in memory[-5:]:
                who = entry.get("who", "Someone")
                msg = entry.get("msg", "")
                lines.append(f"  {who}: {msg}")

        caller.msg("\n".join(lines))
