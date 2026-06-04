"""
Journal command — personal adventure log for characters.

Players can write entries, read past entries, and bookmark significant
moments. Journal entries are stored on the character's db attribute
as a rolling list, making them portable across rooms and sessions.

Examples:
  journal                 — show most recent journal entry
  journal add Defeated the brass sentinel in the Grand Foyer
  journal list            — show last 10 journal entries
  journal list 5          — show last 5 entries
  journal entry 3         — show the 3rd most recent entry
  journal clear           — wipe all entries
  journal date Dawn breaks over the seaside lounge.

Each entry is automatically time-stamped with the in-game time of day.
"""
from evennia import Command


class CmdJournal(Command):
    """
    Personal character journal for logging adventures.

    Usage:
      journal                    — show most recent entry
      journal add <text>         — add a new entry
      journal list [N]          — show last N entries (default 10)
      journal entry <N>         — show the Nth most recent entry
      journal date <text>        — add an entry prefixed with game time
      journal clear             — wipe all entries
      journal count             — show total number of entries

    Journal entries are stored on your character, so they persist
    across rooms and sessions.
    """
    key = "journal"
    aliases = ["log", "diary"]
    locks = "cmd:all()"
    help_category = "Character"

    MAX_ENTRIES = 50  # rolling buffer

    def _get_entries(self):
        """Retrieve the journal entry list from the caller's db attribute."""
        return getattr(self.caller.db, "journal_entries", [])

    def _save_entries(self, entries):
        """Save the journal entry list to the caller's db attribute."""
        self.caller.db.journal_entries = entries[-self.MAX_ENTRIES:]

    def _get_game_time_label(self):
        """Get the in-game time of day label, falling back to a default."""
        try:
            from commands.time import get_time_of_day, format_time
            room = self.caller.location
            if room and hasattr(room.db, "game_hour"):
                hour = int(room.db.game_hour)
                return format_time(hour)
        except Exception:
            pass
        return "unknown hour"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            # No subcommand: show most recent entry
            entries = self._get_entries()
            if not entries:
                caller.msg("Your journal is blank. Try: |wjournal add <text>|n")
                return
            latest = entries[-1]
            caller.msg(f"|wLatest entry:|n {latest.get('text', '...')}")
            return

        parts = args.split(None, 1)
        subcmd = parts[0].lower()

        # --- ADD ---
        if subcmd == "add":
            if len(parts) < 2 or not parts[1].strip():
                caller.msg("|wUsage: journal add <text>|n")
                return
            entries = self._get_entries()
            entry = {
                "text": parts[1].strip()[:500],
                "time": self._get_game_time_label(),
            }
            entries.append(entry)
            self._save_entries(entries)
            caller.msg(f"|wJournal entry added ({len(entries)} total).|n")
            return

        # --- DATE ---
        if subcmd == "date":
            if len(parts) < 2 or not parts[1].strip():
                caller.msg("|wUsage: journal date <text>|n")
                return
            text = parts[1].strip()[:500]
            time_label = self._get_game_time_label()
            full_text = f"[{time_label}] {text}"
            entries = self._get_entries()
            entries.append({"text": full_text, "time": time_label})
            self._save_entries(entries)
            caller.msg(f"|wDated entry added.|n")
            return

        # --- LIST ---
        if subcmd == "list":
            entries = self._get_entries()
            if not entries:
                caller.msg("Your journal is blank.")
                return

            # Optional count argument
            count = self.MAX_ENTRIES
            if len(parts) >= 2:
                try:
                    count = min(int(parts[1].strip()), self.MAX_ENTRIES)
                except (ValueError, TypeError):
                    pass

            shown = entries[-count:]
            caller.msg(f"|w=== Your Journal ({len(entries)} entries) ===|n")
            for i, entry in enumerate(shown):
                idx = len(entries) - len(shown) + i + 1
                caller.msg(f"  {idx}. {entry.get('text', '...')}")
            return

        # --- COUNT ---
        if subcmd == "count":
            entries = self._get_entries()
            caller.msg(f"|wYour journal has {len(entries)} entries.|n")
            return

        # --- ENTRY ---
        if subcmd == "entry":
            if len(parts) < 2:
                caller.msg("|wUsage: journal entry <N>|n")
                return
            try:
                idx = int(parts[1].strip())
            except ValueError:
                caller.msg("Entry number must be an integer.")
                return
            entries = self._get_entries()
            if not entries:
                caller.msg("Your journal is blank.")
                return
            # 1-indexed from most recent
            n = len(entries) - idx
            if 0 <= n < len(entries):
                entry = entries[n]
                caller.msg(f"|wEntry #{idx}:|n {entry.get('text', '...')}")
            else:
                caller.msg(f"Entry #{idx} out of range (you have {len(entries)} entries).")
            return

        # --- CLEAR ---
        if subcmd == "clear":
            entries = self._get_entries()
            if not entries:
                caller.msg("Your journal is already blank.")
                return
            self._save_entries([])
            caller.msg("|wYour journal has been cleared.|n")
            return

        # --- FALLBACK ---
        caller.msg("|wUsage: journal [add <text> | date <text> | list [N] | entry <N> | clear | count]|n")
