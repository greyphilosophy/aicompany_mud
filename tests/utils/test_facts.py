# tests/utils/test_facts.py
import time
from types import SimpleNamespace

import utils.facts as facts


class FakeObj:
    def __init__(self, facts_value=None):
        self.db = SimpleNamespace(facts=facts_value)


def test_new_fact_structure_and_fields(monkeypatch):
    fixed_time = 1234567890.0
    monkeypatch.setattr(time, "time", lambda: fixed_time)

    f = facts.new_fact(
        text="  Hello world  ",
        created_by="alice",
        scope="room",
        strength=0.9,
        tags=["foo", "bar"],
    )

    assert f["id"].startswith("fact_")
    assert f["text"] == "Hello world"
    assert f["scope"] == "room"
    assert f["strength"] == 0.9
    assert f["tags"] == ["foo", "bar"]
    assert f["created_by"] == "alice"
    assert f["created_ts"] == fixed_time


def test_new_fact_defaults():
    f = facts.new_fact("x")

    assert f["text"] == "x"
    assert f["scope"] == "local"
    assert f["strength"] == 0.6
    assert f["tags"] == []
    assert f["created_by"] == ""


def test_add_fact_initializes_list_when_missing():
    obj = FakeObj(facts_value=None)
    f = {"id": "fact_1", "text": "hello"}

    facts.add_fact(obj, f)
    assert obj.db.facts == [f]


def test_add_fact_overwrites_non_list_storage():
    obj = FakeObj(facts_value={"bad": "data"})
    f = {"id": "fact_1", "text": "hello"}

    facts.add_fact(obj, f)
    assert obj.db.facts == [f]


def test_get_facts_returns_list_or_empty():
    assert facts.get_facts(FakeObj(facts_value=None)) == []
    assert facts.get_facts(FakeObj(facts_value={"x": 1})) == []

    lst = [{"id": "fact_1"}]
    assert facts.get_facts(FakeObj(facts_value=lst)) is lst


def test_remove_fact_success_and_failure():
    f1 = {"id": "fact_1", "text": "a"}
    f2 = {"id": "fact_2", "text": "b"}
    obj = FakeObj(facts_value=[f1, f2])

    removed = facts.remove_fact(obj, "fact_1")
    assert removed is True
    assert obj.db.facts == [f2]

    # removing again should fail
    removed_again = facts.remove_fact(obj, "fact_1")
    assert removed_again is False
    assert obj.db.facts == [f2]


def test_remove_fact_non_list_storage_is_safe():
    obj = FakeObj(facts_value={"bad": "data"})
    assert facts.remove_fact(obj, "fact_1") is False


def test_fact_texts_filters_and_strips():
    obj = FakeObj(
        facts_value=[
            {"id": "f1", "text": " hello "},
            {"id": "f2", "text": ""},
            {"id": "f3", "text": None},
            {"id": "f4"},
            "not a dict",
        ]
    )

    out = facts.fact_texts(obj)
    assert out == ["hello"]
