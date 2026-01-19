# utils/computer_payloads.py
from __future__ import annotations

from typing import Any, Dict, List


def build_prop_create_payload(
    *,
    player: str,
    instruction: str,
    room_desc: str,
    anchors: List[Dict[str, Any]],
    recent_memory: str,
) -> Dict[str, Any]:
    return {
        "player": player,
        "instruction": instruction,
        "room_desc": room_desc,
        "notable_anchors": [{"key": a["key"], "shortdesc": a["shortdesc"]} for a in anchors],
        "recent_memory": recent_memory,
    }


def build_intent_payload(
    *,
    player: str,
    utterance: str,
    room_desc: str,
    anchors: List[Dict[str, Any]],
    recent_memory: str,
) -> Dict[str, Any]:
    return {
        "player": player,
        "utterance": utterance,
        "room_desc": room_desc,
        "notable_anchors": [{"key": a["key"], "shortdesc": a["shortdesc"], "dbref": a["dbref"]} for a in anchors],
        "recent_memory": recent_memory,
    }


def build_prop_edit_payload(
    *,
    player: str,
    instruction: str,
    room_desc: str,
    room_facts: List[str],
    target: Dict[str, Any],
    anchors: List[Dict[str, Any]],
    recent_memory: str,
) -> Dict[str, Any]:
    return {
        "player": player,
        "instruction": instruction,
        "room_desc": room_desc,
        "room_facts": room_facts,
        "target": target,
        "notable_anchors": [{"key": a["key"], "shortdesc": a["shortdesc"], "dbref": a["dbref"]} for a in anchors],
        "recent_memory": recent_memory,
    }
