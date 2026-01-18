# tests/utils/test_room_object_query_edgecases.py
from types import SimpleNamespace

import utils.room_object_query as q


class FakeObj:
    def __init__(self, key, dbref, shortdesc="", notable=True, kind="prop"):
        self.key = key
        self.dbref = dbref
        self._kind = kind
        self.db = SimpleNamespace(shortdesc=shortdesc, notable=notable)
        self.deleted = False

    def delete(self):
        self.deleted = True


class FakeRoom:
    def __init__(self, contents):
        self.contents = contents


def patch_inherits_from(monkeypatch):
    def fake_inherits_from(obj, path: str) -> bool:
        if not obj:
            return False
        if path.endswith("DefaultExit"):
            return getattr(obj, "_kind", None) == "exit"
        if path.endswith("DefaultCharacter"):
            return getattr(obj, "_kind", None) == "char"
        return False

    monkeypatch.setattr(q, "inherits_from", fake_inherits_from)


def test_find_object_empty_and_dbref_not_found(monkeypatch):
    patch_inherits_from(monkeypatch)

    room = FakeRoom(contents=[FakeObj("Lamp", "#1", shortdesc="a lamp")])

    assert q.find_object_in_room(room, "") is None            # hits line 35
    assert q.find_object_in_room(room, "   ") is None         # hits line 35
    assert q.find_object_in_room(room, "#999") is None        # hits line 42


def test_find_object_skips_non_props(monkeypatch):
    patch_inherits_from(monkeypatch)

    exit_obj = FakeObj("North", "#2", shortdesc="an exit", kind="exit")
    char_obj = FakeObj("Bob", "#3", shortdesc="a person", kind="char")
    lamp = FakeObj("Lamp", "#1", shortdesc="a lamp", kind="prop")

    room = FakeRoom(contents=[exit_obj, char_obj, lamp])

    # Should ignore exit/char and match prop by exact key
    assert q.find_object_in_room(room, "lamp") is lamp        # hits line 48 continue


def test_delete_object_selector_empty_and_dbref_not_found_and_skips_non_props(monkeypatch):
    patch_inherits_from(monkeypatch)

    exit_obj = FakeObj("North", "#2", shortdesc="an exit", kind="exit")
    char_obj = FakeObj("Bob", "#3", shortdesc="a person", kind="char")
    lamp = FakeObj("Lamp", "#1", shortdesc="a lamp", kind="prop")

    room = FakeRoom(contents=[exit_obj, char_obj, lamp])

    assert q.delete_object_by_selector(room, "") is None      # hits line 72
    assert q.delete_object_by_selector(room, "   ") is None   # hits line 72
    assert q.delete_object_by_selector(room, "#999") is None  # hits line 81

    # Force loops that have non-prop continues (87 and 99):
    # - exact-match loop runs, sees exit/char, continues, then fails (no delete)
    assert q.delete_object_by_selector(room, "nope") is None

    # - substring loop runs, sees exit/char, continues, then ambiguity or none
    assert q.delete_object_by_selector(room, "o") is None
