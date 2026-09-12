"""Shared task-budget and equipment-movement lifecycle coordination.

Concrete components are imported inside lifecycle hooks to keep object typeclass
construction independent of the reasoning implementation.
"""

from uuid import uuid4
from twisted.internet import reactor
from typeclasses.actors import ActorMixin


def decision_limit(task):
    value = task.db.max_actions
    return max(0, int(12 if value is None else value))


def budget_task(task):
    """Subtasks cannot mint a fresh reasoning budget for an autonomous chain."""
    from typeclasses.tasks import Task

    seen = set()
    while isinstance(task.db.parent_task, Task):
        if task.id in seen:
            raise ValueError("Cyclic task ancestry")
        seen.add(task.id)
        task = task.db.parent_task
    return task


def has_budget(task):
    budget = budget_task(task)
    return int(budget.db.action_count or 0) < decision_limit(budget)


def schedule_wake(actor):
    # Creation hooks run before Evennia has refreshed the holder's contents cache.
    # Run once on the next reactor turn, after the inventory change is complete.
    pending = actor.ndb.agency_wake_call
    if pending and pending.active():
        return

    def wake():
        actor.ndb.agency_wake_call = None
        if actor.pk is not None:
            actor.reconsider()

    actor.ndb.agency_wake_call = reactor.callLater(0, wake)


def moved(obj, source):
    """Invalidate snapshots even when an object is moved away and then back."""
    from typeclasses.components.brain import Brain
    from typeclasses.components.context import Context
    from typeclasses.components.memory import Memory
    from typeclasses.components.listener import Listener
    from typeclasses.tasks import Task
    from typeclasses.tools.base import Tool

    obj.ndb.agency_revision = uuid4().hex
    if isinstance(obj, (Brain, Tool, Task, Context, Memory, Listener)):
        for holder in (source, obj.location):
            if isinstance(holder, Task):
                holder.ndb.agency_revision = uuid4().hex
                holder = holder.location
            if isinstance(holder, ActorMixin):
                holder.ndb.agency_revision = uuid4().hex
        if isinstance(obj, Task):
            obj.db.assignee = (
                obj.location if isinstance(obj.location, ActorMixin) else None
            )
        if isinstance(obj, (Brain, Task)) and isinstance(obj.location, ActorMixin):
            if isinstance(obj, Brain) or obj.can_continue():
                schedule_wake(obj.location)
