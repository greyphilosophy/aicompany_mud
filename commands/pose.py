"""
Pose command: let players change their character's posture in a room.

Usage:
  pose          — show current pose
  pose sit      — sit down
  pose stand    — stand up
  pose lie      — lie down
  pose crouch   — crouch low
  pose kneel    — kneel
  pose lean     — lean against something
  pose recline  — recline
  pose custom   — custom pose text

Pose state is stored on the character object and displayed in room look output.
"""

from evennia import Command

# Allowed preset poses with their display text
POSE_PRESETS = {
    "sit": ("is sitting.", "sit"),
    "stand": ("is standing.", "stand"),
    "lie": ("is lying down.", "lie down"),
    "crouch": ("is crouching.", "crouch"),
    "kneel": ("is kneeling.", "kneel"),
    "lean": ("is leaning.", "lean"),
    "recline": ("is reclining.", "recline"),
}


class CmdPose(Command):
    """
    Change or check your character's pose.

    Usage:
      pose          — show current pose
      pose sit      — sit down
      pose stand    — stand up
      pose lie      — lie down
      pose crouch   — crouch low
      pose kneel    — kneel
      pose lean     — lean against something
      pose recline  — recline
      pose <text>   — custom pose

    Examples:
      pose sit
      pose recline
      pose leaning against the wall, watching the door

    Your pose is visible to others when they look around the room.
    """
    key = "pose"
    aliases = ["posture"]
    locks = "cmd:all()"
    help_category = "Social"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip().lower()

        # No args: show current pose
        if not args:
            current = caller.db.pose_text or "is standing."
            caller.msg(f"|wYou: |n{current}")
            return

        # Check if it's a preset
        if args in POSE_PRESETS:
            display_text, short_action = POSE_PRESETS[args]
            caller.db.pose_text = display_text

            # Announce to room
            room = caller.location
            if room:
                room.msg_contents(
                    f"|y{caller.key} |n{short_action}{display_text}"
                )
            else:
                caller.msg(f"You {display_text}")

        else:
            # Custom pose text
            text = args.title()
            # Make it grammatically sensible
            if text.endswith("."):
                pose_text = text
            else:
                pose_text = text + "."

            caller.db.pose_text = pose_text
            caller.msg(f"You are now: {pose_text}")

            # Announce to room
            room = caller.location
            if room:
                room.msg_contents(
                    f"|y{caller.key} |nis now {text.lower()}|n"
                )
