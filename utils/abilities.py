# utils/abilities.py
# Ability Framework — Extensible ability system for MUD objects

from typing import Dict, List, Optional
from evennia.utils import logger

# Registry of all known abilities
_ABILITIES = {}


def register_ability(name, verbs=None, requires_property=None, description=""):
    """
    Register a new ability with the framework.
    
    Args:
        name: Canonical name of the ability (e.g., "drink", "wear", "wield")
        verbs: List of natural language verbs that trigger this ability
        requires_property: Property requirements for the target object
        description: Human-readable description
    
    Returns:
        Decorator function for the ability handler
    """
    def decorator(func):
        _ABILITIES[name] = {
            "handler": func,
            "verbs": verbs or [name],
            "requires_property": requires_property or {},
            "description": description,
            "name": name,
        }
        return func
    return decorator


def get_abilities():
    """Return all registered abilities."""
    return _ABILITIES


def find_ability_by_verb(verb):
    """Find an ability name by its verb form."""
    verb = verb.lower().strip()
    for name, info in _ABILITIES.items():
        if verb in info["verbs"]:
            return name
    return None


def find_abilities_for_object(obj):
    """
    Find all abilities that apply to an object based on its properties.
    
    Args:
        obj: Evennia object with db.properties
    
    Returns:
        List of matching ability info dicts
    """
    props = obj.db.properties or {}
    matches = []
    
    for name, info in _ABILITIES.items():
        req = info.get("requires_property", {})
        if not req:
            matches.append(info)
            continue
        
        # Check if object meets all property requirements
        all_match = True
        for prop_name, prop_value in req.items():
            if prop_name == "object_type":
                if prop_value == obj.db.properties.get("object_type"):
                    continue
                all_match = False
                break
            
            if prop_name == "liquid_name":
                if "liquid_name" not in props:
                    all_match = False
                    break
                continue
            
            if prop_name not in props:
                all_match = False
                break
            if props[prop_name] != prop_value:
                all_match = False
                break
        
        if all_match:
            matches.append(info)
    
    return matches


def execute_ability(caller, ability_name, target):
    """
    Execute an ability on a target object.
    
    Args:
        caller: The Evennia character calling the ability
        ability_name: The canonical ability name
        target: The target Evennia object
    
    Returns:
        True if the ability was successfully executed, False otherwise
    """
    ability = _ABILITIES.get(ability_name)
    if not ability:
        caller.msg(f"Unknown ability: {ability_name}")
        return False
    
    handler = ability["handler"]
    try:
        handler(caller, target)
        return True
    except Exception as e:
        logger.log_err(f"[Ability] Error executing {ability_name}: {e}")
        caller.msg(f"The {ability_name} ability encountered an error.")
        return False


def get_verb_map():
    """
    Build a map from verbs to ability names for command parsing.
    """
    verb_map = {}
    for name, info in _ABILITIES.items():
        for verb in info["verbs"]:
            verb_map[verb] = name
    return verb_map
