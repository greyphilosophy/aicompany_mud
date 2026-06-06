"""
Examine Command
===============
Lets players look more closely at objects, exits, and other characters
in the current room. Supports optional LLM-generated detail if the room
has an LLM available.
"""

from evennia import Command
from evennia.utils.search import search_object


class CmdExamine(Command):
    """
    Examine a thing in the room more closely.

    Usage:
      examine <name>

    Examples:
      examine lamp
      examine the brass cat idol
      examine #67
      examine Alice
    """
    key = "examine"
    aliases = ["ex", "examine"]
    locks = "cmd:all()"
    help_category = "Looking"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("You are nowhere — nothing to examine.")
            return

        args = (self.args or "").strip()
        if not args:
            caller.msg("What do you want to examine more closely?\n"
                        "Usage: examine <name>")
            return

        # Strip leading articles ("the", "a", "an")
        import re
        clean = re.sub(r"^(the|a|an)\s+", "", args, flags=re.IGNORECASE).strip()
        if not clean:
            caller.msg("Usage: examine <name>")
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
                # Try a looser name match (case-insensitive)
                low = clean.lower()
                matches = [
                    obj for obj in room.contents
                    if (obj.key or "").lower() == low or
                       low in [a.lower() for a in getattr(obj.aliases, "all", lambda: [])()]
                ]
            if not matches:
                # Fuzzy: check if it's a substring of any key
                fuzzy = [obj for obj in room.contents
                         if clean.lower() in (obj.key or "").lower()]
                if fuzzy:
                    matches = fuzzy
                else:
                    # List what's in the room
                    names = [obj.key for obj in room.contents
                             if obj.key and obj != caller]
                    if names:
                        caller.msg(f"I don't see '{clean}' here. "
                                    f"Present: {', '.join(sorted(names))}")
                    else:
                        caller.msg(f"I don't see '{clean}' here.")
                    return

        # Pick the best match (or show disambiguation)
        target = matches[0]

        # Skip examining yourself
        if target == caller:
            caller.msg("You squint at yourself in the dim light.\n"
                        f"You are {caller.key}.")
            return

        # Gather what we know about the target
        lines = []
        lines.append(f"= {target.key}")

        # Short description (if set)
        sd = getattr(target, "db", None)
        if sd and sd.shortdesc:
            lines.append(f"  {sd.shortdesc}")

        # Full description (if set)
        if sd and sd.desc:
            lines.append(f"  {sd.desc}")

        # Type hint (character, exit, object)
        from evennia import DefaultCharacter, DefaultExit, DefaultObject
        if isinstance(target, DefaultExit):
            lines.append(f"  An exit leading {target.key} "
                         f"to {target.destination.key if target.destination else 'nowhere'}.")
        elif isinstance(target, DefaultCharacter):
            lines.append(f"  {target.key} is here.")
            if sd and sd.flavor_text:
                lines.append(f"  {sd.flavor_text}")
        else:
            lines.append(f"  {target.key} is here.")

        # Notable property (for SmartRoom props)
        if sd and sd.notable:
            lines.append("  |wNotable|n — this object stands out in the room.")

        # Pinned facts (if the room tracks them)
        if sd:
            facts = getattr(target, "db_facts", None) or \
                    getattr(target, "db_pinned_facts", None) or []
            if facts:
                lines.append("  |wPinned facts:|n")
                for f in facts:
                    if isinstance(f, dict):
                        lines.append(f"    {f.get('text', '')}")
                    else:
                        lines.append(f"    {f}")

        # Image (if the target is an ImageMixin)
        if hasattr(target, "get_image_url"):
            img_url = target.get_image_url()
            if img_url:
                lines.append(f"  |yImage:|n {img_url}")

        caller.msg("\n".join(lines))
