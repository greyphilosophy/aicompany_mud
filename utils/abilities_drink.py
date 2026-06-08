# utils/abilities_drink.py
# Drink ability registration — proof-of-concept for the ability system

from utils.abilities import register_ability


@register_ability(
    name="drink",
    verbs=["drink", "sip", "gulp", "swallow", "quaff"],
    requires_property={
        "is_drinkable": True,
        "current_volume_ml": 1,  # Just needs to have some volume
    },
    description="Drink from a liquid container, reducing its volume"
)
def ability_drink(caller, target):
    """
    Drink from a drinkable object.
    
    Reduces the liquid volume by 60ml per sip.
    When empty, updates the object's description.
    """
    props = target.db.properties
    if not props:
        caller.msg(f"The {target.key} doesn't seem to have any liquid properties.")
        return
    
    current_vol = props.get("current_volume_ml", 0)
    liquid_name = props.get("liquid_name", "liquid")
    
    if current_vol <= 0:
        caller.msg(f"The {target.key} is empty.")
        return
    
    # Drink 60ml per sip (or the remaining amount)
    drink_amount = min(60, current_vol)
    
    # Update volume
    props["current_volume_ml"] = current_vol - drink_amount
    
    if current_vol - drink_amount <= 0:
        # Empty!
        props["current_volume_ml"] = 0
        old_key = target.key
        # Try to create an empty version
        if "glass" in old_key.lower():
            new_key = "Empty Glass"
        elif "cup" in old_key.lower():
            new_key = "Empty Cup"
        elif "bottle" in old_key.lower():
            new_key = "Empty Bottle"
        else:
            new_key = "Empty Container"
        
        target.key = new_key
        target.db.shortdesc = "an empty container"
        caller.msg(f"You drink the last of the {liquid_name}. The container is empty.")
    else:
        caller.msg(f"You take a sip of the {liquid_name}.")
    
    # Save the updated properties
    target.db.properties = props
    target.save_attribute("properties", props)