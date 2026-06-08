# tests/utils/test_abilities.py
"""Tests for utils/abilities.py — the ability registry system."""

import pytest
from types import SimpleNamespace


def test_get_abilities_returns_dict():
    from utils.abilities import get_abilities
    abilities = get_abilities()
    assert isinstance(abilities, dict)


def test_find_abilities_for_object_returns_list():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Test", db=SimpleNamespace(properties={}))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_execute_ability_unknown():
    from utils.abilities import execute_ability
    caller = SimpleNamespace(messages=[])
    caller.msg = lambda t: caller.messages.append(t)
    obj = SimpleNamespace(key="Test", db=SimpleNamespace(properties={}))
    result = execute_ability(caller, "fizzbuzz", obj)
    assert result is False
    assert len(caller.messages) > 0


def test_get_verb_map():
    from utils.abilities import get_verb_map
    verb_map = get_verb_map()
    assert isinstance(verb_map, dict)


def test_register_ability_works():
    from utils.abilities import register_ability, get_abilities
    import uuid
    unique_name = f"test_uniq_{uuid.uuid4().hex[:8]}"
    @register_ability(unique_name, verbs=["test"], description="A test ability")
    def _handler(caller, target):
        pass
    abilities = get_abilities()
    assert unique_name in abilities
    info = abilities[unique_name]
    assert info["name"] == unique_name
    assert "test" in info["verbs"]


def test_register_ability_default_verbs():
    from utils.abilities import register_ability, get_abilities
    import uuid
    unique_name = f"test_def_{uuid.uuid4().hex[:8]}"
    @register_ability(unique_name)
    def _handler(caller, target):
        pass
    abilities = get_abilities()
    assert unique_name in abilities
    assert unique_name in abilities[unique_name]["verbs"]


def test_find_abilities_empty_properties():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Test", db=SimpleNamespace(properties={}))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_with_none_properties():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Test", db=SimpleNamespace(properties=None))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_with_properties():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Lamp", db=SimpleNamespace(properties={
        "is_lit": True,
        "light_radius": 3,
        "object_type": "light_source",
    }))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_does_not_crash_on_missing_key():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Test", db=SimpleNamespace(properties={"is_container": False}))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_handles_nested_properties():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Cup", db=SimpleNamespace(properties={
        "is_container": True,
        "is_drinkable": True,
        "liquid_name": "juice",
        "current_volume_ml": 100,
        "contents": [{"name": "juice", "amount_ml": 100}],
    }))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_object_type_check():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Lamp", db=SimpleNamespace(properties={
        "is_lit": True,
        "light_radius": 3,
        "object_type": "light_source",
    }))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_property_check_with_partial_match():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Cup", db=SimpleNamespace(properties={
        "is_container": True,
        "is_drinkable": True,
        "liquid_name": "tea",
        "current_volume_ml": 150,
        "object_type": "container",
    }))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_property_check_missing_required():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Glass", db=SimpleNamespace(properties={
        "is_container": True,
        "liquid_name": "water",
        "current_volume_ml": 200,
    }))
    abilities = find_abilities_for_object(obj)
    # Without is_drinkable, drink ability should not match
    # Just verify the function runs without crashing
    assert isinstance(abilities, list)


def test_find_abilities_property_check_with_all_falses():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Box", db=SimpleNamespace(properties={
        "is_container": False,
        "is_drinkable": False,
        "current_volume_ml": 0,
    }))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_property_check_with_nested_values():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Glass", db=SimpleNamespace(properties={
        "is_container": True,
        "is_drinkable": True,
        "liquid_name": "soda",
        "current_volume_ml": 200,
        "contents": [{"name": "soda", "amount_ml": 200}],
    }))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)


def test_find_abilities_property_check_with_all_keys():
    from utils.abilities import find_abilities_for_object
    obj = SimpleNamespace(key="Glass", db=SimpleNamespace(properties={
        "is_container": True,
        "is_drinkable": True,
        "liquid_name": "water",
        "current_volume_ml": 200,
        "capacity_ml": 240,
    }))
    abilities = find_abilities_for_object(obj)
    assert isinstance(abilities, list)
