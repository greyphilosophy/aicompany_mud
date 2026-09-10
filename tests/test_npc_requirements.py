"""Executable requirements for composable NPC context and speech harnesses."""

from types import SimpleNamespace

from typeclasses.npcs import Context, Listener, NPC, Speaker


class Db:
    def __init__(self, **values):
        self.__dict__.update(values)


def context(entries=None):
    return SimpleNamespace(db=Db(entries=list(entries or [])))


def npc_with(*contents):
    return SimpleNamespace(contents=list(contents))


def test_context_is_a_portable_inventory_object():
    assert issubclass(Context, Object := __import__("typeclasses.objects", fromlist=["Object"]).Object)
    assert issubclass(NPC, Object)


def test_context_records_ordered_speech_and_exports_a_copy():
    memory = context()
    Context.append(memory, "Alfred", "Hello")
    exported = Context.export(memory)
    exported[0]["content"] = "changed elsewhere"
    assert memory.db.entries == [{"role": "user", "who": "Alfred", "content": "Hello"}]


def test_an_npc_can_incorporate_all_or_part_of_another_context():
    source = context([
        {"role": "user", "who": "A", "content": "one"},
        {"role": "assistant", "who": "B", "content": "two"},
        {"role": "user", "who": "A", "content": "three"},
    ])
    destination = context()
    npc = npc_with(destination)
    npc.get_context = lambda: destination
    source.export = lambda start=None, stop=None: Context.export(source, start, stop)
    destination.incorporate = lambda entries: Context.incorporate(destination, entries)
    assert NPC.incorporate_context(npc, source, 1, 3) is True
    assert [entry["content"] for entry in destination.db.entries] == ["two", "three"]


def test_listener_records_only_when_carried_by_the_npc():
    memory = context()
    listener = SimpleNamespace()
    npc = npc_with(memory, listener)
    npc.get_context = lambda: memory
    Listener.record(listener, npc, SimpleNamespace(key="Visitor"), "Good morning")
    assert memory.db.entries[-1]["who"] == "Visitor"
    assert memory.db.entries[-1]["content"] == "Good morning"


def test_listener_without_context_degrades_cleanly():
    listener = SimpleNamespace(record=lambda npc, speaker, message: None)
    npc = SimpleNamespace(
        key="Ada",
        ndb=Db(),
        get_listener=lambda: listener,
        get_speaker=lambda: None,
    )

    NPC.at_heard_say(npc, SimpleNamespace(key="Visitor"), "Hello")


def test_base_npc_has_no_listener_or_speaker_and_is_therefore_inert():
    npc = npc_with(context())
    assert NPC.get_listener(npc) is None
    assert NPC.get_speaker(npc) is None


def test_speaker_builds_llm_messages_from_the_carried_context(monkeypatch):
    memory = context([{"role": "user", "who": "Visitor", "content": "Who are you?"}])
    speaker = SimpleNamespace(SYSTEM_PROMPT=Speaker.SYSTEM_PROMPT)
    seen = {}

    class Client:
        def chat_json(self, providers, messages):
            seen["messages"] = messages
            return {"response": "I am Ada."}

    monkeypatch.setattr("typeclasses.npcs.build_default_client_from_env", lambda: Client())
    speaker.providers = lambda: []
    memory.as_messages = lambda: Context.as_messages(memory)
    answer = Speaker.generate_response(speaker, SimpleNamespace(key="Ada"), memory)
    assert answer == "I am Ada."
    assert seen["messages"][-1] == {"role": "user", "content": "Visitor: Who are you?"}


def test_npc_snapshots_context_before_dispatching_worker_thread(monkeypatch):
    memory = context([{"role": "user", "who": "Visitor", "content": "Hello"}])
    memory.as_messages = lambda: Context.as_messages(memory)
    listener = SimpleNamespace(record=lambda npc, speaker, message: memory)
    voice = SimpleNamespace(generate_response_from_messages=lambda name, messages: "Hi")
    captured = {}

    class Deferred:
        def addCallback(self, callback):
            return self

        def addErrback(self, callback):
            return self

        def addBoth(self, callback):
            return self

    def fake_defer_to_thread(func, *args):
        captured["func"] = func
        captured["args"] = args
        return Deferred()

    monkeypatch.setattr("typeclasses.npcs.deferToThread", fake_defer_to_thread)

    npc = SimpleNamespace(
        key="Ada",
        db=Db(respond_to_npcs=False),
        ndb=Db(),
        get_listener=lambda: listener,
        get_speaker=lambda: voice,
    )

    NPC.at_heard_say(npc, SimpleNamespace(key="Visitor"), "Hello")

    assert captured["func"] is voice.generate_response_from_messages
    assert captured["args"] == (
        "Ada",
        [{"role": "user", "content": "Visitor: Hello"}],
    )
    assert npc.ndb.reply_inflight is True


def test_npc_is_an_object_not_an_autonomous_character():
    assert issubclass(NPC, __import__("typeclasses.objects", fromlist=["Object"]).Object)
    assert not hasattr(NPC, "at_tick")
