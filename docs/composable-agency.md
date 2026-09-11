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
