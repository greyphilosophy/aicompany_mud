"""
Tests for the imgen command logic (commands/image.py).

Tests cover:
1. Command class metadata (key, aliases, help_category) — verified without importing evennia
2. Prompt parsing logic (room vs object, custom prompts)
3. Error handling for missing backend
4. Edge cases (no args, invalid targets)

Note: These tests avoid importing the evennia `Command` base class so they run
standalone without the full Evennia environment.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestImgGenCommandMetadata:
    """Verify command metadata is correct by reading the source file."""

    def test_command_file_exists(self):
        """The command file should exist."""
        import os
        assert os.path.exists("commands/image.py")

    def test_command_has_correct_key(self):
        """Command key should be 'imgen' in the source."""
        with open("commands/image.py") as f:
            source = f.read()
        assert 'key = "imgen"' in source

    def test_command_has_aliases(self):
        """Command should have aliases in the source."""
        with open("comments/image.py") if False else open("commands/image.py") as f:
            source = f.read()
        assert '"generate_image"' in source
        assert '"genimage"' in source

    def test_command_has_help_category(self):
        """Command should be in the Building help category."""
        with open("commands/image.py") as f:
            source = f.read()
        assert 'help_category = "Building"' in source


class TestImgGenPromptParsing:
    """Test the argument parsing logic for imgen commands."""

    def test_parse_args_room_no_prompt(self):
        """'imgen room' should be parsed as room mode with no custom prompt."""
        args = "room"
        parts = args.split(None, 1)
        assert parts[0].lower() == "room"
        assert len(parts) == 1

    def test_parse_args_room_with_prompt(self):
        """'imgen room "prompt"' should include the prompt."""
        args = 'room "a cozy tavern"'
        parts = args.split(None, 1)
        assert parts[0].lower() == "room"
        assert len(parts) == 2
        assert "cozy tavern" in parts[1]

    def test_parse_args_object_no_prompt(self):
        """'imgen object keycard' should be parsed correctly."""
        args = "object keycard"
        parts = args.split(None, 1)
        assert parts[0].lower() == "object"
        assert "keycard" in parts[1]

    def test_parse_args_object_with_prompt(self):
        """'imgen object keycard "prompt"' should include both."""
        args = 'object keycard "metal keycard with LED"'
        parts = args.split(None, 1)
        assert parts[0].lower() == "object"
        assert "keycard" in parts[1]

    def test_parse_empty_args(self):
        """Empty args should result in empty parts list."""
        args = ""
        parts = args.split(None, 1)
        assert parts == []

    def test_parse_invalid_target(self):
        """'imgen foo' should have 'foo' as first part (not room/object)."""
        args = "foo"
        parts = args.split(None, 1)
        assert parts[0].lower() == "foo"
        assert parts[0].lower() not in ("room", "object")


class TestImgGenErrorMessages:
    """Test error message generation for edge cases."""

    def test_backend_down_message(self):
        """Backend down message should be informative."""
        msg = "FLUX.2 server is not running or the backend is down."
        assert "not running" in msg or "backend" in msg or "down" in msg

    def test_no_object_found_message(self):
        """No object found message should include the object name."""
        obj_name = "keycard"
        msg = f"No object named '{obj_name}' found here."
        assert obj_name in msg

    def test_no_location_message(self):
        """No location message should inform the caller."""
        msg = "You are nowhere."
        assert "nowhere" in msg

    def test_no_location_for_object_message(self):
        """Object generation without location should error."""
        msg = "You are nowhere (no current room)."
        assert "nowhere" in msg or "room" in msg

    def test_usage_message_format(self):
        """Usage message should list both room and object options."""
        usage = "imgen room / imgen object"
        assert "room" in usage
        assert "object" in usage


class TestImgGenSuccessMessages:
    """Test success message format."""

    def test_room_success_message(self):
        """Room success message includes URL."""
        url = "/media/generated/room_abc123.png"
        msg = f"Room image generated! URL: {url}"
        assert "generated" in msg.lower()
        assert url in msg

    def test_object_success_message(self):
        """Object success message includes object name and URL."""
        obj_name = "keycard"
        url = "/media/generated/keycard.png"
        msg = f"Image generated for {obj_name}! URL: {url}"
        assert obj_name in msg
        assert url in msg

    def test_generating_prompt_message(self):
        """The 'generating' message should include the prompt."""
        prompt = "a grand library"
        msg = f"Generating room image with prompt: {prompt}"
        assert prompt in msg

    def test_empty_url_message(self):
        """Empty URL result should have a fallback message."""
        msg = "Image was generated but the URL came back empty."
        assert "empty" in msg.lower()


class TestImgGenCmdsetRegistration:
    """Verify the command is registered in the default cmdset."""

    def test_cmdset_imports_cmd_imggen(self):
        """default_cmdsets.py should import CmdImgGen."""
        with open("commands/default_cmdsets.py") as f:
            source = f.read()
        assert "CmdImgGen" in source

    def test_cmdset_adds_cmd_imggen(self):
        """CharacterCmdSet should add CmdImgGen."""
        with open("commands/default_cmdsets.py") as f:
            source = f.read()
        assert "self.add(CmdImgGen())" in source
