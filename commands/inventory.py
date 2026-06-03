"""
commands/inventory.py

Inventory command: list items your character is carrying.

Usage:
  inv                    — show your character's carried items
  inventory              — same, longer alias
  inv <character>       — peek at another character's inventory
"""

from evennia import Command
from evennia.utils.search import search_object


class CmdInventory(Command):
    """
    List the items you are carrying (or another character's inventory).

    Usage:
      inv
      inventory
      inv <character>

    Examples:
      inv
      inv Elara

    Shows each object at your location's contents that has this character
    as its holder, or simply lists all objects in your current room that
    are of type Object (not Exit, not Character).

    If a name is given, searches for a character and shows their inventory
    (objects located on that character).
    """
    key = "inv"
    aliases = ["inventory", "gear", "carrying"]
    help_category = "Character"
    locks = "cmd:all()"

    def _list_inventory(self, caller, container):
        """List objects held by or located at a container."""
        if not container:
            caller.msg("You find nothing to list.")
            return

        items = [
            obj for obj in container.contents
            if obj and not obj.exits and
            not obj.__class__.__name__ in ("Character", "DefaultCharacter")
            and not obj.key.lower() in ("exit", "door")
        ]

        if not items:
            caller.msg(f"No items in {container.key}.")
            return

        lines = [f"Carried items ({len(items)}):"]
        for obj in items:
            short = getattr(obj.db, "shortdesc", None)
            desc = getattr(obj.db, "desc", None)
            key = obj.key

            if short:
                display = short
            elif desc:
                # truncate first sentence of description
                display = desc.split(".")[0].strip() + "."
            else:
                display = key

            lines.append(f"  - {display}")

        caller.msg("\n".join(lines))

    def func(self):
        """Execute the inventory command."""
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            # Show caller's own inventory (objects at the same location
            # that aren't the caller or exits, plus anything the caller
            # is "holding" — convention: objects whose .location is the
            # character's home or current room).
            #
            # Simplest useful interpretation: list all non-exit, non-character
            # objects in the caller's current room.
            room = caller.location
            if not room:
                caller.msg("You are nowhere — nothing to carry.")
                return

            # Filter: objects in this room (not the caller, not exits, not other chars)
            items = [
                obj for obj in room.contents
                if obj and obj is not caller
                and not hasattr(obj, "exits")  # exits have .exits
                and not obj.__class__.__name__ in ("Character", "DefaultCharacter")
            ]

            if not items:
                caller.msg("You carry nothing.")
                return

            lines = [f"You carry {len(items)} item(s):"]
            for obj in items:
                short = getattr(obj.db, "shortdesc", None)
                desc = getattr(obj.db, "desc", None)
                key = obj.key

                if short:
                    display = short
                elif desc:
                    display = desc.split(".")[0].strip() + "."
                else:
                    display = key

                lines.append(f"  - {display}")

            caller.msg("\n".join(lines))

        else:
            # Look at another character's inventory
            matches = search_object(args)
            if not matches:
                caller.msg(f"No character named '{args}' found.")
                return

            target = matches[0]
            if target.location:
                self._list_inventory(caller, target.location)
            else:
                caller.msg(f"{target.key} is nowhere right now.")
