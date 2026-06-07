"""
Recall command: teleport to a previously marked room.

Usage:
  recall              — list all marked rooms (same as mark)
  recall <name>       — teleport to the room marked with <name>

This is a natural companion to the |wmark|n command.  Use |wmark|n to
bookmark rooms, then |wrecall|n to jump right back to them.

Examples:
  mark tavern
  recall tavern
  recall
"""

from evennia import Command
from evennia.utils.search import search_object


class CmdRecall(Command):
    """
    Teleport to a bookmarked room.

    Usage:
      recall              — list marked rooms
      recall <name>       — teleport to the room marked <name>

    Examples:
      recall tavern
      recall
    """
    key = "recall"
    aliases = ["teleport", "jump"]
    locks = "cmd:all()"
    help_category = "Navigation"

    def _get_marks(self):
        """Get the caller's mark dictionary from db property."""
        marks = self.caller.db.marked_rooms
        if marks is None:
            self.caller.db.marked_rooms = {}
            marks = self.caller.db.marked_rooms
        return marks

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        marks = self._get_marks()

        if not args:
            # No args: list all marks
            if not marks:
                caller.msg("You have no marked rooms.")
                caller.msg("Use |wmark <name>|n to bookmark a room first.")
                return

            caller.msg("Your marked rooms:")
            caller.msg("")
            for name, data in sorted(marks.items()):
                note = data.get("note", "")
                room_name = data.get("room_name", "Unknown")
                note_str = f" — {note}" if note else ""
                caller.msg(f"  |w{name}|n → {room_name}{note_str}")
            return

        parts = args.split()
        mark_name = parts[0].lower()

        if mark_name not in marks:
            caller.msg(f"No mark named '{mark_name}'.")
            if marks:
                caller.msg("Your marks: " + ", ".join(marks.keys()))
            return

        # Look up the room by dbref
        room_id = marks[mark_name].get("room_id")
        if not room_id:
            caller.msg(f"Mark '{mark_name}' exists but has no room reference.")
            return

        # Find the room object by dbref
        target = search_object(None, search_type="room", global_name=f"#{room_id}")
        if not target:
            # Room might have been deleted; clean up the stale mark
            del marks[mark_name]
            caller.db.marked_rooms = marks
            caller.msg(f"Mark '{mark_name}' is stale — the room is gone.")
            return

        target = target[0]

        # Teleport the caller
        caller.msg(f"You concentrate and recall the place you marked as '|w{mark_name}|n'.")
        caller.move_to(target)
        target.msg(f"{caller.key} appears in a shimmer of recollection.")
