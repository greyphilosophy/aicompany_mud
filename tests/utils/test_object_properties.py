# tests/utils/test_object_properties.py
"""Tests for utils/object_properties.py — the object properties system."""

import pytest
from types import SimpleNamespace


def test_ensure_properties_creates_defaults():
    from utils.object_properties import ensure_properties, DEFAULT_PROPERTIES
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    result = ensure_properties(obj)
    assert isinstance(result, dict)
    for key in DEFAULT_PROPERTIES:
        assert key in result, f"Missing default key: {key}"
    assert result["is_container"] == DEFAULT_PROPERTIES["is_container"]
    assert result["is_drinkable"] == DEFAULT_PROPERTIES["is_drinkable"]
    assert result["current_volume_ml"] == DEFAULT_PROPERTIES["current_volume_ml"]


def test_ensure_properties_preserves_existing():
    from utils.object_properties import ensure_properties
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties={
        "is_container": True,
        "is_drinkable": True,
        "liquid_name": "tea",
    })
    result = ensure_properties(obj)
    assert result["is_container"] is True
    assert result["is_drinkable"] is True
    assert result["liquid_name"] == "tea"
    assert "current_volume_ml" in result
    assert "object_type" in result


def test_ensure_properties_handles_non_dict():
    from utils.object_properties import ensure_properties
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties="string")
    result = ensure_properties(obj)
    assert isinstance(result, dict)
    assert "is_container" in result


def test_ensure_properties_handles_none_properties():
    from utils.object_properties import ensure_properties
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    result = ensure_properties(obj)
    assert isinstance(result, dict)
    assert result["is_container"] is False


def test_apply_properties_from_json_merges_correctly():
    from utils.object_properties import apply_properties_from_json, ensure_properties
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    ensure_properties(obj)
    llm_props = {
        "is_container": True,
        "is_drinkable": True,
        "liquid_name": "soda",
        "current_volume_ml": 200,
        "capacity_ml": 240,
    }
    result = apply_properties_from_json(obj, llm_props)
    assert result["is_container"] is True
    assert result["is_drinkable"] is True
    assert result["liquid_name"] == "soda"
    assert result["current_volume_ml"] == 200
    assert result["capacity_ml"] == 240
    assert result["weight_lbs"] == 1.0
    assert result["is_fragile"] is False


def test_apply_properties_from_json_empty_dict():
    from utils.object_properties import apply_properties_from_json, ensure_properties
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    ensure_properties(obj)
    result = apply_properties_from_json(obj, {})
    assert result["is_container"] is False


def test_apply_properties_from_json_overwrites_previous():
    from utils.object_properties import apply_properties_from_json, ensure_properties
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    ensure_properties(obj)
    obj.db.properties["liquid_name"] = "coffee"
    apply_properties_from_json(obj, {"liquid_name": "tea"})
    assert obj.db.properties["liquid_name"] == "tea"


def test_has_property_exists_check():
    from utils.object_properties import ensure_properties, has_property
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    props = ensure_properties(obj)
    props["liquid_name"] = "soda"
    obj.db.properties = props
    assert has_property(obj, "liquid_name") is True
    assert has_property(obj, "is_lit") is True
    assert has_property(obj, "nonexistent") is False


def test_has_property_value_check():
    from utils.object_properties import ensure_properties, has_property
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    props = ensure_properties(obj)
    props["is_drinkable"] = True
    props["liquid_name"] = "soda"
    obj.db.properties = props
    assert has_property(obj, "is_drinkable", True) is True
    assert has_property(obj, "is_drinkable", False) is False
    assert has_property(obj, "liquid_name", "soda") is True
    assert has_property(obj, "liquid_name", "tea") is False


def test_get_property_returns_value():
    from utils.object_properties import get_property, apply_properties_from_json
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    apply_properties_from_json(obj, {"liquid_name": "tea", "is_drinkable": True})
    assert get_property(obj, "liquid_name") == "tea"
    assert get_property(obj, "is_drinkable") is True
    assert get_property(obj, "nonexistent", "default") == "default"


def test_update_property_sets_value():
    from utils.object_properties import update_property, ensure_properties
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    ensure_properties(obj)
    update_property(obj, "liquid_name", "tea")
    update_property(obj, "current_volume_ml", 150)
    update_property(obj, "is_fragile", True)
    assert obj.db.properties["liquid_name"] == "tea"
    assert obj.db.properties["current_volume_ml"] == 150
    assert obj.db.properties["is_fragile"] is True


def test_object_is_drinkable_true():
    from utils.object_properties import object_is_drinkable, apply_properties_from_json
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    apply_properties_from_json(obj, {
        "is_drinkable": True,
        "liquid_name": "soda",
        "current_volume_ml": 200,
    })
    assert object_is_drinkable(obj) is True


def test_object_is_drinkable_false_when_empty():
    from utils.object_properties import object_is_drinkable, apply_properties_from_json
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    apply_properties_from_json(obj, {
        "is_drinkable": True,
        "liquid_name": "soda",
        "current_volume_ml": 0,
    })
    assert object_is_drinkable(obj) is False


def test_object_is_drinkable_false_when_not_drinkable():
    from utils.object_properties import object_is_drinkable, apply_properties_from_json
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties=None)
    apply_properties_from_json(obj, {
        "is_drinkable": False,
        "liquid_name": "oil",
        "current_volume_ml": 200,
    })
    assert object_is_drinkable(obj) is False


def test_object_is_drinkable_false_when_default_liquid_name():
    from utils.object_properties import object_is_drinkable
    obj = SimpleNamespace()
    obj.db = SimpleNamespace(properties={
        "is_drinkable": True,
        "liquid_name": "liquid",
        "current_volume_ml": 200,
    })
    assert object_is_drinkable(obj) is False


def test_get_property_schema_text_exists():
    from utils.object_properties import get_property_schema_text
    schema = get_property_schema_text()
    assert isinstance(schema, str)
    assert "is_container" in schema
    assert "is_drinkable" in schema


def test_default_properties_never_return_none():
    from utils.object_properties import DEFAULT_PROPERTIES
    for key, value in DEFAULT_PROPERTIES.items():
        assert value is not None or key == "contents", f"Default property {key} has None value"
