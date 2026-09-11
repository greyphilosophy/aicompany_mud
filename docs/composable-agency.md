# Composable agency requirements

Scope: a portable Brain, an executable tool contract, Speaker as a tool, and a
StickyNotePad that creates real Task objects. Tool fabrication, wiki/memory tools,
and independent completion validation are separate features.

## Acceptance requirements

1. An NPC without a Brain observes through its Listener but makes no new decisions.
   A Brain can decide to wait instead of answering speech. Speaker supplies speech,
   not the default reasoning loop.
2. Active tasks carried directly by an actor are its objectives. Transfer/drop
   changes responsibility and invalidates decisions pending for the former holder.
   Multiple objectives have a deterministic order: highest priority, then oldest.
3. A Brain snapshots observations, personal Context/Memory, tasks, local actors,
   and carried executable tools on the reactor thread. The model worker receives
   only plain data; no live Evennia objects enter the worker.
4. Tools publish actions and input schemas. Both players and Brains use the same
   authorized, validated invocation interface. Unknown actions/tools/arguments and
   malformed values produce observable errors without side effects.
5. A decision can wait, invoke one advertised action, or report a held task complete.
   Completing a task is a claim, not independent validation. No arbitrary Python,
   shell execution, dynamic imports, or invented tool capabilities are model actions.
6. Each actor has at most one decision in flight. Each wake permits a bounded burst;
   task decision budgets persist across wakes and transfers. Failed or repeated
   identical actions stop the burst. Waiting never schedules polling.
7. Equipment/task/actor movement invalidates pending work, including away-and-back
   transfers. Removing the Brain prevents execution. Ownership, access, schema and
   budget are checked again before the selected action runs.
8. Tool results are recorded and supplied to the next decision. Successful tool
   actions may continue within the same budget; speech ends the local burst and
   waits for a new observation. Unscoped generated speech cannot cause reply loops.
9. The sticky-note pad creates a real active Task in its user's inventory with a
   nonempty objective, bounded defaults, and requester provenance. Creation makes
   it a want, but does not bypass the Brain's existing budget or force action.
10. Task acquisition, Brain attachment and eligible speech can wake the Brain.
    Restart does not silently resume work; explicit reconsideration is supported.

The old Speaker-only reply mechanism is retained only behind explicit
`npc.db.legacy_autoreply = True` for migration. It is off by default and never runs
alongside an equipped Brain.

## Setup and use

Equip an NPC in a SmartRoom from the Evennia shell (the model connection uses the
existing local-provider configuration and optional OpenAI fallback):

```python
from evennia.utils.create import create_object
from typeclasses.agency import Brain, StickyNotePad
from typeclasses.npcs import Listener, Speaker

# nova is an existing NPC object. Add only equipment it does not already carry.
create_object(Listener, key="Ears", location=nova)
create_object(Speaker, key="Voice", location=nova)
create_object(StickyNotePad, key="Notes", location=nova)
create_object(Brain, key="Brain", location=nova)
nova.create_task("Ask Alice where the generator key is")
```

Brain/task acquisition wakes on the next reactor turn so Evennia has time to
refresh inventory. New task configuration wakes its holder after the note has
been created and configured. A Listener is needed for speech observations; a
Brain can work on carried tasks without a Listener or Speaker.

Players can inspect and invoke carried tools without using a model:

```text
tool Notes
tool Notes/create_task = {"objective": "Find the generator key", "priority": 3}
```

The pad gives the task to its user. Transfer the task using normal world movement
or the shell `task.move_to(nova)`; the new holder acquires that want. A player can
carry and create task notes but is not automatically controlled by a Brain.

A Brain's model output uses a stable object identifier from its snapshot:

```json
{"action":"invoke","tool":"#123","name":"create_task","arguments":{"objective":"Find the key"}}
```

Tool action descriptions publish object-shaped schemas with string/integer
properties, required fields, bounds and no additional arguments. The current
validator intentionally supports only this small subset. New capabilities must
be implemented as Tool subclasses; the model cannot define or execute code.
Tools are currently synchronous. The model decision itself runs in a worker.

## Execution and migration boundaries

- Each wake allows at most four model decisions, including waits/failures. Active
  tasks share a persistent twelve-decision budget across holders and helpers
  (`task.db.action_count`, `task.db.max_actions`). Notes made while pursuing a task
  inherit its root task budget through `parent_task`, including after transfer;
  creating subtasks cannot renew that budget. Speech also consumes the existing
  turn budget. The Brain skips held tasks whose decision budget is exhausted.
- Speech ends the local burst. Targeted task speech may wake the addressed actor,
  which can choose to contribute or wait; it does not gain ownership of that task.
  Only the holder can report it complete through its Brain.
- Successful non-speech tool use feeds its result into the next decision within
  the same burst. Consecutive identical invocations in a burst are rejected.
  No-progress semantics beyond failures/repetition remain model judgment, bounded
  by the hard decision budget.
- Waiting does not poll. New eligible observations, task/Brain acquisition, or an
  explicit `npc.reconsider()` can start work. Simultaneous observations coalesce
  into one latest pending observation, within the existing burst budget.
- Budget exhaustion does not verify or complete an objective. Increasing a task's
  budget is an explicit operator action, not an action offered to the model.
- Status and the last twenty tool outcomes are inspectable at
  `npc.ndb.agency_state` and `npc.ndb.agency_results`. These execution diagnostics
  and pending observations are transient; tasks and their budgets persist.
  No general durable action journal or exactly-once external execution is claimed.
- Existing Speaker-only NPCs become passive listeners by default. Equip a Brain
  to adopt agency, or explicitly set `npc.db.legacy_autoreply = True` to preserve
  the prior conversation behavior. An attached Brain takes precedence; an already
  running legacy reply is suppressed and allowed to finish before Brain dispatch.
- No automatic work resumes after server restart. Operators can call
  `npc.reconsider()` after loading the world. No background polling is installed.
- Ordinary player speech is an observation, not automatic task enrollment.
  Only carried tools are advertised; nearby public-tool discovery is future work.
- Use Evennia's `move_to()` for transfers. Direct database location edits that
  bypass movement hooks are administrative operations outside this lifecycle.

Run the executable requirements and the legacy regression suite with:

```sh
python -m pytest --ds=tests.npc_settings tests/test_agency_requirements.py tests/test_npc_requirements.py tests/test_agent_collaboration_requirements.py tests/test_collaboration_integration.py
```

These tests use real Evennia objects, a controlled reactor clock and Deferred model
responses. A live provider smoke test is still needed to evaluate model choices.

### Verification scope

Acceptance tests cover both player command invocation and the Brain provider
adapter, task acquisition/transfer, prioritization, shared subtask budgets,
silence, conversation routing, stale/deleted equipment, and failure recovery.
The repository-wide suite has known collection blockers in the optional image
backend and external gateway tests; those components are not exercised by this
feature's focused settings.
