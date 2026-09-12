"""Bounded, transferable working history."""

from uuid import uuid4
from typeclasses.objects import Object
from typeclasses.compat import persisted_typeclass


@persisted_typeclass("typeclasses.npcs.Context")
class Context(Object):
    """A portable, bounded working conversation history."""

    MAX_ENTRIES = 100
    _ENTRY_ID = "_entry_id"

    def at_object_creation(self):
        super().at_object_creation()
        self.db.entries = []
        self.db.desc = "A bounded working record of recent conversation."

    def _entries_with_ids(self):
        entries = [dict(entry) for entry in list(self.db.entries or [])]
        changed = False
        for entry in entries:
            if not entry.get(self._ENTRY_ID):
                entry[self._ENTRY_ID] = uuid4().hex
                changed = True
        if changed:
            self.db.entries = entries
        return entries

    def append(self, who, message, role="user"):
        entries = Context._entries_with_ids(self)
        entries.append(
            {
                "role": str(role),
                "who": str(who),
                "content": str(message),
                self._ENTRY_ID: uuid4().hex,
            }
        )
        self.db.entries = entries[-self.MAX_ENTRIES :]

    def insert_after_snapshot(self, snapshot_ids, who, message, role="assistant"):
        entries = Context._entries_with_ids(self)
        snapshot_ids = set(snapshot_ids or [])
        insert_at = 0
        for index, entry in enumerate(entries):
            if entry.get(self._ENTRY_ID) in snapshot_ids:
                insert_at = index + 1
        entries.insert(
            insert_at,
            {
                "role": str(role),
                "who": str(who),
                "content": str(message),
                self._ENTRY_ID: uuid4().hex,
            },
        )
        self.db.entries = entries[-self.MAX_ENTRIES :]

    def incorporate(self, entries):
        for entry in entries or []:
            if not isinstance(entry, dict) or not entry.get("content"):
                continue
            self.append(
                entry.get("who", "unknown"),
                entry["content"],
                entry.get("role", "user"),
            )

    def export(self, start=None, stop=None):
        entries = Context._entries_with_ids(self)[start:stop]
        return [
            {key: value for key, value in entry.items() if key != self._ENTRY_ID}
            for entry in entries
        ]

    @staticmethod
    def _messages_from_entries(entries):
        messages = []
        for entry in entries or []:
            role = entry.get("role", "user")
            if role not in {"system", "user", "assistant"}:
                role = "user"
            content = entry.get("content", "")
            if role == "user" and entry.get("who"):
                content = f"{entry['who']}: {content}"
            messages.append({"role": role, "content": str(content)})
        return messages

    def as_messages(self):
        return Context._messages_from_entries(Context._entries_with_ids(self))

    def snapshot(self):
        entries = Context._entries_with_ids(self)
        return (
            Context._messages_from_entries(entries),
            [entry[self._ENTRY_ID] for entry in entries],
        )
