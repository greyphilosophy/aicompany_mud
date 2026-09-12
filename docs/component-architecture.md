# Actor components and tools

This refactor separates reusable actor equipment from NPC starter bodies and
provides a construction API for the existing executable tool types.

## Acceptance requirements

- Context, Memory, Listener and Brain have dedicated component modules. Tasks
  have their own module. Tool authorization/validation and concrete tools live
  in a tools package. NPC remains a starter body using these shared components.
- Previously stored typeclass paths, exact/family queries and Python imports
  continue to identify the same classes. Loading an existing object preserves its identity, attributes,
  inventory and capabilities without a database migration.
- Agency scheduling and budgets remain shared runtime concerns. Moving modules
  must preserve current task, speech, inventory and capability behavior.
- Brain and legacy Speaker configuration use the same provider selection helper;
  configuring a Brain does not require a Speaker instance.
- A catalog identifies the built-in tool types by stable IDs. A factory creates
  real, independent Evennia tool objects in a supplied location with defaults.
  Unknown IDs and invalid inputs fail before any object is created.
- Factory-created tools use the existing action validation, permissions, player
  commands and Brain discovery. The catalog lists definitions, not an actor's
  authorized capabilities: only carried tools are currently advertised to a Brain.
- Documentation describes canonical imports, adding a tool, construction and
  compatibility. The factory is a trusted Python setup API; a player/model-facing
  fabrication tool and generated tool implementations remain future work.

## Module map

| Concern | Canonical location |
| --- | --- |
| Shared holder behavior | `typeclasses.actors.ActorMixin` via `ObjectParent` |
| Starter NPC body | `typeclasses.npcs.NPC` |
| Working context | `typeclasses.components.context.Context` |
| Durable knowledge | `typeclasses.components.memory.Memory` |
| Speech perception | `typeclasses.components.listener.Listener` |
| Reasoning | `typeclasses.components.brain.Brain` |
| Objectives | `typeclasses.tasks.Task` |
| Executable tool contract | `typeclasses.tools.base.Tool` |
| Speech tool | `typeclasses.tools.speaker.Speaker` |
| Task-note tool | `typeclasses.tools.notes.StickyNotePad` |
| Tool catalog and factory | `typeclasses.tools.factory` |
| Movement invalidation, wake scheduling and shared budgets | `systems.agency` |
| Model provider selection | `utils.actor_llm.get_actor_providers` |

Components provide perception, knowledge or reasoning. Executable tools expose
actions; task notes carry objectives. These are all ordinary world objects, and
their capabilities follow transfers. Rooms remain passive locations under the
current class hierarchy. Server configuration and web integration stay in their
existing Evennia directories.

## Constructing tools

Run this in trusted setup code or the Evennia shell, with an existing holder:

```python
from typeclasses.tools.factory import create_tool, list_tool_types

# Metadata contains stable type IDs, default names and copied action schemas.
catalog = list_tool_types()
voice = create_tool("speaker", location=nova, key="Voice")
notes = create_tool("sticky_note_pad", location=nova, key="Notes")
```

Omitting `key` uses the catalog's display name. Each call creates a new persistent
Evennia object in the supplied live location, runs its normal creation/movement
hooks, and returns it. IDs are exact: `speaker` and `sticky_note_pad` are currently
registered. Unknown IDs, invalid names and missing/deleted locations fail before
creation. Direct `create_object(ConcreteTool, ...)` remains supported.

The factory constructs a **tool type**; the resulting object's **dbref** identifies
that particular tool for Brain invocation. A catalog entry does not grant the
holder access to anything. The holder must carry an instance, and `Tool.invoke()`
still checks ownership/public use, its `use` lock, the action and arguments.

The factory is not an executable Tool and is not advertised to players or models.
It does not generate Python, load caller-supplied import paths, or manufacture
new behaviors from prose. A future fabrication tool can call this construction
API after its own requirements define authorization, resource limits and which
definitions it may create.

## Adding an executable tool

1. Add a module under `typeclasses/tools/` with a subclass of `Tool`.
2. Declare `ACTIONS`: action descriptions and object-shaped parameter schemas.
   The existing validator supports nonempty strings and bounded integers, required
   fields and rejection of unknown arguments. Extend validation and acceptance
   tests before using other schema types.
3. Implement `perform(actor, action, arguments, **context)` and return a
   JSON-serializable result. `Tool.invoke()` validates before calling it. Keep
   tool execution synchronous and any object access on the reactor thread.
4. Set `ENDS_BURST = True` if successful use should hand off control and end the
   current reasoning burst. Speaker does this; other tools default to continuing
   within the same budget. The Brain does not import concrete tool classes.
5. Add a `ToolDefinition` to the code-owned `BUILTIN_TOOLS` catalog if setup code
   should construct it by ID. Keep IDs stable; existing catalog metadata is
   copied when listed so callers cannot accidentally alter action schemas.
6. Add acceptance tests for meaningful effects, invalid arguments, authorization,
   transfer/removal and interaction with the Brain or player command as applicable.

New tools do not need branches added to the Brain dispatcher. Discovery is based
on carried `Tool` instances and their advertised actions. Context, Memory, Listener,
Brain and Task are instantiated normally; the tool factory does not classify
them as executable tools.

## Existing worlds and imports

The old imports remain aliases to the same classes in the implementation modules.
Existing classes retain their original persisted typeclass identities through
`typeclasses.compat.persisted_typeclass`, which preserves the metadata Evennia
uses for exact and family queries. This keeps both old and newly created objects
visible to the same queries. The following canonical paths are Python imports;
the legacy paths remain the storage identities:

| Legacy path | Canonical path |
| --- | --- |
| `typeclasses.npcs.Context` | `typeclasses.components.context.Context` |
| `typeclasses.npcs.Memory` | `typeclasses.components.memory.Memory` |
| `typeclasses.npcs.Listener` | `typeclasses.components.listener.Listener` |
| `typeclasses.npcs.Task` | `typeclasses.tasks.Task` |
| `typeclasses.npcs.Tool` | `typeclasses.tools.base.Tool` |
| `typeclasses.npcs.Speaker` | `typeclasses.tools.speaker.Speaker` |
| `typeclasses.agency.Brain` | `typeclasses.components.brain.Brain` |
| `typeclasses.agency.StickyNotePad` | `typeclasses.tools.notes.StickyNotePad` |

`typeclasses.npcs.NPC` stays in place. Earlier imports of the lifecycle/budget
helpers from `typeclasses.agency` also remain available. Use the canonical
modules for new code and test patch targets.

Restart the Evennia server after deploying the Python refactor. Existing records
can load through their legacy paths without recreating objects or modifying their
attributes, inventories, tasks or budgets. No database migration is required or
run. New objects of these existing types retain the same stored paths as old
objects. Both legacy and canonical import strings work with `create_object()`.
Use class objects for type checks, for example `isinstance(obj, Speaker)` or
`obj.is_typeclass(Speaker)`. Exact path-string checks and raw database filters
continue using the legacy storage identities in the table.

Preserving runtime identity means a class's `__module__` names its compatibility
module; the module map above identifies where its implementation lives. New tool
types that have never been persisted do not need the compatibility decorator.

## Verification

`tests/test_component_architecture.py` reloads database records with every legacy
path, checks retained attributes and nested contents, constructs and uses factory
tools, rejects invalid inputs without side effects, and exercises Brain discovery.
Run it with the existing portable-capability, inventory, agency and legacy speech
suites (command in the repository README). Tests control model responses; they
verify execution and data preservation, not live model quality or external services.
