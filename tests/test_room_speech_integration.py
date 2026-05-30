"""
Integration tests for SmartRoom.handle_speech -> computer command flow.

These tests verify the full chain: message normalization -> computer address
check -> instruction extraction. They also test that SmartRoom has all
the class attributes that handle_speech depends on, catching regressions
like MEMORY_MAX being deleted but still referenced.

Run with:
    pytest tests/test_room_speech_integration.py -v
"""
import pytest


class TestSpeechChain:
    """
    Test the normalize -> is_computer_addressed -> extract_computer_instruction
    chain as it would be exercised by handle_speech.
    """

    @pytest.fixture
    def rt(self):
        from utils.room_text import (
            normalize_say_message,
            is_computer_addressed,
            extract_computer_instruction,
        )
        return {
            "normalize": normalize_say_message,
            "addressed": is_computer_addressed,
            "extract": extract_computer_instruction,
        }

    def _check_chain(self, rt, raw, expected_instruction):
        """Helper: normalize -> check -> extract chain."""
        normalized = rt["normalize"](raw)
        assert rt["addressed"](normalized) is True, (
            f"Expected '{raw}' to be computer-addressed after normalization"
        )
        instruction = rt["extract"](normalized)
        assert instruction == expected_instruction
        return instruction

    def test_destroy_baseball(self, rt):
        """Original bug report: 'say computer destroy baseball' stopped working."""
        self._check_chain(rt, "computer, destroy baseball", "destroy baseball")

    def test_destroy_with_quotes(self, rt):
        self._check_chain(rt, '"computer, destroy the baseball"', "destroy the baseball")

    def test_create_object(self, rt):
        self._check_chain(rt, "computer: create a brass telescope", "create a brass telescope")

    def test_facts(self, rt):
        self._check_chain(rt, "computer facts", "facts")

    def test_pin_fact(self, rt):
        self._check_chain(rt, "computer, pin This is cozy", "pin This is cozy")

    def test_edit_object(self, rt):
        self._check_chain(rt, "computer, change the lamp to be blue", "change the lamp to be blue")

    def test_negative_non_computer(self, rt):
        """Messages not addressed to computer should not trigger."""
        normalized = rt["normalize"]("destroy baseball")
        assert rt["addressed"](normalized) is False

    def test_negative_similar_prefix(self, rt):
        """'compute' and 'computers' shouldn't match."""
        assert rt["addressed"](rt["normalize"]("compute something")) is False
        assert rt["addressed"](rt["normalize"]("computers, look")) is False

    def test_leading_punctuation_stripped(self, rt):
        """Messages with leading punctuation should still work."""
        self._check_chain(rt, ",computer look", "look")
        self._check_chain(rt, ";computer look", "look")
        self._check_chain(rt, " :computer look", "look")


class TestSmartRoomClassAttributes:
    """
    Verify SmartRoom has all required class attributes. This catches the
    MEMORY_MAX regression where the attribute was deleted but _remember()
    still referenced it, causing every handle_speech call to crash before
    reaching is_computer_addressed.
    """

    def test_smart_room_has_memory_max(self):
        """
        SmartRoom._remember() uses self.MEMORY_MAX. If this is missing,
        handle_speech crashes before reaching is_computer_addressed.
        """
        import re
        source_path = "/home/greyphilosophy/muddev/aicompany_mud/typeclasses/rooms.py"
        with open(source_path) as f:
            source = f.read()
        assert re.search(r"MEMORY_MAX\s*=", source), (
            "SmartRoom references MEMORY_MAX but it's not defined as a class attribute. "
            "This causes _remember() to raise AttributeError on every handle_speech call."
        )

    def test_smart_room_class_attrs_exist(self):
        """Verify all critical SmartRoom class attributes are defined."""
        import re
        source_path = "/home/greyphilosophy/muddev/aicompany_mud/typeclasses/rooms.py"
        with open(source_path) as f:
            source = f.read()
        required_attrs = [
            "MEMORY_MAX",
            "LLM_COOLDOWN_SECONDS",
            "LLM_MAX_ATTEMPTS",
            "DESC_UPDATE_DEBOUNCE_S",
            "DESC_UPDATE_COOLDOWN_S",
        ]
        for attr in required_attrs:
            assert re.search(attr + r"\s*=", source), (
                f"SmartRoom references {attr} but it's not defined as a class attribute"
            )
