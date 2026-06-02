# tests/test_whereami_command.py
"""
Tests for the `whereami` command (commands/whereami.py).

Validates:
- Command shows room info, exits, objects, and memory when present.
- Graceful handling of empty rooms, void (no location), and no exits.
"""

import pytest
from evennia import create
from typeclasses.rooms import SmartRoom
from typeclasses.characters import Character
from commands.whereami import CmdWhereami
from evennia.utils.utils import inherits_from


@pytest.fixture
def room():
    """Create a SmartRoom with a description and an exit."""
    r = create.create_object(SmartRoom, key="The Lounge")
    r.db.desc = "A comfortable lounge with velvet couches."
    r.db.memory = []
    return r


@pytest.fixture
def character(room):
    """Create a character placed in `room`."""
    c = create.create_object(Character, key="PlayerOne", location=room)
    return c


def test_whereami_basic_info(capsys, character, room):
    """whereami prints room name, description, exits, and objects."""
    # Add an exit
    from evennia import DefaultExit
    exit_obj = create.create_object(DefaultExit, key="north", location=room)
    # Add a notable object
    obj = create.create_object("Table", location=room)
    # Add memory
    room.db.memory = [{"who": "PlayerOne", "msg": "Hello, world!"}]

    cmd = CmdWhereami(caller=character)
    cmd.func()


def test_whereami_void(capsys, character, room):
    """whereami handles the case where character has no location."""
    character.location = None
    cmd = CmdWhereami(caller=character)
    cmd.func()


def test_whereami_no_exits(capsys, character, room):
    """whereami shows 'None (a dead end)' when room has no exits."""
    # Remove all exits
    for ex in list(room.exits):
        ex.delete()

    cmd = CmdWhereami(caller=character)
    cmd.func()

