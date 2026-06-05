"""
Help command — display available commands and their descriptions.

Usage:
  help
  help <command_name>
  help <category>

Examples:
  help
  help smell
  help Observation

Features:
- Lists all custom commands with brief descriptions
- Filters by category or command name
- Shows usage information for a specific command
- Integrates with Evennia's help system
"""

from evennia import Command

# Command catalog: hand-curated list of custom commands and their descriptions.
# When a new command is added, add an entry here.
_COMMANDS = [
    # Observation
    {
        "key": "look",
        "category": "Observation",
        "desc": "Look around the current room or at a specific object.",
        "usage": "look\nlook [object]\nlook [character]",
    },
    {
        "key": "smell",
        "category": "Observation",
        "desc": "Detect and describe scents in the current room or on a specific item.",
        "usage": "smell\nsmell [item]",
    },
    {
        "key": "listen",
        "category": "Observation",
        "desc": "Eavesdrop on room speech and recent conversations.",
        "usage": "listen\nlisten [character]",
    },
    {
        "key": "touch",
        "category": "Observation",
        "desc": "Examine room objects by touch for texture and feel.",
        "usage": "touch [item]",
    },
    {
        "key": "search",
        "category": "Observation",
        "desc": "Find rooms, objects, and characters by name.",
        "usage": "search [term]",
    },
    {
        "key": "weather",
        "category": "Observation",
        "desc": "Check atmospheric conditions in the current room.",
        "usage": "weather",
    },
    {
        "key": "whispers",
        "category": "Observation",
        "desc": "View the room's speech memory — recent lines said in the room.",
        "usage": "whispers",
    },
    {
        "key": "peek",
        "category": "Observation",
        "desc": "Scout an adjacent room through its exit.",
        "usage": "peek [exit direction]\npeek through [door/window]",
    },
    {
        "key": "point",
        "category": "Observation",
        "desc": "Draw attention to a room object by pointing at it.",
        "usage": "point [object]\npoint at [object]",
    },
    # Movement
    {
        "key": "compass",
        "category": "Movement",
        "desc": "Quick overview of all exits from the current room.",
        "usage": "compass",
    },
    {
        "key": "nearby",
        "category": "Movement",
        "desc": "Show adjacent rooms with occupancy information.",
        "usage": "nearby",
    },
    {
        "key": "trail",
        "category": "Movement",
        "desc": "View recent room navigation breadcrumbs.",
        "usage": "trail",
    },
    {
        "key": "follow",
        "category": "Movement",
        "desc": "Follow another character through the same exits.",
        "usage": "follow [character]",
    },
    # Inventory
    {
        "key": "inventory",
        "category": "Inventory",
        "desc": "List items carried by your character.",
        "usage": "inventory\ninv\ni",
    },
    {
        "key": "take",
        "category": "Inventory",
        "desc": "Pick up an object from the current room.",
        "usage": "take [item]\nget [item]",
    },
    {
        "key": "drop",
        "category": "Inventory",
        "desc": "Set down an item in the current room.",
        "usage": "drop [item]\ndrop [item] [direction]",
    },
    {
        "key": "give",
        "category": "Inventory",
        "desc": "Hand an item to another character.",
        "usage": "give [item] to [character]",
    },
    {
        "key": "dye",
        "category": "Inventory",
        "desc": "Dye an item to change its color.",
        "usage": "dye [item] [color]",
    },
    # Social
    {
        "key": "emote",
        "category": "Social",
        "desc": "Express yourself with a social emote.",
        "usage": "emote [action]\nem [action]",
    },
    {
        "key": "gesture",
        "category": "Social",
        "desc": "Quick social gestures (wave, nod, shrug, etc.).",
        "usage": "gesture [gesture]\nwave\nnod\nshrug",
    },
    {
        "key": "whisper",
        "category": "Social",
        "desc": "Whisper a private message to another character in the room.",
        "usage": "whisper [character] [message]\nwhisper to [character] [message]",
    },
    {
        "key": "shout",
        "category": "Social",
        "desc": "Broadcast a message to everyone in the room.",
        "usage": "shout [message]\nshout to [character] [message]",
    },
    {
        "key": "rest",
        "category": "Social",
        "desc": "Rest in the room for a moment to recover.",
        "usage": "rest\nrest [duration]",
    },
    # Character
    {
        "key": "score",
        "category": "Character",
        "desc": "Display your character's stats and attributes.",
        "usage": "score",
    },
    {
        "key": "flavor",
        "category": "Character",
        "desc": "Set or view your character's flavor text (status/appearance).",
        "usage": "flavor [text]\nflavor set [text]\nflavor view",
    },
    {
        "key": "time",
        "category": "Character",
        "desc": "Check the in-game time of day.",
        "usage": "time\nhour\nminute",
    },
    {
        "key": "journal",
        "category": "Character",
        "desc": "View or write entries in your personal character adventure log.",
        "usage": "journal\njournal add [entry]\njournal view",
    },
    {
        "key": "who",
        "category": "Character",
        "desc": "List online characters in the MUD.",
        "usage": "who",
    },
    # Building
    {
        "key": "dig",
        "category": "Building",
        "desc": "Create, link, or remove room exits.",
        "usage": "dig <exitname> <RoomKey>\ndig <exitname> #<dbref>\ndig <exitname> (remove exit)",
    },
    {
        "key": "mood",
        "category": "Building",
        "desc": "Set the atmospheric mood of the current room.",
        "usage": "mood [mood]\nmood set [mood]",
    },
    {
        "key": "notes",
        "category": "Building",
        "desc": "Leave notes on room objects or walls.",
        "usage": "notes\nnotes add [text]\nnotes remove [index]",
    },
]

def _search_commands(query):
    """Search the command catalog for matching entries."""
    if not query:
        return list(_COMMANDS)
    low = query.lower()
    return [c for c in _COMMANDS if low in c["key"] or low in c.get("desc", "") or low in c.get("category", "")]

def _get_command(key):
    """Find a command by key name."""
    low = key.lower()
    for c in _COMMANDS:
        if c["key"].lower() == low:
            return c
    return None


class CmdHelp(Command):
    """
    Display available commands and their descriptions.

    Usage:
      help
      help <command_name>
      help <category>
    """

    key = "help"
    aliases = ["hlp", "?", "help"]
    locks = "cmd:all()"
    help_category = "Utility"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        if not args:
            self._list_all(caller)
            return

        # Check if it's a specific command
        cmd = _get_command(args)
        if cmd:
            self._show_command(caller, cmd)
            return

        # Check if it's a category
        matching = _search_commands(args)
        if matching:
            self._list_category(caller, args, matching)
            return

        # Fallback
        caller.msg(f"No command or category found for '{args}'.\n\n"
                    f"Type 'help' to see the full list, or 'help <command>' for details.")

    def _list_all(self, caller):
        """List all commands grouped by category."""
        categories = {}
        for cmd in sorted(_COMMANDS, key=lambda c: (c.get("category", "Other"), c["key"])):
            cat = cmd.get("category", "Other")
            categories.setdefault(cat, []).append(cmd)

        lines = ["|wAvailable commands:|n"]
        for cat in sorted(categories.keys()):
            lines.append(f"\n|y{cat}:|n")
            for cmd in categories[cat]:
                usage = cmd.get("usage", cmd["key"])
                lines.append(f"  |m{cmd['key']}|n — {cmd['desc']}")

        lines.append("\n|wType |hhelp <command>|n|w for details on a specific command.|n")
        lines.append(f"({len(_COMMANDS)} commands available)")
        caller.msg("\n".join(lines))

    def _show_command(self, caller, cmd):
        """Show detailed help for a specific command."""
        lines = [f"|wHelp: {cmd['key']}|n"]
        lines.append(f"\n{cmd['desc']}")
        lines.append(f"\nCategory: |y{cmd.get('category', 'Other')}|n")
        lines.append(f"\n|wUsage:|n")
        for line in cmd.get("usage", cmd["key"]).split("\n"):
            lines.append(f"  |m{line}|n")
        caller.msg("\n".join(lines))

    def _list_category(self, caller, category, commands):
        """List commands filtered by category."""
        lines = ["|wCommands matching '|n|y" + category + "|n|w':|n"]
        for cmd in commands:
            lines.append(f"  |m{cmd['key']}|n — {cmd['desc']}")
        if len(commands) == 1:
            lines.append("\nType 'help " + commands[0]["key"] + "' for more details.")
        caller.msg("\n".join(lines))
