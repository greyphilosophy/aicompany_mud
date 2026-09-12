"""Equipment grants ordinary objects the same capabilities as NPC bodies."""

import pytest
from evennia.utils.create import create_object
from typeclasses.objects import Object
from typeclasses.components.context import Context
from typeclasses.components.memory import Memory
from typeclasses.tasks import Task
from typeclasses.components.brain import Brain
from typeclasses.tools.notes import StickyNotePad
from tests.test_agency_requirements import world, decide


def test_ordinary_object_has_no_abilities_until_equipped(world):
    box = create_object(Object, key="Wooden box", location=world.room)
    assert box.get_brain() is None
    assert box.get_listener() is None
    assert box.get_speaker() is None
    box.at_heard_say(world.other, "Hello")
    assert world.jobs == []


def test_transferred_equipment_lets_object_hear_think_and_speak(world):
    box = create_object(Object, key="Wooden box", location=world.room)
    context = world.npc.get_context()
    context.append("Archivist", "The key is under the mat")
    memory = world.npc.get_memory()
    memory.remember("The key opens the generator")
    brain = create_object(Brain, key="Brain", location=world.npc)
    for equipment in list(world.npc.contents):
        equipment.move_to(box)
    world.clock.advance(0)
    world.room.handle_speech(world.other, "Where is the key?")
    assert len(world.jobs) == 1
    snapshot = world.jobs[0][1][0]
    assert snapshot["actor"]["name"] == "Wooden box"
    assert any("under the mat" in e["content"] for e in snapshot["context"])
    assert any("opens the generator" in e["content"] for e in snapshot["memory"])
    decide(
        world,
        {
            "action": "invoke",
            "tool": world.voice.dbref,
            "name": "say",
            "arguments": {"message": "Under the mat"},
        },
    )
    assert box.ndb.agency_results[-1]["result"]["spoken"] == "Under the mat"
    assert world.npc.get_brain() is None
    assert world.npc.get_speaker() is None
    assert world.npc.get_context() is None
    assert box.get_context() == context
    assert box.get_memory() == memory


def test_object_can_use_task_pad_and_acquire_wants(world):
    box = create_object(Object, key="Wooden box", location=world.room)
    pad = create_object(StickyNotePad, key="Notes", location=box)
    create_object(Brain, key="Brain", location=box)
    task = world.npc.create_task("Organize work")
    task.move_to(box)
    world.clock.advance(0)
    assert task.db.assignee == box
    assert box.get_active_task() == task
    assert world.npc.get_active_task() is None
    assert len(world.jobs) == 1
    decide(
        world,
        {
            "action": "invoke",
            "tool": pad.dbref,
            "name": "create_task",
            "arguments": {"objective": "Find the key"},
        },
    )
    child = next(t for t in box.get_tasks() if t != task)
    assert child.db.assignee == box
    assert child.db.parent_task == task
    assert len(world.jobs) == 2
    decide(world, {"action": "wait"})


def test_moving_brain_and_task_to_object_invalidates_old_body_decision(world):
    box = create_object(Object, key="Wooden box", location=world.room)
    brain = create_object(Brain, key="Brain", location=world.npc)
    task = world.npc.create_task("Find the key")
    for equipment in list(world.npc.contents):
        equipment.move_to(box)
    world.clock.advance(0)
    assert len(world.jobs) == 2
    decide(world, {"action": "complete", "result": "Old body's stale result"}, 0)
    assert task.db.status == "active"
    decide(world, {"action": "complete", "result": "New body's result"}, 1)
    assert task.db.status == "completed"
    assert task.db.result == "New body's result"
    assert task.db.assignee == box


@pytest.mark.parametrize("equipment", ["brain", "speaker", "context"])
def test_removing_equipment_from_object_invalidates_pending_action(world, equipment):
    box = create_object(Object, key="Wooden box", location=world.room)
    for obj in list(world.npc.contents):
        obj.move_to(box)
    brain = create_object(Brain, key="Brain", location=box)
    task = box.create_task("Find the key")
    selected = {
        "brain": brain,
        "speaker": box.get_speaker(),
        "context": box.get_context(),
    }[equipment]
    selected.move_to(world.npc)
    decide(world, {"action": "complete", "result": "Stale result"}, 0)
    assert task.db.status == "active"


def test_transferred_task_context_invalidates_object_decision(world):
    box = create_object(Object, key="Wooden box", location=world.room)
    create_object(Brain, key="Brain", location=box)
    task = box.create_task("Find the key")
    task.get_context().move_to(world.npc)
    decide(world, {"action": "complete", "result": "Stale result"})
    assert task.db.status == "active"


def test_equipped_character_uses_same_capabilities(world):
    from typeclasses.characters import Character

    character = create_object(Character, key="Avatar", location=world.room)
    create_object(Brain, key="Brain", location=character)
    task = world.npc.create_task("Find the key")
    task.move_to(character)
    world.clock.advance(0)
    assert task.db.assignee == character
    assert world.jobs[-1][1][0]["actor"]["id"] == character.dbref
    decide(world, {"action": "complete", "result": "Under the mat"})
    assert task.db.status == "completed"


def test_dropping_equipment_in_room_does_not_animate_room(world):
    brain = create_object(Brain, key="Brain", location=world.npc)
    task = world.npc.create_task("Find the key")
    brain.move_to(world.room)
    task.move_to(world.room)
    world.clock.advance(0)
    decide(world, {"action": "complete", "result": "Stale result"})
    assert task.db.status == "active"
    assert task.db.assignee is None
    assert len(world.jobs) == 1
