# tests/utils/test_computer_director_pipeline.py
from types import SimpleNamespace

import utils.computer as comp


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
            director_facts=[],
            last_generated_desc="OLD GEN",
        )


class RecordingClient:
    def __init__(self):
        self.calls = []

    def chat_json(self, providers, messages):
        self.calls.append({"providers": providers, "messages": messages})
        return {"ok": True}


def test_generate_room_desc_passes_correct_args(monkeypatch):
    fake_settings = SimpleNamespace(
        LOCAL_BASE_URL="http://test/v1",
        LOCAL_MODEL="test-model",
        OPENAI_API_KEY=None,
    )
    monkeypatch.setattr(comp, "settings", fake_settings, raising=False)

    r = FakeRoom()
    c = comp.Computer(r)

    fake_client = RecordingClient()
    monkeypatch.setattr(comp, "build_default_client_from_env", lambda: fake_client)

    captured = {}
    def fake_generate_from_snapshot(client, providers, snapshot):
        captured["client"] = client
        captured["providers"] = providers
        captured["snapshot"] = snapshot
        return {"desc": "NEW DESC"}

    monkeypatch.setattr(comp, "generate_from_snapshot", fake_generate_from_snapshot)

    c.generate_room_desc({"snap": True})

    # Verify the call graph: generate_room_desc delegates to generate_from_snapshot
    assert captured["client"] is fake_client
    assert [p.label for p in captured["providers"]] == ["LOCAL"]
    assert captured["snapshot"] == {"snap": True}


def test_director_snapshot_passed_through_to_generate(monkeypatch):
    fake_settings = SimpleNamespace(
        LOCAL_BASE_URL="http://test/v1",
        LOCAL_MODEL="test-model",
        OPENAI_API_KEY=None,
    )
    monkeypatch.setattr(comp, "settings", fake_settings, raising=False)

    r = FakeRoom()
    c = comp.Computer(r)

    monkeypatch.setattr(comp.Computer, "director_snapshot", lambda self: {"snap": "S"})

    fake_client = RecordingClient()
    monkeypatch.setattr(comp, "build_default_client_from_env", lambda: fake_client)

    captured = {}
    def fake_generate_from_snapshot(client, providers, snapshot):
        captured["client"] = client
        captured["providers"] = providers
        captured["snapshot"] = snapshot
        return {"desc": "NEW DESC"}

    monkeypatch.setattr(comp, "generate_from_snapshot", fake_generate_from_snapshot)

    c.generate_room_desc(c.director_snapshot())

    # Verify that the snapshot from director_snapshot flowed through
    assert captured["snapshot"] == {"snap": "S"}
    # Verify only LOCAL provider (no OpenAI key)
    assert [p.label for p in captured["providers"]] == ["LOCAL"]

