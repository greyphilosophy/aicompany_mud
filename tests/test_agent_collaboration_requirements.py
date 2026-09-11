"""Requirements for controller-agnostic, bounded actor collaboration."""

from types import SimpleNamespace

from typeclasses.npcs import Context, Listener, Memory, NPC, Task, Tool
from typeclasses.objects import Object


class Db:
    def __init__(self, **values):
        self.__dict__.update(values)


def context(entries=None):
    memory = SimpleNamespace(
        db=Db(entries=list(entries or [])),
        MAX_ENTRIES=Context.MAX_ENTRIES,
        _ENTRY_ID=Context._ENTRY_ID,
    )
    memory.append = lambda who, message, role="user": Context.append(
        memory, who, message, role
    )
    memory.export = lambda start=None, stop=None: Context.export(memory, start, stop)
    memory.as_messages = lambda: Context.as_messages(memory)
    memory.snapshot = lambda: Context.snapshot(memory)
    return memory


def durable_memory(entries=None):
    memory = SimpleNamespace(
        db=Db(entries=list(entries or [])),
        MAX_ENTRIES=Memory.MAX_ENTRIES,
    )
    memory.remember = lambda content, source=None, kind="fact", task=None: Memory.remember(
        memory, content, source=source, kind=kind, task=task
    )
    memory.export = lambda: Memory.export(memory)
    memory.as_message = lambda: Memory.as_message(memory)
    return memory


def task_state(max_turns=4, max_no_progress_turns=2, working_context=None):
    task = SimpleNamespace(
        db=Db(
            objective="Solve the problem",
            status="active",
            requester=None,
            assignee=None,
            parent_task=None,
            result=None,
            turn_count=0,
            max_turns=max_turns,
            no_progress_turns=0,
            max_no_progress_turns=max_no_progress_turns,
            progress_notes=[],
        )
    )
    task.can_continue = lambda: Task.can_continue(task)
    task.record_turn = lambda actor=None, message=None, progress=None: Task.record_turn(
        task, actor, message, progress
    )
    task.mark_progress = lambda note=None: Task.mark_progress(task, note)
    task.get_context = lambda: working_context
    return task


def test_task_memory_and_tool_are_transferable_world_objects():
    assert issubclass(Task, Object)
    assert issubclass(Memory, Object)
    assert issubclass(Tool, Object)


def test_long_working_conversation_cannot_overwrite_durable_memory():
    working = context()
    durable = durable_memory()
    durable.remember("The brass key opens the observatory cabinet", source="Alice")

    for index in range(Context.MAX_ENTRIES + 25):
        working.append("Visitor", f"turn {index}")

    assert len(Context.export(working)) == Context.MAX_ENTRIES
    assert durable.export() == [
        {
            "content": "The brass key opens the observatory cabinet",
            "source": "Alice",
            "kind": "fact",
            "task": None,
        }
    ]


def test_task_listener_consumes_shared_context_without_copying_into_actor_memory():
    actor_context = context()
    task_context = context(
        [{"role": "user", "who": "Alice", "content": "The key is in the observatory"}]
    )
    task = task_state(working_context=task_context)
    actor = SimpleNamespace(get_context=lambda: actor_context)
    speaker = SimpleNamespace(key="Alice")

    returned = Listener.record(
        SimpleNamespace(), actor, speaker, "The key is in the observatory", task=task
    )

    assert returned is task_context
    assert Context.export(actor_context) == []
    assert [entry["content"] for entry in Context.export(task_context)] == [
        "The key is in the observatory"
    ]


def test_task_turn_budget_hard_stops_collaboration():
    task = task_state(max_turns=2)

    assert task.can_continue() is True
    assert task.record_turn(message="first") is True
    assert task.can_continue() is True
    assert task.record_turn(message="second") is True

    assert task.db.status == "budget_exhausted"
    assert task.can_continue() is False


def test_task_can_stop_for_explicit_no_progress_and_reset_on_progress():
    task = task_state(max_turns=10, max_no_progress_turns=2)

    task.record_turn(message="guess one", progress=False)
    task.mark_progress("Found a new clue")
    assert task.db.no_progress_turns == 0

    task.record_turn(message="guess two", progress=False)
    task.record_turn(message="guess three", progress=False)
    assert task.db.status == "stalled"
    assert task.can_continue() is False


def test_response_gate_does_not_need_to_know_controller_type():
    actor = SimpleNamespace(key="Nova", id=1, get_active_task=lambda: None)

    class PlayerLike:
        key = "Alfred"
        id = 2

    class NpcLike:
        key = "Alice"
        id = 3

    player_result = NPC.should_respond_to_speech(actor, PlayerLike(), "Hello")
    npc_result = NPC.should_respond_to_speech(actor, NpcLike(), "Hello")

    assert player_result is True
    assert npc_result is True


def test_unscoped_autonomous_reply_metadata_prevents_feedback_loop():
    actor = SimpleNamespace(key="Nova", id=1, get_active_task=lambda: None)
    other = SimpleNamespace(key="Alice", id=2)

    assert NPC.should_respond_to_speech(
        actor,
        other,
        "A generated reply",
        allow_reply=False,
    ) is False


def test_task_scoped_targeted_exchange_can_continue_while_budget_remains():
    task = task_state(max_turns=3)
    nova = SimpleNamespace(key="Nova", id=1, get_active_task=lambda: None)
    alice = SimpleNamespace(key="Alice", id=2)

    assert NPC.should_respond_to_speech(
        nova,
        alice,
        "Can you help with this objective?",
        task=task,
        target=nova,
        allow_reply=True,
    ) is True

    task.record_turn(message="one")
    task.record_turn(message="two")
    task.record_turn(message="three")

    assert NPC.should_respond_to_speech(
        nova,
        alice,
        "One more thought",
        task=task,
        target=nova,
        allow_reply=True,
    ) is False


def test_task_targeting_prevents_every_actor_in_room_from_joining_in():
    task = task_state()
    nova = SimpleNamespace(key="Nova", id=1, get_active_task=lambda: None)
    alice = SimpleNamespace(key="Alice", id=2)
    bob = SimpleNamespace(key="Bob", id=3)

    assert NPC.should_respond_to_speech(
        nova,
        alice,
        "Bob, what do you know?",
        task=task,
        target=bob,
        allow_reply=True,
    ) is False


def test_tool_authorization_is_independent_of_actor_controller_type():
    carrier = SimpleNamespace(key="Carrier", id=7)
    same_identity = SimpleNamespace(key="Proxy", id=7)
    stranger = SimpleNamespace(key="Stranger", id=9)
    tool = SimpleNamespace(db=Db(public=False), location=carrier)

    assert Tool.can_use(tool, carrier) is True
    assert Tool.can_use(tool, same_identity) is True
    assert Tool.can_use(tool, stranger) is False


def test_unscoped_npc_speech_is_terminal_and_task_speech_is_written_once():
    calls = []

    class Room:
        def msg_contents(self, message, from_obj=None):
            pass

        def handle_speech(self, speaker, message, **kwargs):
            calls.append(kwargs)

    npc = SimpleNamespace(key="Nova", location=Room())

    assert NPC.say(npc, "Hello") is True
    assert calls[-1]["allow_reply"] is False

    task_context = context()
    task = task_state(max_turns=3, working_context=task_context)
    target = SimpleNamespace(key="Alice", id=2, location=npc.location)
    assert NPC.say(
        npc,
        "What do you know?",
        task=task,
        target=target,
        allow_reply=True,
    ) is True

    assert calls[-1]["task"] is task
    assert calls[-1]["target"] is target
    assert calls[-1]["allow_reply"] is True
    assert task.db.turn_count == 1
    assert [entry["content"] for entry in Context.export(task_context)] == [
        "What do you know?"
    ]

    recipient = SimpleNamespace(get_context=lambda: context())
    Listener.record(
        SimpleNamespace(), recipient, npc, "What do you know?", task=task
    )
    assert [entry["content"] for entry in Context.export(task_context)] == [
        "What do you know?"
    ]
