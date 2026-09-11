"""Acceptance tests for physical, bounded agency (real Evennia objects)."""

import json
from types import SimpleNamespace

import evennia
import pytest
from twisted.internet.defer import Deferred
from evennia.utils.create import create_object
from typeclasses.npcs import NPC, Listener, Speaker, Task
from typeclasses.agency import Brain, StickyNotePad


@pytest.fixture
def world(transactional_db, monkeypatch, settings):
    settings.TEST_ENVIRONMENT = True
    settings.DEFAULT_HOME = None
    from evennia.utils.idmapper.models import flush_cache

    flush_cache()
    evennia._init()
    from typeclasses.rooms import SmartRoom

    room = create_object(SmartRoom, key="Workshop")
    settings.DEFAULT_HOME = room.dbref
    npc = create_object(NPC, key="Nova", location=room)
    other = create_object(NPC, key="Alice", location=room)
    from twisted.internet.task import Clock

    clock = Clock()
    monkeypatch.setattr("typeclasses.agency.reactor", clock)
    jobs = []

    def dispatch(fn, *args):
        d = Deferred()
        jobs.append((fn, args, d))
        return d

    monkeypatch.setattr("typeclasses.agency.deferToThread", dispatch)
    listener = create_object(Listener, key="Listener", location=npc)
    voice = create_object(Speaker, key="Voice", location=npc)
    return SimpleNamespace(
        room=room, npc=npc, other=other, jobs=jobs, voice=voice, clock=clock
    )


def equip(w):
    brain = create_object(Brain, key="Brain", location=w.npc)
    w.clock.advance(0)
    return brain


def decide(w, decision, index=-1):
    w.jobs[index][2].callback(decision)


def test_speaker_without_brain_is_inert(world, monkeypatch):
    def forbidden(*args):
        pytest.fail("Speaker must not reason without a Brain")

    monkeypatch.setattr("typeclasses.npcs.deferToThread", forbidden)
    world.npc.at_heard_say(world.other, "Hello")
    assert len(world.npc.get_context().export()) == 1
    assert world.jobs == []


def test_brain_can_wait_instead_of_replying(world):
    equip(world)
    world.npc.at_heard_say(world.other, "Hello")
    assert len(world.jobs) == 1
    decide(world, {"action": "wait", "reason": "No useful contribution"})
    assert len(world.jobs) == 1
    assert not world.npc.ndb.agency_inflight


def test_pad_creates_real_task_and_wakes_brain(world):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    equip(world)
    result = pad.invoke(world.npc, "create_task", {"objective": "Find the key"})
    task = world.npc.get_active_task()
    assert result["task"] == task.dbref
    assert task.db.objective == "Find the key"
    assert task.db.assignee == world.npc
    assert task.db.requester == world.npc
    assert task.get_context() is not None
    assert len(world.jobs) == 1


def test_tool_result_feeds_next_decision_without_overlapping(world):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    equip(world)
    world.npc.at_heard_say(world.other, "Write down an objective")
    decide(
        world,
        {
            "action": "invoke",
            "tool": pad.dbref,
            "name": "create_task",
            "arguments": {"objective": "Find the key"},
        },
    )
    assert len(world.jobs) == 2
    snapshot = world.jobs[-1][1][0]
    assert snapshot["results"][-1]["ok"] is True
    assert len(world.npc.get_tasks()) == 1
    decide(world, {"action": "wait"})
    assert len(world.jobs) == 2


@pytest.mark.parametrize(
    "change",
    [
        "brain",
        "tool",
        "task",
        "actor",
        "brain_roundtrip",
        "tool_roundtrip",
        "task_roundtrip",
    ],
)
def test_pending_actions_invalidated_by_movement(world, change):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    brain = equip(world)
    task = world.npc.create_task("Organize work")
    obj = {
        "brain": brain,
        "tool": pad,
        "task": task,
        "actor": world.npc,
        "brain_roundtrip": brain,
        "tool_roundtrip": pad,
        "task_roundtrip": task,
    }[change]
    original = obj.location
    obj.move_to(world.other)
    if change.endswith("roundtrip"):
        obj.move_to(original)
    decide(
        world,
        {
            "action": "invoke",
            "tool": pad.dbref,
            "name": "create_task",
            "arguments": {"objective": "Stale work"},
        },
        0,
    )
    assert all(t.db.objective != "Stale work" for t in world.npc.get_tasks())


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"objective": ""},
        {"objective": "x", "bogus": 1},
        {"objective": "x", "max_turns": True},
    ],
)
def test_invalid_tool_arguments_have_no_effect(world, arguments):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    with pytest.raises(ValueError):
        pad.invoke(world.npc, "create_task", arguments)
    assert world.npc.get_tasks() == []


def test_tool_access_rechecked(world):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    equip(world)
    world.npc.create_task("Organize work")
    pad.locks.add("use:false()")
    decide(
        world,
        {
            "action": "invoke",
            "tool": pad.dbref,
            "name": "create_task",
            "arguments": {"objective": "Forbidden"},
        },
    )
    assert len(world.npc.get_tasks()) == 1
    assert world.npc.ndb.agency_results[-1]["ok"] is False


def test_transfer_changes_wants_and_assignee(world):
    task = world.npc.create_task("Find the key")
    task.move_to(world.other)
    assert world.npc.get_active_task() is None
    assert world.other.get_active_task() == task
    assert task.db.assignee == world.other
    task.move_to(world.room)
    assert world.other.get_active_task() is None
    assert task.db.assignee is None


def test_brain_worker_gets_only_plain_data(world):
    equip(world)
    world.npc.create_task("Find the key")
    json.dumps(world.jobs[0][1][0])


def test_speech_requires_speaker(world):
    world.voice.move_to(world.other)
    equip(world)
    world.npc.create_task("Ask for help")
    snapshot = world.jobs[0][1][0]
    assert not any(t["id"] == world.voice.dbref for t in snapshot["tools"])
    decide(
        world,
        {
            "action": "invoke",
            "tool": world.voice.dbref,
            "name": "say",
            "arguments": {"message": "Hello"},
        },
    )
    assert world.npc.ndb.agency_results[-1]["ok"] is False


def test_repeat_action_stops_without_creating_duplicate(world):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    equip(world)
    world.npc.at_heard_say(world.other, "Make a note")
    decision = {
        "action": "invoke",
        "tool": pad.dbref,
        "name": "create_task",
        "arguments": {"objective": "Find the key"},
    }
    decide(world, decision)
    decide(world, decision)
    assert len(world.npc.get_tasks()) == 1
    assert len(world.jobs) == 2


def test_completion_is_a_claim_on_held_task(world):
    equip(world)
    task = world.npc.create_task("Find the key")
    decide(world, {"action": "complete", "result": "It is under the mat"})
    assert task.db.status == "completed"
    assert task.db.result == "It is under the mat"


def test_one_model_call_at_a_time_and_latest_observation_is_coalesced(world):
    equip(world)
    world.npc.at_heard_say(world.other, "Hello")
    world.npc.at_heard_say(world.other, "One more thing")
    world.npc.at_heard_say(world.other, "Latest question")
    assert len(world.jobs) == 1
    decide(world, {"action": "wait"})
    assert len(world.jobs) == 2
    assert world.jobs[-1][1][0]["observation"]["message"] == "Latest question"
    decide(world, {"action": "wait"})
    assert len(world.jobs) == 2


def test_budget_bounds_chained_task_creation(world):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    equip(world)
    world.npc.at_heard_say(world.other, "Organize some work")
    for index in range(Brain.MAX_STEPS):
        decide(
            world,
            {
                "action": "invoke",
                "tool": pad.dbref,
                "name": "create_task",
                "arguments": {"objective": f"Work {index}"},
            },
        )
    assert len(world.jobs) == Brain.MAX_STEPS
    assert len(world.npc.get_tasks()) == Brain.MAX_STEPS
    assert world.npc.ndb.agency_state == "budget_exhausted"
    assert not world.npc.ndb.agency_inflight


def test_task_budget_persists_across_wakes_and_transfer(world):
    task = world.npc.create_task("Find the key")
    task.db.max_actions = 2
    equip(world)
    decide(world, {"action": "wait"})
    world.npc.reconsider()
    decide(world, {"action": "wait"})
    world.npc.reconsider()
    assert len(world.jobs) == 2
    task.move_to(world.other)
    create_object(Brain, key="Other brain", location=world.other)
    assert len(world.jobs) == 2
    assert task.db.action_count == 2


def test_highest_priority_then_oldest_task_selected(world):
    low = world.npc.create_task("Low priority")
    first = world.npc.create_task("High priority")
    first.db.priority = 5
    second = world.npc.create_task("Also high")
    second.db.priority = 5
    equip(world)
    assert world.jobs[0][1][0]["selected_task"]["id"] == first.dbref
    assert [t["id"] for t in world.jobs[0][1][0]["tasks"]] == [
        first.dbref,
        second.dbref,
        low.dbref,
    ]


def test_model_failure_stops_and_releases_actor(world):
    equip(world)
    world.npc.create_task("Find the key")
    world.jobs[0][2].errback(RuntimeError("Provider unavailable"))
    assert world.npc.ndb.agency_state == "blocked"
    assert not world.npc.ndb.agency_inflight
    assert len(world.jobs) == 1
    assert world.npc.ndb.agency_results[-1]["ok"] is False


def test_brain_decision_runs_through_real_provider_adapter(world, monkeypatch):
    equip(world)
    task = world.npc.create_task("Find the key")
    seen = {}

    def chat(providers, messages):
        seen["messages"] = messages
        return {"action": "complete", "result": "Found it"}

    monkeypatch.setattr(
        "typeclasses.agency.build_default_client_from_env",
        lambda: SimpleNamespace(chat_json=chat),
    )
    fn, args, d = world.jobs[0]
    json.dumps(args)
    d.callback(fn(*args))
    assert task.db.status == "completed"
    assert (
        json.loads(seen["messages"][-1]["content"])["selected_task"]["objective"]
        == "Find the key"
    )


def test_two_brains_converse_using_speakers_then_wait(world):
    create_object(Listener, key="Ears", location=world.other)
    voice = create_object(Speaker, key="Other voice", location=world.other)
    create_object(Brain, key="Other brain", location=world.other)
    world.other.get_context().append("Archivist", "The key is under the mat")
    equip(world)
    task = world.npc.create_task("Find the key")
    decide(
        world,
        {
            "action": "invoke",
            "tool": world.voice.dbref,
            "name": "say",
            "arguments": {
                "message": "Do you know where the key is?",
                "target": world.other.dbref,
            },
        },
    )
    assert len(world.jobs) == 2
    assert "under the mat" in json.dumps(world.jobs[-1][1][0]["context"])
    decide(
        world,
        {
            "action": "invoke",
            "tool": voice.dbref,
            "name": "say",
            "arguments": {"message": "Under the mat", "target": world.npc.dbref},
        },
    )
    assert len(world.jobs) == 3
    decide(world, {"action": "complete", "result": "The key is under the mat"})
    assert task.db.status == "completed"
    assert len(task.get_context().export()) == 2
    assert world.npc.get_context().export() == []
    assert len(world.other.get_context().export()) == 1


def test_unscoped_brain_speech_cannot_wake_other_brains(world):
    create_object(Listener, key="Ears", location=world.other)
    create_object(Brain, key="Other brain", location=world.other)
    equip(world)
    world.npc.at_heard_say(world.other, "Hello")
    decide(
        world,
        {
            "action": "invoke",
            "tool": world.voice.dbref,
            "name": "say",
            "arguments": {"message": "Hello back"},
        },
    )
    assert len(world.jobs) == 1


def test_player_command_uses_same_tool_validation(world, monkeypatch):
    from typeclasses.characters import Character
    from commands.tools import CmdUseTool

    player = create_object(Character, key="Alfred", location=world.room)
    pad = create_object(StickyNotePad, key="Notes", location=player)
    messages = []
    monkeypatch.setattr(player, "msg", lambda text, **kwargs: messages.append(text))
    command = CmdUseTool()
    command.caller = player
    command.args = 'Notes/create_task = {"objective": "Find the key"}'
    command.func()
    assert json.loads(messages[-1])["ok"] is True
    task = next(obj for obj in player.contents if isinstance(obj, Task))
    assert task.db.assignee == player
    command.args = 'Notes/create_task = {"objective": ""}'
    command.func()
    assert json.loads(messages[-1])["ok"] is False
    assert len([obj for obj in player.contents if isinstance(obj, Task)]) == 1


def test_task_context_roundtrip_invalidates_pending_work(world):
    equip(world)
    task = world.npc.create_task("Find the key")
    context = task.get_context()
    context.move_to(world.other)
    context.move_to(task)
    decide(world, {"action": "complete", "result": "Stale answer"})
    assert task.db.status == "active"


def test_equipping_brain_during_legacy_call_does_not_overlap(world, monkeypatch):
    world.npc.db.legacy_autoreply = True
    old = Deferred()
    monkeypatch.setattr("typeclasses.npcs.deferToThread", lambda *args: old)
    world.npc.at_heard_say(world.other, "Hello")
    equip(world)
    world.npc.at_heard_say(world.other, "Think about this")
    assert world.jobs == []
    old.callback("An obsolete reply")
    assert len(world.jobs) == 1
    assert not any(
        e["content"] == "An obsolete reply" for e in world.npc.get_context().export()
    )


def test_wait_never_polls_even_with_multiple_tasks(world):
    world.npc.create_task("First want")
    world.npc.create_task("Second want")
    equip(world)
    decide(world, {"action": "wait"})
    world.clock.advance(100)
    assert len(world.jobs) == 1


def test_completing_task_can_advance_to_next_want_within_burst(world):
    first = world.npc.create_task("First want")
    second = world.npc.create_task("Second want")
    equip(world)
    decide(world, {"action": "complete", "result": "Done"})
    assert first.db.status == "completed"
    assert len(world.jobs) == 2
    assert world.jobs[-1][1][0]["selected_task"]["id"] == second.dbref
    decide(world, {"action": "wait"})


def test_exhausted_task_does_not_starve_other_wants(world):
    exhausted = world.npc.create_task("No budget")
    exhausted.db.action_count = 12
    available = world.npc.create_task("Still actionable")
    equip(world)
    assert world.jobs[0][1][0]["selected_task"]["id"] == available.dbref


def test_manual_reconsider_does_not_reuse_departed_speaker(world):
    equip(world)
    world.npc.at_heard_say(world.other, "Hello")
    decide(world, {"action": "wait"})
    world.other.move_to(world.npc)
    task = world.npc.create_task("Independent work")
    decide(world, {"action": "complete", "result": "Done independently"})
    assert task.db.status == "completed"


def test_moving_task_to_equipped_npc_wakes_it_on_next_reactor_turn(world):
    brain = equip(world)
    task = world.other.create_task("Find the key")
    task.move_to(world.npc)
    assert not world.jobs
    world.clock.advance(0)
    assert len(world.jobs) == 1


def test_reduced_budget_invalidates_pending_action(world):
    equip(world)
    task = world.npc.create_task("Find the key")
    task.db.max_actions = -1
    decide(world, {"action": "complete", "result": "Not allowed"})
    assert task.db.status == "active"


def test_deleted_tool_cannot_execute_pending_action(world):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    tool_id = pad.dbref
    equip(world)
    task = world.npc.create_task("Organize work")
    pad.delete()
    decide(
        world,
        {
            "action": "invoke",
            "tool": tool_id,
            "name": "create_task",
            "arguments": {"objective": "Ghost action"},
        },
    )
    assert len(world.npc.get_tasks()) == 1


def test_foreign_task_cannot_be_completed_by_helper(world):
    equip(world)
    task = world.other.create_task("Find the key")
    world.other.ask(world.npc, "Any clues?", task)
    decide(world, {"action": "complete", "result": "I declare it done"})
    assert task.db.status == "active"
    assert world.npc.ndb.agency_results[-1]["ok"] is False


def test_unknown_actions_and_unadvertised_tools_are_rejected(world):
    equip(world)
    world.npc.create_task("Find the key")
    decide(world, {"action": "execute_python", "code": "print('No')"})
    assert world.npc.ndb.agency_state == "blocked"
    assert len(world.jobs) == 1


def test_decision_dispatch_failure_releases_actor(world, monkeypatch):
    equip(world)

    def fail(*args):
        raise RuntimeError("Thread pool unavailable")

    monkeypatch.setattr("typeclasses.agency.deferToThread", fail)
    world.npc.create_task("Find the key")
    assert not world.npc.ndb.agency_inflight
    assert world.npc.ndb.agency_state == "blocked"


def test_zero_task_budget_disables_decisions(world):
    task = world.npc.create_task("Paused work")
    task.db.max_actions = 0
    equip(world)
    assert world.jobs == []
    assert world.npc.ndb.agency_state == "budget_exhausted"


def test_autonomous_subtasks_share_parent_budget(world):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    parent = world.npc.create_task("Organize work")
    parent.db.max_actions = 2
    equip(world)
    decide(
        world,
        {
            "action": "invoke",
            "tool": pad.dbref,
            "name": "create_task",
            "arguments": {"objective": "Follow-up work"},
        },
    )
    child = next(t for t in world.npc.get_tasks() if t != parent)
    assert child.db.parent_task == parent
    decide(world, {"action": "complete", "result": "Planning done"})
    assert parent.db.status == "completed"
    assert len(world.jobs) == 2
    world.npc.reconsider()
    assert len(world.jobs) == 2
    assert parent.db.action_count == 2
    assert child.db.status == "active"


def test_subtask_budget_does_not_reset_when_transferred(world):
    from typeclasses.agency import budget_task

    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    parent = world.npc.create_task("Organize work")
    result = pad.invoke(
        world.npc, "create_task", {"objective": "Follow-up work"}, task=parent
    )
    child = next(t for t in world.npc.get_tasks() if t.dbref == result["task"])
    parent.db.action_count = 12
    child.move_to(world.other)
    create_object(Brain, key="Other brain", location=world.other)
    world.clock.advance(0)
    assert budget_task(child) == parent
    assert not world.jobs
