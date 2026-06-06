"""
equip command — equip and unequip items on your character.

Usage:
  equip <item>          (put on an item)
  equip <item> <slot>   (put on an item into a specific slot)
  equip                (show what you're wearing)
  unequip <slot>        (remove item from slot)
  unequip <item>        (remove a specific item)

Items are tracked in named slots (head, torso, legs, feet, hands,
back, waist, neck, weapon, accessory) for simple RPG-style dressing.

Examples:
  equip leather cap
  equip sword weapon
  equip
  unequip neck
"""
from commands.command import Command

SLOTS = [
    "head", "torso", "legs", "feet", "hands",
    "back", "waist", "neck", "weapon", "accessory"
]

def _find_item(caller, item_name):
    """Find a carried item matching the name (case-insensitive partial match)."""
    low = item_name.lower()
    matches = []
    for obj in caller.contents:
        if obj == caller and hasattr(obj, "key"):
            if low in (obj.key or "").lower():
                matches.append(obj)
    return matches


class CmdEquip(Command):
    """
    Equip or unequip items on your character.

    Usage:
      equip <item>          (auto-detect slot by item type)
      equip <item> <slot>   (force slot)
      equip                 (show equipped items)
    """
    key = "equip"
    aliases = ["wear", "don"]
    help_category = "Character"

    def func(self):
        caller = self.caller
        args = self.args

        # No arguments: show equipped slots
        if not args or args.strip() == "":
            equipped = getattr(caller.db, "equipped", None) or {}
            if not equipped:
                caller.msg("You are wearing nothing notable.")
                return
            lines = ["You have the following equipped:"]
            for slot, item_key in equipped.items():
                lines.append(f"  |w{slot:<12}|n — {item_key}")
            caller.msg("\n".join(lines))
            return

        parts = args.strip().split(maxsplit=1)
        item_name = parts[0]
        forced_slot = parts[1] if len(parts) > 1 else None

        # If user specified a slot (second arg), validate it
        if forced_slot:
            if forced_slot.lower() not in SLOTS:
                caller.msg(f"Invalid slot '{forced_slot}'. Choices: {', '.join(SLOTS)}")
                return
            slot = forced_slot.lower()
        else:
            # Auto-detect slot from item name
            slot = _auto_detect_slot(item_name)

        # Find the item in inventory
        matches = _find_item(caller, item_name)
        if not matches:
            caller.msg(f"No item matching '{item_name}' found in your inventory.")
            return
        if len(matches) > 1:
            caller.msg(f"Ambiguous: {', '.join(m.key for m in matches)}. Try a more specific name.")
            return

        item = matches[0]

        # Equip it
        equipped = getattr(caller.db, "equipped", None) or {}
        if slot in equipped:
            # Unequip the old item implicitly
            caller.msg(f"Swapped {equipped[slot]} for {item.key} on your {slot}.")
        else:
            caller.msg(f"You equip the {item.key} on your {slot}.")

        equipped[slot] = item.key
        caller.db.equipped = equipped


def _auto_detect_slot(item_name: str):
    """Guess an equipment slot from the item's name."""
    low = item_name.lower()
    if any(w in low for w in ["helmet", "hat", "cap", "visor", "headband", "crown"]):
        return "head"
    if any(w in low for w in ["armor", "vest", "coat", "shirt", "robe", "breastplate", "tunic", "jacket"]):
        return "torso"
    if any(w in low for w in ["pants", "trousers", "greaves", "leggings", "shorts", "boots"]):
        return "legs"
    if any(w in low for w in ["boots", "sandals", "sabots", "soles", "shoes"]):
        return "feet"
    if any(w in low for w in ["gloves", "gauntlets", "bracelets", "rings", "wrist"]):
        return "hands"
    if any(w in low for w in ["cloak", "cape", "mantle", "shroud"]):
        return "back"
    if any(w in low for w in ["belt", "sash", "girdle", "belt"]):
        return "waist"
    if any(w in low for w in ["amulet", "pendant", "chain", "medallion", "choker"]):
        return "neck"
    if any(w in low for w in ["sword", "blade", "axe", "mace", "staff", "dagger", "weapon"]):
        return "weapon"
    return "accessory"


class CmdUnequip(Command):
    """
    Unequip an item from your character.

    Usage:
      unequip <slot>     (remove by slot)
      unequip <item>     (remove by item name)
    """
    key = "unequip"
    aliases = ["remove", "undress", "strip"]
    help_category = "Character"

    def func(self):
        caller = self.caller
        args = self.args

        if not args or args.strip() == "":
            caller.msg("Usage: unequip <slot>  or  unequip <item>")
            return

        equipped = getattr(caller.db, "equipped", None) or {}
        target = args.strip().lower()

        # Check if target is a known slot
        if target in SLOTS:
            if target in equipped:
                removed = equipped.pop(target)
                caller.db.equipped = equipped
                caller.msg(f"You remove the {removed} from your {target}.")
            else:
                caller.msg(f"Nothing equipped in your {target} slot.")
            return

        # Otherwise, find the item by name and locate its slot
        for slot, item_key in list(equipped.items()):
            if target in item_key.lower():
                equipped.pop(slot)
                caller.db.equipped = equipped
                caller.msg(f"You remove the {item_key} from your {slot}.")
                return

        caller.msg(f"No equipped item matching '{args.strip()}'.")
