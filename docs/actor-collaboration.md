# Bounded actor collaboration

This feature supplies task-scoped NPC conversations, not a general autonomous
executor. Actors are not classified by player/NPC controller type when deciding
whether to respond. Speech routing still requires a SmartRoom and Listener/Speaker
equipment.

## Start a conversation

From the Evennia shell, with two equipped NPC objects in the same SmartRoom:

```python
task = nova.create_task("Locate the generator key", max_turns=6,
                        max_no_progress_turns=2)
nova.ask(alice, "What do you know about the key?", task=task)
```

The opening question consumes one turn. Each generated contribution consumes one
more. The task's nested Context records each turn once; the NPCs' personal Contexts
are read as background knowledge without receiving the shared transcript. Carried
Memory objects also contribute retained knowledge. Addressed actors must remain in
the same location. Replies are suppressed when task ownership, task context,
location, or speaker equipment changes while generation is running.

Task-mode model output accepts:

```json
{"response": "The key is under the mat.", "action": "complete", "progress": true}
```

Actions are `continue`, `complete`, `decline`, and `stop`. Terminal actions do not
invite another reply and may contain no speech. `stop` marks the task `stalled`.
Missing control fields default to `continue` and no progress, so older response-only
models still hit the no-progress limit. Malformed control fields fail the response
without broadcasting it. A failed LLM call does not automatically retry or complete
the task; an operator can retry the question while budget remains.

## Current boundaries

- Completion and progress are model judgments, not independently verified results.
  The hard turn budget remains the deterministic safeguard against endless exchanges.
- `Tool` is an abstract, authorization-checked Python interface. There are no concrete
  tools or model tool-call dispatcher in this feature. Tool discovery/execution,
  scheduling, and external objectives require further harness work.
- Ordinary player `say` is unscoped. No player command currently selects a task or
  joins its transcript. An NPC can address a player, but a normal spoken answer
  does not resume that task. Controller-neutral response gating is not yet a full
  player task interface.
- Durable memory promotion is explicit via `remember_context()` or
  `get_memory().remember(...)`; no autonomous summarizer promotes memories.
  Existing NPCs created before this feature need a Memory object provisioned in
  their inventory. New NPCs receive one automatically. Memory retains at most 200
  promoted entries; Context retains at most 100 conversation entries. These are
  entry limits, not token limits.
- These are local conversations. Task transfer does not launch work automatically.
  Use `accept_task()` to transfer assignment, then explicitly start a new exchange.
- An NPC coalesces speech received while busy into one pending response. This is not
  a multi-task scheduler; simultaneous unrelated requests can supersede a queued one.

## Tests

The focused suite runs real Evennia objects in a temporary SQLite test database,
with Deferred LLM responses controlled by the tests. No live model is required.
The isolated settings omit only the unrelated optional image-generator app:

```sh
python -m pytest --ds=tests.npc_settings tests/test_npc_requirements.py tests/test_agent_collaboration_requirements.py tests/test_collaboration_integration.py
```

Install Evennia 5.0.1, pytest, pytest-django, openai, httpx and service_identity.
A live-model smoke test is still needed to assess response quality and provider
adherence to the task JSON protocol.
