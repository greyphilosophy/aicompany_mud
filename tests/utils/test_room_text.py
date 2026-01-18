# tests/utils/test_room_text.py
from utils.room_text import (
    normalize_say_message,
    is_computer_addressed,
    extract_computer_instruction,
    extract_dbref_anywhere,
)


def test_normalize_say_message_strips_quotes_and_punctuation():
    assert normalize_say_message(' "computer, look around" ') == "computer, look around"
    assert normalize_say_message("'computer: status'") == "computer: status"
    assert normalize_say_message("  ,:;computer do thing  ") == "computer do thing"


def test_normalize_empty_or_none():
    assert normalize_say_message("") == ""
    assert normalize_say_message(None) == ""


def test_is_computer_addressed_variants():
    assert is_computer_addressed("computer look") is True
    assert is_computer_addressed("computer, look") is True
    assert is_computer_addressed("computer: look") is True
    assert is_computer_addressed("Computer, Look") is True


def test_is_computer_addressed_negative():
    assert is_computer_addressed("hey computer look") is False
    assert is_computer_addressed("compute something") is False
    assert is_computer_addressed("") is False


def test_extract_computer_instruction_basic():
    msg = "computer, open the pod bay doors"
    assert extract_computer_instruction(msg) == "open the pod bay doors"


def test_extract_computer_instruction_colon_and_space():
    assert extract_computer_instruction("computer:status") == "status"
    assert extract_computer_instruction("computer status") == "status"


def test_extract_computer_instruction_not_addressed():
    assert extract_computer_instruction("hello there") == ""
    assert extract_computer_instruction("") == ""


def test_extract_dbref_anywhere():
    assert extract_dbref_anywhere("look at #123 please") == "#123"
    assert extract_dbref_anywhere("change #67 to blue") == "#67"
    assert extract_dbref_anywhere("no ref here") is None
    assert extract_dbref_anywhere("") is None
