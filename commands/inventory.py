"""Retrieve a direct inventory item using normal pickup and movement hooks."""

import re

from evennia.commands.default.general import CmdGet as DefaultCmdGet
from evennia.objects.objects import DefaultCharacter


class CmdGet(DefaultCmdGet):
    """Pick up an item from the room or a nearby holder.

    Usage:
      get <item>
      get <item> from <holder>

    The holder's get_from lock and the item's get lock must allow access.
    NPCs and objects allow inventory retrieval by default; other Characters
    require an explicit get_from lock granting access.
    """

    def func(self):
        parts = re.split(r"\s+from\s+", self.args, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 1:
            return super().func()
        item_name, holder_name = (part.strip() for part in parts)
        caller = self.caller
        if not item_name or not holder_name or self.number > 1:
            caller.msg("Usage: get <one item> from <holder>")
            return

        def nearby(holder):
            return (
                holder == caller
                or holder.location == caller
                or (caller.location is not None and holder.location == caller.location)
            )

        candidates = list(caller.contents) + [caller]
        if caller.location:
            candidates += list(caller.location.contents)
        holder = caller.search(holder_name, candidates=candidates)
        if not holder:
            return
        if not nearby(holder):
            caller.msg("That holder is out of reach.")
            return

        def allowed():
            return holder.access(
                caller,
                "get_from",
                default=holder == caller or not isinstance(holder, DefaultCharacter),
            )

        if not allowed():
            caller.msg("You cannot take items from that holder.")
            return
        item = caller.search(item_name, candidates=list(holder.contents))
        if not item:
            return
        if item == caller or item.location != holder:
            caller.msg("That item is not available in the holder's inventory.")
            return
        if not item.access(caller, "get"):
            caller.msg(item.db.get_err_msg or "You can't get that.")
            return
        if not item.at_pre_get(caller):
            return
        # Hooks may change the world; never move an item from a stale source.
        if (
            not nearby(holder)
            or item.location != holder
            or not allowed()
            or not item.access(caller, "get")
        ):
            caller.msg("That item is no longer available to take.")
            return
        if not item.move_to(caller, quiet=True, move_type="get"):
            caller.msg("That can't be picked up.")
            return
        item.at_get(caller)
        caller.msg(
            f"You take {item.get_display_name(caller)} from {holder.get_display_name(caller)}."
        )
