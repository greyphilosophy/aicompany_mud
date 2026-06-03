"""
commands/peek.py

Peek command: look inside an adjacent room or the room beyond an exit
without actually entering it.

Usage:
  peek [direction]     Peek through the named exit
  peek                Show your current room (like look)
  peek #<dbref>       Peek inside a specific room by dbref
  peek [direction] detail  Show occupants and notable objects

Helps players scout rooms before committing to a move, or check
on another room while traversing the world.
"""

from evennia import Command
from evennia.utils.search import search_object


class CmdPeek(Command):
    """
    Peek inside a room through an exit or by room dbref.

    Usage:
      peek [direction]     — look through the named exit
      peek                 — look at your current room
      peek #<dbref>       — peek inside a room by dbref
      peek [direction] detail — include occupants and notables

    Examples:
      peek north
      peek kitchen
      peek #42

    Shows the target room's description and a summary of what's there,
    without moving your character.
    """
    key = "peek"
    aliases = ["scout", "glimpse", "through"]
    help_category = "Navigation"
    locks = "cmd:all()"

    def _find_exit(self, room, name):
        """Find exit by key or alias, case-insensitive."""
        low = name.lower()
        for ex in room.exits:
            if (ex.key or "").lower() == low:
                return ex
            if low in [a.lower() for a in ex.aliases.all()]:
                return ex
        return None

    def _get_notable_objects(self, room):
        """Return list of notable object labels in the room."""
        notables = []
        for obj in room.contents:
            if not obj:
                continue
            if hasattr(obj, "destination"):
                continue
            if obj.db.notable:
                label = obj.db.shortdesc or obj.key
                notables.append(label)
        return notables

    def _get_occupants(self, room):
        """Return list of character keys in the room (excluding exits/props)."""
        occupants = []
        for obj in room.contents:
            if not obj:
                continue
            if hasattr(obj, "destination"):
                continue
            if obj.db.notable:
                continue
            if hasattr(obj, "accounts"):
                occupants.append(obj.key)
        return occupants

    def _render_room_summary(self, room, detail=False):
        """Render a room's contents as a peek summary."""
        desc = getattr(room, "get_display_desc", None)
        if desc:
            desc_text = desc(self.caller)
        else:
            desc_text = room.db.desc or ""

        lines = [f"|w{room.key} ({room.dbref})|n"]
        if desc_text:
            lines.append(desc_text)

        if detail:
            occupants = self._get_occupants(room)
            notables = self._get_notable_objects(room)

            if occupants:
                lines.append(f"|yOccupants:|n {', '.join(occupants)}")
            if notables:
                lines.append(f"|yNotable:|n {', '.join(notables)}")
            if not occupants and not notables:
                lines.append("|yThe room is empty.|n")
        else:
            count = 0
            for obj in room.contents:
                if obj and not hasattr(obj, "destination") and not obj.db.notable:
                    count += 1
            if count:
                lines.append(f"({count} occupant{'s' if count > 1 else ''} here)")
            notables = self._get_notable_objects(room)
            if notables:
                lines.append(f"|wNotable:|n {', '.join(notables[:5])}")
                if len(notables) > 5:
                    lines[-1] += f" (+{len(notables) - 5} more)"

        return "\n".join(lines)

    def _resolve_target(self, arg):
        """Resolve a dbref argument to a room object. Returns (room, error)."""
        if not arg or not arg.startswith("#"):
            return None, None
        if not arg[1:].isdigit():
            return None, None
        matches = search_object(arg)
        if not matches:
            return None, f"No room found for {arg}."
        target = matches[0]
        # Check if it's room-like (no location = it's a container)
        if getattr(target, "location", None) is not None:
            return None, f"{arg} seems to be an object, not a room."
        return target, None

    def func(self):
        """Execute the peek command."""
        caller = self.caller
        room = caller.location

        if not room:
            caller.msg("You are nowhere to peek from.")
            return

        args = (self.args or "").strip()
        detail_mode = False

        # Check for detail flag
        if args.lower().endswith(" detail"):
            detail_mode = True
            args = args[:-(7)].strip()

        if not args:
            # No argument: peek at current room (like 'look')
            caller.msg(self._render_room_summary(room, detail_mode))
            return

        # Try to resolve as dbref
        target_room, err = self._resolve_target(args)
        if target_room:
            caller.msg(self._render_room_summary(target_room, detail_mode))
            return
        if err:
            caller.msg(err)
            return

        # Try to find an exit by name
        exit_obj = self._find_exit(room, args)
        if not exit_obj:
            caller.msg(f"No exit named '{args}' from here. Use |wnearby|n to see your exits.")
            return

        dest = getattr(exit_obj, "destination", None)
        if not dest:
            caller.msg(f"The exit '{args}' leads to... nothing? Spooky.")
            return

        caller.msg(f"|wPeeking through '{args}':|n\n" + self._render_room_summary(dest, detail_mode))
