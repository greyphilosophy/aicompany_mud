"""Compatibility and construction acceptance tests for the component refactor."""

from importlib import import_module

import pytest
from evennia.objects.models import ObjectDB
from evennia.utils.create import create_object
from evennia.utils.idmapper.models import flush_cache

from tests.test_agency_requirements import world, decide


MOVED_CLASSES = [
    ('typeclasses.npcs.Context', 'typeclasses.components.context.Context'),
    ('typeclasses.npcs.Memory', 'typeclasses.components.memory.Memory'),
    ('typeclasses.npcs.Listener', 'typeclasses.components.listener.Listener'),
    ('typeclasses.npcs.Task', 'typeclasses.tasks.Task'),
    ('typeclasses.npcs.Tool', 'typeclasses.tools.base.Tool'),
    ('typeclasses.npcs.Speaker', 'typeclasses.tools.speaker.Speaker'),
    ('typeclasses.agency.Brain', 'typeclasses.components.brain.Brain'),
    ('typeclasses.agency.StickyNotePad', 'typeclasses.tools.notes.StickyNotePad'),
]


def resolve(path):
    module, name = path.rsplit('.', 1)
    return getattr(import_module(module), name)


@pytest.mark.parametrize('legacy,canonical', MOVED_CLASSES)
def test_saved_legacy_paths_reload_without_losing_state(world, legacy, canonical):
    cls = resolve(canonical)
    assert resolve(legacy) is cls
    obj = create_object(legacy, key='Existing equipment', location=world.npc)
    obj.db.preserved = {'content': ['learned fact'], 'budget': 3}
    object_id, holder_id = obj.id, world.npc.id
    contents = [item.id for item in obj.contents]
    # Emulate a database record saved by the previous version, then reload it.
    ObjectDB.objects.filter(pk=object_id).update(db_typeclass_path=legacy)
    flush_cache()
    loaded = ObjectDB.objects.get(pk=object_id)
    assert isinstance(loaded, cls)
    assert loaded.location.id == holder_id
    assert loaded.db.preserved == {'content': ['learned fact'], 'budget': 3}
    assert [item.id for item in loaded.contents] == contents
    assert loaded.db_typeclass_path == legacy


def test_catalog_and_factory_create_independent_functional_tools(world):
    from typeclasses.tools.factory import create_tool, list_tool_types
    from typeclasses.tools.base import Tool

    catalog = {item['id']: item for item in list_tool_types()}
    assert set(catalog) == {'speaker', 'sticky_note_pad'}
    assert 'say' in catalog['speaker']['actions']
    assert 'create_task' in catalog['sticky_note_pad']['actions']
    catalog['speaker']['actions'].clear()
    assert list_tool_types()[0]['actions']  # callers cannot mutate definitions
    pad = create_tool('sticky_note_pad', location=world.npc, key='Notes')
    other = create_tool('sticky_note_pad', location=world.other)
    assert isinstance(pad, Tool)
    assert pad.id != other.id
    assert pad.location == world.npc
    assert pad.key == 'Notes'
    result = pad.invoke(world.npc, 'create_task', {'objective': 'Find the key'})
    task = world.npc.get_active_task()
    assert task.dbref == result['task']
    assert task.db.objective == 'Find the key'
    assert other.location == world.other
    with pytest.raises(PermissionError):
        pad.invoke(world.other, 'create_task', {'objective': 'Unauthorized'})


@pytest.mark.parametrize('type_id', ['missing', 'typeclasses.tools.speaker.Speaker', '', None, []])
def test_unknown_factory_types_create_nothing(world, type_id):
    from typeclasses.tools.factory import create_tool
    count = ObjectDB.objects.count()
    with pytest.raises(ValueError):
        create_tool(type_id, location=world.npc)
    assert ObjectDB.objects.count() == count


@pytest.mark.parametrize('kwargs', [{'location': None}, {'key': ''}, {'key': 123}])
def test_invalid_factory_inputs_create_nothing(world, kwargs):
    from typeclasses.tools.factory import create_tool
    count = ObjectDB.objects.count()
    arguments = {'location': world.npc, **kwargs}
    with pytest.raises(ValueError):
        create_tool('speaker', **arguments)
    assert ObjectDB.objects.count() == count


def test_brain_uses_factory_tool_without_speaker(world):
    from typeclasses.components.brain import Brain
    from typeclasses.tools.factory import create_tool
    world.voice.delete()
    pad = create_tool('sticky_note_pad', location=world.npc)
    create_object(Brain, location=world.npc)
    parent = world.npc.create_task('Organize the search')
    snapshot = world.jobs[-1][1][0]
    assert [tool['id'] for tool in snapshot['tools']] == [pad.dbref]
    decide(world, {'action': 'invoke', 'tool': pad.dbref, 'name': 'create_task',
                   'arguments': {'objective': 'Find the key'}})
    child = next(task for task in world.npc.get_tasks() if task != parent)
    assert child.db.parent_task == parent
    assert child.db.assignee == world.npc
    decide(world, {'action': 'wait'})
