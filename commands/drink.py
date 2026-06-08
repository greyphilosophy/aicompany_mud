# commands/drink.py
# Drink command — proof-of-concept for the ability system

import re
from evennia import Command
from evennia.utils.search import search_object

from utils.abilities import find_abilities_for_object
from utils.room_object_query import find_object_in_room


class CmdDrink(Command):
    """
    Drink from a liquid container.
    
    Usage:
      drink [target]
    
    Examples:
      drink glass of soda
      drink tea
      drink #123
    """
    key = "drink"
    aliases = ["sip", "gulp", "swallow"]
    locks = "cmd:all()"
    help_category = "Abilities"
    
    def func(self):
        caller = self.caller
        room = caller.location
        
        if not room:
            caller.msg("You are nowhere to drink in.")
            return
        
        # Parse target from arguments
        target_key = (self.args or "").strip()
        
        if not target_key:
            # No target specified — list drinkable things
            drinkable = [
                obj for obj in room.contents 
                if hasattr(obj, 'db') and 
                obj.db.properties and
                obj.db.properties.get("is_drinkable") and
                obj.db.properties.get("current_volume_ml", 0) > 0
            ]
            
            if drinkable:
                lines = ["|yYou can drink from:|n"]
                for obj in drinkable:
                    props = obj.db.properties
                    name = props.get("liquid_name", "liquid")
                    vol = props.get("current_volume_ml", 0)
                    lines.append(f"  {obj.key} ({vol}ml of {name})")
                caller.msg("\n".join(lines))
                caller.msg("Try: |wdrink [object]|n")
            else:
                caller.msg("There's nothing drinkable here.")
            return
        
        # Try to find the target object
        target = find_object_in_room(room, target_key)
        
        if not target:
            # Try dbref
            if target_key.startswith("#"):
                matches = search_object(target_key)
                if matches:
                    target = matches[0]
                    if target.location != room:
                        target = None
            
            if not target:
                caller.msg(f"You don't see '{target_key}' to drink from.")
                return
        
        # Check if the target is drinkable
        if not hasattr(target, 'db') or not target.db.properties:
            caller.msg(f"The {target.key} doesn't seem to be drinkable.")
            return
        
        if not target.db.properties.get("is_drinkable"):
            caller.msg(f"The {target.key} isn't drinkable.")
            return
        
        current_vol = target.db.properties.get("current_volume_ml", 0)
        
        if current_vol <= 0:
            caller.msg(f"The {target.key} is empty.")
            return
        
        # Perform the drink action
        liquid_name = target.db.properties.get("liquid_name", "liquid")
        drink_amount = min(60, current_vol)  # Drink 60ml per sip
        
        # Update the object's properties
        target.db.properties["current_volume_ml"] = current_vol - drink_amount
        target.save_attribute("properties", target.db.properties)
        
        # Update the short description to reflect the change
        if current_vol - drink_amount <= 0:
            # Empty!
            old_key = target.key
            target.key = target.key.replace("of " + liquid_name, "empty glass")
            if "glass" not in target.key.lower():
                target.key = "Empty " + target.key.split()[0]
            target.db.shortdesc = "an empty container"
            caller.msg(f"You drink the rest of the {liquid_name}. The container is empty.")
        else:
            caller.msg(f"You take a sip of the {liquid_name}.")
        
        # Announce to the room
        room.msg_contents(f"{caller.key} drinks from the {target.key}.", exclude=caller)


class CmdCheckAbilities(Command):
    """
    Check what abilities are available for an object.
    
    Usage:
      check [target]
      abilities [target]
    """
    key = "check"
    aliases = ["abilities", "inspect", "probe"]
    locks = "cmd:all()"
    help_category = "Abilities"
    
    def func(self):
        caller = self.caller
        room = caller.location
        
        if not room:
            caller.msg("You are nowhere.")
            return
        
        target_key = (self.args or "").strip()
        
        if not target_key:
            # List objects with special abilities
            objects_with_abilities = []
            for obj in room.contents:
                if hasattr(obj, 'db') and obj.db.properties:
                    abilities = find_abilities_for_object(obj)
                    if abilities:
                        objects_with_abilities.append((obj, abilities))
            
            if objects_with_abilities:
                lines = ["|yObjects with special abilities:|n"]
                for obj, abilities in objects_with_abilities:
                    ability_names = [a.get("name", "unknown") for a in abilities]
                    lines.append(f"  {obj.key}: {', '.join(ability_names)}")
                caller.msg("\n".join(lines))
            else:
                caller.msg("No special abilities detected on objects here.")
            return
        
        # Find the target
        target = find_object_in_room(room, target_key)
        
        if not target:
            if target_key.startswith("#"):
                matches = search_object(target_key)
                if matches:
                    target = matches[0]
            
            if not target:
                caller.msg(f"You don't see '{target_key}'.")
                return
        
        if not hasattr(target, 'db'):
            caller.msg(f"The {target.key} seems like a normal object.")
            return
        
        # Show object properties
        props = target.db.properties
        if props:
            lines = [f"|y{target.key} properties:|n"]
            
            if props.get("object_type"):
                lines.append(f"  Type: {props['object_type']}")
            
            if props.get("is_container"):
                lines.append(f"  Container (capacity: {props.get('capacity_ml', 240)}ml)")
            
            if props.get("is_liquid"):
                lines.append(f"  Liquid: {props.get('liquid_name', 'liquid')} ({props.get('current_volume_ml', 0)}ml)")
            
            if props.get("is_drinkable"):
                lines.append("  ✓ Drinkable")
            
            if props.get("is_lit"):
                lines.append(f"  Light (radius: {props.get('light_radius', 3)} rooms)")
            
            caller.msg("\n".join(lines) + "\n\n")
        
        # Show available abilities
        abilities = find_abilities_for_object(target)
        if abilities:
            lines = ["|wAvailable abilities:|n"]
            for ability in abilities:
                name = ability.get("name", "unknown")
                description = ability.get("description", "")
                lines.append(f"  {name}: {description}")
            caller.msg("\n".join(lines))
        else:
            caller.msg(f"No special abilities available for the {target.key}.")


class CmdObjectInfo(Command):
    """
    Get detailed information about an object.
    
    Usage:
      info [target]
      details [target]
    """
    key = "info"
    aliases = ["details", "stats"]
    locks = "cmd:all()"
    help_category = "Abilities"
    
    def func(self):
        caller = self.caller
        room = caller.location
        
        if not room:
            caller.msg("You are nowhere.")
            return
        
        target_key = (self.args or "").strip()
        
        if not target_key:
            # Show all objects and their properties
            lines = ["|yObjects in the room:|n"]
            for obj in room.contents:
                if hasattr(obj, 'db') and obj.db.properties:
                    props = obj.db.properties
                    lines.append(f"  {obj.key} ({obj.dbref}):")
                    if props.get("object_type"):
                        lines.append(f"    Type: {props['object_type']}")
                    if props.get("is_drinkable"):
                        lines.append(f"    Drinkable ({props.get('current_volume_ml', 0)}ml)")
            caller.msg("\n".join(lines))
            return
        
        # Find target
        target = find_object_in_room(room, target_key)
        
        if not target:
            if target_key.startswith("#"):
                matches = search_object(target_key)
                if matches:
                    target = matches[0]
            
            if not target:
                caller.msg(f"You don't see '{target_key}'.")
                return
        
        # Display full object info
        if hasattr(target, 'db'):
            lines = [f"|y{target.key} ({target.dbref}):|n"]
            lines.append(f"  Description: {target.db.desc or 'A basic object.'}")
            
            if target.db.properties:
                props = target.db.properties
                lines.append("  Properties:")
                for key, value in props.items():
                    lines.append(f"    {key}: {value}")
            
            caller.msg("\n".join(lines))
        else:
            caller.msg(f"The {target.key} is a basic object.")