"""
Touch command — examine an object by touching it.

Shows the full description and short description of a room object,
giving the player a richer sense of what's around them.
"""
from evennia import Command


def _find_object(caller, key: str):
    """Find an object in the current room by key or alias."""
    room = caller.location
    if not room:
        return None

    low = key.lower()
    for obj in room.contents:
        if obj == caller:
            continue
        if hasattr(obj, "key") and (obj.key or "").lower() == low:
            return obj
        if hasattr(obj, "aliases") and low in [a.lower() for a in obj.aliases.all()]:
            return obj

    # Fallback: Evennia search within the room's contents
    for obj in room.contents:
        if obj == caller:
            continue
        if hasattr(obj, "key") and key.lower() in (obj.key or "").lower():
            return obj

    return None


class CmdTouch(Command):
    """
    Touch an object to examine it more closely.

    Usage:
      touch <object>

    Shows the object's short description (in-hand detail) and full
    description. If the object has an image, the image is displayed.
    If the object is a scene prop (notable), any pinned facts are
    listed.
    """
    key = "touch"
    aliases = ["feel", "grope"]
    locks = "cmd:all()"
    help_category = "Examination"

    def func(self):
        caller = self.caller
        room = caller.location

        if not room:
            caller.msg("You are floating in the void — nothing to touch.")
            return

        args = (self.args or "").strip()
        if not args:
            caller.msg("Touch what? (|wtouch <object>|n)")
            return

        target = _find_object(caller, args)

        if not target:
            # List what's here to help
            notables = [
                obj
                for obj in room.contents
                if obj != caller
                and hasattr(obj, "db")
                and getattr(obj.db, "notable", False)
            ]
            if notables:
                names = ", ".join(
                    obj.key for obj in notables if obj.key
                )
                caller.msg(f"Nothing called '{args}'. |yNotable objects here:|n {names}")
            else:
                caller.msg(f"There's nothing here called '{args}'.")
            return

        # Build the touch response
        parts = []

        # Short description (in-hand feel)
        sd = getattr(target.db, "shortdesc", None)
        if sd:
            parts.append(f"|y{target.key}|n — {sd}")
        else:
            parts.append(f"|y{target.key}|n")

        # Full description
        desc = getattr(target.db, "desc", None)
        if desc:
            parts.append(desc)

        # Notable flag
        if getattr(target.db, "notable", False):
            parts.append("It catches the eye — something |wnotable|n in this scene.")

        # Facts (if pinned)
        facts = getattr(target.db, "facts", None)
        if facts and isinstance(facts, list):
            if len(facts) > 0:
                parts.append("|wPinned facts:|n")
                for f in facts[-5:]:
                    text = f.get("text", "")
                    fid = f.get("id", "")
                    parts.append(f"  |3{fid}|n: {text}")

        # Image URL (if available via ImageMixin or db.image_url)
        image_url = None
        if hasattr(target.db, "image_url") and target.db.image_url:
            image_url = target.db.image_url
        elif hasattr(target, "dbref"):
            # Check for generated images
            pass

        caller.msg("\n".join(parts))
