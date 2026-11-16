import asyncio
import math

from bkitevsim.core.logical_coProcess import (
    BkSysCoEventLoop,
    BkSysCoLPStatus,
)

from spe_core.event_queue import EventQueue


class _CoroutineEventQueue(EventQueue):
    """Adapter for the framework coroutine event loop."""

    def peek_priority(self):
        event = self.peek()
        return None if event is None else event.timestamp

    def size(self):
        return len(self)


class SpeCoEventLoop(BkSysCoEventLoop):
    """Coroutine event loop using deterministic event ordering."""

    def __init__(self, end_time=float("inf"), bucket_width=1.0):
        super().__init__(
            end_time=end_time,
            bucket_width=bucket_width
        )

        # Replace original event queue
        self._event_queue = _CoroutineEventQueue()

        # Auditable counters for asynchronous behavior. Do not infer a real
        # asyncio context-switch count from the framework's unused field.
        self.stats.update({
            "buffered_event_reads": 0,
            "event_waits_registered": 0,
            "event_waits_resumed": 0,
            "virtual_timeouts": 0,
            "lp_cancellations": 0,
        })

    def _create_lp_tasks(self):
        """Handle LP cancellation without stopping the simulation."""

        async def run_lp(coroutine_factory):
            try:
                await coroutine_factory()
            except asyncio.CancelledError:
                # A deliberately cancelled LP is not an experiment failure.
                self.stats["lp_cancellations"] += 1
                return

        for lp_id, coroutine_factory in list(self._lp_coroutines.items()):
            if callable(coroutine_factory):
                self._lp_coroutines[lp_id] = asyncio.create_task(
                    run_lp(coroutine_factory)
                )
                self.stats["coroutines_scheduled"] += 1
    

    def run(self, max_iterations=None):
        stats = super().run(max_iterations=max_iterations)

        # The framework logs coroutine errors without propagating them.
        # Check completed tasks after the loop exits and surface failures.
        for lp_id, task in self._lp_coroutines.items():
            if isinstance(task, asyncio.Task) and task.done() and not task.cancelled():
                error = task.exception()
                if error is not None:
                    raise error

        return stats

    async def wait_for_event(self, lp_id, event_type, timeout=None):
        """Wait without blocking other LPs; deadlines use simulation time.

        The framework buffers incoming messages in LP._pending_events.
        Consume those messages before registering a Future, otherwise an
        event that arrived earlier is ignored and the request can time out.
        """
        if timeout is not None and (not math.isfinite(timeout) or timeout < 0):
            raise ValueError("timeout must be a finite non-negative number")

        lp = self._lp_instances.get(lp_id)
        if lp is None:
            raise ValueError(f"Unknown waiting LP {lp_id}")

        # FCFS within the requested event type. Keep unrelated types buffered.
        for index, pending in enumerate(lp._pending_events):
            if pending.event_type == event_type:
                self.stats["buffered_event_reads"] += 1
                return lp._pending_events.pop(index)

        event_future = self.create_future()
        timer_future = None
        self._event_waiters[event_type].append((lp_id, event_future))
        self.stats["event_waits_registered"] += 1
        self._lp_status[lp_id] = BkSysCoLPStatus.WAITING_EVENT
        self._lp_waiting_for[lp_id] = event_type

        if timeout is not None:
            timer_future = self.create_future()
            deadline = self.current_time + timeout
            self._time_waiters.push((deadline, lp_id, timer_future), priority=deadline)

        try:
            if timer_future is None:
                result = await event_future
                self.stats["event_waits_resumed"] += 1
                return result

            done, _ = await asyncio.wait(
                (event_future, timer_future),
                return_when=asyncio.FIRST_COMPLETED,
            )
            # If both complete at exactly the deadline, prefer delivery.
            if event_future in done:
                self.stats["event_waits_resumed"] += 1
                return event_future.result()
            self.stats["virtual_timeouts"] += 1
            raise asyncio.TimeoutError(
                f"Timeout waiting for {event_type!r} at simulation time {deadline}"
            )
        finally:
            # Remove only this particular waiter; another LP may wait for
            # the same type concurrently.
            self._event_waiters[event_type] = [
                (lid, future)
                for lid, future in self._event_waiters[event_type]
                if future is not event_future
            ]
            if not event_future.done():
                event_future.cancel()
            if timer_future is not None and not timer_future.done():
                timer_future.cancel()
            self._lp_status[lp_id] = BkSysCoLPStatus.READY
            self._lp_waiting_for.pop(lp_id, None)

    def _process_events_at_current_time(self):
        """Deliver events exactly once and propagate handler/route errors.

        Unlike the framework default, do not log-and-swallow exceptions from
        LP.handle_event(): a broken experiment must not look successful.
        """
        count = 0
        while not self._event_queue.is_empty():
            event = self._event_queue.peek()
            if event is None or event.timestamp > self._current_time:
                break
            event = self._event_queue.pop()

            lp = self._lp_instances.get(event.receiver_id)
            if lp is None:
                raise ValueError(
                    f"Unknown receiver LP {event.receiver_id} "
                    f"for event {event.event_type!r}"
                )

            if self._on_event is not None:
                self._on_event(event)

            # Keep the LP's local virtual clock causally consistent.
            lp.set_local_virt_time(event.timestamp)
            lp.handle_event(event)  # Intentionally propagate exceptions.

            # A delivery may have been buffered by the default handle_event.
            # If a Future is already waiting, consume *that exact event* from
            # the buffer so a later wait_for cannot receive it twice.
            waiters = self._event_waiters.get(event.event_type, [])
            for target_id, future in waiters:
                if target_id == event.receiver_id and not future.done():
                    pending = getattr(lp, "_pending_events", None)
                    if pending is not None:
                        for index, buffered in enumerate(pending):
                            if buffered is event:
                                pending.pop(index)
                                break
                    future.set_result(event)
                    self._lp_status[target_id] = BkSysCoLPStatus.READY
                    break  # One message must not resolve multiple waiters.

            self._event_waiters[event.event_type] = [
                (target_id, future)
                for target_id, future in waiters
                if not future.done()
            ]
            count += 1
            self.stats["events_processed"] += 1
        return count

    def schedule_event(self, event):
        # Reject events scheduled in the past
        if event.timestamp < self.current_time:
            raise ValueError(
                f"Cannot schedule event at t={event.timestamp}; "
                f"current time is {self.current_time}"
            )

        super().schedule_event(event)

    def _advance_time_to_next_event(self):
        # Discard cancelled timer futures left by successful event waits.
        while not self._time_waiters.is_empty():
            waiter = self._time_waiters.peek()
            if not waiter[2].cancelled():
                break
            self._time_waiters.pop()

        # Find next scheduled event
        event = self._event_queue.peek()
        event_time = None if event is None else event.timestamp

        # Find next coroutine waiting deadline
        waiter = self._time_waiters.peek()
        waiter_time = None if waiter is None else waiter[0]

        # Only consider timestamps within simulation horizon
        candidates = [
            t for t in (event_time, waiter_time)
            if t is not None and t <= self.end_time
        ]

        if not candidates:
            return False

        next_time = min(candidates)

        if next_time < self.current_time:
            raise ValueError("Simulation time cannot move backwards")

        # Advance virtual clock
        self._current_time = next_time

        # At equal timestamps, deliver events before expiring wait_for timeouts.
        if event_time is not None and event_time == next_time:
            return True

        # Wake up coroutines whose wait time has arrived
        while not self._time_waiters.is_empty():
            waiter = self._time_waiters.peek()

            if waiter[0] > next_time:
                break

            _, lp_id, future = self._time_waiters.pop()

            if not future.done():
                self._lp_status[lp_id] = BkSysCoLPStatus.READY
                future.set_result(next_time)

        return True
