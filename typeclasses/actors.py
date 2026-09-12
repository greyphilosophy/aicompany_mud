"""Shared inventory-derived capabilities for world object holders.

Concrete equipment is imported locally to avoid the Object/equipment typeclass
import cycle. NPC is just a convenient body with starter Context and Memory.
"""

import re
from twisted.internet.threads import deferToThread
from evennia.utils import create, logger


class ActorMixin:
    """Reason, listen and act only through equipment carried by this holder."""

    def _first_carried(self, typeclass):
        return next((obj for obj in self.contents if isinstance(obj, typeclass)), None)

    def get_context(self):
        from typeclasses.components.context import Context

        return self._first_carried(Context)

    def get_memory(self):
        from typeclasses.components.memory import Memory

        return self._first_carried(Memory)

    def get_listener(self):
        from typeclasses.components.listener import Listener

        return self._first_carried(Listener)

    def get_speaker(self):
        from typeclasses.tools.speaker import Speaker

        return self._first_carried(Speaker)

    def get_brain(self):
        from typeclasses.components.brain import Brain

        return self._first_carried(Brain)

    def reconsider(self, observation=None):
        brain = self.get_brain()
        return brain.wake(self, observation) if brain else False

    def get_tasks(self):
        from typeclasses.tasks import Task

        return sorted(
            (obj for obj in self.contents if isinstance(obj, Task)),
            key=lambda task: (-int(task.db.priority or 0), task.id),
        )

    def get_active_task(self):
        return next((task for task in self.get_tasks() if task.can_continue()), None)

    def get_tools(self):
        from typeclasses.tools.base import Tool

        return [obj for obj in self.contents if isinstance(obj, Tool)]

    def create_task(
        self,
        objective,
        requester=None,
        max_turns=None,
        max_no_progress_turns=None,
    ):
        from typeclasses.tasks import Task

        key = f"Task: {str(objective or '').strip()[:48] or 'untitled'}"
        task = create.create_object(Task, key=key, location=self)
        task.configure(
            objective,
            requester=requester,
            assignee=self,
            max_turns=max_turns,
            max_no_progress_turns=max_no_progress_turns,
        )
        return task

    def accept_task(self, task):
        if not task:
            return False
        if task.location is not self:
            if not task.move_to(self, quiet=True):
                return False
        task.db.assignee = self
        if task.db.status == "pending":
            task.db.status = "active"
        return True

    def incorporate_context(self, other_context, start=None, stop=None):
        own = self.get_context()
        if not own:
            return False
        own.incorporate(other_context.export(start, stop))
        return True

    def remember_context(
        self, other_context=None, start=None, stop=None, kind="experience"
    ):
        memory = self.get_memory()
        source_context = other_context or self.get_context()
        if not memory or not source_context:
            return 0
        count = 0
        for entry in source_context.export(start, stop):
            if memory.remember(
                entry.get("content"), source=entry.get("who"), kind=kind
            ):
                count += 1
        return count

    @staticmethod
    def _same_object(left, right):
        if left is right:
            return True
        left_id = getattr(left, "id", None)
        right_id = getattr(right, "id", None)
        return left_id is not None and left_id == right_id

    def _is_current_context(self, context):
        return ActorMixin._same_object(self.get_context(), context)

    def _is_current_speaker(self, speaker):
        return ActorMixin._same_object(self.get_speaker(), speaker)

    def _is_addressed(self, message):
        name = str(getattr(self, "key", "") or "").strip()
        if not name:
            return False
        return bool(
            re.search(rf"(?<!\w){re.escape(name)}(?!\w)", str(message), re.IGNORECASE)
        )

    def should_respond_to_speech(
        self,
        speaker,
        message,
        task=None,
        target=None,
        allow_reply=None,
    ):
        if not speaker or ActorMixin._same_object(self, speaker):
            return False
        if target is not None and not ActorMixin._same_object(self, target):
            return False
        if allow_reply is False:
            return False
        if task is not None:
            if hasattr(task, "can_continue") and not task.can_continue():
                return False
            return target is None or ActorMixin._same_object(self, target)
        if target is not None and ActorMixin._same_object(self, target):
            return True
        if ActorMixin._is_addressed(self, message):
            return True

        # Raw actor speech has no hidden reply-control metadata. This preserves the
        # existing player-facing behavior without checking what controls the speaker.
        if allow_reply is None:
            return True

        active_task = None
        try:
            active_task = self.get_active_task()
        except Exception:
            active_task = None
        if active_task and ActorMixin._same_object(
            getattr(active_task.db, "requester", None), speaker
        ):
            return "?" in str(message)
        return False

    def _history_for_reply(self, context, task=None):
        from typeclasses.components.context import Context

        history_messages, history_ids = Context.snapshot(context)
        prefix = []
        try:
            memory = self.get_memory()
        except Exception:
            memory = None
        if memory and hasattr(memory, "as_message"):
            memory_message = memory.as_message()
            if memory_message:
                prefix.append(memory_message)
        if task is not None:
            own_context = self.get_context()
            if own_context and not ActorMixin._same_object(own_context, context):
                # Personal knowledge is input only; never copy the shared exchange back.
                prefix.extend(own_context.as_messages())
            objective = str(getattr(task.db, "objective", "") or "").strip()
            if objective:
                prefix.append(
                    {
                        "role": "system",
                        "content": (
                            f"Active task objective: {objective}. Keep the exchange focused on "
                            "advancing this objective and stop when no useful contribution remains."
                        ),
                    }
                )
        return prefix + history_messages, history_ids

    def _dispatch_reply(self, context, voice, heard_from=None, task=None):
        from typeclasses.components.context import Context
        from typeclasses.tools.speaker import Speaker

        npc_name = str(self.key)
        history_messages, history_ids = ActorMixin._history_for_reply(
            self, context, task=task
        )
        providers = voice.providers()
        system_prompt = str(voice.SYSTEM_PROMPT)
        origin = getattr(self, "location", None)
        task_owner = getattr(task, "location", None)

        def task_is_current():
            return (
                task.can_continue()
                and ActorMixin._same_object(task.get_context(), context)
                and ActorMixin._same_object(getattr(task, "location", None), task_owner)
                and ActorMixin._same_object(getattr(self, "location", None), origin)
                and (
                    heard_from is None
                    or ActorMixin._same_object(
                        getattr(heard_from, "location", None), origin
                    )
                )
            )

        logger.log_info(f"[Actor {self.key}] dispatching LLM call in thread")
        try:
            deferred = deferToThread(
                Speaker.generate_response_from_messages,
                npc_name,
                history_messages,
                providers,
                system_prompt,
                *([True] if task is not None else []),
            )
        except Exception:
            logger.log_trace()
            self.ndb.reply_inflight = False
            return None

        self.ndb.reply_inflight = True

        def _say(response):
            logger.log_info(f"[Actor {self.key}] callback fired, recording reply")
            if hasattr(self, "get_brain") and self.get_brain():
                return response
            if task is not None and not task_is_current():
                return response
            if task is None:
                try:
                    Context.insert_after_snapshot(
                        context, history_ids, self.key, response, role="assistant"
                    )
                except Exception:
                    logger.log_trace()
                    return response

                if not ActorMixin._is_current_context(self, context):
                    logger.log_warn(
                        f"[Actor {self.key}] reply recorded to its original Context, "
                        "but that Context is no longer carried; suppressing stale speech"
                    )
                    return response

            if not ActorMixin._is_current_speaker(self, voice):
                logger.log_warn(
                    f"[Actor {self.key}] reply recorded, but its Speaker is no longer "
                    "carried; suppressing stale speech"
                )
                return response

            logger.log_info(f"[Actor {self.key}] speaking: {str(response)[:120]}")
            if task is None:
                # Preserve compatibility with existing one-argument say() callers and
                # mocks. ActorMixin.say itself marks unscoped autonomous speech terminal.
                self.say(response)
            else:
                action = response["action"]
                self.say(
                    response["response"],
                    task=task,
                    target=heard_from,
                    allow_reply=action == "continue",
                    progress=response["progress"],
                )
                if action == "complete":
                    task.complete(response["response"])
                elif action == "decline":
                    task.decline(response["response"])
                elif action == "stop":
                    task.db.status = "stalled"
                    task.db.result = response["response"]
            return response

        def _failed(failure):
            logger.log_err(
                f"[Actor {self.key}] response failure:\n{failure.getTraceback()}"
            )
            return None

        def _finished(result):
            self.ndb.reply_inflight = False
            logger.log_info(f"[Actor {self.key}] reply cycle complete")
            if hasattr(self, "get_brain") and self.get_brain():
                self.ndb.reply_pending = False
                self.reconsider(getattr(self.ndb, "agency_observation", None))
                return result

            if getattr(self.ndb, "reply_pending", False):
                pending_context = getattr(self.ndb, "reply_pending_context", None)
                pending_speaker = getattr(self.ndb, "reply_pending_speaker", None)
                pending_task = getattr(self.ndb, "reply_pending_task", None)
                pending_room = getattr(self.ndb, "reply_pending_room", None)
                pending_owner = getattr(self.ndb, "reply_pending_owner", None)
                self.ndb.reply_pending = False
                self.ndb.reply_pending_context = None
                self.ndb.reply_pending_speaker = None
                self.ndb.reply_pending_task = None
                self.ndb.reply_pending_room = None
                self.ndb.reply_pending_owner = None
                pending_voice = self.get_speaker()
                context_is_valid = bool(
                    pending_context
                    and (
                        (
                            pending_task is not None
                            and ActorMixin._same_object(
                                pending_task.get_context(), pending_context
                            )
                        )
                        or (
                            pending_task is None
                            and ActorMixin._is_current_context(self, pending_context)
                        )
                    )
                )
                task_is_valid = pending_task is None or (
                    pending_task.can_continue()
                    and ActorMixin._same_object(pending_task.location, pending_owner)
                    and ActorMixin._same_object(self.location, pending_room)
                    and ActorMixin._same_object(
                        getattr(pending_speaker, "location", None), pending_room
                    )
                )
                if context_is_valid and pending_voice and task_is_valid:
                    logger.log_info(
                        f"[Actor {self.key}] dispatching one queued follow-up reply"
                    )
                    ActorMixin._dispatch_reply(
                        self,
                        pending_context,
                        pending_voice,
                        heard_from=pending_speaker,
                        task=pending_task,
                    )
                else:
                    logger.log_info(
                        f"[Actor {self.key}] dropping queued follow-up because its "
                        "Context, Task, or Speaker is no longer usable"
                    )
            return result

        deferred.addCallback(_say)
        deferred.addErrback(_failed)
        deferred.addBoth(_finished)
        return deferred

    def at_heard_say(self, speaker, message, **kwargs):
        listener = self.get_listener()
        if not listener or ActorMixin._same_object(self, speaker):
            return

        task = kwargs.get("task")
        target = kwargs.get("target")
        allow_reply = kwargs.get("allow_reply")

        if task is not None:
            context = listener.record(self, speaker, message, task=task)
        else:
            context = listener.record(self, speaker, message)
        logger.log_info(
            f"[Actor {self.key}] heard speech from "
            f"{getattr(speaker, 'key', 'unknown')}: {str(message)[:100]}"
        )
        if not context:
            logger.log_warn(
                f"[Actor {self.key}] listener heard speech but no Context is available"
            )
            return
        logger.log_info(
            f"[Actor {self.key}] working context now has "
            f"{len(context.db.entries or [])} entr(y/ies)"
        )

        brain = self.get_brain() if hasattr(self, "get_brain") else None
        if brain:
            if ActorMixin.should_respond_to_speech(
                self,
                speaker,
                message,
                task=task,
                target=target,
                allow_reply=allow_reply,
            ):
                self.reconsider(
                    {"speaker": speaker, "message": str(message), "task": task}
                )
            return
        if not bool(getattr(self.db, "legacy_autoreply", False)):
            return

        voice = self.get_speaker()
        if not voice:
            return

        if not ActorMixin.should_respond_to_speech(
            self,
            speaker,
            message,
            task=task,
            target=target,
            allow_reply=allow_reply,
        ):
            return

        if getattr(self.ndb, "reply_inflight", False):
            self.ndb.reply_pending = True
            self.ndb.reply_pending_context = context
            self.ndb.reply_pending_speaker = speaker
            self.ndb.reply_pending_task = task
            self.ndb.reply_pending_room = getattr(self, "location", None)
            self.ndb.reply_pending_owner = getattr(task, "location", None)
            logger.log_info(
                f"[Actor {self.key}] reply already in flight; speech recorded and follow-up queued"
            )
            return

        self.ndb.reply_pending = False
        self.ndb.reply_pending_context = None
        self.ndb.reply_pending_speaker = None
        self.ndb.reply_pending_task = None
        ActorMixin._dispatch_reply(self, context, voice, heard_from=speaker, task=task)

    def say(self, message, task=None, target=None, allow_reply=None, progress=None):
        """Speak as an actor and attach hidden collaboration metadata when needed."""
        if not self.location or not message:
            return False
        if target is not None and not ActorMixin._same_object(
            getattr(target, "location", None), self.location
        ):
            return False

        if task is not None and hasattr(task, "can_continue"):
            if not task.can_continue():
                return False
            task_context = task.get_context() if hasattr(task, "get_context") else None
            if task_context is None:
                return False
            if hasattr(task, "record_turn"):
                if not task.record_turn(self, message, progress=progress):
                    return False
            if task_context:
                # Shared task transcripts use speaker-labelled user records rather than
                # assistant roles, since the same transcript is viewed by every actor.
                task_context.append(self.key, message, role="user")
            task_can_continue = task.can_continue()
            if allow_reply is None:
                allow_reply = task_can_continue
            else:
                allow_reply = bool(allow_reply and task_can_continue)
        elif allow_reply is None:
            # Unscoped autonomous replies do not invite another autonomous reply.
            allow_reply = False

        logger.log_info(
            f"[Actor {self.key}] broadcasting to room: {str(message)[:120]}"
        )
        self.location.msg_contents(f'{self.key} says, "{message}"', from_obj=self)
        if hasattr(self.location, "handle_speech"):
            self.location.handle_speech(
                self,
                message,
                task=task,
                target=target,
                allow_reply=allow_reply,
            )
        return True

    def ask(self, actor, message, task=None):
        """Ask another actor for task-relevant help without caring how it is controlled."""
        task = task or self.get_active_task()
        if task is None:
            return False
        if hasattr(task, "can_continue") and not task.can_continue():
            return False
        return self.say(message, task=task, target=actor, allow_reply=True)
