"""
commands/map.py

Map command — visualize nearby rooms, exits, and occupants.

Usage:
  map              (show a compact map of surrounding rooms)
  map exits        (show only exits, no occupants)
  map verbose      (show detailed info including occupants in each room)
"""

from evennia import Command


class CmdMap(Command):
    """
    Display a compact map of your surroundings.

    Shows your current room, its exits, the adjacent rooms, and (optionally)
    who or what occupies each space. Useful for getting your bearings
    without walking everywhere.

    Usage:
      map
      map exits
      map verbose

    Examples:
      map
        Displays a 3-line-per-room overview: room name, exits, occupants.

      map exits
        Compact list of exits and destination rooms only.

      map verbose
        Full detail: each room's key, exits, characters, and objects.
    """
    key = "map"
    aliases = ["area", "surroundings"]
    locks = "cmd:all()"
    help_category = "Navigation"

    def _get_exits_for_room(self, room):
        """Return list of (exit_key, destination_room) pairs for a room."""
        exits = []
        if not room or not hasattr(room, 'contents'):
            return exits
        for obj in room.contents:
            if obj and hasattr(obj, 'destination') and getattr(obj, 'destination') is not None:
                dest = obj.destination
                exits.append((obj.key, dest))
        return exits

    def _get_occupants(self, room):
        """Return lists of characters and objects in a room (excluding exits)."""
        characters = []
        objects = []
        if not room or not hasattr(room, 'contents'):
            return characters, objects
        for obj in room.contents:
            if not obj:
                continue
            # Skip exits
            if hasattr(obj, 'destination') and getattr(obj, 'destination') is not None:
                continue
            # Skip the room itself
            if obj.dbref == room.dbref:
                continue
            # Classify: characters have an account attribute
            if hasattr(obj, 'account') and obj.account:
                characters.append(obj.key)
            else:
                objects.append(obj.key)
        return characters, objects

    def _get_exit_names(self, exits):
        """Extract capitalized exit names (e.g., 'north', 'east')."""
        return [e[0].split()[-1].capitalize() for e in exits if e]

    def _format_room_line(self, room, exits):
        """Format a room line for exit-only mode."""
        exit_names = self._get_exit_names(exits)
        exit_str = " → " + ", ".join(exit_names) if exit_names else " (dead end)"
        return f"  {room.key}{exit_str}"

    def _format_room_detail(self, room, exits, chars, objs):
        """Format a detailed room block."""
        exit_dests = [f"{e[0]} → {e[1].key}" if e[1] else e[0] for e in exits]
        lines = []
        lines.append(f"  |w{room.key}|n (#{room.id})")
        if exit_dests:
            lines.append(f"    Exits: {', '.join(exit_dests)}")
        if chars:
            lines.append(f"    Characters: {', '.join(chars[:5])}" + (" …" if len(chars) > 5 else ""))
        if objs:
            lines.append(f"    Objects: {', '.join(objs[:5])}" + (" …" if len(objs) > 5 else ""))
        if not chars and not objs:
            lines.append(f"    (empty)")
        return "\n".join(lines)

    def _format_room_compact(self, room, exits, chars, objs):
        """Format a compact room line with occupant counts."""
        exit_names = self._get_exit_names(exits)
        exit_str = ", ".join(exit_names) if exit_names else "—"

        occ_parts = []
        if chars:
            occ_parts.append(f"{len(chars)} char(s)")
        if objs:
            occ_parts.append(f"{len(objs)} item(s)")
        occ_str = ", ".join(occ_parts) if occ_parts else "empty"

        return f"  {room.key} [{exit_str}] — {occ_str}"

    def func(self):
        """Execute the map command."""
        caller = self.caller
        args = (self.args or "").strip().lower()

        room = caller.location
        if not room:
            caller.msg("You are nowhere — the map is blank.")
            return

        caller.msg(f"|w=== MAP (centered on {room.key}) ===|n")

        # Current room data
        current_exits = self._get_exits_for_room(room)
        current_chars, current_objs = self._get_occupants(room)

        # Collect adjacent rooms directly from exit destinations
        adjacent_rooms = []
        seen_refs = set()
        for exit_key, dest in current_exits:
            if dest and dest.dbref != room.dbref and dest.dbref not in seen_refs:
                adjacent_rooms.append(dest)
                seen_refs.add(dest.dbref)

        if args == "verbose":
            caller.msg("|yYou are here:|n")
            caller.msg(self._format_room_detail(room, current_exits, current_chars, current_objs))
            if adjacent_rooms:
                caller.msg("\n|yNearby rooms:|n")
                for adj_room in adjacent_rooms:
                    adj_exits = self._get_exits_for_room(adj_room)
                    adj_chars, adj_objs = self._get_occupants(adj_room)
                    caller.msg(self._format_room_detail(adj_room, adj_exits, adj_chars, adj_objs))
            else:
                caller.msg("\nNo adjacent rooms found. You are isolated.")

        elif args == "exits":
            caller.msg("|yYou are here:|n")
            caller.msg(self._format_room_line(room, current_exits))
            if adjacent_rooms:
                caller.msg("\n|yNearby rooms:|n")
                for adj_room in adjacent_rooms:
                    adj_exits = self._get_exits_for_room(adj_room)
                    caller.msg(self._format_room_line(adj_room, adj_exits))
            else:
                caller.msg("\nNo adjacent rooms found.")

        else:
            # Default: compact with occupants
            caller.msg("|yYou are here:|n")
            caller.msg(self._format_room_compact(room, current_exits, current_chars, current_objs))
            if adjacent_rooms:
                caller.msg("\n|yNearby rooms:|n")
                for adj_room in adjacent_rooms:
                    adj_exits = self._get_exits_for_room(adj_room)
                    adj_chars, adj_objs = self._get_occupants(adj_room)
                    caller.msg(self._format_room_compact(adj_room, adj_exits, adj_chars, adj_objs))
            else:
                caller.msg("\nNo adjacent rooms found. You are isolated.")
