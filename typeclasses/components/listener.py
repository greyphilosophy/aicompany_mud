"""Speech perception for any equipped holder."""

from typeclasses.objects import Object
from typeclasses.compat import persisted_typeclass


@persisted_typeclass("typeclasses.npcs.Listener")
class Listener(Object):
    """Equipment that lets the carrying holder hear speech into working context."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.desc = (
            "A listener harness that records nearby speech into working context."
        )

    def record(self, npc, speaker, message, task=None):
        if task is not None and hasattr(task, "get_context"):
            # Task speech is written once by its speaker into the shared task context.
            # Listeners consume that context without duplicating the line per listener.
            return task.get_context()
        context = npc.get_context()
        if context:
            context.append(getattr(speaker, "key", "unknown"), message, role="user")
        return context
