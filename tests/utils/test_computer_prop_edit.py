# tests/utils/test_computer_prop_edit.py
import json
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
            affordance=affordance if affordance is not None else {"weight": 1.0, "immovable": False},
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
            memory=[{"who": "A", "msg": "hello"}],
            director_facts=["dir1", "dir2"],
            last_generated_desc="",
            # this is used via get_facts(self.room) in generate_prop_edit_json
            notable=True,
            shortdesc="a room",
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


class RecordingClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def chat_json(self, providers, messages):
        self.calls.append({"providers": providers, "messages": messages})
        return self.reply


def test_generate_prop_edit_json_missing_target_returns_empty_dict(monkeypatch):
    patch_inherits_from(monkeypatch)

    rc = RecordingClient(reply={"should_not": "be called"})
    monkeypatch.setattr(comp, "build_default_client_from_env", lambda: rc)

    r = FakeRoom()
    r.contents = [FakeObj("Lamp", "#10", shortdesc="a lamp", desc="desc", notable=True)]
    c = comp.Computer(r)

    out = c.generate_prop_edit_json("Player", "change it", target_dbref="#999")
    assert out == {"dbref": "", "key": "", "shortdesc": "", "desc": ""}

    # no LLM call should happen
    assert rc.calls == []


def test_generate_prop_edit_json_builds_payload(monkeypatch):
    patch_inherits_from(monkeypatch)

    # Patch facts/affordance
    ensured = []
    def fake_ensure_affordance(obj):
        ensured.append(str(obj.dbref))
        if obj.db.affordance is None:
            obj.db.affordance = {"weight": 2.0, "immovable": False}

    def fake_get_facts(obj):
        # room facts should be dicts with "text"
        if obj is r:
            return [{"text": "pinned-room-1"}, {"text": ""}, {"nope": "x"}]
        return [{"text": f"fact-{obj.dbref}"}]

    monkeypatch.setattr(comp, "ensure_affordance", fake_ensure_affordance)

    rc = RecordingClient(reply={"dbref": "#10", "key": "Lamp", "shortdesc": "a lamp", "desc": "new"})
    monkeypatch.setattr(comp, "build_default_client_from_env", lambda: rc)

    # room + objects
    global r
    r = FakeRoom()
    lamp = FakeObj("Seafoam Brass Lamp", "#10", shortdesc="a brass lamp", desc="old lamp desc", notable=True)
    sofa = FakeObj("Coastal Velvet Sofa", "#11", shortdesc="a velvet sofa", desc="old sofa desc", notable=True)

    r.contents = [lamp, sofa]
    monkeypatch.setattr(comp, "get_facts", fake_get_facts)

    c = comp.Computer(r)
    out = c.generate_prop_edit_json("Player", "change the lamp to blue", target_dbref="#10")
    assert out["dbref"] == "#10"

    assert len(rc.calls) == 1
    msgs = rc.calls[0]["messages"]
    assert msgs[0]["role"] == "system"
    assert "You edit ONE existing physical object" in msgs[0]["content"]

    payload = json.loads(msgs[1]["content"])
    assert payload["player"] == "Player"
    assert payload["instruction"] == "change the lamp to blue"
    assert payload["room_desc"] == "ROOM DESC"
    assert payload["recent_memory"] == "A: hello"

    # room_facts = pinned room facts + director facts
    assert payload["room_facts"] == ["pinned-room-1", "dir1", "dir2"]

    # target packet
    tgt = payload["target"]
    assert tgt["dbref"] == "#10"
    assert tgt["key"] == "Seafoam Brass Lamp"
    assert tgt["shortdesc"] == "a brass lamp"
    assert tgt["desc"] == "old lamp desc"
    assert tgt["facts"] == [{"text": "fact-#10"}]
    assert "affordance" in tgt

    # anchors include dbrefs
    anchors = payload["notable_anchors"]
    assert {"key": "Seafoam Brass Lamp", "shortdesc": "a brass lamp", "dbref": "#10"} in anchors
    assert {"key": "Coastal Velvet Sofa", "shortdesc": "a velvet sofa", "dbref": "#11"} in anchors

    # ensure_affordance called on target
    assert set(ensured) == {"#10", "#11"}
    assert ensured.count("#10") >= 2


def test_generate_prop_edit_json_uses_json_safe(monkeypatch):
    patch_inherits_from(monkeypatch)

    # Put bytes in director_facts to ensure json serialization doesn't explode
    r = FakeRoom()
    r.db.director_facts = [b"dirbytes"]
    lamp = FakeObj("Lamp", "#10", shortdesc="a lamp", desc="old", notable=True)
    r.contents = [lamp]

    monkeypatch.setattr(comp, "ensure_affordance", lambda obj: None)
    monkeypatch.setattr(comp, "get_facts", lambda obj: [{"text": "x"}] if obj is r else [{"text": "y"}])

    rc = RecordingClient(reply={"dbref": "#10", "key": "Lamp", "shortdesc": "a lamp", "desc": "new"})
    monkeypatch.setattr(comp, "build_default_client_from_env", lambda: rc)

    c = comp.Computer(r)
    c.generate_prop_edit_json("Player", "change it", target_dbref="#10")

    payload = json.loads(rc.calls[0]["messages"][1]["content"])
    # bytes were stringified safely
    assert "dirbytes" in "".join(payload["room_facts"])
