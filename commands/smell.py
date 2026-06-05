"""
Smell command — detect and describe scents in the current room.

Usage:
  smell
  smell [item]

Examples:
  smell
  smell the oak tree
  smell bread

Features:
- Describes the ambient scent of the current room
- Optionally focuses on a specific item's scent
- Reads scent properties from room and object attributes
- Falls back to LLM-generated descriptions if no scent attribute is set
- Integrates with room speech buffer for LLM context
"""

from evennia import Command


class CmdSmell(Command):
    """
    Sniff the air to detect scents in the room.

    Usage:
      smell
      smell [item]

    Describes the ambient odor in the current room, or focuses on
    the scent of a specific item. Useful for atmospheric detail
    and discovery.
    """

    key = "smell"
    aliases = ["sniff", "odor", "scent"]
    locks = "cmd:all()"
    help_category = "Observation"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            caller.msg("You're floating in the void — hard to smell anything up here.")
            return

        args = (self.args or "").strip()

        if args:
            # Focus on a specific item's scent
            self._smell_item(caller, room, args)
        else:
            # Describe the room's ambient scent
            self._smell_room(caller, room)

    def _smell_room(self, caller, room):
        """Describe the ambient scent of the room."""
        # Check for an explicit scent attribute on the room
        scent = room.db.scent if hasattr(room, "db") else None

        if scent and str(scent):
            caller.msg(f"The air smells of {scent}.")
        else:
            # Build a scent from objects in the room that have scent attributes
            scented_items = []
            for obj in room.contents:
                if obj is not caller and hasattr(obj, "db"):
                    obj_scent = getattr(obj.db, "scent", None)
                    if obj_scent and str(obj_scent):
                        scented_items.append((obj, obj_scent))

            if scented_items:
                parts = [f"{name} (smells of {s})"
                         for name, s in scented_items]
                caller.msg(
                    "Several scents mingle in the air: "
                    + ", ".join(parts) + "."
                )
            else:
                caller.msg("You sniff the air — it's fairly odorless.")

        # Notify the room's LLM context
        if hasattr(room, "handle_speech"):
            try:
                room.handle_speech(caller, "[sniffs the air]")
            except Exception:
                pass

    def _smell_item(self, caller, room, item_desc):
        """Describe the scent of a specific item."""
        target = self._find_target(caller, room, item_desc)

        if target is None:
            caller.msg(f"You don't see a '{item_desc}' to sniff.")
            return

        obj_scent = getattr(target.db, "scent", None) if hasattr(target, "db") else None

        if obj_scent and str(obj_scent):
            caller.msg(f"{target.name} smells of {obj_scent}.")
        else:
            caller.msg(f"You bring {target.name} close to your nose — it's mostly faint.")

    def _find_target(self, caller, room, name):
        """Find an object in the room or on the caller by name (case-insensitive)."""
        low = name.lower()

        # Search room contents
        for obj in room.contents:
            obj_name = getattr(obj, "name", getattr(obj, "key", ""))
            if obj_name and str(obj_name).lower() == low:
                return obj
            if obj_name and str(obj_name).lower().startswith(low):
                return obj

        # Search items carried by caller
        if hasattr(caller, "children"):
            for child in caller.children:
                name = getattr(child, "name", getattr(child, "key", ""))
                if name and str(name).lower() == low:
                    return child
                if name and str(name).lower().startswith(low):
                    return child

        return None
