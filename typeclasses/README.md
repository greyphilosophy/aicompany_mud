# Typeclasses

Typeclasses define persistent Evennia world objects. Runtime coordination lives in
`systems/`, and service adapters and room helpers live in `utils/`.

| Module/package | Responsibility |
| --- | --- |
| `objects.py`, `characters.py`, `rooms.py`, `exits.py` | World bodies and locations |
| `actors.py` | Inventory-derived capabilities shared through `ObjectParent` |
| `npcs.py` | Carryable starter NPC with Context and Memory |
| `components/` | Portable Brain, Listener, Context and Memory |
| `tasks.py` | Transferable objectives and their working contexts |
| `tools/base.py` | Tool authorization, schemas and invocation |
| `tools/speaker.py`, `tools/notes.py` | Speech and task-note tools |
| `tools/factory.py` | Built-in tool definitions and construction |
| `agency.py` | Compatibility aliases for old typeclass/import paths |
| `accounts.py`, `channels.py`, `scripts.py` | Evennia account, communication and script typeclasses |

Concrete modules are imported explicitly; package initializers do not eagerly
load every typeclass. This avoids cycles during Evennia startup. `ActorMixin`
and movement hooks import equipment locally because equipment inherits `Object`.

See [Component architecture](../docs/component-architecture.md) for supported
paths, factory usage, adding a tool and loading existing worlds. Keep compatibility
aliases: Evennia stores typeclass paths in the database. Core configured paths
such as `typeclasses.characters.Character` and the command-set locations remain
stable; this refactor requires no settings change.
