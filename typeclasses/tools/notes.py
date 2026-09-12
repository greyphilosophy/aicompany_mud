"""Tool for creating real task-note objectives."""

from typeclasses.tools.base import Tool
from typeclasses.tasks import Task
from typeclasses.compat import persisted_typeclass


@persisted_typeclass("typeclasses.agency.StickyNotePad")
class StickyNotePad(Tool):
    """Write a real objective into the user's inventory."""

    ACTIONS = {
        "create_task": {
            "description": "Create an active task note carried by you; it becomes your objective.",
            "parameters": {
                "type": "object",
                "required": ["objective"],
                "additionalProperties": False,
                "properties": {
                    "objective": {"type": "string", "minLength": 1, "maxLength": 2000},
                    "max_turns": {"type": "integer", "minimum": 1, "maximum": 50},
                    "priority": {"type": "integer", "minimum": 0, "maximum": 10},
                },
            },
        }
    }

    def perform(self, actor, action, arguments, **context):
        from evennia.utils.create import create_object

        task = create_object(
            Task, key=f"Task: {arguments['objective'][:48]}", location=actor
        )
        task.db.priority = arguments.get("priority", 0)
        task.db.parent_task = context.get("task")
        task.configure(
            arguments["objective"],
            requester=actor,
            assignee=actor,
            max_turns=arguments.get("max_turns", Task.DEFAULT_MAX_TURNS),
        )
        return {
            "task": task.dbref,
            "objective": task.db.objective,
            "status": task.db.status,
        }
