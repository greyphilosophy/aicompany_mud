# utils/room_text.py
import re
from typing import Optional, Tuple

_COMPUTER_PREFIXES = ("computer ", "computer:", "computer,")

def normalize_say_message(message: str) -> str:
    msg = str(message or "").strip()
    if not msg:
        return ""
    # normalize quotes/punctuation similar to current behavior
    return msg.strip(' "\'').lstrip(" ,:;").strip()

def is_computer_addressed(normalized: str) -> bool:
    low = (normalized or "").lower()
    return low.startswith(_COMPUTER_PREFIXES)

def extract_computer_instruction(normalized: str) -> str:
    """
    Given a normalized message that starts with 'computer', return the instruction text.
    Mirrors: instruction = norm[len("computer"):].lstrip(" :,").strip()
    """
    if not normalized:
        return ""
    if not is_computer_addressed(normalized):
        return ""
    after = normalized[len("computer"):]
    return after.lstrip(" :,").strip()

def extract_dbref_anywhere(text: str) -> Optional[str]:
    """
    Find '#123' anywhere in text.
    """
    if not text:
        return None
    m = re.search(r"(#\d+)", text)
    return m.group(1) if m else None
