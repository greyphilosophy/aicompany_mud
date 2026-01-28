# utils/room_targeting.py
import re

from utils.room_object_query import find_object_by_dbref, iter_notable_props

def _words(s: str) -> list[str]:
    s = (s or "").lower()
    return [w for w in re.findall(r"[a-z0-9]+", s) if len(w) >= 3]

def resolve_edit_target(room, instruction: str):
    """
    Port of SmartRoom._resolve_edit_target, but as a helper:
      returns (target_obj_or_none, ambiguity_list)
    Note: still inspects room.contents (main-thread use).
    """
    text = (instruction or "").strip()
    if not text:
        return (None, [])

    # explicit dbref anywhere
    m = re.search(r"(#\d+)", text)
    if m:
        dbref = m.group(1)
        obj = find_object_by_dbref(room, dbref)
        return (obj, []) if obj else (None, [])

    low = text.lower()
    scored = []
    for obj in iter_notable_props(room):

        key = (obj.key or "").strip()
        sd = (obj.db.shortdesc or "").strip()
        sd_no_article = re.sub(r"^(a|an|the)\s+", "", sd, flags=re.IGNORECASE).strip()

        tokens = set(_words(key)) | set(_words(sd_no_article))
        hits = sum(1 for w in tokens if re.search(rf"\b{re.escape(w)}\b", low))
        if hits > 0:
            scored.append((hits, obj))

    if not scored:
        return (None, [])

    scored.sort(key=lambda t: t[0], reverse=True)
    best_score = scored[0][0]
    best = [o for s, o in scored if s == best_score]

    if len(best) == 1:
        return (best[0], [])
    return (None, best)

def instruction_mentions_target(instruction: str, target) -> bool:
    """
    Returns True if the instruction appears to refer to this target by name-ish tokens.
    Prevents applying a valid edit to the wrong object when the resolver guesses wrong.
    """
    text = (instruction or "").lower()
    if re.search(r"(#\d+)", text):
        return True  # explicit dbref -> trust it

    key = (target.key or "").lower()
    sd = (target.db.shortdesc or "").lower()
    sd = re.sub(r"^(a|an|the)\s+", "", sd).strip()

    # Tokens we allow to count as "mentioned"
    tokens = set(re.findall(r"[a-z0-9]+", key)) | set(re.findall(r"[a-z0-9]+", sd))

    # prune super-generic tokens that cause false positives
    stop = {"a", "an", "the", "of", "to", "and", "in", "on", "with", "from", "into", "more", "make", "change"}
    tokens = {t for t in tokens if len(t) >= 4 and t not in stop}

    # If any meaningful token appears as a whole word in the instruction, we're good.
    for t in tokens:
        if re.search(rf"\b{re.escape(t)}\b", text):
            return True
    return False
