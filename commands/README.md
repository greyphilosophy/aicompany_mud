# Player commands

`default_cmdsets.py` extends Evennia's standard command sets. Add a custom command
there to make it available to Characters. Preserve these configured command-set
paths unless the corresponding server settings are updated too.

| Module | Command | Purpose |
| --- | --- | --- |
| `inventory.py` | `get <item> from <holder>` / `grab` | Retrieve a nearby holder's direct inventory item with access checks; ordinary room pickup is preserved |
| `tools.py` | `tool <name>[/<action> = <JSON>]` | Inspect or invoke a carried executable tool |
| `dig.py` | `dig` | Create SmartRoom locations |
| `drink.py` | `drink`, `check` | Consume drinks and inspect object abilities |
| `regen.py` | `regen` | Request image regeneration |

Giving uses the inherited Evennia command: `give <item> to <holder>`. See
[Inventory transfers](../docs/inventory-transfers.md) for retrieval defaults and
holder locks.

The player `tool` command and Brain use the same `Tool.invoke()` contract. Tool
construction is currently a trusted Python setup operation described in
[Component architecture](../docs/component-architecture.md); no fabrication
command is installed.
