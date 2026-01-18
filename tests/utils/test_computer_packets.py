# tests/utils/test_computer_packets.py
from types import SimpleNamespace

import utils.computer as comp


class FakeObj:
    def __init__(self, key, dbref, shortdesc="", desc="", notable=True, kind="prop", affordance=None):
        self.key = key
        self.dbref = dbref
        self._kind = kind
        self.db = SimpleNamespace(
            shortdesc=shortdesc,
            desc=desc,
            notable=notable,
            affordance=affordance,
        )


class FakeRoom:
    def __init__(self):
        self.LOCAL_BASE_URL = "http://local/v1"
        self.LOCAL_MODEL = "local-model"
        self.OPENAI_BASE_URL = "https://api.openai.com/v1"
        self.OPENAI_MODEL = "gpt-x"
        self.OPENAI_API_KEY = ""
        self.key = "Test Room"
        self.contents = []
        self.db = SimpleNamespace(
            desc="ROOM DESC",
            memory=[],
            director_facts=[" fact1 ", "", "fact2"],
            last_generated_desc="OLD GEN",
        )


def patch_inherits_from(monkeypatch):
    def fake_inherits_from(obj, path: str) -> bool:
        if not obj:
            return False
        if path.endswith("DefaultExit"):
            return getattr(obj, "_kind", None) == "exit"
        if path.endswith("DefaultCharacter"):
            return getattr(obj, "_kind", None) == "char"
        return False

    monkeypatch.setattr(comp, "inherits_from", fake_inherits_from)


def test_notable_objects_packet_filters_and_truncates(monkeypatch):
    patch_inherits_from(monkeypatch)

    ensured = []
    facts_calls = []

    def fake_ensure_affordance(obj):
        ensured.append(obj.dbref)
        if obj.db.affordance is None:
            obj.db.affordance = {"weight": 1.0, "immovable": False}

    def fake_get_facts(obj):
        facts_calls.append(obj.dbref)
        return [{"text": f"fact-{obj.dbref}"}]

    monkeypatch.setattr(comp, "ensure_affordance", fake_ensure_affordance)
    monkeypatch.setattr(comp, "get_facts", fake_get_facts)

    r = FakeRoom()
    exit_obj = FakeObj("North", "#1", notable=True, kind="exit")
    char_obj = FakeObj("Bob", "#2", notable=True, kind="char")
    not_notable = FakeObj("Table", "#3", notable=False, kind="prop")
    long_desc = "x" * 1000
    lamp = FakeObj("Lamp", "#4", shortdesc="a lamp", desc=long_desc, notable=True, kind="prop", affordance=None)

    r.contents = [exit_obj, char_obj, not_notable, lamp]
    c = comp.Computer(r)

    pkt = c.notable_objects_packet(include_desc=True, max_desc_chars=100)

    assert len(pkt) == 1
    one = pkt[0]
    assert one["dbref"] == "#4"
    assert one["key"] == "Lamp"
    assert one["shortdesc"] == "a lamp"
    assert one["desc"] == "x" * 100
    assert one["facts"] == [{"text": "fact-#4"}]
    assert one["affordance"] == {"weight": 1.0, "immovable": False}

    assert ensured == ["#4"]
    assert facts_calls == ["#4"]


def test_notable_objects_packet_can_omit_desc(monkeypatch):
    patch_inherits_from(monkeypatch)

    monkeypatch.setattr(comp, "ensure_affordance", lambda obj: setattr(obj.db, "affordance", {"weight": 1, "immovable": True}))
    monkeypatch.setattr(comp, "get_facts", lambda obj: [])

    r = FakeRoom()
    lamp = FakeObj("Lamp", "#4", shortdesc="a lamp", desc="hello", notable=True, kind="prop")
    r.contents = [lamp]
    c = comp.Computer(r)

    pkt = c.notable_objects_packet(include_desc=False)
    assert pkt[0]["desc"] == ""


def test_director_snapshot_calls_build_snapshot_with_clean_facts(monkeypatch):
    patch_inherits_from(monkeypatch)

    # make notable_objects_packet deterministic for this unit test
    def fake_notables(*_a, **_kw):
        return [{"key": "Lamp", "shortdesc": "a lamp", "desc": "desc", "dbref": "#4"}]

    monkeypatch.setattr(comp.Computer, "notable_objects_packet", fake_notables)
    monkeypatch.setattr(comp.Computer, "room_memory_text", lambda self, max_chars=3000: "MEM")

    captured = {}

    def fake_build_snapshot(**kwargs):
        captured.update(kwargs)
        return {"snap": True}

    monkeypatch.setattr(comp, "build_snapshot", fake_build_snapshot)

    r = FakeRoom()
    c = comp.Computer(r)

    snap = c.director_snapshot()
    assert snap == {"snap": True}

    assert captured["room_key"] == "Test Room"
    assert captured["previous_desc"] == "ROOM DESC"
    assert captured["previous_generated_desc"] == "OLD GEN"
    assert captured["facts"] == ["fact1", "fact2"]  # stripped + empties removed
    assert captured["memory_text"] == "MEM"
    assert captured["objects"] == [
        {"key": "Lamp", "shortdesc": "a lamp", "desc": "desc", "notable": True}
    ]
