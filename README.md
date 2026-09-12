# AICompany MUD

This is an experimental **Evennia-based MUD** exploring AI-assisted worldbuilding, room management, and object interaction.

The primary goal of this repository is **version control and iteration**. Collaboration is welcome but not required; the project is designed to run locally with its Python dependencies and configured local model services.

---

## Overview

This codebase builds on the Evennia MUD framework and adds:

- **Composable actors** whose hearing, reasoning, speech and knowledge come from transferable inventory objects
- **Executable tools** with shared validation, a built-in catalog and a Python construction factory
- **Task notes** that transfer objectives between holders, with bounded reasoning and conversation
- **Smart rooms** that can dynamically refine their descriptions
- An in-world assistant (`computer`) that can:
  - Create, edit, and remove objects
  - Pin and manage room/object facts
  - Trigger room rewrites based on changes and conversation
- A **local-first LLM workflow**, with optional fallback to a remote API
- **AI-generated images** for rooms and objects via FLUX.2 REST
  - `regen` command regenerates images for the current room or any object (builder lock)
  - Images are stored on objects and displayed automatically in `look` output

If no API keys are configured, the game still runs normally and will rely only on locally available models.

---

## Repository Structure

| Directory | Contents |
| --- | --- |
| `commands/` | Custom player commands and command sets |
| `docs/` | Requirements, setup and architecture guides |
| `systems/` | Shared agency lifecycle and budget coordination |
| `tests/` | Acceptance and regression tests |
| `server/` | Evennia configuration and server integration |
| `typeclasses/` | Bodies, portable components, tasks and executable tools |
| `utils/` | LLM clients, room helpers and image generation |
| `web/` | Web client overrides |
| `world/` | Content definitions and prototypes |

Start with [Component architecture](docs/component-architecture.md) for the module map,
tool catalog/factory and adding a tool. [Composable agency](docs/composable-agency.md)
covers equipping actors and model execution; [Inventory transfers](docs/inventory-transfers.md)
covers giving and retrieving equipment. [Actor collaboration](docs/actor-collaboration.md)
documents the legacy task-scoped speech API.

The `server/` directory structure follows Evennia's expectations and should not be reorganized without updating configuration.

---

## Requirements

- **Python 3.12+** (with a virtual environment recommended)
- **Evennia 5.0.1** (installed by `requirements.txt`)
- A locally running **OpenAI-compatible LLM server** (e.g., vLLM, LM Studio)
- *(Optional)* **FLUX.2 REST image server** (on a separate machine or container)

No external API keys are required to run the game.

---

## Optional: Remote API Support

If you *do* want to enable a remote LLM fallback, set the following environment variable:

```bash
export OPENAI_API_KEY="your-key-here"
```

A file named `server/conf/secret_settings.py` may exist locally, but it is intentionally not tracked by git.

---

## Optional: FLUX.2 Image Generation

If you want AI-generated images for rooms and objects:

1. **Set up a FLUX.2 REST server** on a separate machine or container.
2. Configure the backend by setting the `FLUX2_SERVER_URL` environment variable:

```bash
export FLUX2_SERVER_URL="http://your-flux-server:8190"
```

The default server URL is `http://169.254.209.73:8190` (link-local on the DGX Spark GPU node).

3. In-game, use the `regen` command (requires **builder** lock):
   - `regen` — regenerate image for current room
   - `regen keycard` — regenerate image for an object by name (current room only)

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
- `SECRET_KEY` — Django secret key (generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- `LOCAL_BASE_URL` / `LOCAL_MODEL` — your LLM endpoint and model
- `STARTING_POSITION_ID` — dbref of the starting room

For image generation, set the `FLUX2_SERVER_URL` environment variable (see above).

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

## Tests

The component, tool, agency and inventory acceptance suite uses real Evennia objects
with controlled model responses:

```sh
python -m pytest --ds=tests.npc_settings tests/test_component_architecture.py tests/test_inventory_transfers.py tests/test_portable_capabilities.py tests/test_agency_requirements.py tests/test_npc_requirements.py tests/test_agent_collaboration_requirements.py tests/test_collaboration_integration.py
```

These settings omit the optional image-generator app. This suite does not validate
live model quality, image services or the Discord gateway.

## Philosophy

This project favors:
- Local-first execution
- Explicit state over hidden magic
- Versioned experimentation
- Systems that fail gracefully when AI components are unavailable

It is a sandbox for ideas, not a production service.

---

Enjoy exploring.
