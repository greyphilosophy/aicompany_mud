"""Compatibility imports for saved typeclass paths and earlier setup scripts.

New code uses typeclasses.components.brain, typeclasses.tools.notes and
systems.agency. Keep these aliases so existing world objects can reload.
"""

from typeclasses.components.brain import Brain
from typeclasses.tools.notes import StickyNotePad
from systems.agency import budget_task, decision_limit, has_budget, moved, schedule_wake

__all__ = [
    "Brain",
    "StickyNotePad",
    "budget_task",
    "decision_limit",
    "has_budget",
    "moved",
    "schedule_wake",
]
