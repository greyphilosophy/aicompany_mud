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
    npc = create_object(NPC, key="Nova", location=room)
    other = create_object(NPC, key="Alice", location=room)
    jobs = []
    def dispatch(fn, *args):
        d = Deferred()
        jobs.append((fn, args, d))
        return d
    monkeypatch.setattr("typeclasses.agency.deferToThread", dispatch)
    listener = create_object(Listener, key="Listener", location=npc)
    voice = create_object(Speaker, key="Voice", location=npc)
    return SimpleNamespace(room=room, npc=npc, other=other, jobs=jobs, voice=voice)


def equip(w):
    return create_object(Brain, key="Brain", location=w.npc)


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
    decide(world, {"action": "invoke", "tool": pad.dbref, "name": "create_task", "arguments": {"objective": "Find the key"}})
    assert len(world.jobs) == 2
    snapshot = world.jobs[-1][1][0]
    assert snapshot["results"][-1]["ok"] is True
    assert len(world.npc.get_tasks()) == 1
    decide(world, {"action": "wait"})
    assert len(world.jobs) == 2


@pytest.mark.parametrize("change", ["brain", "tool", "task", "actor", "brain_roundtrip", "tool_roundtrip", "task_roundtrip"])
def test_pending_actions_invalidated_by_movement(world, change):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    brain = equip(world)
    task = world.npc.create_task("Organize work")
    obj = {"brain": brain, "tool": pad, "task": task, "actor": world.npc,
           "brain_roundtrip": brain, "tool_roundtrip": pad, "task_roundtrip": task}[change]
    original = obj.location
    obj.move_to(world.other)
    if change.endswith("roundtrip"):
        obj.move_to(original)
    decide(world, {"action": "invoke", "tool": pad.dbref, "name": "create_task", "arguments": {"objective": "Stale work"}}, 0)
    assert all(t.db.objective != "Stale work" for t in world.npc.get_tasks())


@pytest.mark.parametrize("arguments", [{}, {"objective": ""}, {"objective": "x", "bogus": 1}, {"objective": "x", "max_turns": True}])
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
    decide(world, {"action": "invoke", "tool": pad.dbref, "name": "create_task", "arguments": {"objective": "Forbidden"}})
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
    decide(world, {"action": "invoke", "tool": world.voice.dbref, "name": "say", "arguments": {"message": "Hello"}})
    assert world.npc.ndb.agency_results[-1]["ok"] is False


def test_repeat_action_stops_without_creating_duplicate(world):
    pad = create_object(StickyNotePad, key="Notes", location=world.npc)
    equip(world)
    world.npc.at_heard_say(world.other, "Make a note")
    decision = {"action": "invoke", "tool": pad.dbref, "name": "create_task", "arguments": {"objective": "Find the key"}}
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
