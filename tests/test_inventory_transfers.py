"""Player-command acceptance tests for portable inventory capabilities."""
from unittest.mock import Mock

import pytest
from evennia.utils.create import create_object
from typeclasses.objects import Object
from typeclasses.characters import Character
from typeclasses.agency import Brain
from tests.test_agency_requirements import world


def run_get(w, args):
    from commands.inventory import CmdGet
    cmd = CmdGet()
    cmd.caller = w.player
    cmd.args = args
    cmd.cmdstring = 'get'
    cmd.raw_string = 'get ' + args
    cmd.parse()
    cmd.func()


@pytest.fixture
def transfer(world):
    world.player = create_object(Character, key='Player', location=world.room)
    world.player.msg = Mock()
    return world


def test_get_equipment_from_npc(transfer):
    w = transfer
    run_get(w, 'Voice from Nova')
    assert w.voice.location == w.player
    assert w.npc.get_speaker() is None
    assert w.player.get_speaker() == w.voice


@pytest.mark.parametrize('carried', [False, True])
def test_get_from_ordinary_object(transfer, carried):
    w = transfer
    box = create_object(Object, key='Box', location=w.player if carried else w.room)
    w.voice.move_to(box)
    run_get(w, 'Voice from Box')
    assert w.voice.location == w.player


@pytest.mark.parametrize('lock_target,lock', [('holder', 'get_from:false()'), ('item', 'get:false()')])
def test_locks_prevent_removal(transfer, lock_target, lock):
    w = transfer
    (w.npc if lock_target == 'holder' else w.voice).locks.add(lock)
    run_get(w, 'Voice from Nova')
    assert w.voice.location == w.npc
    assert w.player.msg.called


def test_character_inventory_requires_explicit_access(transfer):
    w = transfer
    other = create_object(Character, key='Visitor', location=w.room)
    w.voice.move_to(other)
    run_get(w, 'Voice from Visitor')
    assert w.voice.location == other
    other.locks.add('get_from:all()')
    run_get(w, 'Voice from Visitor')
    assert w.voice.location == w.player


def test_remote_holder_not_accessible_even_by_dbref(transfer):
    w = transfer
    w.npc.move_to(None)
    run_get(w, f'{w.voice.dbref} from {w.npc.dbref}')
    assert w.voice.location == w.npc


def test_nested_item_not_accessible_by_dbref(transfer):
    w = transfer
    box = create_object(Object, key='Box', location=w.npc)
    w.voice.move_to(box)
    run_get(w, f'{w.voice.dbref} from Nova')
    assert w.voice.location == box


@pytest.mark.parametrize('failure', ['hook', 'move'])
def test_failed_pickup(transfer, monkeypatch, failure):
    w = transfer
    monkeypatch.setattr(w.voice, 'at_pre_get' if failure == 'hook' else 'move_to', lambda *a, **kw: False)
    run_get(w, 'Voice from Nova')
    assert w.voice.location == w.npc


def test_ambiguous_item_not_moved(transfer):
    w = transfer
    duplicate = create_object(Object, key='Voice', location=w.npc)
    run_get(w, 'Voice from Nova')
    assert w.voice.location == w.npc
    assert duplicate.location == w.npc


def test_real_cmdset_give_and_get(transfer):
    w = transfer
    brain = create_object(Brain, key='Brain', location=w.player)
    w.player.execute_cmd('give Brain to Nova')
    assert brain.location == w.npc
    w.player.execute_cmd('get Brain from Nova')
    assert brain.location == w.player
    assert w.npc.get_brain() is None
    assert w.player.get_brain() == brain
    w.voice.move_to(w.room)
    w.player.execute_cmd('get Voice')
    assert w.voice.location == w.player
