# tests/test_llm_live_schema.py
# Live integration tests: actually call the model and verify JSON schema quality.

import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

import django
django.setup()

from django.conf import settings
import pytest
from utils.llm_client import LLMClient, LLMProvider


@pytest.fixture
def live_provider():
    return LLMProvider(
        label="LIVE",
        base_url=getattr(settings, "LOCAL_BASE_URL", "http://127.0.0.1:30001/v1"),
        model=getattr(settings, "LOCAL_MODEL", "/models/qwen3-14b-nvfp4"),
        api_key=None,
    )


@pytest.fixture
def live_client():
    return LLMClient(timeout_s=120, max_attempts=2, temperature=0.6)


def test_live_prop_create_has_required_fields(live_client, live_provider):
    """Call the live model with a prop_create prompt and verify key+desc+shortdesc."""
    system_prompt = (
        "You create physical objects for a text MUD.\n"
        "Return STRICT JSON ONLY. No markdown, no explanations.\n"
        "Required JSON schema:\n"
        '{"key": "TitleCase Name", "shortdesc": "a description", "desc": "detailed description", "affordance": {"weight": number, "immovable": bool}, "facts": [str]}\n'
        "Rules:\n"
        "- key is REQUIRED: short Title-Case name, 2-6 words, NO leading article.\n"
        "- shortdesc is REQUIRED: a one-line description starting with 'a' or 'an', \u2264 140 characters.\n"
        "- desc is REQUIRED: 1-3 sentences describing the object concretely.\n"
        "- affordance: include weight (number) and immovable (bool) when obvious.\n"
        "- facts: optional short stable statements the object itself implies.\n"
        "- ALL required keys (key, shortdesc, desc) MUST appear in the top-level JSON object.\n"
        "- Do NOT return a partial response with only affordance fields.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps({
                "player": "Tester",
                "instruction": "Create a brass telescope on a table",
                "room_desc": "A warm tavern.",
                "notable_anchors": [],
                "recent_memory": "",
            }),
        },
    ]

    result = live_client.chat_json([live_provider], messages)

    assert "key" in result, f"Missing 'key' in response: {result}"
    assert "desc" in result, f"Missing 'desc' in response: {result}"
    assert "shortdesc" in result, f"Missing 'shortdesc' in response: {result}"
    assert isinstance(result["key"], str) and len(result["key"]) > 0
    assert isinstance(result["desc"], str) and len(result["desc"]) > 0
    assert isinstance(result["shortdesc"], str) and len(result["shortdesc"]) > 0


def test_live_intent_router_has_required_fields(live_client, live_provider):
    """Call the live model with an intent_router prompt and verify 'intent' field."""
    system_prompt = (
        "You are an intent router for a text MUD assistant named 'computer'.\n"
        "Given a user's raw request, predict what they intend.\n"
        "Return STRICT JSON ONLY.\n"
        'Schema: {"intent": str, "normalized": str, "question": str}\n'
        "\n"
        "Allowed intents:\n"
        "- create: create/manifest an object\n"
        "- destroy: remove an object in the current room\n"
        "- pin: pin a fact (optionally 'to <target>')\n"
        "- unpin: unpin a fact id\n"
        "- facts: list facts\n"
        "- refine: rewrite/refine the room description\n"
        "- unknown: cannot determine\n"
        "\n"
        "Rules:\n"
        "- normalized MUST be a single concrete computer instruction.\n"
        "- If you are unsure, set intent='unknown' and ask a clarifying yes/no question.\n"
        "- question MUST be a yes/no confirmation phrased to the player.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps({
                "player": "Tester",
                "utterance": "computer, make a wooden chair",
                "room_desc": "A warm tavern.",
                "notable_anchors": [],
                "recent_memory": "",
            }),
        },
    ]

    result = live_client.chat_json([live_provider], messages)

    assert "intent" in result, f"Missing 'intent' in response: {result}"


def test_live_multiple_prop_creates_are_consistent(live_client, live_provider):
    """Run multiple prop_create calls and verify each returns required fields."""
    system_prompt = (
        "You create physical objects for a text MUD.\n"
        "Return STRICT JSON ONLY. No markdown, no explanations.\n"
        "Required JSON schema:\n"
        '{"key": "TitleCase Name", "shortdesc": "a description", "desc": "detailed description", "affordance": {"weight": number, "immovable": bool}, "facts": [str]}\n'
        "Rules:\n"
        "- key is REQUIRED: short Title-Case name, 2-6 words, NO leading article.\n"
        "- shortdesc is REQUIRED: a one-line description starting with 'a' or 'an', \u2264 140 characters.\n"
        "- desc is REQUIRED: 1-3 sentences describing the object concretely.\n"
        "- affordance: include weight (number) and immovable (bool) when obvious.\n"
        "- facts: optional short stable statements the object itself implies.\n"
        "- ALL required keys (key, shortdesc, desc) MUST appear in the top-level JSON object.\n"
        "- Do NOT return a partial response with only affordance fields.\n"
    )

    instructions = [
        "Create a glass of soda on the counter",
        "Create a rusty sword hanging on the wall",
        "Create a flickering candle on a desk",
        "Create a leather-bound book on a shelf",
        "Create a stone lantern in the garden",
    ]

    failures = []
    for instruction in instructions:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps({
                    "player": "Tester",
                    "instruction": instruction,
                    "room_desc": "A warm tavern.",
                    "notable_anchors": [],
                    "recent_memory": "",
                }),
            },
        ]

        try:
            result = live_client.chat_json([live_provider], messages)
            missing = {"key", "desc", "shortdesc"} - set(result.keys())
            if missing:
                failures.append((instruction, result, missing))
        except Exception as exc:
            failures.append((instruction, str(exc), {"all"}))

    if failures:
        fail_report = "\n".join(
            f"  {inst}: {err}" for inst, err, _ in failures
        )
        assert False, f"{len(failures)}/5 calls missing fields:\n{fail_report}"