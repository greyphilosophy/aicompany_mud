"""Transferable objectives, working context and conversation budgets."""

from uuid import uuid4
from evennia.utils import create
from typeclasses.objects import Object
from typeclasses.components.context import Context
from typeclasses.compat import persisted_typeclass


@persisted_typeclass("typeclasses.npcs.Task")
class Task(Object):
    """A transferable objective with its own bounded working context and budget."""

    DEFAULT_MAX_TURNS = 8
    DEFAULT_MAX_NO_PROGRESS_TURNS = 3

    def at_object_creation(self):
        super().at_object_creation()
        self.db.objective = ""
        self.db.status = "pending"
        self.db.requester = None
        self.db.assignee = None
        self.db.parent_task = None
        self.db.result = None
        self.db.turn_count = 0
        self.db.max_turns = self.DEFAULT_MAX_TURNS
        self.db.no_progress_turns = 0
        self.db.max_no_progress_turns = self.DEFAULT_MAX_NO_PROGRESS_TURNS
        self.db.progress_notes = []
        self.db.priority = 0
        self.db.action_count = 0
        self.db.max_actions = 12
        self.db.desc = "A transferable objective with bounded working context."
        if not self.get_context():
            create.create_object(
                Context, key=f"{self.key} working context", location=self
            )

    def get_context(self):
        return next((obj for obj in self.contents if isinstance(obj, Context)), None)

    def configure(
        self,
        objective,
        requester=None,
        assignee=None,
        max_turns=None,
        max_no_progress_turns=None,
    ):
        self.db.objective = str(objective or "").strip()
        self.db.requester = requester
        self.db.assignee = assignee
        if max_turns is not None:
            self.db.max_turns = max(1, int(max_turns))
        if max_no_progress_turns is not None:
            self.db.max_no_progress_turns = max(1, int(max_no_progress_turns))
        self.db.status = "active"
        self.ndb.agency_revision = uuid4().hex
        if hasattr(self.location, "reconsider"):
            self.location.reconsider()
        return self

    def can_continue(self):
        if self.db.status != "active":
            return False
        if int(self.db.turn_count or 0) >= int(
            self.db.max_turns or Task.DEFAULT_MAX_TURNS
        ):
            return False
        if int(self.db.no_progress_turns or 0) >= int(
            self.db.max_no_progress_turns or Task.DEFAULT_MAX_NO_PROGRESS_TURNS
        ):
            return False
        return True

    def record_turn(self, actor=None, message=None, progress=None):
        if not self.can_continue():
            return False
        self.db.turn_count = int(self.db.turn_count or 0) + 1
        if progress is True:
            self.db.no_progress_turns = 0
        elif progress is False:
            self.db.no_progress_turns = int(self.db.no_progress_turns or 0) + 1

        if int(self.db.turn_count or 0) >= int(
            self.db.max_turns or Task.DEFAULT_MAX_TURNS
        ):
            self.db.status = "budget_exhausted"
        elif int(self.db.no_progress_turns or 0) >= int(
            self.db.max_no_progress_turns or Task.DEFAULT_MAX_NO_PROGRESS_TURNS
        ):
            self.db.status = "stalled"
        return True

    def mark_progress(self, note=None):
        self.db.no_progress_turns = 0
        if note:
            notes = list(self.db.progress_notes or [])
            notes.append(str(note))
            self.db.progress_notes = notes[-50:]
        return True

    def complete(self, result=None):
        self.db.status = "completed"
        self.db.result = result

    def decline(self, reason=None):
        self.db.status = "declined"
        self.db.result = reason
