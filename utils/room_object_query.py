# utils/room_object_query.py
import re
from evennia.utils.utils import inherits_from

def is_exit(obj) -> bool:
    return bool(obj) and inherits_from(obj, "evennia.objects.objects.DefaultExit")

def is_character(obj) -> bool:
    return bool(obj) and inherits_from(obj, "evennia.objects.objects.DefaultCharacter")

def is_prop(obj) -> bool:
    return bool(obj) and (not is_exit(obj)) and (not is_character(obj))

def iter_notable_props(room):
    for obj in (room.contents or []):
        if not obj or not is_prop(obj):
            continue
        if getattr(obj.db, "notable", False):
            yield obj

def list_notables_with_dbref(room, limit: int = 12) -> str:
    out = [f"{o.key}({o.dbref})" for o in iter_notable_props(room)]
    return ", ".join(out[:limit])

def find_object_in_room(room, target_text: str, notable_only: bool = False):
    """
    Matches by:
    - exact dbref "#67"
    - exact key or shortdesc (case-insensitive)
    - substring match (if unique)
    Returns obj or None.
    """
    t = (target_text or "").strip()
    if not t:
        return None

    # dbref
    if t.startswith("#") and t[1:].isdigit():
        for obj in (room.contents or []):
            if obj and str(obj.dbref) == t:
                return obj
        return None

    needle = t.lower()
    candidates = []
    for obj in (room.contents or []):
        if not obj or not is_prop(obj):
            continue
        if notable_only and not getattr(obj.db, "notable", False):
            continue

        key = (obj.key or "").lower()
        sd = (obj.db.shortdesc or "").lower()

        if needle == key or needle == sd:
            return obj
        if needle in key or (sd and needle in sd):
            candidates.append(obj)

    return candidates[0] if len(candidates) == 1 else None

def delete_object_by_selector(room, selector: str):
    """
    Deterministically delete a single object by:
    - dbref "#67"
    - exact match
    - unique substring match
    Returns {"key": ..., "dbref": ...} or None.
    """
    t = (selector or "").strip()
    if not t:
        return None

    # dbref
    if t.startswith("#") and t[1:].isdigit():
        for obj in (room.contents or []):
            if obj and str(obj.dbref) == t:
                removed = {"key": obj.key, "dbref": str(obj.dbref)}
                obj.delete()
                return removed
        return None

    needle = t.lower()
    # exact match first
    for obj in (room.contents or []):
        if not obj or not is_prop(obj):
            continue
        key = (obj.key or "").lower()
        sd = (obj.db.shortdesc or "").lower()
        if needle == key or needle == sd:
            removed = {"key": obj.key, "dbref": str(obj.dbref)}
            obj.delete()
            return removed

    # unique substring
    candidates = []
    for obj in (room.contents or []):
        if not obj or not is_prop(obj):
            continue
        key = (obj.key or "").lower()
        sd = (obj.db.shortdesc or "").lower()
        if needle in key or (sd and needle in sd):
            candidates.append(obj)

    if len(candidates) == 1:
        obj = candidates[0]
        removed = {"key": obj.key, "dbref": str(obj.dbref)}
        obj.delete()
        return removed

    return None
