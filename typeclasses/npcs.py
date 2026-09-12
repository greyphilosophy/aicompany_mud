"""NPC starter body and compatibility imports for existing equipment paths.

The aliases below preserve old Python imports and stored Evennia typeclass paths.
New code should import equipment from its dedicated component or tool module.
"""

from evennia.utils import create
from typeclasses.objects import Object
from typeclasses.components.context import Context
from typeclasses.components.memory import Memory
from typeclasses.components.listener import Listener
from typeclasses.tasks import Task
from typeclasses.tools.base import Tool
from typeclasses.tools.speaker import Speaker

__all__ = ["NPC", "Context", "Memory", "Listener", "Task", "Tool", "Speaker"]


class NPC(Object):
    """An inert, carryable actor whose abilities come from inventory equipment."""

    def at_object_creation(self):
        super().at_object_creation()
        self.locks.add("get:all();puppet:false()")
        self.db.desc = (
            self.db.desc or "A quiet figure waiting for a voice, memories, and work."
        )
        if not self.get_context():
            create.create_object(Context, key=f"{self.key}'s context", location=self)
        if not self.get_memory():
            create.create_object(Memory, key=f"{self.key}'s memory", location=self)
