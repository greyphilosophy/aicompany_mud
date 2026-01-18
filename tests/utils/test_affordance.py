# tests/utils/test_affordance.py
from types import SimpleNamespace

import utils.affordance as af


class FakeObj:
    def __init__(self, affordance_value=None):
        self.db = SimpleNamespace(affordance=affordance_value)


def test_default_affordance_shape_and_defaults():
    a = af.default_affordance()
    assert a["unit"] == "lb"
    assert a["weight"] == 1.0
    assert a["immovable"] is False
    assert a["container"]["is_container"] is False
    assert a["container"]["capacity_weight"] == 0.0
    assert a["container"]["openable"] is False
    assert a["container"]["is_open"] is True
    assert "pick up" in a["manipulations"]
    assert "examine" in a["manipulations"]


def test_default_affordance_custom_unit():
    a = af.default_affordance(unit="kg")
    assert a["unit"] == "kg"


def test_ensure_affordance_creates_when_missing():
    obj = FakeObj(affordance_value=None)
    out = af.ensure_affordance(obj)

    assert isinstance(out, dict)
    assert obj.db.affordance is out
    assert out["unit"] == "lb"
    assert isinstance(out["container"], dict)
    assert out["container"]["is_open"] is True


def test_ensure_affordance_overwrites_non_dict():
    obj = FakeObj(affordance_value="not-a-dict")
    out = af.ensure_affordance(obj)

    assert isinstance(out, dict)
    assert out["unit"] == "lb"
    assert out["weight"] == 1.0


def test_ensure_affordance_preserves_existing_top_level_keys():
    obj = FakeObj(affordance_value={"unit": "kg", "weight": 5.5, "immovable": True})
    out = af.ensure_affordance(obj)

    assert out["unit"] == "kg"
    assert out["weight"] == 5.5
    assert out["immovable"] is True
    # still ensures missing keys exist
    assert "container" in out
    assert "manipulations" in out


def test_ensure_affordance_merges_container_dict():
    obj = FakeObj(affordance_value={
        "container": {
            "is_container": True,
            "capacity_weight": 10.0,
            # missing openable/is_open should be filled
        }
    })
    out = af.ensure_affordance(obj)

    assert out["container"]["is_container"] is True
    assert out["container"]["capacity_weight"] == 10.0
    assert out["container"]["openable"] is False
    assert out["container"]["is_open"] is True


def test_ensure_affordance_replaces_container_when_not_dict():
    obj = FakeObj(affordance_value={"container": "nope"})
    out = af.ensure_affordance(obj)

    assert isinstance(out["container"], dict)
    assert out["container"]["is_container"] is False
    assert out["container"]["is_open"] is True


def test_ensure_affordance_custom_unit_applied_on_creation():
    obj = FakeObj(affordance_value=None)
    out = af.ensure_affordance(obj, unit="kg")
    assert out["unit"] == "kg"
