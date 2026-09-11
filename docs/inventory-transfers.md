# Inventory transfers

Players can use `give <item> to <holder>` to give a carried item to an NPC or ordinary object, and `get <item> from <holder>` to retrieve it. `grab` is an alias; ordinary `get <item>` retains Evennia's behavior. Use names that uniquely identify the holder and item.

Acceptance criteria:
- Source holders must be in the player's room or directly carried by the player. Only their direct contents are searched.
- NPC and ordinary object inventories allow removal by default. Character inventories deny removal by default, except the player's own inventory.
- An explicit `get_from` lock on the holder overrides that default; the item's `get` lock and pickup hooks still apply.
- Locked, missing, ambiguous or unreachable targets produce feedback without moving an item.
- Successful retrieval uses normal movement and pickup hooks, so equipment capabilities and task assignment follow the item. Failed movement never reports success.
- Existing room pickup and giving remain functional through the character command set.

Builders can protect a holder with `@lock Nova = get_from:false()` or allow access with `@lock Nova = get_from:all()`. This is an access rule, not an NPC consent negotiation or theft simulation. Moving a Brain onto a player Character grants that Character agency, as with other equipped holders.
