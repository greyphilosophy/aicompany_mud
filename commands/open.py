"""
Open Command
============
Lets players open objects in the current room — doors, chests, bottles,
windows, envelopes. Toggles between opened/closed states and optionally
reveals contents for container-type props.

This is a classic MUD verb that complements read, examine, and touch.
"""

from evennia import Command
from evennia.utils.search import search_object
import re


class CmdOpen(Command):
    """
    Open something in the current room.

    Usage:
      open <name>

    Examples:
      open door
      open the brass chest
      open #42
      open window

    Opens (or closes) props like doors, chests, bottles, and windows.
    Containers reveal their contents when opened. Already-open objects
    will be closed again.
    """
    key = "open"
    aliases = ["op", "unlock"]
    locks = "cmd:all()"
    help_category = "Interaction"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("You are nowhere — nothing to open.")
            return

        args = (self.args or "").strip()
        if not args:
            caller.msg("What do you want to open?\n"
                        "Usage: open <name>")
            return

        # Strip leading articles ("the", "a", "an")
        clean = re.sub(r"^(the|a|an)\s+", "", args, flags=re.IGNORECASE).strip()
        if not clean:
            caller.msg("Usage: open <name>")
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
                        caller.msg("It's empty here — nothing to open.")
                    return

        target = matches[0]

        # Check if the target is an exit (door-like)
        from evennia.utils.utils import inherits_from
        if inherits_from(target, "evennia.objects.objects.DefaultExit"):
            # Exiting through a door counts as "opening" it
            caller.msg(f"You push {target.key} open and step through.")
            caller.teleport(target.destination)
            return

        # Skip opening yourself
        if target == caller:
            caller.msg(f"You open yourself — you look like you feel more approachable now.")
            return

        # Handle the open/close toggle
        is_open = getattr(target.db, "is_open", False)

        if is_open:
            # Close it
            target.db.is_open = False
            caller.msg(f"You close {target.key}.")
            if hasattr(target.db, "contents") and target.db.contents:
                caller.msg(f"The contents disappear inside {target.key}.")
            return

        # Open it
        target.db.is_open = True
        caller.msg(f"You open {target.key} and peer inside.")

        # Check for contents (props inside the container)
        contents = getattr(target.db, "contents", None)
        if contents:
            if isinstance(contents, list):
                items = [str(c) for c in contents if c]
                if items:
                    caller.msg(f"Inside {target.key} you can see: {', '.join(items)}.")
            else:
                caller.msg(f"Inside {target.key} you can see: {contents}.")
        else:
            # Check if the object has child objects (Evennia's native nesting)
            children = getattr(target, "contents", None)
            if children:
                child_names = [c.key for c in children if c.key]
                if child_names:
                    caller.msg(f"Inside {target.key}: {', '.join(child_names)}.")
                else:
                    caller.msg(f"{target.key} is empty inside.")
            else:
                # Default: check for a description of the inside
                inner = getattr(target.db, "inside", None)
                if inner:
                    caller.msg(f"|wInside: {inner}|n")
                elif target.db.desc:
                    # Use the description as what you see inside
                    short = target.db.desc[:120]
                    caller.msg(f"|yInside: {short}…|n")
                else:
                    caller.msg(f"{target.key} is open, though its interior is hard to make out.")
