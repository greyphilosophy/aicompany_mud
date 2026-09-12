"""Preserve Evennia's persisted typeclass identities when code moves modules."""


def persisted_typeclass(path):
    """Keep old database queries, inheritance queries and imports working.

    Evennia uses both ``path`` and ``__module__``/``__name__`` when selecting
    typeclasses and their families. Preserve both after its metaclass has run.
    The legacy module must continue exporting this exact class. Source code and
    new Python imports can live in a dedicated implementation module.
    """
    module, name = path.rsplit(".", 1)

    def decorate(cls):
        if cls.__name__ != name:
            raise ValueError("Persisted typeclass name must match its class")
        cls.__module__ = module
        cls.path = path
        return cls

    return decorate
