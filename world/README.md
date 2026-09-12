# World content

`prototypes.py` and `help_entries.py` hold game content using Evennia's expected
entry points. Add reusable content definitions and world setup scripts here.

Object behavior belongs in `typeclasses/`; shared runtime coordination belongs
in `systems/`; service adapters and room helpers belong in `utils/`.

Setup scripts can construct registered tools through
`typeclasses.tools.factory.create_tool()`. See
[Component architecture](../docs/component-architecture.md) for examples and
compatibility paths.
