# tests/utils/test_room_targeting.py
from types import SimpleNamespace

import utils.room_targeting as rt


class FakeObj:
    def __init__(
        self,
        key: str,
        dbref: str,
        shortdesc: str = "",
        notable: bool = True,
        kind: str = "prop",  # "prop" | "exit" | "char"
    ):
        self.key = key
        self.dbref = dbref
        self.db = SimpleNamespace(shortdesc=shortdesc, notable=notable)
        self._kind = kind


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

    monkeypatch.setattr(rt, "inherits_from", fake_inherits_from)


def test_words_min_length_and_alnum_only():
    assert rt._words("A an the 12 abc DEF ghi-jkl") == ["the", "abc", "def", "ghi", "jkl"]


def test_resolve_edit_target_empty():
    room = FakeRoom([])
    assert rt.resolve_edit_target(room, "") == (None, [])
    assert rt.resolve_edit_target(room, None) == (None, [])


def test_resolve_edit_target_dbref_anywhere_hits(monkeypatch):
    patch_inherits_from(monkeypatch)

    lamp = FakeObj("Lamp", "#10", "a brass lamp", notable=True)
    room = FakeRoom([lamp])

    obj, amb = rt.resolve_edit_target(room, "computer, change #10 to blue")
    assert obj is lamp
    assert amb == []


def test_resolve_edit_target_dbref_anywhere_miss(monkeypatch):
    patch_inherits_from(monkeypatch)

    lamp = FakeObj("Lamp", "#10", "a brass lamp", notable=True)
    room = FakeRoom([lamp])

    obj, amb = rt.resolve_edit_target(room, "edit #999 please")
    assert obj is None
    assert amb == []


def test_resolve_edit_target_ignores_exit_and_character(monkeypatch):
    patch_inherits_from(monkeypatch)

    ex = FakeObj("North", "#1", "an exit", notable=True, kind="exit")
    ch = FakeObj("Bob", "#2", "a person", notable=True, kind="char")
    prop = FakeObj("Seafoam Brass Lamp", "#3", "a brass lamp", notable=True, kind="prop")
    room = FakeRoom([ex, ch, prop])

    obj, amb = rt.resolve_edit_target(room, "change brass lamp to blue")
    assert obj is prop
    assert amb == []


def test_resolve_edit_target_requires_notable(monkeypatch):
    patch_inherits_from(monkeypatch)

    notable = FakeObj("Lamp", "#10", "a brass lamp", notable=True)
    plain = FakeObj("Table", "#11", "a wooden table", notable=False)
    room = FakeRoom([notable, plain])

    obj, amb = rt.resolve_edit_target(room, "change table to red")
    assert obj is None  # not notable => ignored
    assert amb == []


def test_resolve_edit_target_scores_by_word_hits(monkeypatch):
    patch_inherits_from(monkeypatch)

    lamp = FakeObj("Seafoam Brass Lamp", "#10", "a brass lamp", notable=True)
    sofa = FakeObj("Coastal Velvet Sofa", "#11", "a sea-blue velvet sofa", notable=True)
    room = FakeRoom([lamp, sofa])

    obj, amb = rt.resolve_edit_target(room, "please change the velvet sofa legs")
    assert obj is sofa
    assert amb == []


def test_resolve_edit_target_strips_articles_in_shortdesc(monkeypatch):
    patch_inherits_from(monkeypatch)

    lamp = FakeObj("Lamp", "#10", "a brass lamp", notable=True)
    room = FakeRoom([lamp])

    obj, amb = rt.resolve_edit_target(room, "change brass lamp to green")
    assert obj is lamp
    assert amb == []


def test_resolve_edit_target_ambiguity_returns_list(monkeypatch):
    patch_inherits_from(monkeypatch)

    lamp1 = FakeObj("Lamp One", "#10", "a brass lamp", notable=True)
    lamp2 = FakeObj("Lamp Two", "#11", "a brass lamp", notable=True)
    room = FakeRoom([lamp1, lamp2])

    obj, amb = rt.resolve_edit_target(room, "change brass lamp to blue")
    assert obj is None
    assert set(amb) == {lamp1, lamp2}

def test_resolve_edit_target_skips_none_entries(monkeypatch):
    # Patch inherits_from so nothing is treated as exit/character
    monkeypatch.setattr(rt, "inherits_from", lambda obj, path: False)

    class Obj:
        def __init__(self, key, sd, notable=True, dbref="#1"):
            self.key = key
            self.dbref = dbref
            self.db = type("DB", (), {"shortdesc": sd, "notable": notable})()

    room = type("Room", (), {})()
    room.contents = [None, Obj("Seafoam Brass Lamp", "a brass lamp", notable=True, dbref="#10")]

    # No dbref in instruction, so it goes into scoring loop and must skip None (line 32)
    target, amb = rt.resolve_edit_target(room, "change lamp to blue")
    assert target is not None
    assert amb == []
    assert target.dbref == "#10"

def test_instruction_mentions_target_dbref_trusts(monkeypatch):
    patch_inherits_from(monkeypatch)

    lamp = FakeObj("Lamp", "#10", "a brass lamp", notable=True)
    assert rt.instruction_mentions_target("change #10 to blue", lamp) is True


def test_instruction_mentions_target_matches_meaningful_tokens():
    lamp = FakeObj("Seafoam Brass Lamp", "#10", "a brass lamp", notable=True)

    assert rt.instruction_mentions_target("please change the seafoam color", lamp) is True
    assert rt.instruction_mentions_target("make the lamp brighter", lamp) is True  # "lamp" is meaningful (len>=4)
    assert rt.instruction_mentions_target("change it to blue", lamp) is False  # only generic words


def test_instruction_mentions_target_ignores_stopwords_and_short_tokens():
    obj = FakeObj("Table", "#1", "the table of wood", notable=True)

    # stopwords like "change" should not count; "wood" (len 4) should.
    assert rt.instruction_mentions_target("change it", obj) is False
    assert rt.instruction_mentions_target("make it wood", obj) is True
