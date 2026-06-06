"""
Read Command
============
Lets players read the full description of objects, exits, and characters
in the current room. Unlike examine (which shows metadata), read focuses
purely on the descriptive text — like reading a sign or studying an object.
"""

from evennia import Command
from evennia.utils.search import search_object
import re


class CmdRead(Command):
    """
    Read the description of something in the room.

    Usage:
      read <name>

    Examples:
      read sign
      read the brass plaque
      read #142
      read Alice
    """
    key = "read"
    aliases = ["rd", "read"]
    locks = "cmd:all()"
    help_category = "Looking"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("You are nowhere — nothing to read.")
            return

        args = (self.args or "").strip()
        if not args:
            caller.msg("What do you want to read?\n"
                        "Usage: read <name>")
            return

        # Strip leading articles ("the", "a", "an")
        clean = re.sub(r"^(the|a|an)\s+", "", args, flags=re.IGNORECASE).strip()
        if not clean:
            caller.msg("Usage: read <name>")
            return

        # Handle dbref (#NNN)
        if clean.startswith("#") and clean[1:].isdigit():
            matches = search_object(clean, location=room)
            if not matches:
                caller.msg(f"Nothing here matches {clean}.")
                return
            target = matches[0]
        else:
            # Search in the room for the name
            matches = search_object(clean, location=room)
            if not matches:
                # Case-insensitive key match
                low = clean.lower()
                matches = [
                    obj for obj in room.contents
                    if (obj.key or "").lower() == low or
                       low in [a.lower() for a in getattr(obj.aliases, "all", lambda: [])()]
                ]
            if not matches:
                # Fuzzy: substring of key
                fuzzy = [obj for obj in room.contents
                         if clean.lower() in (obj.key or "").lower()]
                if fuzzy:
                    matches = fuzzy
                else:
                    # List what's in the room
                    names = [obj.key for obj in room.contents
                             if obj.key and obj != caller]
                    if names:
                        caller.msg(f"Here I see: {', '.join(sorted(names))}")
                    else:
                        caller.msg("It's empty here — nothing to read.")
                    return

        target = matches[0]

        # Skip reading yourself
        if target == caller:
            caller.msg(f"You are {caller.key} — reading yourself is oddly introspective.")
            return

        # Gather readable text
        sd = getattr(target, "db", None)
        text_parts = []

        # Short description (primary readable content)
        if sd and sd.shortdesc:
            text_parts.append(sd.shortdesc)

        # Full description
        if sd and sd.desc:
            text_parts.append(sd.desc)

        # Pinned facts as "notes" on the object
        if sd:
            facts = getattr(target, "db_facts", None) or \
                    getattr(target, "db_pinned_facts", None) or []
            if facts:
                for f in facts:
                    if isinstance(f, dict):
                        text_parts.append(f.get("text", ""))
                    else:
                        text_parts.append(str(f))

        if not text_parts:
            caller.msg(f"{target.key} has little written on it — just a quiet presence here.")
            return

        caller.msg(f"|y{target.key}:|n\n" + "\n".join(text_parts))
