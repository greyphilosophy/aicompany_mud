"""
Characters

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""

from evennia.objects.objects import DefaultCharacter
from evennia.utils import logger
from .objects import ObjectParent


class Character(ObjectParent, DefaultCharacter):
    """
    The Character just re-implements some of the Object's methods and hooks
    to represent a Character entity in-game.

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Object child classes like this.

    """

    def at_say(self, message, **kwargs):
        # normal say handling
        super().at_say(message, **kwargs)

        # delegate to the room manager (if it exists)
        loc = self.location
        if loc and hasattr(loc, "handle_speech"):
            try:
                loc.handle_speech(self, message, **kwargs)
            except Exception:
                logger.log_trace()

    pass
