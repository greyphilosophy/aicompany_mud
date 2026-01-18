# tests/utils/test_computer_llm_calls.py
import json
from types import SimpleNamespace

import utils.computer as comp


class FakeObj:
    def __init__(self, key, dbref, shortdesc="", desc="", notable=True, kind="prop"):
        self.key = key
        self.dbref = dbref
        self._kind = kind
        self.db = SimpleNamespace(
            shortdesc=shortdesc,
            desc=desc,
            notable=notable,
            affordance={"weight": 1.0, "immovable": False},
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
            director_facts=[],
            last_generated_desc="",
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


def test_generate_prop_json_builds_messages_and_payload(monkeypatch):
    patch_inherits_from(monkeypatch)

    # Patch affordance/facts to avoid Evennia dependencies
    monkeypatch.setattr(comp, "ensure_affordance", lambda obj: None)
    monkeypatch.setattr(comp, "get_facts", lambda obj: [{"text": "f"}])

    # Record LLM call
    rc = RecordingClient(reply={"key": "Thing", "shortdesc": "a thing", "desc": "desc"})
    monkeypatch.setattr(comp, "build_default_client_from_env", lambda: rc)

    r = FakeRoom()
    r.contents = [
        FakeObj("Lamp", "#10", shortdesc="a lamp", notable=True),
        FakeObj("North", "#1", shortdesc="an exit", notable=True, kind="exit"),
    ]
    c = comp.Computer(r)

    out = c.generate_prop_json("Player", "create a shiny orb")
    assert out["key"] == "Thing"

    assert len(rc.calls) == 1
    call = rc.calls[0]
    providers = call["providers"]
    messages = call["messages"]

    # providers: local only (since no OPENAI key)
    assert len(providers) == 1
    assert providers[0].label == "LOCAL"

    assert messages[0]["role"] == "system"
    assert "Return STRICT JSON ONLY" in messages[0]["content"]

    assert messages[1]["role"] == "user"
    payload = json.loads(messages[1]["content"])

    assert payload["player"] == "Player"
    assert payload["instruction"] == "create a shiny orb"
    assert payload["room_desc"] == "ROOM DESC"
    assert "recent_memory" in payload
    assert payload["notable_anchors"] == [{"key": "Lamp", "shortdesc": "a lamp"}]


def test_predict_intent_builds_messages_and_payload(monkeypatch):
    patch_inherits_from(monkeypatch)

    monkeypatch.setattr(comp, "ensure_affordance", lambda obj: None)
    monkeypatch.setattr(comp, "get_facts", lambda obj: [])

    rc = RecordingClient(reply={"intent": "unknown", "normalized": "", "question": "Is it this?"})
    monkeypatch.setattr(comp, "build_default_client_from_env", lambda: rc)

    r = FakeRoom()
    r.contents = [FakeObj("Lamp", "#10", shortdesc="a lamp", notable=True)]
    c = comp.Computer(r)

    out = c.predict_intent("Player", "computer, make it nicer")
    assert out["intent"] == "unknown"

    call = rc.calls[0]
    msgs = call["messages"]
    assert msgs[0]["role"] == "system"
    assert "Allowed intents" in msgs[0]["content"]

    payload = json.loads(msgs[1]["content"])
    assert payload["player"] == "Player"
    assert payload["utterance"] == "computer, make it nicer"
    assert payload["room_desc"] == "ROOM DESC"
    assert payload["notable_anchors"][0]["dbref"] == "#10"


def test_generate_prop_json_uses_json_safe(monkeypatch):
    """
    Prove that weird Mapping/Sequence objects won't break serialization.
    We simulate by injecting bytes in memory and ensure payload JSON-dumps.
    """
    patch_inherits_from(monkeypatch)

    monkeypatch.setattr(comp, "ensure_affordance", lambda obj: None)
    monkeypatch.setattr(comp, "get_facts", lambda obj: [])

    rc = RecordingClient(reply={"ok": True})
    monkeypatch.setattr(comp, "build_default_client_from_env", lambda: rc)

    r = FakeRoom()
    # Inject bytes into memory messages (would normally break json.dumps without _json_safe)
    r.db.memory = [{"who": b"A", "msg": b"hello"}]
    r.contents = [FakeObj("Lamp", "#10", shortdesc="a lamp", notable=True)]

    c = comp.Computer(r)
    c.generate_prop_json("Player", "create something")

    payload = json.loads(rc.calls[0]["messages"][1]["content"])
    assert "b'A': b'hello'" in payload["recent_memory"]
