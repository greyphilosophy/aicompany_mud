"""
craft command — create items using the crafting skill.

Usage:
  craft <item>            (craft a single item)
  <item> x<n>              (craft n copies)
  craft                  (show craftable items)

Players can craft equipment, potions, and trinkets from their inventory.
The item's quality depends on the player's Crafting skill level.

Examples:
  craft leather armor
  craft health potion x3
  craft
"""
from commands.command import Command

# Recipes: item_name -> (required_materials, required_crafting_level, description_template)
RECIPE_BOOK = {
    # Armor
    "leather armor": (["leather", "thread"], 0, "You craft a sturdy leather armor from the materials."),
    "iron breastplate": (["iron", "leather", "thread"], 1, "You hammer out a gleaming iron breastplate."),
    "dragon scale armor": (["dragon scale", "iron", "leather"], 2, "You forge an impressive dragon scale armor."),
    "enchanted robe": (["silk", "crystal", "thread"], 2, "You weave a robe shimmering with enchantment."),
    "plate mail": (["iron", "leather", "rivets"], 1, "You assemble a full set of plate mail."),

    # Weapons
    "iron sword": (["iron", "wood", "leather"], 0, "You forge a sharp iron sword."),
    "steel dagger": (["iron", "leather", "thread"], 0, "You craft a slender steel dagger."),
    "battle axe": (["iron", "wood", "leather"], 1, "You hammer a fierce battle axe."),
    "magic staff": (["wood", "crystal", "thread"], 2, "You bind a staff humming with magic."),
    "silver bow": (["wood", "leather", "silver"], 1, "You craft a graceful silver bow."),

    # Potions
    "health potion": (["herb", "crystal", "glass"], 0, "You brew a restorative health potion."),
    "strength potion": (["herb", "iron", "glass"], 1, "You distill a potent strength potion."),
    "wisdom potion": (["crystal", "herb", "silk"], 2, "You prepare a shimmering wisdom potion."),
    "speed potion": (["herb", "silver", "glass"], 1, "You mix a swift speed potion."),
    "luck charm": (["crystal", "silver", "thread"], 1, "You craft a lucky charm from rare materials."),

    # Accessories
    "silver ring": (["silver", "thread"], 0, "You fashion a simple silver ring."),
    "crystal necklace": (["crystal", "silver", "thread"], 1, "You set a crystal into a silver necklace."),
    "leather belt": (["leather", "iron"], 0, "You craft a sturdy leather belt."),
    "adventurer's cloak": (["silk", "leather", "thread"], 1, "You weave a fine adventurer's cloak."),
    "iron crown": (["iron", "crystal", "silver"], 2, "You forge an ornate iron crown."),
}


def _find_materials(caller, materials_needed):
    """Check if the caller has all needed materials in inventory."""
    available = {}
    missing = []
    for needed in materials_needed:
        found = False
        for obj in caller.contents:
            if hasattr(obj, "key") and needed.lower() in (obj.key or "").lower():
                if needed not in available:
                    available[needed] = obj
                    found = True
                    break
        if not found:
            missing.append(needed)
    return available, missing


def _consume_materials(caller, materials):
    """Remove materials from the caller's inventory (via unequip + delete)."""
    for name, obj in materials.items():
        # Remove from equipped if present
        equipped = getattr(caller.db, "equipped", None) or {}
        for slot, item_key in list(equipped.items()):
            if obj.key and obj.key.lower() in item_key.lower():
                equipped.pop(slot)
                caller.db.equipped = equipped
                break
        # Remove from inventory
        if obj in caller.contents:
            caller.contents.remove(obj)


def _check_crafting_level(caller, required_level):
    """Check if the caller's crafting skill is high enough."""
    xp = getattr(caller.db, "xp", {}).get("crafting", 0)
    # Simple level calculation: 0=Novice(0+), 1=Adept(5+), 2=Veteran(17+), 3=Master(42+), 4=Legend(92+)
    XP_THRESHOLDS = [0, 5, 17, 42, 92]
    level = 0
    for i, threshold in enumerate(XP_THRESHOLDS):
        if xp >= threshold:
            level = i
    return level >= required_level


class CmdCraft(Command):
    """
    Craft items from materials in your inventory.

    Usage:
      craft                (show craftable items)
      craft <item>         (craft one item)
      craft <item> x<n>    (craft n copies)
    """
    key = "craft"
    aliases = ["make", "forge", "brew", "fashion"]
    help_category = "Character"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            # Show all craftable items grouped by type
            categories = {"Armor": [], "Weapons": [], "Potions": [], "Accessories": []}
            armor_keywords = ["armor", "breastplate", "robe", "mail", "cloak"]
            weapon_keywords = ["sword", "dagger", "axe", "staff", "bow"]
            potion_keywords = ["potion", "charm"]
            accessory_keywords = ["ring", "necklace", "belt", "crown"]

            for item_name, (materials, req_level, _) in RECIPE_BOOK.items():
                level_name = ["Novice", "Adept", "Veteran", "Master", "Legend"][min(req_level, 4)]
                mat_str = ", ".join(materials)
                entry = f"  {item_name} ({mat_str}) [Crafting: {level_name}]"

                if any(kw in item_name for kw in armor_keywords):
                    categories["Armor"].append(entry)
                elif any(kw in item_name for kw in weapon_keywords):
                    categories["Weapons"].append(entry)
                elif any(kw in item_name for kw in potion_keywords):
                    categories["Potions"].append(entry)
                else:
                    categories["Accessories"].append(entry)

            lines = ["Available items to craft:"]
            for cat_name, items in categories.items():
                if items:
                    lines.append(f"  — {cat_name} —")
                    lines.extend(items)
            caller.msg("\n".join(lines))
            return

        # Parse args for item name and quantity
        parts = args.split()
        item_name = None
        quantity = 1
        for i, part in enumerate(parts):
            if part.startswith("x") and i > 0:
                try:
                    quantity = int(part[1:])
                    item_name = " ".join(parts[:i])
                except ValueError:
                    caller.msg(f"Invalid quantity: '{part}'. Use format: craft <item> x3")
                    return
            elif part.lower().startswith("x") and i == 0:
                caller.msg("Usage: craft <item> [x<quantity>]")
                return

        if item_name is None:
            item_name = " ".join(parts)

        item_name_lower = item_name.lower()

        # Find matching recipe
        matched_recipe = None
        for recipe_name, recipe_data in RECIPE_BOOK.items():
            if item_name_lower == recipe_name or item_name_lower in recipe_name:
                matched_recipe = (recipe_name, recipe_data)
                break

        if not matched_recipe:
            caller.msg(f"No recipe found for '{item_name}'. Type 'craft' to see available items.")
            return

        recipe_name, (materials, req_level, success_msg) = matched_recipe

        # Check crafting level
        if not _check_crafting_level(caller, req_level):
            level_name = ["Novice", "Adept", "Veteran", "Master", "Legend"][req_level]
            caller.msg(f"Your crafting skill isn't high enough. You need to be at least {level_name} (Level {req_level}).")
            caller.msg("  Try 'train crafting' to improve your skill!")
            return

        # Check materials (for all copies)
        for _ in range(quantity):
            available, missing = _find_materials(caller, materials)
            if missing:
                caller.msg(f"Missing materials for '{recipe_name}': {', '.join(missing)}")
                caller.msg("You'll need to find or gather these items first.")
                return

        # Consume materials and create crafted items
        success_count = 0
        for i in range(quantity):
            available, _ = _find_materials(caller, materials)
            _consume_materials(caller, available)
            # Create the crafted item and add it to inventory
            crafted = caller.create(
                key=recipe_name,
                type_class="typeclasses.objects.Object"
            )
            if crafted:
                caller.inventory.add(crafted)
                success_count += 1

        if success_count == 1:
            caller.msg(success_msg)
        else:
            caller.msg(f"You craft {success_count}x {recipe_name}.")

        caller.msg("Crafting experience earned!")
