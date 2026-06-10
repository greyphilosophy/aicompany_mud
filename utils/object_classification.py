# utils/object_classification.py
# Automatic object classification — maps object types to property schemas

from utils.object_properties import PROPERTY_SCHEMAS
from utils.abilities import get_abilities, find_abilities_for_object

# Map of object_type -> list of property schema names to apply
TYPE_TO_SCHEMAS = {
    "drinkable": ["liquid", "container"],
    "food": ["food"],
    "wearable": ["wearable"],
    "light_source": ["light_source"],
    "container": ["container"],
    "furniture": [],
    "decoration": [],
    "tool": [],
    "weapon": [],
    "misc": [],
}


def classify_object(obj) -> str:
    """
    Inspect an existing object and return the best-fitting object_type.
    Uses the object's key, shortdesc, and existing properties to guess.
    """
    props = obj.db.properties or {}
    # If properties are already set, infer from them
    if props.get("is_drinkable") or props.get("is_liquid"):
        return "drinkable"
    if props.get("is_food"):
        return "food"
    if props.get("is_wearable"):
        return "wearable"
    if props.get("is_lit"):
        return "light_source"
    if props.get("object_type"):
        return props["object_type"]

    # Fallback: inspect key and shortdesc for common patterns
    key = (obj.key or "").lower()
    sd = (obj.db.shortdesc or "").lower()
    combined = f"{key} {sd}"

    drinkable_keywords = ["drink", "soda", "water", "tea", "coffee", "juice", "beer", "wine", "ale", "milk", "soda", "cola", "potion", "elixir", "nectar", "tea"]
    if any(kw in combined for kw in drinkable_keywords):
        return "drinkable"

    food_keywords = ["bread", "apple", "fruit", "cake", "cookie", "snack", "meal", "sandwich", "pizza", "bun", "toast", "salad", "cheese", "meat"]
    if any(kw in combined for kw in food_keywords):
        return "food"

    wearable_keywords = ["hat", "coat", "shirt", "shoe", "ring", "necklace", "bracelet", "belt", "glove", "vest", "scarf", "crown", "robe"]
    if any(kw in combined for kw in wearable_keywords):
        return "wearable"

    return "misc"


def apply_classification(obj, object_type: str | None = None, properties: dict | None = None) -> dict:
    """
    Classify an object and apply the appropriate property schemas.

    Args:
        obj: Evennia object
        object_type: Explicit type from LLM (e.g. "drinkable", "food")
        properties: Properties dict from LLM (takes priority over defaults)

    Returns:
        The updated properties dict on obj.db.properties
    """
    if object_type is None:
        object_type = classify_object(obj)

    # Initialize empty properties
    props = dict(obj.db.properties or {})

    # Mark the object's type
    props["object_type"] = object_type

    # If LLM provided properties, merge them in (LLM wins)
    if properties:
        props.update(properties)

    # Apply schema defaults for the type (fills in missing keys)
    schemas = TYPE_TO_SCHEMAS.get(object_type, [])
    for schema_name in schemas:
        defaults = dict(PROPERTY_SCHEMAS.get(schema_name, {}))
        for k, v in defaults.items():
            if k not in props:
                props[k] = v

    # Save back
    obj.db.properties = props

    # Verify abilities are discoverable
    abilities = find_abilities_for_object(obj)
    return props
