"""
Inventory command — list items the character is carrying.

Usage:
  inventory
  inv
  pack
  gear

Examples:
  inventory
  inv
  pack

Features:
- Lists all objects in the character's inventory
- Shows a clean, numbered list of carried items
- Works with objects previously picked up via the Take command
- Handles empty inventory with a flavor message

Help category: Inventory
"""

from evennia import Command


class CmdInventory(Command):
    """
    List the items you are currently carrying.

    Usage:
      inventory
      inv
      pack
      gear

    Shows everything you've picked up and haven't dropped yet.
    """

    key = "inventory"
    aliases = ["inv", "pack", "gear"]
    locks = "cmd:all()"
    help_category = "Inventory"

    def func(self):
        caller = self.caller
        items = caller.contents

        # Filter out exits and other non-inventory objects
        carried = [
            obj for obj in items
            if obj.is_character or not obj.is_exit
        ]

        if not carried:
            caller.msg("|yYour pack is light.|n You're carrying nothing but the air on your shoulders.")
            return

        caller.msg("|wYour inventory:|n")
        for i, obj in enumerate(carried, 1):
            name = obj.key or "unnamed object"
            shortdesc = getattr(obj.db, "shortdesc", None)
            if shortdesc:
                line = f"  |c{i}.|n {name} — |y{shortdesc}|n"
            else:
                line = f"  |c{i}.|n {name}"
            caller.msg(line)

        total = len(carried)
        caller.msg(f"\n|wTotal: {total} item{'s' if total != 1 else ''}|n")
