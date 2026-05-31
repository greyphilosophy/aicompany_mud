# test_llm_stress_schema.py
# Stress test: hit the model with many prop_create calls to reproduce
# the occasional truncated/incomplete JSON response.

import json
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

import django
django.setup()

import pytest
from django.conf import settings
from utils.llm_client import LLMClient, LLMProvider

SYSTEM_PROMPT = (
    "You create physical objects for a text MUD.\n"
    "Return STRICT JSON ONLY. No markdown, no explanations.\n"
    "Required JSON schema:\n"
    '{"key": "TitleCase Name", "shortdesc": "a description", "desc": "detailed description", "affordance": {"weight": number, "immovable": bool}, "facts": [str]}\n'
    "Rules:\n"
    "- key is REQUIRED: short Title-Case name, 2-6 words, NO leading article.\n"
    "- shortdesc is REQUIRED: a one-line description starting with 'a' or 'an', ≤ 140 characters.\n"
    "- desc is REQUIRED: 1-3 sentences describing the object concretely.\n"
    "- affordance: include weight (number) and immovable (bool) when obvious.\n"
    "- facts: optional short stable statements the object itself implies.\n"
    "- ALL required keys (key, shortdesc, desc) MUST appear in the top-level JSON object.\n"
    "- Do NOT return a partial response with only affordance fields.\n"
)

def test_stress_prop_create_schema():
    """Run 15 prop_create calls. Report results — don't hard-assert on pass rate."""
    provider = LLMProvider(
        label="STRESS",
        base_url=getattr(settings, "LOCAL_BASE_URL", "http://127.0.0.1:30001/v1"),
        model=getattr(settings, "LOCAL_MODEL", "/models/qwen3-14b-nvfp4"),
        api_key=None,
    )
    client = LLMClient(timeout_s=120, max_attempts=2, temperature=0.6)

    props = [
        "A brass telescope on a table",
        "A glass of soda on the counter",
        "A rusty sword hanging on the wall",
        "A flickering candle on a desk",
        "A leather-bound book on a shelf",
        "A stone lantern in the garden",
        "A wooden stool by the door",
        "A copper kettle on the hearth",
        "A silver spoon on a tray",
        "A feather quill on a parchment",
        "A clay mug on a windowsill",
        "A brass bell on a hook",
        "A tin box on a chest",
        "A rolled-up map on a desk",
        "A porcelain vase on a mantel",
    ]

    results = {"complete": [], "incomplete": [], "timeouts": []}
    for inst in props:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({
                    "player": "StressTester",
                    "instruction": f"Create {inst}",
                    "room_desc": "A warm tavern.",
                    "notable_anchors": [],
                    "recent_memory": "",
                }),
            },
        ]
        try:
            result = client.chat_json([provider], messages)
            if result is None:
                results["timeouts"].append((inst, None))
                continue

            missing = {"key", "shortdesc", "desc"} - set(result.keys())
            if missing:
                results["incomplete"].append((inst, result, missing))
                continue

            results["complete"].append((inst, result))
        except Exception as exc:
            results["timeouts"].append((inst, str(exc)))

    print(f"\nTotal: {len(props)} calls")
    print(f"  Complete: {len(results['complete'])}")
    print(f"  Incomplete: {len(results['incomplete'])}")
    print(f"  Timeouts: {len(results['timeouts'])}")

    if results["incomplete"]:
        print("\nIncomplete responses:")
        for inst, resp, missing in results["incomplete"]:
            print(f"  {inst} — missing {missing}: {resp}")

    assert len(results['complete']) + len(results['incomplete']) + len(results['timeouts']) == len(props)
