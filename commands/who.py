"""
commands/who.py

Who command: list online characters and their current rooms.

Usage:
  who            — show all online characters
  who <name>     — filter by character name
"""

from evennia import Command
from evennia.utils import search


class CmdWho(Command):
    """
    List online characters and their locations.

    Usage:
      who
      who <name>    — filter by name (partial match)
      who #<dbref> — filter by dbref

    Shows each character's name, title, level, and current room.
    """
    key = "who"
    aliases = ["online", "players"]
    help_category = "Character"
    locks = "cmd:all()"

    def func(self):
        """Execute the who command."""
        caller = self.caller
        if not caller:
            return

        args = (self.args or "").strip()

        # Filter by name if provided
        if args:
            characters = search.search(caller, args,
                                       category=search.CHARACTERS)
            if not characters:
                caller.msg(f"No character matching '{args}'.")
                return
        else:
            # All characters (includes characters in rooms + in inventory)
            characters = search.search(caller, ".*",
                                       category=search.CHARACTERS, regex=True)

        # Gather stats for each character
        entries = []
        for char in characters:
            title = getattr(char.db, "title", "Novice")
            level = getattr(char.db, "level", 1)
            loc = char.location
            loc_name = loc.key if loc else "Nowhere"

            entries.append({
                "name": char.key,
                "title": title,
                "level": level,
                "location": loc_name,
            })

        if not entries:
            caller.msg("The world is quiet... no one is online.")
            return

        # Build formatted output
        # Column widths
        name_w = max(len(e["name"]) for e in entries)
        name_w = max(name_w, len("Name"))
        title_w = max(len(e["title"]) for e in entries)
        title_w = max(title_w, len("Title"))
        loc_w = max(len(e["location"]) for e in entries)
        loc_w = max(loc_w, len("Room"))

        lines = [
            "  ╔══════════════════════════════════════════════╗",
            "  ║              Online Characters              ║",
            "  ╚══════════════════════════════════════════════╝",
            "",
            f"  {'Name':<{name_w}} {'Title':<{title_w}} Level  Room",
            f"  {'-'*(name_w)} {'-'*(title_w)} -----  {'-'*30}",
        ]

        for e in entries:
            name_pad = e['name'].ljust(name_w)
            title_pad = e['title'].ljust(title_w)
            lines.append(
                f"  {name_pad} {title_pad} {e['level']:>5}  {e['location']}"
            )

        lines.append("")
        lines.append(f"  Total: {len(entries)} online")
        caller.msg("\n".join(lines))
