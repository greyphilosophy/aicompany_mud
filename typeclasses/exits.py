from evennia import DefaultExit
from evennia.utils import create

ALIASES = {
    "north": ["n"],
    "south": ["s"],
    "east": ["e"],
    "west": ["w"],
    "up": ["u"],
    "down": ["d"],
}

DIRECTIONS = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
    "up": "down",
    "down": "up",
}

class Exit(DefaultExit):
    """
    Default exit. Automatically adds direction aliases.
    """
    def at_object_creation(self):
        super().at_object_creation()
        key = (self.key or "").lower().strip()
        aliases = ALIASES.get(key)
        if aliases:
            self.aliases.add(*aliases)

class SmartExit(Exit):
    """
    Smart exit. No auto-room-creation; rooms are created via the `dig` command.
    """
    pass
