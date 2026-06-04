"""
Pending operations queue for LLM operations.

When an LLM call times out or fails, the operation is queued for retry
with exponential backoff. After MAX_RETRIES, the operation is marked stale
and the room owner is notified.
"""

import time
from evennia.utils.utils import delay


class PendingOps:
    """Manages a queue of pending LLM operations with retry logic."""

    MAX_RETRIES = 5
    RETRY_BASE = 15
    NOTIFICATION_THRESHOLD = 3

    def __init__(self, room):
        self.room = room
        if not getattr(self.room.db, "pending_ops", None):
            self.room.db.pending_ops = []

    def enqueue(self, op_type, instruction, speaker_key, target_ref=None, target_name=None):
        """Add an operation to the retry queue."""
        ops = self.room.db.pending_ops
        ops.append({
            "type": op_type,
            "instruction": instruction,
            "speaker_key": speaker_key,
            "target_ref": target_ref,
            "target_name": target_name,
            "attempts": 1,
            "first_attempt": time.time(),
            "last_attempt": time.time(),
            "status": "pending",
        })
        self.room.db.pending_ops = ops
        self.room.msg_contents("|mThe room notes the attempt.|n Retrying shortly...")
        self._schedule_retry()

    def _backoff(self, attempt):
        """Exponential backoff: 15s, 30s, 60s, 120s, 240s."""
        return min(self.RETRY_BASE * (2 ** (attempt - 1)), 240)

    def _schedule_retry(self):
        """Schedule the next retry pass."""
        task = getattr(self.room.ndb, "retry_task", None)
        if task:
            try:
                task.cancel()
            except Exception:
                pass

        ops = self.room.db.pending_ops or []
        pending = [op for op in ops if op["status"] == "pending"]
        if not pending:
            return

        max_attempt = max(op["attempts"] for op in pending)
        wait = self._backoff(max_attempt)
        self.room.ndb.retry_task = delay(wait, self._retry_loop)

    def _retry_loop(self):
        """Process all pending operations."""
        ops = self.room.db.pending_ops or []
        if not ops:
            return

        remaining = []
        any_success = False

        for op in ops:
            if op["status"] != "pending":
                continue

            success = self._retry_single(op)
            if success:
                op["status"] = "done"
                any_success = True
            else:
                op["attempts"] += 1
                op["last_attempt"] = time.time()
                remaining.append(op)

        # Check for stale operations
        stale = [op for op in remaining if op["attempts"] >= self.MAX_RETRIES]
        for op in stale:
            self.room.msg_contents(
                f"|rThe room sighs.|n Stale operation: {op['instruction'][:60]} "
                f"(attempted {op['attempts']} times). Consider trying again later."
            )

        # Persist only non-stale pending ops
        kept = [op for op in remaining if op["attempts"] < self.MAX_RETRIES]
        self.room.db.pending_ops = kept

        # Schedule next retry if anything is still pending
        if kept:
            self._schedule_retry()

    def _retry_single(self, op):
        """Try a single LLM operation. Returns True on success."""
        if op["type"] == "create":
            return self._retry_create(op)
        elif op["type"] == "edit":
            return self._retry_edit(op)
        return False

    def _retry_create(self, op):
        """Retry a create operation."""
        try:
            from utils.computer import Computer
            comp = Computer(self.room)
            propdata = comp.generate_prop_json(op["speaker_key"], op["instruction"])
            if not isinstance(propdata, dict):
                return False

            key = str(propdata.get("key") or "").strip()
            shortdesc = str(propdata.get("shortdesc") or "").strip()
            desc = (propdata.get("desc") or propdata.get("description") or "").strip()

            if not key and not shortdesc and not desc:
                return False

            if not desc:
                desc = f"A newly manifested {op['instruction'][:50]}."

            from evennia import create_object
            from typeclasses.objects import PropObject
            obj = create_object(
                PropObject,
                key=key[:60] if key else op["instruction"][:60],
                location=self.room,
                name=key if key else op["instruction"],
            )
            obj.db.shortdesc = shortdesc[:140] if shortdesc else f"a {key}"
            obj.db.desc = desc
            obj.db.notable = True
            self.room.msg_contents(
                f"|mThe room hums.|n {obj.key} appears (retry #{op['attempts']})."
            )
            self.room._schedule_desc_rewrite()

            if self.room.image_enabled and self.room._can_trigger_image():
                self.room._trigger_object_image(obj)

            return True
        except Exception as e:
            return False

    def _retry_edit(self, op):
        """Retry an edit operation."""
        try:
            from utils.computer import Computer
            comp = Computer(self.room)
            if not op.get("target_ref"):
                return False
            data = comp.generate_prop_edit_json(
                op["speaker_key"], op["instruction"], str(op["target_ref"])
            )
            if not isinstance(data, dict):
                return False

            from evennia.search_object import search_object
            target = search_object(ref=op["target_ref"], typeclass="typeclasses.objects.PropObject")
            if not target:
                return False

            new_key = str(data.get("key") or "").strip()
            new_sd = str(data.get("shortdesc") or "").strip()
            new_desc = str(data.get("desc") or "").strip()

            if new_key and new_key != target.key:
                target.key = new_key[:60]
            if new_sd:
                target.db.shortdesc = new_sd[:140]
            if new_desc:
                target.db.desc = new_desc

            if self.room.image_enabled and self.room._can_trigger_image():
                self.room._trigger_object_image(target)

            self.room.msg_contents(
                f"|mReality tweaks itself.|n {target.key} updated (retry #{op['attempts']})."
            )
            self.room._schedule_desc_rewrite()
            return True
        except Exception:
            return False
