# Actor components and tools

This refactor separates reusable actor equipment from NPC starter bodies and
provides a construction API for the existing executable tool types.

## Acceptance requirements

- Context, Memory, Listener and Brain have dedicated component modules. Tasks
  have their own module. Tool authorization/validation and concrete tools live
  in a tools package. NPC remains a starter body using these shared components.
- Previously stored typeclass paths and Python imports continue to resolve to the
  same classes. Loading an existing object preserves its identity, attributes,
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
