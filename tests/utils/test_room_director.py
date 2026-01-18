# tests/utils/test_room_director.py
import json

import utils.room_director as rd


class RecordingClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def chat_json(self, providers, messages):
        self.calls.append({"providers": providers, "messages": messages})
        return self.reply


class P:
    def __init__(self, label):
        self.label = label


def test_build_snapshot_defaults():
    snap = rd.build_snapshot(
        room_key="R",
        previous_desc=None,
        previous_generated_desc=None,
        facts=None,
        objects=None,
        memory_text=None,
    )
    assert snap == {
        "room_key": "R",
        "previous_desc": "",
        "previous_generated_desc": "",
        "facts": [],
        "objects": [],
        "memory": "",
    }


def test_build_messages_uses_previous_generated_desc_preferentially_and_coerces_types():
    snap = {
        "room_key": "Room",
        "previous_desc": "OLD",
        "previous_generated_desc": "NEWER",
        "facts": [1, "  x  ", "", None],
        "objects": ("a", "b"),  # sequence coerced to list()
        "memory": None,
    }

    msgs = rd.build_messages(snap)
    assert msgs[0]["role"] == "system"
    assert "Return STRICT JSON ONLY" in msgs[0]["content"]

    payload = json.loads(msgs[1]["content"])
    assert payload["room_key"] == "Room"
    assert payload["previous_desc"] == "NEWER"  # prefers generated
    assert payload["facts"] == ["1", "x", "None"]
    assert payload["objects"] == ["a", "b"]
    assert payload["memory"] == ""


def test_build_messages_falls_back_to_previous_desc_when_no_generated_desc():
    snap = {
        "room_key": "Room",
        "previous_desc": "OLD",
        "previous_generated_desc": "",
        "facts": [],
        "objects": [],
        "memory": "m",
    }
    msgs = rd.build_messages(snap)
    payload = json.loads(msgs[1]["content"])
    assert payload["previous_desc"] == "OLD"


def test_generate_from_snapshot_happy_path_filters_fact_strings(monkeypatch):
    # Patch logger import inside function
    class FakeLogger:
        def __init__(self):
            self.info = []
        def log_info(self, msg):
            self.info.append(str(msg))

    fake_logger = FakeLogger()
    monkeypatch.setattr("evennia.utils.logger", fake_logger, raising=False)

    client = RecordingClient(reply={"desc": "  Hello  ", "facts": [" a ", "", None, 2]})
    providers = [P("LOCAL"), P("OPENAI")]
    snap = rd.build_snapshot("R", "old", "gen", ["x"], [], "mem")

    out = rd.generate_from_snapshot(client, providers, snap)
    assert out == {"desc": "Hello", "facts": ["a", "None", "2"]}

    # client called with messages built from snapshot
    assert len(client.calls) == 1
    assert [p.label for p in client.calls[0]["providers"]] == ["LOCAL", "OPENAI"]
    assert len(client.calls[0]["messages"]) == 2


def test_generate_from_snapshot_facts_non_list_becomes_empty(monkeypatch):
    class StubLogger:
        def log_info(self, *_a, **_kw):
            pass

    monkeypatch.setattr("evennia.utils.logger", StubLogger(), raising=False)

    client = RecordingClient(reply={"desc": "Hi", "facts": "nope"})
    out = rd.generate_from_snapshot(client, [P("LOCAL")], {"room_key": "R"})
    assert out == {"desc": "Hi", "facts": []}


def test_generate_from_snapshot_raises_on_empty_desc(monkeypatch):
    class StubLogger:
        def log_info(self, *_a, **_kw):
            pass

    monkeypatch.setattr("evennia.utils.logger", StubLogger(), raising=False)


    client = RecordingClient(reply={"desc": "   ", "facts": ["x"]})
    try:
        rd.generate_from_snapshot(client, [P("LOCAL")], {"room_key": "R"})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "empty desc" in str(e)
