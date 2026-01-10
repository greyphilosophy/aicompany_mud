# utils/facts.py
import time
import secrets

def new_fact(text: str, created_by: str = "", scope: str = "local", strength: float = 0.6, tags=None) -> dict:
    return {
        "id": f"fact_{secrets.token_hex(3)}",
        "text": text.strip(),
        "scope": scope,           # local | room | carried | worn (later)
        "strength": float(strength),
        "tags": tags or [],
        "created_by": created_by,
        "created_ts": float(time.time()),
    }

def add_fact(obj, fact: dict):
    facts = obj.db.facts or []
    if not isinstance(facts, list):
        facts = []
    facts.append(fact)
    obj.db.facts = facts

def get_facts(obj) -> list:
    facts = obj.db.facts or []
    return facts if isinstance(facts, list) else []

def remove_fact(obj, fact_id: str) -> bool:
    facts = obj.db.facts or []
    if not isinstance(facts, list):
        return False
    before = len(facts)
    facts = [f for f in facts if isinstance(f, dict) and f.get("id") != fact_id]
    obj.db.facts = facts
    return len(facts) != before

def fact_texts(obj) -> list[str]:
    out = []
    for f in get_facts(obj):
        if isinstance(f, dict):
            t = str(f.get("text") or "").strip()
            if t:
                out.append(t)
    return out
