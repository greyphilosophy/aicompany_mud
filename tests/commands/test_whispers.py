# tests/commands/test_whispers.py
"""
Tests for the Whispers command (commands/whispers.py).
"""
import sys
import os

# Add the project root to sys.path so we can import commands/whispers
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import unittest
from unittest.mock import MagicMock

# Mock the evennia module since it's the main external dependency
class MockEvennia:
    class Command:
        def __init__(self):
            self.caller = MagicMock()
            self.args = ""

        def msg(self, text):
            self._last_msg = text

    pass

# Patch the import before importing the command module
sys.modules["evennia"] = MockEvennia
sys.modules["evennia.commands"] = MagicMock()

from commands.whispers import CmdWhispers


class TestCmdWhispersBasic(unittest.TestCase):
    """Unit tests for the Whispers command logic."""

    def setUp(self):
        self.cmd = CmdWhispers()
        self.cmd.caller = MagicMock()
        self.cmd.caller.msg = MagicMock()

    def test_no_room(self):
        """When the caller has no location, we get a 'nowhere' message."""
        self.cmd.caller.location = None
        self.cmd.func()
        self.cmd.caller.msg.assert_called_once()
        msg = self.cmd.caller.msg.call_args[0][0]
        self.assertIn("nowhere", msg.lower())

    def test_room_without_memory(self):
        """When the room has no memory attribute, we get a quiet message."""
        room = MagicMock(spec=[])
        room.db = MagicMock(memory=None)
        room.db.memory = None
        self.cmd.caller.location = room
        self.cmd.func()
        self.cmd.caller.msg.assert_called_once()
        msg = self.cmd.caller.msg.call_args[0][0]
        self.assertIn("quiet", msg.lower())

    def test_room_with_empty_memory(self):
        """When the room has an empty memory list, we get a quiet message."""
        room = MagicMock(spec=[])
        room.db = MagicMock(memory=[])
        room.db.memory = []
        self.cmd.caller.location = room
        self.cmd.func()
        self.cmd.caller.msg.assert_called_once()
        msg = self.cmd.caller.msg.call_args[0][0]
        self.assertIn("quiet", msg.lower())

    def test_room_with_memories(self):
        """When the room has memories, they are displayed."""
        room = MagicMock(spec=[])
        memories = [
            {"who": "Alice", "msg": "Hello, world!"},
            {"who": "Bob", "msg": "Welcome!"},
        ]
        room.db = MagicMock(memory=memories)
        room.db.memory = memories
        self.cmd.caller.location = room
        self.cmd.func()
        self.cmd.caller.msg.assert_called_once()
        msg = self.cmd.caller.msg.call_args[0][0]
        self.assertIn("whispers", msg.lower())
        self.assertIn("Alice", msg)
        self.assertIn("Bob", msg)

    def test_max_display_limit(self):
        """Only the last MAX_DISPLAY memories are shown."""
        room = MagicMock(spec=[])
        memories = [{"who": f"Player{i}", "msg": f"msg{i}"} for i in range(20)]
        room.db = MagicMock(memory=memories)
        room.db.memory = memories
        self.cmd.caller.location = room
        self.cmd.func()
        msg = self.cmd.caller.msg.call_args[0][0]
        # Should show last 10 (Player10..Player19), not Player0..Player9
        # Player9 should NOT be in the output (only last 10)
        # Actually MAX_DISPLAY=10, so last 10: indices 10-19
        self.assertIn("Player19", msg)
        self.assertIn("Player10", msg)
        self.assertNotIn("Player0", msg)
        self.assertNotIn("Player5", msg)


if __name__ == "__main__":
    unittest.main()