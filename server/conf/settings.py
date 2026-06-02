r"""
Evennia settings file.

The available options are found in the default settings file found
here:

https://www.evennia.com/docs/latest/Setup/Settings-Default.html

Remember:

Don't copy more from the default file than you actually intend to
change; this will make sure that you don't overload upstream updates
unnecessarily.

When changing a setting requiring a file system path (like
path/to/actual/file.py), use GAME_DIR and EVENNIA_DIR to reference
your game folder and the Evennia library folders respectively. Python
paths (path.to.module) should be given relative to the game's root
folder (typeclasses.foo) whereas paths within the Evennia library
needs to be given explicitly (evennia.foo).

If you want to share your game dir, including its settings, you can
put secret game- or server-specific settings in secret_settings.py.

"""

# Use the defaults from Evennia unless explicitly overridden
import os
from evennia.settings_default import *

######################################################################
# Evennia base server config
######################################################################

# This is the name of your game. Make it catchy!
SERVERNAME = "aicompany_mud"
ALLOWED_HOSTS = ["pr1357.ddns.net"]
BASE_EXIT_TYPECLASS = "typeclasses.exits.Exit"

# Image directory for generated assets
IMAGES_DIR = os.path.join(GAME_DIR, "images")

# evennia-ai-image-generator: FLUX.2 REST backend configuration
# Set the FLUX2_REST_URL env var to point to your FLUX.2 REST server.
EVENNIA_AI_IMAGE_GENERATOR_CONFIG = {
    "backend": {
        "backend": "flux2_rest",
        "options": {
            "server_url": os.getenv("FLUX2_REST_URL", "http://127.0.0.1:8190"),
            "output_dir": "generated",
            "media_url_base": os.getenv(
                "MEDIA_URL_BASE",
                "https://game.test/media/generated",
            ),
            "timeout_s": 120.0,
        },
    },
}

# Serve generated images via Evennia's Django static handler
STATICFILES_DIRS = [IMAGES_DIR]

######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")
