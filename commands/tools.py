"""A direct player interface to the same tool contract used by Brains."""

import json
from commands.command import Command
from typeclasses.npcs import Tool


class CmdUseTool(Command):
    """Inspect or invoke a carried tool.

    Usage:
      tool <name or #id>
      tool <name or #id>/<action> = <JSON arguments>

    Example:
      tool Notes/create_task = {"objective": "Find the generator key"}

    With no action, lists the tool's actions and accepted inputs. Only carried
    tools are available. Tool actions enforce the same permissions and schemas
    whether invoked here or by a Brain.
    """

    key = "tool"
    locks = "cmd:all()"
    help_category = "Tools"

    def func(self):
        selection, equals, payload = self.args.partition("=")
        name, slash, action = selection.partition("/")
        if not name.strip():
            self.caller.msg("Usage: tool <name>[/<action> = <JSON arguments>]")
            return
        tool = self.caller.search(
            name.strip(),
            candidates=[obj for obj in self.caller.contents if isinstance(obj, Tool)],
        )
        if tool is None:
            return
        try:
            if not slash:
                self.caller.msg(json.dumps(tool.describe_actions(), indent=2))
                return
            arguments = json.loads(payload) if equals else {}
            result = tool.invoke(self.caller, action.strip(), arguments)
            self.caller.msg(json.dumps({"ok": True, "result": result}))
        except (ValueError, PermissionError) as exc:
            self.caller.msg(json.dumps({"ok": False, "error": str(exc)}))
