"""
Object

The Object is the class for general items in the game world.

Use the ObjectParent class to implement common features for *all* entities
with a location in the game world (like Characters, Rooms, Exits).

"""

from evennia.objects.objects import DefaultObject
from evennia.utils.utils import inherits_from


class ObjectParent:
    """
    This is a mixin that can be used to override *all* entities inheriting at
    some distance from DefaultObject (Objects, Exits, Characters and Rooms).

    Just add any method that exists on `DefaultObject` to this class. If one
    of the derived classes has itself defined that method already, that will
    take precedence.
    """


class Object(ObjectParent, DefaultObject):
    # Object image generation settings (parallel to ImageMixin)
    image_enabled = True
    image_generation_cooldown = 5.0

    def at_object_creation(self):
        super().at_object_creation()
        # Initialize image state
        self.db.image_url = None
        self.db.image_generating = False
        self.db._image_generation_last_ts = 0.0

    def at_object_delete(self):
        """
        When a notable prop is deleted inside a SmartRoom, trigger a rewrite.
        """
        loc = self.location
        if loc and hasattr(loc, "_schedule_desc_rewrite") and getattr(self.db, "notable", False):
            try:
                loc._schedule_desc_rewrite()
            except Exception:
                pass
        return super().at_object_delete()

    def get_display_desc(self, looker=None, **kwargs):
        """Return the object description with image URL appended."""
        desc = getattr(self.db, "desc", "") or ""

        if getattr(self.db, "image_generating", False):
            return f"{desc}\n\n|yImage: generating...|n"

        url = getattr(self.db, "image_url", None)
        if url:
            return f"{desc}\n\n|yImage: {url}|n"
        return desc
