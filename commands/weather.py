# commands/weather.py
"""
Weather Command

Allows players to set and view weather conditions for their current room.
Weather adds atmosphere and can be used as a storytelling tool or environmental clue.

Weather states include: clear, overcast, rainy, snowy, foggy, windy, stormy, twilight
Players can also set custom weather with descriptions.
"""
from evennia import Command


WEATHER_STATES = {
    "clear": ("☀", "The sky is a brilliant blue, and the air is crisp.", True),
    "overcast": ("☁", "Grey clouds blanket the sky, casting a soft, diffused light.", True),
    "rainy": ("🌧", "A steady drizzle patters against the surroundings.", True),
    "snowy": ("❄", "Snowflakes drift down, dusting everything in white.", True),
    "foggy": ("🌫", "Thick fog rolls in, obscuring distant details.", True),
    "windy": ("💨", "The wind howls, carrying the scent of change.", True),
    "stormy": ("⛈", "Thunder rumbles in the distance as dark clouds gather.", True),
    "twilight": ("🌅", "The golden light of dusk filters through everything.", True),
    "moonlit": ("🌙", "Silver moonlight spills over the surroundings.", True),
    "still": ("~", "An eerie stillness settles over everything.", True),
    "crisp": ("✨", "The air is sharp and invigorating.", True),
}

WEATHER_LIST = " | ".join(sorted(WEATHER_STATES.keys()))


class CmdWeather(Command):
    """
    Set and view the weather for your current room.

    Usage:
      weather [condition]   — set the weather (e.g., weather rainy)
      weather                — view current weather
      weather list          — list available weather states
      weather custom <desc> — set a custom weather description
      weather clear         — clear the weather

    Weather is stored per-room and affects the atmosphere for everyone in that room.

    Examples:
      weather rainy
      weather
      weather list
      weather custom The air shimmers with an otherworldly hum
      weather clear
    """
    key = "weather"
    aliases = ["climate"]
    locks = "cmd:all()"
    help_category = "World"

    def _get_weather(self):
        """Get the weather data for the caller's current room."""
        room = self.caller.location
        if not room:
            return None
        return getattr(room.db, "weather", None)

    def _set_weather(self, condition, custom_desc=None):
        """Set the weather for the caller's current room."""
        room = self.caller.location
        if not room:
            return False

        if condition in WEATHER_STATES:
            room.db.weather = {
                "state": condition,
                "custom": False,
                "desc": WEATHER_STATES[condition][1],
            }
            self.caller.msg(f"Room weather set: {condition}.")
            return True
        elif condition and custom_desc:
            room.db.weather = {
                "state": custom_desc,
                "custom": True,
                "desc": custom_desc,
            }
            self.caller.msg(f"Room weather set: '{custom_desc}'.")
            return True
        return False

    def _clear_weather(self):
        """Clear the weather for the caller's current room."""
        room = self.caller.location
        if room:
            room.db.weather = None
            self.caller.msg("Room weather cleared.")
            return True
        return False

    def func(self):
        args = (self.args or "").strip()

        if not args:
            # No args: show current weather
            room = self.caller.location
            if not room:
                self.caller.msg("You are nowhere — hard to check the weather in the void.")
                return
            weather = self._get_weather()
            if weather:
                state = weather.get("state", "unknown")
                desc = weather.get("desc", "")
                emoji = WEATHER_STATES.get(state, ("", ""))[0]
                self.caller.msg(f"|wCurrent weather:|n {state} {emoji}\n{desc}")
            else:
                self.caller.msg("The room's weather is unset. Set it with |wweather <condition>|n.")
            return

        if args.lower() == "list":
            lines = ["|wAvailable weather states:|n"]
            for name in sorted(WEATHER_STATES.keys()):
                emoji = WEATHER_STATES[name][0]
                lines.append(f"  {name:12} {emoji}")
            lines.append(f"\n|nSet: |wweather <state>|n  or  |wweather custom <description>|n")
            self.caller.msg("\n".join(lines))
            return

        if args.lower() == "clear":
            self._clear_weather()
            return

        if args.lower().startswith("custom"):
            # Custom weather: "weather custom <description>"
            rest = args[len("custom"):].strip()
            if rest:
                self._set_weather(None, custom_desc=rest)
            else:
                self.caller.msg("|wUsage: weather custom <description>|n")
            return

        # Direct weather state
        self._set_weather(args.lower())
