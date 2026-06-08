# utils/object_properties.py
# Object Properties System — semantic properties for MUD objects

DEFAULT_PROPERTIES = {
    "is_container": False,
    "is_open": True,
    "capacity_ml": 0,
    "is_liquid": False,
    "is_drinkable": False,
    "liquid_name": "liquid",
    "current_volume_ml": 0,
    "weight_lbs": 1.0,
    "is_portable": True,
    "is_fragile": False,
    "is_wearable": False,
    "is_wieldable": False,
    "is_lit": False,
    "light_radius": 3,
    "object_type": "container",
}


def ensure_properties(obj):
    """Ensure obj.db.properties exists with all default keys."""
    props = obj.db.properties or {}
    if not isinstance(props, dict):
        props = {}
    for key, value in DEFAULT_PROPERTIES.items():
        if key not in props:
            props[key] = value
    obj.db.properties = props
    return props


def apply_properties_from_json(obj, properties_json: dict) -> dict:
    """Merge LLM-provided properties into the object's properties dict."""
    props = ensure_properties(obj)
    if isinstance(properties_json, dict):
        for key, value in properties_json.items():
            props[key] = value
    obj.db.properties = props
    return props


def has_property(obj, prop_name: str, value=None):
    """Check if object has a property (optionally matching a value)."""
    props = obj.db.properties or {}
    if value is None:
        return prop_name in props
    return props.get(prop_name) == value


def get_property(obj, prop_name: str, default=None):
    """Get a single property value."""
    props = obj.db.properties or {}
    return props.get(prop_name, default)


def update_property(obj, prop_name: str, value) -> dict:
    """Update a single property value."""
    props = ensure_properties(obj)
    props[prop_name] = value
    obj.db.properties = props
    return props


def object_is_drinkable(obj) -> bool:
    """Quick check: can you drink from this object?"""
    props = obj.db.properties or {}
    return (
        props.get("is_drinkable", False) and
        props.get("current_volume_ml", 0) > 0 and
        props.get("liquid_name", "liquid") != "liquid"
    )


def get_property_schema_text() -> str:
    """Return LLM-readable property schema for prompts."""
    return (
        "\nObject properties schema — include a 'properties' object with:\n"
        "  is_container: bool — Holds things/liquids?\n"
        "  is_open: bool — Currently open?\n"
        "  capacity_ml: number — Total liquid capacity\n"
        "  is_liquid: bool — Primarily liquid?\n"
        "  is_drinkable: bool — Can it be drunk?\n"
        "  liquid_name: str — Name of liquid (e.g. 'soda', 'tea')\n"
        "  current_volume_ml: number — Current liquid amount\n"
        "  weight_lbs: number — Weight\n"
        "  is_portable: bool — Can be picked up\n"
        "  is_fragile: bool — Breaks easily\n"
        "  is_wearable: bool — Can be worn\n"
        "  is_wieldable: bool — Can be wielded\n"
        "  is_lit: bool — Emits light\n"
        "  light_radius: number — Light radius in rooms\n"
        "  object_type: str — 'container', 'liquid', 'furniture', 'light_source', 'weapon', 'food', 'key', 'book'\n"
        "Examples:\n"
        "  Glass of Soda: {is_container: true, is_drinkable: true, liquid_name: 'soda', current_volume_ml: 200}\n"
        "  Brass Lamp: {is_lit: true, light_radius: 4, object_type: 'light_source'}\n"
    )
