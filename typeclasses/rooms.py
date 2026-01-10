"""
Rooms

Rooms are simple containers that has no location of their own.
"""

import os
import time
import json
import re
from twisted.internet.threads import deferToThread

from evennia import DefaultRoom, DefaultObject
from evennia.utils import create, logger
from evennia.utils.utils import inherits_from
from evennia.utils.utils import delay

from utils.llm_client import (
    LLMProvider,
    build_default_client_from_env,
)
from utils.computer import Computer
from utils.room_director import build_snapshot, generate_from_snapshot
from utils.room_object_query import (
    iter_notable_props,
    list_notables_with_dbref,
    find_object_in_room,
    delete_object_by_selector,
    is_prop,
)
from utils.room_targeting import resolve_edit_target, instruction_mentions_target
from utils.room_text import normalize_say_message, is_computer_addressed, extract_computer_instruction


class Room(DefaultRoom):
    """
    Default Room typeclass (kept for compatibility with the game template).
    """
    pass


class SmartRoom(DefaultRoom):
    """
    Room-as-manager:
    - Remembers recent speech (rolling buffer)
    - Dynamically appends a short "staging" line based on notable contents
    - Listens for "computer, ..." and manifests props with LLM-generated descriptions
    """

    MEMORY_MAX = 50                 # remember last N lines of speech
    LLM_COOLDOWN_SECONDS = 2.0      # minimum time between LLM calls per room
    LLM_MAX_ATTEMPTS = 4            # total attempts per request (per provider)

    # Room rewrite controls
    DESC_UPDATE_DEBOUNCE_S = 1.0
    DESC_UPDATE_COOLDOWN_S = 3.0

    # Local first (LM Studio OpenAI-compatible server)
    LOCAL_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:1234/v1")
    LOCAL_MODEL = os.getenv("LOCAL_LLM_MODEL", "gpt-oss-120b")

    # Fallback (OpenAI)
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "30"))

    # ----------------------------
    # Init
    # ----------------------------

    def at_object_creation(self):
        super().at_object_creation()
        if not self.db.desc:
            self.db.desc = "You are in an unfinished place. The world feels ready to grow."
            # Director-managed base description by default (only for default/empty rooms).
            self.db.auto_desc = True
            self.db.director_facts = []
            self.db.last_generated_desc = self.db.desc
        if self.db.memory is None:
            self.db.memory = []
        if self.db.last_llm_call_ts is None:
            self.db.last_llm_call_ts = 0.0
        if self.db.last_desc_rewrite_ts is None:
            self.db.last_desc_rewrite_ts = 0.0

    # ----------------------------
    # Memory
    # ----------------------------

    def _remember(self, speaker, message):
        """
        Store a rolling buffer of recent speech in the room.
        """
        mem = self.db.memory or []
        mem.append({"who": speaker.key, "msg": str(message)})
        self.db.memory = mem[-self.MEMORY_MAX:]

    def get_memory_text(self):
        """
        Human-readable memory for debugging or feeding into an LLM later.
        """
        mem = self.db.memory or []
        return "\n".join(f'{m["who"]}: {m["msg"]}' for m in mem)

    # ----------------------------
    # Auto room description rewrites (director)
    # ----------------------------

    def get_display_name(self, looker, **kwargs):
        name = super().get_display_name(looker, **kwargs)
        # Ensure we don't double-append if Evennia already did for builders
        if f"(#{self.id})" not in name:
            name = f"{name} (#{self.id})"
        return name

    def _is_scene_object(self, obj) -> bool:
        """
        Strict by default: only notable props influence room rewrites.
        Change to `return True` if you want *all* non-exit/non-character objects.
        """
        if not obj:
            return False
        if inherits_from(obj, "evennia.objects.objects.DefaultExit"):
            return False
        if inherits_from(obj, "evennia.objects.objects.DefaultCharacter"):
            return False
        return bool(obj.db.notable)

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        super().at_object_receive(moved_obj, source_location, **kwargs)
        if self.db.auto_desc and self._is_scene_object(moved_obj):
            self._schedule_desc_rewrite()

    def at_object_leave(self, moved_obj, destination, **kwargs):
        super().at_object_leave(moved_obj, destination, **kwargs)
        if self.db.auto_desc and self._is_scene_object(moved_obj):
            self._schedule_desc_rewrite()

    def _schedule_desc_rewrite(self):
        """
        Coalesce bursts of changes into one LLM call.
        """
        task = getattr(self.ndb, "desc_rewrite_task", None)
        if task:
            try:
                task.cancel()
            except Exception:
                pass
        self.ndb.desc_rewrite_task = delay(self.DESC_UPDATE_DEBOUNCE_S, self._start_desc_rewrite)

    def _start_desc_rewrite(self):
        if getattr(self.ndb, "desc_rewrite_inflight", False):
            return
        self.ndb.desc_rewrite_inflight = True

        now = time.time()
        last = float(self.db.last_desc_rewrite_ts or 0.0)
        if now - last < self.DESC_UPDATE_COOLDOWN_S:
            # Don't drop rewrites; retry after remaining cooldown.
            remaining = (self.DESC_UPDATE_COOLDOWN_S - (now - last)) + 0.05
            self.ndb.desc_rewrite_inflight = False
            delay(remaining, self._start_desc_rewrite)
            return
        self.db.last_desc_rewrite_ts = now

        # NEW: subtle “thinking” cue
        self.msg_contents("|mThe set shimmers, reconsidering itself…|n")
        computer = Computer(self)
        snapshot = computer.director_snapshot()
        d = deferToThread(computer.generate_room_desc, snapshot)

        def _on_ok(data):
            try:
                if not self.db.auto_desc:
                    return
                if not isinstance(data, dict):
                    raise ValueError(f"Director returned non-dict: {data!r}")
                new_desc = (data.get("desc") or "").strip()
                facts = data.get("facts") or []

                if new_desc and new_desc != (self.db.desc or ""):
                    self.db.desc = new_desc
                    self.db.last_generated_desc = new_desc
                    if isinstance(facts, list):
                        self.db.director_facts = facts

                    # NEW: only announce if something actually changed
                    self.msg_contents("|mReality settles into a new arrangement.|n")
            finally:
                self.ndb.desc_rewrite_inflight = False

        def _on_fail(failure):
            try:
                logger.log_err(f"[SmartRoom] Director rewrite failure:\n{failure.getTraceback()}")
            except Exception:
                logger.log_err("[SmartRoom] Director rewrite failure (could not render traceback).")
            self.ndb.desc_rewrite_inflight = False

        d.addCallback(_on_ok)
        d.addErrback(_on_fail)

    # ----------------------------
    # Speech handler (called by Character.at_say delegator)
    # ----------------------------

    def handle_speech(self, speaker, message, **kwargs):
        """
        Called by Character.at_say (your Character delegates here).
        """
        if not message:
            return

        from utils.facts import new_fact, add_fact, get_facts, remove_fact

        # Remember ALL speech
        self._remember(speaker, message)

        msg = str(message).strip()
        if not msg:
            return

        # normalize quotes/punctuation
        norm = normalize_say_message(msg)
        if not is_computer_addressed(norm):
            return
        instruction = extract_computer_instruction(norm)

        if not instruction:
            speaker.msg("Try: say computer, create a brass cat idol")
            return
        lowinst = instruction.strip().lower()

        # ---- LIST FACTS ----
        if lowinst in ("facts", "list facts", "show facts"):
            lines = []
            # room facts
            rf = get_facts(self)
            if rf:
                lines.append("|wRoom facts:|n")
                for f in rf[-15:]:
                    lines.append(f"  {f.get('id')}: {f.get('text')}")
            # object facts (notable only)
            for obj in self.contents:
                if not obj or not obj.db.notable:
                    continue
                of = get_facts(obj)
                if of:
                    lines.append(f"|w{obj.key} facts:|n")
                    for f in of[-10:]:
                        lines.append(f"  {f.get('id')}: {f.get('text')}")
            if not lines:
                speaker.msg("No pinned facts yet. Try: |wsay computer, pin This is a seaside lounge.|n")
            else:
                speaker.msg("\n".join(lines))
            return

        # ---- UNPIN (room only, for now) ----
        m = re.match(r"^unpin\s+([a-zA-Z0-9_]+)$", instruction.strip(), flags=re.IGNORECASE)
        if m:
            fid = m.group(1)
            ok = remove_fact(self, fid)
            if ok:
                self.msg_contents(f"|mThe room nods.|n Unpinned {fid}.")
                self._schedule_desc_rewrite()
            else:
                speaker.msg(f"I can't find a room fact with id '{fid}'. Try: |wsay computer, facts|n")
            return

        # ---- PIN: "pin <text>" or "pin <text> to <target>" ----
        m = re.match(r"^pin\s+(.+)$", instruction.strip(), flags=re.IGNORECASE)
        if m:
            rest = m.group(1).strip()

            # Split on " to " if present
            fact_text = rest
            target_text = None
            if " to " in rest.lower():
                # case-insensitive split preserving original
                parts = re.split(r"\s+to\s+", rest, maxsplit=1, flags=re.IGNORECASE)
                fact_text = parts[0].strip()
                target_text = parts[1].strip() if len(parts) > 1 else None

            if not fact_text:
                speaker.msg("Try: |wsay computer, pin This is a seaside lounge.|n")
                return

            # Choose target
            target_obj = self  # default: room
            if target_text:
                found = find_object_in_room(self, target_text)
                if not found:
                    speaker.msg(f"I couldn't find '{target_text}' to pin that to.")
                    return
                target_obj = found

            f = new_fact(fact_text, created_by=speaker.key, scope="pinned", strength=1.0)
            add_fact(target_obj, f)
            self.msg_contents(f"|mThe room remembers.|n Pinned: “{fact_text}”")
            self._schedule_desc_rewrite()
            return

        m = re.match(r"^(destroy|delete|remove)\b(.*)$", lowinst)
        if m:
            remainder = instruction.strip()[len(m.group(1)):].strip()  # keep original casing
            # strip leading articles
            remainder = re.sub(r"^(the|a|an)\s+", "", remainder, flags=re.IGNORECASE).strip()

            if not remainder:
                speaker.msg("Tell me what to destroy, e.g. |wsay computer, destroy Thorned Yuletide Sentinel|n")
                return

            removed = delete_object_by_selector(self, remainder)
            if not removed:
                opts = list_notables_with_dbref(self)
                if opts:
                    speaker.msg("|yIn this room I can remove:|n " + opts)
            if removed:
                self.msg_contents(f"|mThe room complies.|n {removed['key']}({removed['dbref']}) is removed.")
                self._schedule_desc_rewrite()
            else:
                speaker.msg(f"|yI couldn't find|n '{remainder}'. Try the exact name, or copy a dbref from the list above (example format: |w#67|n).")
            return

        # --- EDITING ---
        m = re.match(r"^(edit|update|change|recolor|paint)\b(.*)$", lowinst)
        if m:
            now = time.time()
            last = float(self.db.last_llm_call_ts or 0.0)
            if now - last < self.LLM_COOLDOWN_SECONDS:
                speaker.msg("|yThe room holds up a paw.|n Give it a second…")
                return
            self.db.last_llm_call_ts = now


            target, ambiguous = resolve_edit_target(self, instruction)
            
            if target and not instruction_mentions_target(instruction, target):
                # The resolver guessed a target that the instruction doesn't even name.
                # Treat as ambiguous and force dbref.
                target = None
                ambiguous = []

            if not target:
                opts = list_notables_with_dbref(self)
                if ambiguous:
                    amb = ", ".join(f"{o.key}({o.dbref})" for o in ambiguous[:12])
                    speaker.msg("|yWhich one did you mean?|n Use a dbref, e.g. |wsay computer, change #67 to be blue|n\n"
                                f"I see: {amb}")
                else:
                    if opts:
                        speaker.msg("I couldn't tell what object you meant. Use a dbref like |w#67|n.\n"
                                    f"I see: {opts}")
                    else:
                        speaker.msg("I couldn't tell what object you meant. Try including its name or a dbref like |w#67|n.")
                return

            self.msg_contents("|mThe room studies the object, considering your request…|n")

            computer = Computer(self)
            d = deferToThread(computer.generate_prop_edit_json, speaker.key, instruction, str(target.dbref))

            def _on_ok(data):
                if not isinstance(data, dict):
                    raise ValueError(f"Editor returned non-dict: {data!r}")

                # Hard guard: model must confirm which object it edited.
                resp_dbref = str(data.get("dbref") or "").strip()
                if resp_dbref and resp_dbref != str(target.dbref):
                    raise ValueError(f"Editor dbref mismatch: got {resp_dbref}, expected {target.dbref}")

                new_key = str(data.get("key") or "").strip()
                new_sd = str(data.get("shortdesc") or "").strip()
                new_desc = str(data.get("desc") or "").strip()

                # --- Apply key (object name) ---
                if new_key:
                    new_key = re.sub(r"\s+", " ", new_key).strip()
                    new_key = new_key[:60].strip()

                    # Must contain at least one letter (avoid pure punctuation / empty)
                    if re.search(r"[A-Za-z]", new_key) and new_key != target.key:
                        target.key = new_key

                # --- Apply shortdesc ---
                if new_sd:
                    new_sd = re.sub(r"\s+", " ", new_sd).strip()
                    # (Optional) enforce article rule only if you want it; otherwise remove this block.
                    # if not re.match(r"^(a|an|the)\b", new_sd, re.IGNORECASE):
                    #     new_sd = "a " + new_sd
                    target.db.shortdesc = new_sd[:140]

                # --- Apply desc ---
                if new_desc:
                    new_desc = new_desc.strip()
                    target.db.desc = new_desc

                self.msg_contents(
                    f"|mReality tweaks itself.|n {target.key} now looks a little different."
                )
                self._schedule_desc_rewrite()

            def _on_fail(failure):
                logger.log_err(f"[SmartRoom] edit failure:\n{failure.getTraceback()}")
                self.msg_contents("|rThe room hesitates.|n The edit doesn't take. (Try again.)")
                return None

            d.addCallback(_on_ok)
            d.addErrback(_on_fail)
            return


        # --- Explicit create/make/summon commands ---
        if re.match(r"^(create|make|manifest|summon)\b", lowinst):
            # normalize into an instruction for the prop-writer (strip the verb)
            remainder = re.sub(r"^(create|make|manifest|summon)\s+", "", instruction, flags=re.IGNORECASE).strip()
            if not remainder:
                speaker.msg("Try: say computer, create a brass cat idol")
                return

            now = time.time()
            last = float(self.db.last_llm_call_ts or 0.0)
            if now - last < self.LLM_COOLDOWN_SECONDS:
                speaker.msg("|yThe room holds up a paw.|n Give it a second…")
                return
            self.db.last_llm_call_ts = now

            self.msg_contents("|mThe room listens.|n Something begins to take shape…")

            computer = Computer(self)
            d = deferToThread(computer.generate_prop_json, speaker.key, remainder)

            def _on_ok(propdata):
                if not isinstance(propdata, dict):
                    raise ValueError(f"LLM returned non-dict: {propdata!r}")

                key = str(propdata.get("key") or "").strip() or remainder.strip().title()[:60]
                shortdesc = str(propdata.get("shortdesc") or "").strip() or f"a manifested {remainder[:40].strip()}"

                desc = (propdata.get("desc") or propdata.get("description") or "").strip()
                if not desc:
                    desc = f"A newly manifested {remainder.strip()}."

                obj = self._manifest_prop(key=key[:60], shortdesc=shortdesc[:140], desc=desc)
                self.msg_contents(f"|mThe room hums.|n {obj.db.shortdesc or obj.key} appears at {speaker.key}'s request.")
                self._schedule_desc_rewrite()

            def _on_fail(failure):
                logger.log_err(f"[SmartRoom] LLM/manifestation failure:\n{failure.getTraceback()}")
                self.msg_contents("|rThe room sputters.|n The manifestation fails. (Try again in a moment.)")
                return None

            d.addCallback(_on_ok)
            d.addErrback(_on_fail)
            return

        
        else:
            # --- Fallback intent router (LLM) with confirmation ---
            now = time.time()
            last = float(self.db.last_llm_call_ts or 0.0)
            if now - last < self.LLM_COOLDOWN_SECONDS:
                speaker.msg("|yThe room holds up a paw.|n Give it a second…")
                return
            self.db.last_llm_call_ts = now

            self.msg_contents("|mThe room tilts its head, interpreting…|n")

            computer = Computer(self)
            d = deferToThread(computer.predict_intent, speaker.key, instruction)

            def _ok(data):
                if not isinstance(data, dict):
                    raise ValueError(f"Intent router returned non-dict: {data!r}")

                intent = str(data.get("intent") or "unknown").strip().lower()
                normalized = str(data.get("normalized") or "").strip()

                # If the router couldn't produce a concrete command, give a short help nudge.
                if not normalized or intent == "unknown":
                    speaker.msg(
                        "I’m not sure what you meant. Try one of:\n"
                        "  |wsay computer, create <thing>|n\n"
                        "  |wsay computer, destroy <thing>|n\n"
                        "  |wsay computer, pin <fact>|n\n"
                        "  |wsay computer, facts|n"
                    )
                    return

                # Suggest-only: no pending state, no y/n.
                speaker.msg(
                    "I can’t run that as-written, but I think you meant:\n"
                    f"  |wsay computer, {normalized}|n\n"
                    "(Copy/paste that line.)"
                )

            def _fail(failure):
                logger.log_err(f"[SmartRoom] intent router failure:\n{failure.getTraceback()}")
                speaker.msg("I couldn't interpret that. Try starting with: create / destroy / pin / facts.")
                return None

            d.addCallback(_ok)
            d.addErrback(_fail)
            return

    def _run_computer_instruction(self, speaker, instruction: str):
        """
        Execute a deterministic instruction string as if it came after 'computer,'.
        Must run on main thread.
        """
        instruction = (instruction or "").strip()
        if not instruction:
            speaker.msg("I didn't get a usable instruction.")
            return

        lowinst = instruction.lower()

        # facts
        if lowinst in ("facts", "list facts", "show facts"):
            # reuse your existing branch by just calling handle_speech with synthetic message
            self.handle_speech(speaker, f'computer, {instruction}')
            return

        # refine
        if lowinst in ("refine", "rewrite", "refresh", "update room", "update"):
            self._schedule_desc_rewrite()
            self.msg_contents("|mThe room takes another look at itself…|n")
            return

        # destroy
        m = re.match(r"^(destroy|delete|remove)\b(.*)$", lowinst)
        if m:
            remainder = instruction[len(m.group(1)):].strip()
            remainder = re.sub(r"^(the|a|an)\s+", "", remainder, flags=re.IGNORECASE).strip()
            removed = delete_object_by_selector(self, remainder)
            if not removed:
                opts = list_notables_with_dbref(self)
                if opts:
                    speaker.msg("|yIn this room I can remove:|n " + opts)
            if removed:
                self.msg_contents(f"|mThe room complies.|n {removed['key']}({removed['dbref']}) is removed.")
                self._schedule_desc_rewrite()
            return

        # pin/unpin and create: easiest is to re-enter normal parsing
        self.handle_speech(speaker, f'computer, {instruction}')


    # ----------------------------
    # LLM plumbing (thread-safe)
    # ----------------------------

    def _llm_providers(self):
        providers = [
            LLMProvider(
                label="LOCAL",
                base_url=self.LOCAL_BASE_URL,
                model=self.LOCAL_MODEL,
                api_key=None,
            )
        ]
        if self.OPENAI_API_KEY:
            providers.append(
                LLMProvider(
                    label="OPENAI",
                    base_url=self.OPENAI_BASE_URL,
                    model=self.OPENAI_MODEL,
                    api_key=self.OPENAI_API_KEY,
                )
            )
        return providers

    # Prop generation moved to utils/computer.py (Computer.generate_prop_json)


    # ----------------------------
    # Manifestation (main thread only)
    # ----------------------------

    def _manifest_prop(self, key, shortdesc=None, desc=None):
        """
        Create a basic prop in this room.
        """
        # Create off-room so we can set flags BEFORE the move triggers at_object_receive.
        obj = create.create_object(DefaultObject, key=key, location=None)
        if shortdesc:
            obj.db.shortdesc = shortdesc
        if desc:
            obj.db.desc = desc
        # Make it show up in our dynamic staging line
        obj.db.notable = True
        # scaffold defaults (facts/affordance)
        if obj.db.facts is None:
            obj.db.facts = []
        if obj.db.affordance is None:
            obj.db.affordance = {"unit": "lb", "weight": 1.0, "immovable": False}
        obj.move_to(self, quiet=True)
        return obj
