"""Catalog and construction of explicitly implemented tool types.

This trusted Python setup API is not advertised as a player or Brain action.
Definitions are code-owned; callers select an ID, not an import path or program.
"""

from dataclasses import dataclass
from types import MappingProxyType

from evennia.objects.models import ObjectDB
from evennia.utils.create import create_object

from typeclasses.tools.base import Tool
from typeclasses.tools.notes import StickyNotePad
from typeclasses.tools.speaker import Speaker


@dataclass(frozen=True)
class ToolDefinition:
    """A stable catalog ID, default display name and implemented typeclass."""

    id: str
    name: str
    typeclass: type[Tool]


BUILTIN_TOOLS = MappingProxyType(
    {
        definition.id: definition
        for definition in (
            ToolDefinition("speaker", "Speaker", Speaker),
            ToolDefinition("sticky_note_pad", "Sticky note pad", StickyNotePad),
        )
    }
)


def list_tool_types():
    """Return plain catalog metadata; editing the result cannot change tools."""
    from copy import deepcopy

    return [
        {
            "id": definition.id,
            "name": definition.name,
            "actions": deepcopy(definition.typeclass.ACTIONS),
        }
        for definition in BUILTIN_TOOLS.values()
    ]


def create_tool(type_id, *, location, key=None):
    """Create a registered tool in a live location using normal Evennia hooks.

    Raises ValueError for invalid construction inputs before creating anything.
    The caller is trusted setup code; invocation still uses Tool.invoke checks.
    """
    if not isinstance(type_id, str) or type_id not in BUILTIN_TOOLS:
        raise ValueError("Unknown tool type ID")
    if not isinstance(location, ObjectDB) or location.pk is None:
        raise ValueError("Tool location must be a live world object")
    if key is not None and (not isinstance(key, str) or not key.strip()):
        raise ValueError("Tool name must be nonempty text")
    definition = BUILTIN_TOOLS[type_id]
    return create_object(
        definition.typeclass,
        key=key.strip() if key is not None else definition.name,
        location=location,
    )
