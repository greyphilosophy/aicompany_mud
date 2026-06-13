# AICompany MUD

This is an experimental **Evennia-based MUD** exploring AI-assisted worldbuilding, room management, and object interaction.

The primary goal of this repository is **version control and iteration**. Collaboration is welcome but not required; the project is designed to run locally with minimal setup and without external dependencies by default.

---

## Overview

This codebase builds on the Evennia MUD framework and adds:

- **Smart rooms** that can dynamically refine their descriptions
- An in-world assistant (`computer`) that can:
  - Create, edit, and remove objects
  - Pin and manage room/object facts
  - Trigger room rewrites based on changes and conversation
- A **local-first LLM workflow**, with optional fallback to a remote API
- **AI-generated images** for rooms and objects via FLUX.2 REST
  - `regen` command regenerates images for the current room or any object
  - Images are stored on objects and displayed automatically in `look` output

If no API keys are configured, the game still runs normally and will rely only on locally available models.

---

## Repository Structure

```
aicompany_mud/
├── commands/        # Custom in-game commands
├── server/          # Evennia server configuration (expected structure)
├── typeclasses/     # Rooms, objects, characters, exits
├── utils/           # LLM clients, room director, helpers, image generation
├── web/             # Web client overrides (if any)
├── world/           # Game content and prototypes
└── README.md
```

The `server/` directory structure follows Evennia's expectations and should not be reorganized without updating configuration.

---

## Requirements

- **Python 3.12+** (with a virtual environment recommended)
- **Evennia** (`pip install evennia`)
- A locally running **OpenAI-compatible LLM server** (e.g., vLLM, LM Studio)
- *(Optional)* **FLUX.2 REST image server** (on a separate machine or container)

No external API keys are required to run the game.

---

## Optional: Remote API Support

If you *do* want to enable a remote LLM fallback, set the following environment variable:

```
export OPENAI_API_KEY="***"
```

A file named `server/conf/secret_settings.py` may exist locally, but it is intentionally not tracked by git.
If absent, the game will continue to operate using local models only.

---

## Optional: FLUX.2 Image Generation

If you want AI-generated images for rooms and objects:

1. **Set up a FLUX.2 REST server** on a separate machine or container.
2. Configure the backend in `server/conf/secret_settings.py` (copy from the `.example` file):

```python
EVENNIA_AI_IMAGE_GENERATOR_CONFIG = {
    "backend": {
        "backend": "flux2_rest",
        "options": {
            "server_url": "http://your-flux-server:8190",
            "output_dir": "generated",
            "media_url_base": "https://your-domain.com/media/generated",
        },
    },
}
```

3. In-game, use the `regen` command:
   - `regen` — regenerate image for current room
   - `regen keycard` — regenerate image for an object by name
   - `regen #42` — regenerate image for an object by dbref

Images are automatically shown when you `look` at the room or object.

---

## Getting Started (Fresh Clone)

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Set up local secrets

Copy the template to create your local config:

```bash
cp server/conf/secret_settings.py.example server/conf/secret_settings.py
```

Edit `secret_settings.py` and adjust values for your environment:
- `SECRET_KEY` — Django secret key (generate with `python -c "from django.core.secretkey import get_secret_key; print(get_secret_key())"`)
- `LOCAL_BASE_URL` / `LOCAL_MODEL` — your LLM endpoint and model
- `STARTING_POSITION_ID` — dbref of the starting room
- `EVENNIA_AI_IMAGE_GENERATOR_CONFIG` — FLUX.2 backend config (if using images)

### 3) Initialize and start

```bash
evennia migrate
evennia start
```

**MUD client:** `localhost:4000`
**Web client:** [http://localhost:4001](http://localhost:4001)

---

## Discord Gateway (Optional)

A companion **Discord gateway** connects the MUD to Discord, allowing players to join via a Discord channel:

- Repository: `muddev/evennia-discord-gateway`
- See `evennia-discord-gateway/README.md` for setup instructions

---

## Philosophy

This project favors:
- Local-first execution
- Explicit state over hidden magic
- Versioned experimentation
- Systems that fail gracefully when AI components are unavailable

It is a sandbox for ideas, not a production service.

---

Enjoy exploring.
