# utils/computer.py
import json
from evennia.utils.utils import inherits_from
from evennia.utils import logger

from utils.llm_client import build_default_client_from_env, LLMProvider
from utils.room_director import build_snapshot, generate_from_snapshot
from utils.affordance import ensure_affordance
from utils.facts import get_facts

from collections.abc import Mapping, Sequence

def _json_safe(x):
    # primitives
    if x is None or isinstance(x, (str, int, float, bool)):
        return x

    # bytes -> string
    if isinstance(x, (bytes, bytearray)):
        return x.decode("utf-8", errors="replace")

    # mappings (covers Evennia _SaverDict)
    if isinstance(x, Mapping):
        return {str(k): _json_safe(v) for k, v in x.items()}

    # sequences (covers Evennia _SaverList) but don’t treat strings as sequences
    if isinstance(x, Sequence) and not isinstance(x, (str, bytes, bytearray)):
        return [_json_safe(v) for v in list(x)]

    # fallback: stringify unknown objects
    return str(x)

class Computer:
    """
    Room-assistant service object.
    - builds context packets
    - routes intents (Phase A later)
    - generates props (Phase B writer)
    - triggers room refinement (director)
    """

    def __init__(self, room):
        self.room = room

    # ---------- Providers ----------
    def llm_providers(self):
        r = self.room
        providers = [
            LLMProvider(label="LOCAL", base_url=r.LOCAL_BASE_URL, model=r.LOCAL_MODEL, api_key=None)
        ]
        if r.OPENAI_API_KEY:
            providers.append(
                LLMProvider(label="OPENAI", base_url=r.OPENAI_BASE_URL, model=r.OPENAI_MODEL, api_key=r.OPENAI_API_KEY)
            )
        return providers

    # ---------- Context ----------
    def notable_objects_packet(self, include_desc=True, max_desc_chars=500):
        r = self.room
        out = []
        for obj in r.contents:
            if not obj:
                continue
            if inherits_from(obj, "evennia.objects.objects.DefaultExit"):
                continue
            if inherits_from(obj, "evennia.objects.objects.DefaultCharacter"):
                continue
            if not obj.db.notable:
                continue

            ensure_affordance(obj)  # scaffold if missing

            desc = (obj.db.desc or "")
            if include_desc and desc:
                desc = desc.strip()[:max_desc_chars]
            else:
                desc = ""

            out.append({
                "dbref": str(obj.dbref),
                "key": obj.key,
                "shortdesc": (obj.db.shortdesc or str(obj.key)),
                "desc": desc,
                "facts": get_facts(obj),
                "affordance": obj.db.affordance,
            })
        return out

    def room_memory_text(self, max_chars=3000):
        mem = self.room.db.memory or []
        text = "\n".join(f'{m.get("who","?")}: {m.get("msg","")}' for m in mem)
        return text[-max_chars:]

    # ---------- Director: refine room ----------
    def director_snapshot(self):
        r = self.room
        # Evennia attributes may be _SaverList; coerce to plain list for JSON safety.
        facts = r.db.director_facts or []
        facts = [str(f).strip() for f in list(facts) if str(f).strip()]
        return build_snapshot(
            room_key=r.key,
            previous_desc=r.db.desc or "",
            previous_generated_desc=r.db.last_generated_desc or "",
            facts=facts,
            objects=[
                {"key": o["key"], "shortdesc": o["shortdesc"], "desc": o["desc"], "notable": True}
                for o in self.notable_objects_packet(include_desc=True)
            ],
            memory_text=self.room_memory_text(),
        )

    def generate_room_desc(self, snapshot: dict) -> dict:
        client = build_default_client_from_env()
        return generate_from_snapshot(client, self.llm_providers(), snapshot)

    # ---------- Writer: create prop ----------
    def generate_prop_json(self, speaker_key: str, instruction: str) -> dict:
        """
        Thread-safe: returns {key, shortdesc, desc, affordance?, facts?}
        """
        sys_prompt = (
            "You create physical objects for a text MUD.\n"
            "Return STRICT JSON ONLY.\n"
            "Schema:\n"
            '{"key": str, "shortdesc": str, "desc": str, "affordance": object, "facts": [str]}\n'
            "Rules:\n"
            "- key: short Title-Case name (2-6 words).\n"
            "- shortdesc: starts with 'a' or 'an'.\n"
            "- desc: 1-3 sentences, concise.\n"
            "- affordance: include weight (number) and immovable (bool) when obvious.\n"
            "- facts: optional short stable statements the object itself implies.\n"
        )

        room_desc = (self.room.db.desc or "").strip()
        memory = self.room_memory_text(max_chars=2000)
        anchors = self.notable_objects_packet(include_desc=False)

        user_payload = {
            "player": speaker_key,
            "instruction": instruction,
            "room_desc": room_desc,
            "notable_anchors": [{"key": a["key"], "shortdesc": a["shortdesc"]} for a in anchors],
            "recent_memory": memory,
        }

        safe_payload = _json_safe(user_payload)

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(safe_payload, ensure_ascii=False)},
        ]

        client = build_default_client_from_env()
        data = client.chat_json(self.llm_providers(), messages)
        return data

    def predict_intent(self, speaker_key: str, utterance: str) -> dict:
        """
        Thread-safe: Ask LLM to classify unknown 'computer' requests into a concrete command.
        Returns dict:
          {"intent": "create|destroy|pin|unpin|facts|refine|unknown",
           "normalized": "<computer instruction to run if confirmed>",
           "question": "<yes/no question>"}
        """
        sys_prompt = (
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
            "- normalized MUST be a single concrete computer instruction that matches the system's commands.\n"
            "  Examples: 'create a hot cup of earl grey tea', 'destroy Seaside Lamp', 'pin This is a living room', 'facts', 'refine'.\n"
            "- If you are unsure, set intent='unknown' and ask a clarifying yes/no question anyway.\n"
            "- question MUST be a yes/no confirmation phrased to the player.\n"
        )

        room_desc = (self.room.db.desc or "").strip()
        memory = self.room_memory_text(max_chars=1500)
        anchors = self.notable_objects_packet(include_desc=False)

        user_payload = {
            "player": speaker_key,
            "utterance": utterance,
            "room_desc": room_desc,
            "notable_anchors": [{"key": a["key"], "shortdesc": a["shortdesc"], "dbref": a["dbref"]} for a in anchors],
            "recent_memory": memory,
        }

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]

        client = build_default_client_from_env()
        return client.chat_json(self.llm_providers(), messages)

    def generate_prop_edit_json(self, speaker_key: str, instruction: str, target_dbref: str) -> dict:
        """
        Thread-safe: returns {dbref, key, shortdesc, desc}
        - target_dbref must identify an object currently in the room.
        """
        # Build target packet deterministically (main-thread object read, but we only read attrs here;
        # if you want *strict* thread safety, you can pass a prebuilt dict instead of dbref).
        target = None
        for obj in self.room.contents:
            if obj and str(obj.dbref) == str(target_dbref):
                target = obj
                break
        if not target:
            return {"dbref": "", "key": "", "shortdesc": "", "desc": ""}

        sys_prompt = (
            "You edit ONE existing physical object in a text MUD.\n"
            "Return STRICT JSON ONLY.\n"
            'Schema: {"dbref": str, "key": str, "shortdesc": str, "desc": str}\n'
            "\n"
            "You must apply the user's requested change(s) to the object.\n"
            "Do not invent new objects.\n"
            "Do not contradict established facts unless the user explicitly requests a change.\n"
            "\n"
            "Return ONLY valid JSON.\n"
            "Do NOT include explanations or markdown.\n"
            "\n"
            "The JSON MUST contain these keys:\n"
            '- "dbref": Always include "dbref" unchanged from the input\n'
            '- "key": the object''s display name (Title Case, NO leading article, ≤ 60 characters\n'
            '- "shortdesc": a one-line description that STARTS with "a" or "an", ≤ 140 characters\n'
            '- "desc": a concise paragraph describing the object\n')


        room_desc = (self.room.db.desc or "").strip()
        memory = self.room_memory_text(max_chars=1500)

        # room facts: pinned facts on the room + director facts (if any)
        pinned_room_facts = [f.get("text") for f in get_facts(self.room) if isinstance(f, dict) and f.get("text")]
        director_facts = list(self.room.db.director_facts or [])

        ensure_affordance(target)

        target_packet = {
            "dbref": str(target.dbref),
            "key": target.key,
            "shortdesc": (target.db.shortdesc or str(target.key)),
            "desc": (target.db.desc or ""),
            "facts": get_facts(target),
            "affordance": target.db.affordance,
        }

        anchors = self.notable_objects_packet(include_desc=False)

        user_payload = {
            "player": speaker_key,
            "instruction": instruction,
            "room_desc": room_desc,
            "room_facts": pinned_room_facts + director_facts,
            "target": target_packet,
            "notable_anchors": [{"key": a["key"], "shortdesc": a["shortdesc"], "dbref": a["dbref"]} for a in anchors],
            "recent_memory": memory,
        }

        safe_payload = _json_safe(user_payload)

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(safe_payload, ensure_ascii=False)},
        ]

        client = build_default_client_from_env()
        return client.chat_json(self.llm_providers(), messages)
