"""
Object

The Object is the class for general items in the game world.

Use the ObjectParent class to implement common features for *all* entities
with a location in the game world (like Characters, Rooms, Exits).

"""

from evennia.objects.objects import DefaultObject
from evennia.utils.utils import inherits_from
from utils.image_mixin import ImageMixin


class ObjectParent:
    """
    This is a mixin that can be used to override *all* entities inheriting at
    some distance from DefaultObject (Objects, Exits, Characters and Rooms).

    Just add any method that exists on `DefaultObject` to this class. If one
    of the derived classes has itself defined that same hook already, that will
    take precedence.
    """


class Object(ImageMixin, ObjectParent, DefaultObject):
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
        """Return the object description with image appended."""
        desc = getattr(self.db, "desc", "") or ""
        if getattr(self.db, "image_generating", False):
            return f"{desc}\n\n|yImage: generating...|n" if desc else "|yImage: generating...|n"
        url = getattr(self.db, "image_url", None)
        if url:
            # Check if the image file still exists — if stale, regenerate
            if self._is_image_stale(url):
                self.db.image_url = None
                self._trigger_image_generation(getattr(self.db, "desc", ""), "object")
                return f"{desc}\n\n|yImage: generating...|n" if desc else "|yImage: generating...|n"
            safe_url = self._make_safe_url(url)
            return f"{desc}\n\n|yImage: {safe_url}|n"

        # No image yet — trigger generation (respects cooldown)
        if self._can_trigger_image():
            self._trigger_image_generation(getattr(self.db, "desc", ""), "object")
            return f"{desc}\n\n|yImage: generating...|n" if desc else "|yImage: generating...|n"

        return desc

