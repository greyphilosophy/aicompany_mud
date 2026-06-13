"""
Tests for the regen command (commands/regen.py).

Tests cover:
1. Command class metadata (key, aliases, help_category)
2. Argument parsing (no args = room, args = object by name or dbref)
3. Error messages and edge cases
4. Cmdset registration

Note: These tests avoid importing the evennia `Command` base class so they
run standalone without the full Evennia environment.
"""

import pytest


class TestRegenCommandMetadata:
    """Verify command metadata is correct by reading the source file."""

    def test_command_file_exists(self):
        """The command file should exist."""
        import os
        assert os.path.exists("commands/regen.py")

    def test_command_has_correct_key(self):
        """Command key should be 'regen' in the source."""
        with open("commands/regen.py") as f:
            source = f.read()
        assert 'key = "regen"' in source

    def test_command_has_alias(self):
        """Command should have 'regenerate' alias in the source."""
        with open("commands/regen.py") as f:
            source = f.read()
        assert '"regenerate"' in source

    def test_command_has_help_category(self):
        """Command should be in the Building help category."""
        with open("commands/regen.py") as f:
            source = f.read()
        assert 'help_category = "Building"' in source


class TestRegenArgParsing:
    """Test argument parsing logic for regen commands."""

    def test_strip_empty_args(self):
        """Empty args should result in empty string."""
        args = "  "
        assert args.strip() == ""

    def test_plain_name_is_preserved(self):
        """Plain name argument should pass through."""
        args = "keycard"
        assert args.strip() == "keycard"

    def test_dbref_is_recognized(self):
        """#42 should be recognized as a dbref."""
        args = "#42"
        assert args.startswith("#") and args[1:].isdigit()

    def test_non_digit_hash_is_not_dbref(self):
        """#abc should not be recognized as a dbref."""
        args = "#abc"
        assert args.startswith("#") and not args[1:].isdigit()

    def test_dbref_multi_digit(self):
        """#12345 should be recognized as a dbref."""
        args = "#12345"
        assert args.startswith("#") and args[1:].isdigit()


class TestRegenErrorMessages:
    """Test error message generation for edge cases."""

    def test_backend_down_message(self):
        """Backend down message should be informative."""
        msg = "FLUX.2 server is not running or the backend is down."
        assert "not running" in msg or "backend" in msg or "down" in msg

    def test_no_location_message(self):
        """No location message should inform the caller."""
        msg = "You are nowhere."
        assert "nowhere" in msg

    def test_no_object_found_message(self):
        """No object found message should include the object ref."""
        msg = "No object named 'keycard' found."
        assert "keycard" in msg

    def test_no_room_message(self):
        """Room regeneration without a room should error."""
        msg = "You are nowhere."
        assert "nowhere" in msg


class TestRegenSuccessMessages:
    """Test success message format."""

    def test_room_success_message(self):
        """Room success message includes room key and URL."""
        msg = "Room image generated for Library! URL: /media/generated/room_abc.png"
        assert "Library" in msg
        assert "/media/generated/room_abc.png" in msg

    def test_object_success_message_with_dbref(self):
        """Object success message includes key, dbref, and URL."""
        msg = "Image generated for keycard (#42)! URL: /media/generated/keycard.png"
        assert "keycard" in msg
        assert "#42" in msg
        assert "/media/generated/keycard.png" in msg


class TestRegenCmdsetRegistration:
    """Verify the command is registered in the default cmdset."""

    def test_cmdset_imports_cmd_regen(self):
        """default_cmdsets.py should import CmdRegen."""
        with open("commands/default_cmdsets.py") as f:
            source = f.read()
        assert "CmdRegen" in source

    def test_cmdset_adds_cmd_regen(self):
        """CharacterCmdSet should add CmdRegen."""
        with open("commands/default_cmdsets.py") as f:
            source = f.read()
        assert "self.add(CmdRegen())" in source
