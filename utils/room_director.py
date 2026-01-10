# utils/room_director.py
import json


def build_snapshot(room_key, previous_desc, previous_generated_desc, facts, objects, memory_text):
    """
    Pure-data snapshot (safe to pass to worker threads).
    """
    return {
        "room_key": room_key,
        "previous_desc": previous_desc or "",
        "previous_generated_desc": previous_generated_desc or "",
        "facts": facts or [],
        "objects": objects or [],
        "memory": memory_text or "",
    }


def build_messages(snapshot: dict):
    """
    Build messages for the room-director LLM call.
    Strict JSON output: {"desc": str, "facts": [str]}
    """
    sys_prompt = (
        "You are SmartRoomDirector for a text MUD.\n"
        "Rewrite the ROOM BASE DESCRIPTION to match the current contents and recent conversation.\n"
        "\n"
        "IMPORTANT GROUNDING RULES:\n"
        "- Objects currently present are authoritative reality.\n"
        "- Do NOT mention any entity unless it is:\n"
        "  • present in the objects list, OR\n"
        "  • explicitly supported by current facts, OR\n"
        "  • explicitly indicated by recent memory as intentionally present.\n"
        "- Previous descriptions are advisory only and MUST NOT introduce entities.\n"
        "- If an entity appeared previously but is not grounded above, REMOVE IT.\n"
        "\n"
        "Return STRICT JSON ONLY (no markdown, no extra text).\n"
        'Schema: {"desc": str, "facts": [str]}\n'
        "\n"
        "Rules:\n"
        "- desc: 1–2 short paragraphs, present tense, evocative but not purple-prose.\n"
        "- Do NOT list every object; weave only the most salient into scene dressing.\n"
        "- Use objects to infer indoor/outdoor/season/mood.\n"
        "- facts: 3–10 short, stable anchors.\n"
        "- Facts MUST be grounded in objects or room-wide truths (e.g. mood, setting).\n"
        "- If objects conflict, you may shift the scene.\n"
        "- Only preserve intentional oddities if memory clearly indicates intent.\n"
    )

    prev = snapshot.get("previous_generated_desc") or snapshot.get("previous_desc") or ""

    # Coerce Evennia _SaverList / other odd types into JSON-safe plain values.
    facts_raw = snapshot.get("facts") or []
    facts = [str(f).strip() for f in list(facts_raw) if str(f).strip()]
    objects_raw = snapshot.get("objects") or []
    objects = list(objects_raw)

    payload = {
        "room_key": snapshot.get("room_key"),
        "previous_desc": prev,
        "facts": facts,
        "objects": objects,
        "memory": snapshot.get("memory") or "",
    }

    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def generate_from_snapshot(client, providers, snapshot: dict) -> dict:
    """
    Thread-safe: call LLM and return validated dict: {"desc": str, "facts": [str, ...]}
    """
    messages = build_messages(snapshot)
    from evennia.utils import logger
    logger.log_info(f"[Director] Calling LLM with {len(messages)} messages; providers={[p.label for p in providers]}")
    data = client.chat_json(providers, messages)

    desc = str(data.get("desc") or "").strip()
    facts = data.get("facts") or []
    if not isinstance(facts, list):
        facts = []

    if not desc:
        raise ValueError("Director returned empty desc")

    facts_out = [str(f).strip() for f in facts if str(f).strip()]
    return {"desc": desc, "facts": facts_out}
