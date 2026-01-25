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

If no API keys are configured, the game still runs normally and will rely only on locally available models.

---

## Repository Structure
```
aicompany_mud/
├── commands/ # Custom in-game commands
├── server/ # Evennia server configuration (expected structure)
├── typeclasses/ # Rooms, objects, characters, exits
├── utils/ # LLM clients, room director, helpers
├── web/ # Web client overrides (if any)
├── world/ # Game content and prototypes
└── README.md
```
The `server/` directory structure follows Evennia’s expectations and should not be reorganized without updating configuration.

---

## Requirements

- Python (with a virtual environment recommended)
- Evennia (`pip install evennia`)
- A locally running OpenAI-compatible LLM server

No external API keys are required to run the game.

---

## Optional: Remote API Support

If you *do* want to enable a remote LLM fallback, set the following environment variable:

```
export OPENAI_API_KEY="your-key-here"
```

A file named server/conf/secret_settings.py may exist locally, but it is intentionally not tracked by git.
If absent, the game will continue to operate using local models only.

---

## Getting Started (Fresh Clone)

### 1) Install dependencies
```
pip install -r requirements.txt
```

### 2) local secrets file

This repo may reference `server/conf/secret_settings.py`, but that file is intentionally not committed.

If the server complains it is missing, create it locally:

`server/conf/secret_settings.py`

```
# Local overrides and secrets live here (not committed).
```

### 3) Initialize and start

```
evennia migrate
evennia start
```

MUD client: localhost:4000
Web client: [http://localhost:4001](http://localhost:4001)

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

---

