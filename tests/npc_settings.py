"""Isolated NPC tests; the unrelated optional image backend is not required."""

from server.conf.settings import *  # noqa: F403

INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "evennia_ai_image_generator"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
