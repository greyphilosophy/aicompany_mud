"""Executable requirements for composable NPC context and speech harnesses."""

from types import SimpleNamespace

from typeclasses.npcs import Context, Listener, NPC, Speaker


class Db:
    def __init__(self, **values):
        self.__dict__.update(values)


class Voice:
    SYSTEM_PROMPT = Speaker.SYSTEM_PROMPT

    def providers(self):
        return []


def context(entries=None):
    memory = SimpleNamespace(
        db=Db(entries=list(entries or [])),
        MAX_ENTRIES=Context.MAX_ENTRIES,
        _ENTRY_ID=Context._ENTRY_ID,
    )
    memory.append = lambda who, message, role="user": Context.append(
        memory, who, message, role
    )
    memory.incorporate = lambda incoming: Context.incorporate(memory, incoming)
    memory.export = lambda start=None, stop=None: Context.export(memory, start, stop)
    memory.as_messages = lambda: Context.as_messages(memory)
    memory.snapshot = lambda: Context.snapshot(memory)
    return memory


def npc_with(*contents):
    npc = SimpleNamespace(contents=list(contents))
    npc._first_carried = lambda cls: NPC._first_carried(npc, cls)
    return npc


class Failure:
    def getTraceback(self):
        return "simulated failure"


class Deferred:
    """Tiny synchronous Deferred stand-in for callback-order tests."""

    def addCallback(self, callback):
        self.callback = callback
        return self

    def addErrback(self, callback):
        self.errback = callback
        return self

    def addBoth(self, callback):
        self.both = callback
        return self

    def fire_success(self, result):
        if hasattr(self, "callback"):
            result = self.callback(result)
        if hasattr(self, "both"):
            result = self.both(result)
        return result

    def fire_failure(self):
        result = Failure()
        if hasattr(self, "errback"):
            result = self.errback(result)
        if hasattr(self, "both"):
            result = self.both(result)
        return result


def test_context_is_a_portable_inventory_object():
    assert issubclass(Context, Object := __import__("typeclasses.objects", fromlist=["Object"]).Object)
    assert issubclass(NPC, Object)


def test_context_records_ordered_speech_and_exports_a_copy():
    memory = context()
    Context.append(memory, "Alfred", "Hello")
    exported = Context.export(memory)
    exported[0]["content"] = "changed elsewhere"
    assert exported[0].get(Context._ENTRY_ID) is None
    assert Context.export(memory) == [
        {"role": "user", "who": "Alfred", "content": "Hello"}
    ]


def test_context_reply_can_be_inserted_after_the_snapshot_it_answered():
    memory = context()
    memory.append("Visitor", "First")
    _, snapshot_ids = Context.snapshot(memory)
    memory.append("Visitor", "Second")

    Context.insert_after_snapshot(memory, snapshot_ids, "Ada", "Hi", role="assistant")

    assert [entry["content"] for entry in Context.export(memory)] == [
        "First",
        "Hi",
        "Second",
    ]


def test_an_npc_can_incorporate_all_or_part_of_another_context():
    source = context([
        {"role": "user", "who": "A", "content": "one"},
        {"role": "assistant", "who": "B", "content": "two"},
        {"role": "user", "who": "A", "content": "three"},
    ])
    destination = context()
    npc = npc_with(destination)
    npc.get_context = lambda: destination
    assert NPC.incorporate_context(npc, source, 1, 3) is True
    assert [entry["content"] for entry in Context.export(destination)] == ["two", "three"]


def test_listener_records_only_when_carried_by_the_npc():
    memory = context()
    listener = SimpleNamespace()
    npc = npc_with(memory, listener)
    npc.get_context = lambda: memory
    Listener.record(listener, npc, SimpleNamespace(key="Visitor"), "Good morning")
    assert Context.export(memory)[-1]["who"] == "Visitor"
    assert Context.export(memory)[-1]["content"] == "Good morning"


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
    answer = Speaker.generate_response(speaker, SimpleNamespace(key="Ada"), memory)
    assert answer == "I am Ada."
    assert seen["messages"][-1] == {"role": "user", "content": "Visitor: Who are you?"}


def test_npc_snapshots_all_evennia_state_before_worker_thread(monkeypatch):
    memory = context([{"role": "user", "who": "Visitor", "content": "Hello"}])
    listener = SimpleNamespace(record=lambda npc, speaker, message: memory)
    voice = Voice()
    captured = {}

    def fake_defer_to_thread(func, *args):
        captured["func"] = func
        captured["args"] = args
        return Deferred()

    monkeypatch.setattr("typeclasses.actors.deferToThread", fake_defer_to_thread)

    npc = SimpleNamespace(
        key="Ada",
        db=Db(respond_to_npcs=False, legacy_autoreply=True),
        ndb=Db(),
        get_context=lambda: memory,
        get_listener=lambda: listener,
        get_speaker=lambda: voice,
    )

    NPC.at_heard_say(npc, SimpleNamespace(key="Visitor"), "Hello")

    assert captured["func"] is Speaker.generate_response_from_messages
    assert captured["args"] == (
        "Ada",
        [{"role": "user", "content": "Visitor: Hello"}],
        [],
        Speaker.SYSTEM_PROMPT,
    )
    assert npc.ndb.reply_inflight is True


def test_synchronous_dispatch_failure_does_not_wedge_npc(monkeypatch):
    memory = context()

    def record(npc, speaker, message):
        memory.append(speaker.key, message)
        return memory

    voice = Voice()
    npc = SimpleNamespace(
        key="Ada",
        db=Db(respond_to_npcs=False, legacy_autoreply=True),
        ndb=Db(),
        get_context=lambda: memory,
        get_listener=lambda: SimpleNamespace(record=record),
        get_speaker=lambda: voice,
    )

    def fail_dispatch(*args, **kwargs):
        raise RuntimeError("thread pool unavailable")

    monkeypatch.setattr("typeclasses.actors.deferToThread", fail_dispatch)
    NPC.at_heard_say(npc, SimpleNamespace(key="Visitor"), "Hello")

    assert npc.ndb.reply_inflight is False


def test_reply_stays_with_the_context_that_generated_it(monkeypatch):
    context_a = context()
    context_b = context()
    current = {"context": context_a}
    spoken = []

    def record(npc, speaker, message):
        current["context"].append(speaker.key, message)
        return current["context"]

    listener = SimpleNamespace(record=record)
    voice = Voice()
    deferreds = []

    def fake_defer_to_thread(func, *args):
        deferred = Deferred()
        deferreds.append(deferred)
        return deferred

    monkeypatch.setattr("typeclasses.actors.deferToThread", fake_defer_to_thread)

    npc = SimpleNamespace(
        key="Ada",
        db=Db(respond_to_npcs=False, legacy_autoreply=True),
        ndb=Db(),
        get_context=lambda: current["context"],
        get_listener=lambda: listener,
        get_speaker=lambda: voice,
        say=lambda message: spoken.append(message),
    )

    NPC.at_heard_say(npc, SimpleNamespace(key="Visitor"), "From A")
    current["context"] = context_b
    deferreds[0].fire_success("Reply to A")

    assert [entry["content"] for entry in Context.export(context_a)] == [
        "From A",
        "Reply to A",
    ]
    assert Context.export(context_b) == []
    assert spoken == []


def test_reply_is_suppressed_if_original_speaker_harness_is_removed(monkeypatch):
    memory = context()
    current_voice = {"voice": Voice()}
    original_voice = current_voice["voice"]
    spoken = []

    def record(npc, speaker, message):
        memory.append(speaker.key, message)
        return memory

    listener = SimpleNamespace(record=record)
    deferreds = []

    def fake_defer_to_thread(func, *args):
        deferred = Deferred()
        deferreds.append(deferred)
        return deferred

    monkeypatch.setattr("typeclasses.actors.deferToThread", fake_defer_to_thread)

    npc = SimpleNamespace(
        key="Ada",
        db=Db(respond_to_npcs=False, legacy_autoreply=True),
        ndb=Db(),
        get_context=lambda: memory,
        get_listener=lambda: listener,
        get_speaker=lambda: current_voice["voice"],
        say=lambda message: spoken.append(message),
    )

    NPC.at_heard_say(npc, SimpleNamespace(key="Visitor"), "Hello")
    current_voice["voice"] = Voice()
    assert current_voice["voice"] is not original_voice
    deferreds[0].fire_success("Reply from old speaker")

    assert [entry["content"] for entry in Context.export(memory)] == [
        "Hello",
        "Reply from old speaker",
    ]
    assert spoken == []


def test_speech_heard_while_replying_queues_one_ordered_follow_up(monkeypatch):
    memory = context()

    def record(npc, speaker, message):
        memory.append(speaker.key, message, role="user")
        return memory

    listener = SimpleNamespace(record=record)
    voice = Voice()
    deferreds = []
    dispatches = []
    spoken = []

    def fake_defer_to_thread(func, *args):
        dispatches.append((func, args))
        deferred = Deferred()
        deferreds.append(deferred)
        return deferred

    monkeypatch.setattr("typeclasses.actors.deferToThread", fake_defer_to_thread)

    npc = SimpleNamespace(
        key="Ada",
        db=Db(respond_to_npcs=False, legacy_autoreply=True),
        ndb=Db(),
        get_context=lambda: memory,
        get_listener=lambda: listener,
        get_speaker=lambda: voice,
        say=lambda message: spoken.append(message),
    )

    visitor = SimpleNamespace(key="Visitor")
    NPC.at_heard_say(npc, visitor, "First")
    NPC.at_heard_say(npc, visitor, "Second")

    assert len(dispatches) == 1
    assert npc.ndb.reply_pending is True
    assert [entry["content"] for entry in Context.export(memory)] == ["First", "Second"]

    deferreds[0].fire_success("Hi")

    assert [entry["content"] for entry in Context.export(memory)] == [
        "First",
        "Hi",
        "Second",
    ]
    assert spoken == ["Hi"]
    assert len(dispatches) == 2
    assert npc.ndb.reply_pending is False
    assert npc.ndb.reply_inflight is True
    assert dispatches[1][1] == (
        "Ada",
        [
            {"role": "user", "content": "Visitor: First"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "Visitor: Second"},
        ],
        [],
        Speaker.SYSTEM_PROMPT,
    )


def test_failed_reply_still_dispatches_queued_follow_up(monkeypatch):
    memory = context()

    def record(npc, speaker, message):
        memory.append(speaker.key, message)
        return memory

    listener = SimpleNamespace(record=record)
    voice = Voice()
    deferreds = []
    dispatches = []

    def fake_defer_to_thread(func, *args):
        dispatches.append((func, args))
        deferred = Deferred()
        deferreds.append(deferred)
        return deferred

    monkeypatch.setattr("typeclasses.actors.deferToThread", fake_defer_to_thread)

    npc = SimpleNamespace(
        key="Ada",
        db=Db(respond_to_npcs=False, legacy_autoreply=True),
        ndb=Db(),
        get_context=lambda: memory,
        get_listener=lambda: listener,
        get_speaker=lambda: voice,
        say=lambda message: None,
    )
    visitor = SimpleNamespace(key="Visitor")

    NPC.at_heard_say(npc, visitor, "First")
    NPC.at_heard_say(npc, visitor, "Second")
    deferreds[0].fire_failure()

    assert len(dispatches) == 2
    assert npc.ndb.reply_pending is False
    assert npc.ndb.reply_inflight is True
    assert dispatches[1][1][1] == [
        {"role": "user", "content": "Visitor: First"},
        {"role": "user", "content": "Visitor: Second"},
    ]


def test_pending_follow_up_does_not_cross_into_a_new_context(monkeypatch):
    context_a = context()
    context_b = context()
    current = {"context": context_a}

    def record(npc, speaker, message):
        current["context"].append(speaker.key, message)
        return current["context"]

    listener = SimpleNamespace(record=record)
    voice = Voice()
    deferreds = []
    dispatches = []

    def fake_defer_to_thread(func, *args):
        dispatches.append((func, args))
        deferred = Deferred()
        deferreds.append(deferred)
        return deferred

    monkeypatch.setattr("typeclasses.actors.deferToThread", fake_defer_to_thread)

    npc = SimpleNamespace(
        key="Ada",
        db=Db(respond_to_npcs=False, legacy_autoreply=True),
        ndb=Db(),
        get_context=lambda: current["context"],
        get_listener=lambda: listener,
        get_speaker=lambda: voice,
        say=lambda message: None,
    )
    visitor = SimpleNamespace(key="Visitor")

    NPC.at_heard_say(npc, visitor, "First")
    NPC.at_heard_say(npc, visitor, "Second")
    current["context"] = context_b
    deferreds[0].fire_success("Reply to A")

    assert len(dispatches) == 1
    assert npc.ndb.reply_pending is False
    assert Context.export(context_b) == []


def test_npc_is_an_object_not_an_autonomous_character():
    assert issubclass(NPC, __import__("typeclasses.objects", fromlist=["Object"]).Object)
    assert not hasattr(NPC, "at_tick")
