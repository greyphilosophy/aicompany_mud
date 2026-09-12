"""Exercise real Evennia objects and speech routing with a controlled LLM worker."""

from types import SimpleNamespace

import evennia
import pytest
from twisted.internet.defer import Deferred

from evennia.utils.create import create_object
from typeclasses.components.context import Context
from typeclasses.components.listener import Listener
from typeclasses.npcs import NPC
from typeclasses.tools.speaker import Speaker
from typeclasses.tasks import Task
from typeclasses.tools.base import Tool


@pytest.fixture
def world(transactional_db, monkeypatch, settings):
    settings.TEST_ENVIRONMENT = True
    settings.DEFAULT_HOME = None
    from evennia.utils.idmapper.models import flush_cache

    flush_cache()
    evennia._init()
    from typeclasses.rooms import SmartRoom

    room = create_object(SmartRoom, key="Lab")
    actors = [
        create_object(NPC, key=name, location=room) for name in ("Nova", "Alice", "Bob")
    ]
    jobs = []
    for actor in actors:
        actor.db.legacy_autoreply = True
        create_object(Listener, key="Listener", location=actor)
        create_object(Speaker, key="Speaker", location=actor)

    def dispatch(function, *args):
        deferred = Deferred()
        jobs.append((function, args, deferred))
        return deferred

    monkeypatch.setattr("typeclasses.actors.deferToThread", dispatch)
    return room, actors, jobs


def answer(jobs, index=0, response="A clue", action="continue", progress=True):
    jobs[index][2].callback(dict(response=response, action=action, progress=progress))


def test_real_room_exchange_combines_private_knowledge_and_stops_at_budget(world):
    room, (nova, alice, bob), jobs = world
    alice.get_context().append("Archivist", "The key is under the mat")
    nova.get_memory().remember("The key opens the generator")
    task = nova.create_task("Locate the generator key", max_turns=3)
    assert nova.ask(alice, "Where is the key?", task)
    assert len(jobs) == 1
    assert any("under the mat" in m["content"] for m in jobs[0][1][1])
    answer(jobs, response="The key is under the mat")
    assert len(jobs) == 2
    assert any("opens the generator" in m["content"] for m in jobs[1][1][1])
    answer(jobs, 1, response="I can retrieve it")
    assert len(jobs) == 2
    assert task.db.status == "budget_exhausted"
    assert task.db.turn_count == 3
    assert len(task.get_context().export()) == 3
    assert nova.get_context().export() == []
    assert len(alice.get_context().export()) == 1
    assert bob.get_context().export() == []


@pytest.mark.parametrize(
    "action,status",
    [("complete", "completed"), ("decline", "declined"), ("stop", "stalled")],
)
@pytest.mark.parametrize("speech", ["Finished", ""])
def test_task_terminal_response_stops_exchange(world, action, status, speech):
    room, (nova, alice, _), jobs = world
    task = nova.create_task("Find the key")
    nova.ask(alice, "Can you help?", task)
    answer(jobs, response=speech, action=action)
    assert task.db.status == status
    assert len(jobs) == 1
    assert not alice.ndb.reply_inflight


def test_no_progress_from_real_responses_stalls_exchange(world):
    room, (nova, alice, _), jobs = world
    task = nova.create_task("Find the key", max_no_progress_turns=2)
    nova.ask(alice, "Any clues?", task)
    answer(jobs, progress=False)
    answer(jobs, 1, progress=False)
    assert task.db.status == "stalled"
    assert len(jobs) == 2


@pytest.mark.parametrize(
    "change",
    ["context", "task_owner", "speaker_room", "target_room", "voice", "completed"],
)
def test_stale_task_reply_is_not_spoken_or_recorded(world, change):
    room, (nova, alice, bob), jobs = world
    task = nova.create_task("Find the key")
    nova.ask(alice, "Any clues?", task)
    original = task.get_context()
    elsewhere = create_object(type(room), key="Elsewhere")
    if change == "context":
        original.move_to(bob)
        create_object(Context, key="Replacement", location=task)
    elif change == "task_owner":
        task.move_to(bob)
    elif change == "speaker_room":
        alice.move_to(elsewhere)
    elif change == "target_room":
        nova.move_to(elsewhere)
    elif change == "voice":
        alice.get_speaker().move_to(bob)
    else:
        task.complete("Already solved")
    answer(jobs)
    assert task.db.turn_count == 1
    assert len(original.export()) == 1
    assert len(jobs) == 1


def test_failed_transfer_does_not_change_assignee(world, monkeypatch):
    room, (nova, alice, _), jobs = world
    task = nova.create_task("Find the key")
    monkeypatch.setattr(task, "move_to", lambda *a, **kw: False)
    assert alice.accept_task(task) is False
    assert task.db.assignee == nova


def test_missing_actor_cannot_use_unplaced_tool(world):
    tool = create_object(Tool, key="Tool")
    assert not tool.can_use(None)


def test_absent_target_does_not_consume_budget(world):
    room, (nova, alice, _), jobs = world
    task = nova.create_task("Find the key")
    alice.location = None
    assert not nova.ask(alice, "Can you help?", task)
    assert task.db.turn_count == 0
    assert jobs == []


@pytest.mark.parametrize(
    "payload",
    [
        {"response": "Yes", "progress": "false"},
        {"response": "Yes", "action": "invented"},
        {"response": "", "action": "continue"},
    ],
)
def test_task_response_protocol_rejects_malformed_control(monkeypatch, payload):
    monkeypatch.setattr(
        "typeclasses.tools.speaker.build_default_client_from_env",
        lambda: SimpleNamespace(chat_json=lambda *args: payload),
    )
    with pytest.raises(ValueError):
        Speaker.generate_response_from_messages(
            "Nova", [], [], Speaker.SYSTEM_PROMPT, True
        )


@pytest.mark.parametrize(
    "change", ["context", "task_owner", "speaker_room", "target_room"]
)
def test_queued_task_is_revalidated_before_dispatch(world, change):
    room, (nova, alice, bob), jobs = world
    # Ordinary speech occupies Alice's worker; task speech is queued behind it.
    alice.at_heard_say(nova, "Hello")
    task = nova.create_task("Find the key")
    nova.ask(alice, "Any clues?", task)
    assert len(jobs) == 1
    elsewhere = create_object(type(room), key="Elsewhere")
    if change == "context":
        task.get_context().move_to(bob)
        create_object(Context, key="Replacement", location=task)
    elif change == "task_owner":
        task.move_to(bob)
    elif change == "speaker_room":
        alice.move_to(elsewhere)
    else:
        nova.move_to(elsewhere)
    jobs[0][2].callback("Hello back")
    assert len(jobs) == 1
    assert not alice.ndb.reply_inflight
    assert not alice.ndb.reply_pending


def test_worker_protocol_reaches_task_completion(world, monkeypatch):
    room, (nova, alice, _), jobs = world
    task = nova.create_task("Find the key")
    nova.ask(alice, "Where is it?", task)
    monkeypatch.setattr(
        "typeclasses.tools.speaker.build_default_client_from_env",
        lambda: SimpleNamespace(
            chat_json=lambda *args: {
                "response": "Under the mat",
                "action": "complete",
                "progress": True,
            }
        ),
    )
    function, args, deferred = jobs[0]
    deferred.callback(function(*args))
    assert task.db.status == "completed"
    assert task.db.result == "Under the mat"
    assert len(jobs) == 1


def test_unscoped_speech_does_not_bounce_between_real_npcs(world):
    room, (nova, alice, bob), jobs = world
    nova.say("Hello")
    assert jobs == []
    assert len(alice.get_context().export()) == 1
    assert len(bob.get_context().export()) == 1


def test_missing_task_context_does_not_broadcast_or_consume_budget(world):
    room, (nova, alice, bob), jobs = world
    task = nova.create_task("Find the key")
    task.get_context().move_to(bob)
    assert not nova.ask(alice, "Can you help?", task)
    assert task.db.turn_count == 0
    assert jobs == []
