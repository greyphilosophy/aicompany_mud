# utils/affordance.py

DEFAULT_UNIT = "lb"

def default_affordance(unit: str = DEFAULT_UNIT) -> dict:
    return {
        "unit": unit,
        "weight": 1.0,
        "immovable": False,
        "container": {
            "is_container": False,
            "capacity_weight": 0.0,
            "openable": False,
            "is_open": True,
        },
        "manipulations": ["pick up", "examine"],
    }

def ensure_affordance(obj, unit: str = DEFAULT_UNIT) -> dict:
    """
    Ensure obj.db.affordance exists and has required keys.
    Safe to call from main thread.
    """
    a = obj.db.affordance or {}
    if not isinstance(a, dict):
        a = {}
    base = default_affordance(unit=unit)

    # shallow-merge for top level
    for k, v in base.items():
        if k not in a:
            a[k] = v

    # nested container merge
    if not isinstance(a.get("container"), dict):
        a["container"] = base["container"]
    else:
        for k, v in base["container"].items():
            a["container"].setdefault(k, v)

    obj.db.affordance = a
    return a

