# commands/dig.py
from evennia import Command
from evennia.utils import create
from evennia.utils.search import search_object

from typeclasses.exits import SmartExit, DIRECTIONS
from typeclasses.rooms import SmartRoom

CARDINALS = set(DIRECTIONS.keys())

def _last_word(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "back"
    return s.split()[-1]

def _find_exit(room, name: str):
    """Find exit by key or alias, case-insensitive."""
    low = name.lower()
    for ex in room.exits:
        if (ex.key or "").lower() == low:
            return ex
        if low in [a.lower() for a in ex.aliases.all()]:
            return ex
    return None

def _has_exit_to(room, keyname: str, destination):
    low = keyname.lower()
    for ex in room.exits:
        if (ex.key or "").lower() == low and ex.destination == destination:
            return ex
    return None

def _compute_back_name(exitname: str, current_room_key: str) -> str:
    low = exitname.lower()
    if low in DIRECTIONS:
        return DIRECTIONS[low]
    return _last_word(current_room_key)

def _resolve_target(caller, arg: str):
    """
    Return (target_room, created_new: bool, error: str|None)
    """
    arg = (arg or "").strip()
    if not arg:
        return None, False, "Missing target."

    # dbref link
    if arg.startswith("#") and arg[1:].isdigit():
        matches = search_object(arg)
        if not matches:
            return None, False, f"No object found for {arg}."
        target = matches[0]
        # verify it's a room (best-effort: has .contents and no .location)
        if getattr(target, "location", None) is not None:
            return None, False, f"{arg} is not a room (it has a location)."
        return target, False, None

    # new room by key (single token or multi-word is fine; your UX uses single word)
    new_room = create.create_object(SmartRoom, key=arg)
    return new_room, True, None


class CmdDigSmart(Command):
    """
    Create, link, or remove exits.

    Usage:
      dig <exitname> <RoomKey>
      dig <exitname> #<dbref>
      dig <exitname>           (remove existing exit + matching back link)

    Examples:
      dig north Kitchen
      dig Library #123
      dig Library
    """
    key = "dig"
    locks = "cmd:all()"   # tighten later if you want Builder-only
    help_category = "Building"

    def func(self):
        caller = self.caller
        room = caller.location
        if not room:
            caller.msg("You are nowhere.")
            return

        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: dig <exitname> <RoomKey|#dbref>  OR  dig <exitname>")
            return

        parts = args.split()
        exitname = parts[0]
        target_arg = " ".join(parts[1:]).strip()  # allows multiword keys if you ever want them

        existing = _find_exit(room, exitname)

        # --- Remove mode: dig <exitname> ---
        if not target_arg:
            if not existing:
                caller.msg(f"No exit named '{exitname}' here.")
                return

            dest = existing.destination
            back_name = _compute_back_name(existing.key, room.key)

            # delete forward exit
            existing.delete()

            # delete back link if it points back to this room
            removed_back = False
            if dest:
                back_ex = _find_exit(dest, back_name)
                if back_ex and back_ex.destination == room:
                    back_ex.delete()
                    removed_back = True

            if removed_back:
                caller.msg(f"Removed exit '{exitname}' and return link '{back_name}'.")
            else:
                caller.msg(f"Removed exit '{exitname}'.")
            return

        # --- Create/link mode: dig <exitname> <target> ---
        target, created_new, err = _resolve_target(caller, target_arg)
        if err:
            caller.msg(err)
            return

        # if exit exists, update it; else create it
        if existing:
            existing.destination = target
            ex = existing
        else:
            ex = create.create_object(SmartExit, key=exitname, location=room, destination=target)

        # auto-create back exit if not already present
        back_name = _compute_back_name(exitname, room.key)
        if not _has_exit_to(target, back_name, room):
            create.create_object(SmartExit, key=back_name, location=target, destination=room)

        # message
        if created_new:
            caller.msg(f"Created room '{target.key}' and linked '{exitname}' (back: '{back_name}').")
        else:
            caller.msg(f"Linked '{exitname}' to {target.key} (back: '{back_name}').")
