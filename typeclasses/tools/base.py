"""Shared authorization, action schemas and execution contract for tools."""

from typeclasses.objects import Object
from typeclasses.compat import persisted_typeclass


@persisted_typeclass("typeclasses.npcs.Tool")
class Tool(Object):
    """Base class for transferable actor tools with independent authorization."""

    def at_object_creation(self):
        super().at_object_creation()
        self.db.public = False
        self.db.desc = "A tool that grants an actor a capability when authorized."

    def can_use(self, actor):
        if actor is None:
            return False
        if bool(self.db.public):
            return True
        if self.location is actor:
            return True
        actor_id = getattr(actor, "id", None)
        location_id = getattr(self.location, "id", None)
        return actor_id is not None and actor_id == location_id

    # Speech and other handoff tools can end the current reasoning burst.
    ENDS_BURST = False
    ACTIONS = {}

    def describe_actions(self):
        import copy

        return copy.deepcopy(self.ACTIONS)

    def invoke(self, actor, action, arguments=None, **context):
        if (
            self.pk is None
            or actor is None
            or actor.pk is None
            or not self.can_use(actor)
            or not self.access(actor, "use", default=True)
        ):
            raise PermissionError("Actor is not authorized to use this tool")
        if not isinstance(action, str) or action not in self.ACTIONS:
            raise ValueError("Unknown tool action")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")
        schema = self.ACTIONS[action]["parameters"]
        parameters = schema["properties"]
        if set(arguments) - set(parameters):
            raise ValueError("Unknown tool argument")
        cleaned = dict(arguments)
        for name, spec in parameters.items():
            if name not in cleaned:
                if name in schema.get("required", []):
                    raise ValueError(f"Missing argument: {name}")
                continue
            value = cleaned[name]
            if spec["type"] == "string":
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{name} must be nonempty text")
                value = value.strip()
                if len(value) > spec.get("maxLength", 4000):
                    raise ValueError(f"{name} is too long")
                cleaned[name] = value
            elif spec["type"] == "integer":
                if type(value) is not int or not spec.get(
                    "minimum", 0
                ) <= value <= spec.get("maximum", 100):
                    raise ValueError(f"{name} must be an integer in range")
            else:
                raise ValueError("Unsupported argument schema")
        return self.perform(actor, action, cleaned, **context)

    def perform(self, actor, action, arguments, **context):
        raise NotImplementedError
