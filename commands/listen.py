# commands/listen.py
"""
Listen command — auditory awareness for rooms, objects, and characters.

Usage:
  listen          (listen to the current room's ambient sounds)
  listen <target> (listen to a specific object, exit, or character)
"""

from evennia import Command


# Ambient sound descriptions for room types
_AMBIENT_SOUNDS = {
    "town square": [
        "The clatter of carts and the murmur of merchants fill the air.",
        "Hooves on cobblestone echo as a messenger rides through.",
        "A street performer's lute drifts on the breeze.",
        "Children laugh from the well at the center of the square.",
    ],
    "tavern": [
        "Mugs clink and raucous laughter bounces off the wooden walls.",
        "The fire crackles in the hearth, sending pops of heat.",
        "A bard strums quietly in the corner, half-heard by all.",
        "The low hum of conversation fills every empty space.",
    ],
    "library": [
        "Pages turn in the hush — quiet, rhythmic, like breathing.",
        "Dust motes seem to settle to the scratch of a quill on parchment.",
        "A distant bell chimes through the arched windows.",
        "The faint creak of floorboards under a scholar's footstep.",
    ],
    "forest": [
        "Leaves rustle overhead in a gentle, restless whisper.",
        "A bird calls from the canopy — melodic and lone.",
        "The creek nearby murmurs over smooth stones.",
        "Branches snap somewhere deeper in the trees.",
    ],
    "market": [
        "Every vendor shouts their wares in a chorus of voices.",
        "The metallic ring of a cobbler's hammer keeps time.",
        "A cart wheel squeaks in a frustrating rhythm.",
        "Coins clink as a deal is struck at the furrier's stall.",
    ],
    "dungeon": [
        "Dripping water echoes in the stone corridor — steady, lonely.",
        "A rat skitters across the flagstones, claws clicking.",
        "The torch sputters, filling the air with a low hissing.",
        "Somewhere below, a chain rattle fades into darkness.",
    ],
    "garden": [
        "Bees drone lazily among the blooming roses.",
        "A fountain splashes softly to the east.",
        "Wind moves through the hedges, brushing leaf against leaf.",
        "A nightingale sings from the oldest apple tree.",
    ],
    "temple": [
        "Chimes resonate from the silver bells suspended above.",
        "Soft chanting rises and falls like the tide.",
        "Incense smoke whispers through the candlelit naves.",
        "The great wooden doors groan as they swing shut.",
    ],
    "workshop": [
        "The anvil rings out — steady, measured, skilled hands.",
        "Sandpaper rasps against fresh wood.",
        "A water wheel creaks through the back window.",
        "Hammers tap at metal in a quiet duet.",
    ],
    "default": [
        "You hear the general hum of presence around you.",
        "The air carries a faint, familiar rhythm to the room.",
        "Nothing particular catches your ear — just the room's steady breath.",
        "Sounds of the surroundings blend into a quiet backdrop.",
    ],
}


def _get_ambient(room):
    """Pick an ambient sound for a room based on its name."""
    key = (room.key or "").lower()
    for pattern, sounds in _AMBIENT_SOUNDS.items():
        if pattern != "default" and pattern in key:
            import random
            return random.choice(sounds)
    import random
    return random.choice(_AMBIENT_SOUNDS["default"])


def _get_object_sounds(obj):
    """Generate plausible sounds for an object or character."""
    import random
    category = obj.key.lower() if obj.key else ""
    sounds = {
        "fire": [
            "The flames crackle and pop softly.",
            "A warm, steady hiss comes from the burning logs.",
            "Smoke curls upward with a faint sizzle.",
        ],
        "door": [
            "The hinges give a faint, dry creak.",
            "Wood settles with a low groan.",
            "The latch clicks as the door breathes with the room.",
        ],
        "window": [
            "The glass rattles gently in its frame.",
            "A breeze whistles through the pane.",
            "The curtain flutters and brushes the sill.",
        ],
        "fountain": [
            "Water cascades in a steady, soothing rhythm.",
            "The basin drips, each drop ringing clear.",
            "A gentle cascade pours over carved stone.",
        ],
        "bell": [
            "A soft, silver tone lingers in the air.",
            "The metal vibrates with a faint resonance.",
            "A distant chime echoes from within.",
        ],
        "book": [
            "The pages whisper as the wind turns them.",
            "The cover creaks open with practiced ease.",
            "A faint rustle — as if words are being read silently.",
        ],
    }
    for keyword, opts in sounds.items():
        if keyword in category:
            return random.choice(opts)

    # Fallback for any object or character
    generic = [
        f"You hear nothing distinctive from the {obj.key}.",
        f"The {obj.key} is quiet, absorbing the room's ambient noise.",
        f"A faint sound emanates from the {obj.key} — subtle and steady.",
    ]
    return random.choice(generic)


class CmdListen(Command):
    """
    Listen to your surroundings for auditory clues.

    Usage:
      listen
      listen <target>

    When used without a target, you hear the ambient sounds of your
    current room. When targeting a specific object or character,
    you focus your attention to discern what it sounds like.

    Examples:
      listen
      listen door
      listen fire
      listen the old bell
    """
    key = "listen"
    aliases = ["lurk"]
    locks = "cmd:all()"
    help_category = "Sensory"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            # No target — listen to the room
            room = caller.location
            if not room:
                caller.msg("You are nowhere — silence is absolute.")
                return

            sound = _get_ambient(room)
            caller.msg(f"{caller.name} listens carefully...\n\n{sound}")
            # Share with nearby observers (subtle social cue)
            for occupant in room.contents:
                if occupant != caller and occupant != room:
                    occupant.msg(f"{caller.name} cups an ear, listening to the room.")
            return

        # Target specified — try to find it in the room
        target = caller.search(args, attribute_name="key", global_name=False)
        if not target:
            caller.msg(f"There is nothing to listen to called '{args}'.")
            return

        if not caller.location or target.location != caller.location:
            # Allow listening to exits (they live in the room)
            if not hasattr(target, 'destination'):
                caller.msg(f"The {args} isn't close enough to hear clearly.")
                return

        sound = _get_object_sounds(target)
        caller.msg(f"You focus your attention on the {target.key}...\n\n{sound}")
