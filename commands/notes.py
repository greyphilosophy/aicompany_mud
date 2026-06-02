# commands/notes.py
"""
Notes Command

Allows players to leave and retrieve personal notes at room locations.
Enhances exploration, social interaction, and serves as a lightweight
"clues" mechanic that pairs well with the LLM-powered world-building.
"""
from evennia import Command


class CmdNote(Command):
    """
    Leave and retrieve notes at your current location.

    Usage:
      note <message>     — leave a note in the current room
      notes              — list all notes in this room
      note clear         — clear your notes in this room

    Notes are stored per-room and attributed to the writer.
    They persist across sessions and are visible to everyone who
    enters the room.

    Examples:
      note The exit to the Library is hidden behind the bookshelf
      note Remember: the guard changes shift at noon
      notes
      note clear
    """
    key = "note"
    aliases = ["notes"]
    locks = "cmd:all()"
    help_category = "World"

    def _get_room_notes(self):
        """Retrieve the list of notes for the caller's current room."""
        room = self.caller.location
        if not room:
            return []
        return getattr(room.db, "notes", [])

    def _save_room_notes(self, notes):
        """Save the notes list back to the room."""
        room = self.caller.location
        if room:
            room.db.notes = notes

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        room = caller.location
        if not room:
            caller.msg("You are nowhere — hard to leave a note in the void.")
            return

        if not args:
            # `note` or `notes` with no args → list notes
            notes = self._get_room_notes()
            if not notes:
                caller.msg("This room has no notes yet. Leave one with |wnote <message>|n.")
                return
            lines = ["|yNotes in this room:|n"]
            for i, entry in enumerate(notes, 1):
                who = entry.get("who", "Someone")
                text = entry.get("text", "")
                lines.append(f"  |w{i}.|n {text} — *{who}")
            caller.msg("\n".join(lines))
            return

        # `note clear` → remove caller's notes from this room
        if args.lower() == "clear":
            notes = self._get_room_notes()
            original_count = len(notes)
            notes = [n for n in notes if n.get("who") != caller.key]
            self._save_room_notes(notes)
            removed = original_count - len(notes)
            if removed:
                caller.msg(f"Cleared {removed} note(s) from this room.")
            else:
                caller.msg("No notes of yours in this room.")
            return

        # Add a note
        notes = self._get_room_notes()
        notes.append({
            "who": caller.key,
            "text": args,
        })
        self._save_room_notes(notes)
        caller.msg(f'Your note has been left here: "{args}"')
