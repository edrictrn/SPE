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

    def _create_lp_tasks(self):
        """Handle LP cancellation without stopping the simulation."""

        async def run_lp(coroutine_factory):
            try:
                await coroutine_factory()
            except asyncio.CancelledError:
                # Cancelled LP terminates normally.
                return

        for lp_id, coroutine_factory in list(self._lp_coroutines.items()):
            if callable(coroutine_factory):
                self._lp_coroutines[lp_id] = asyncio.create_task(
                    run_lp(coroutine_factory)
                )
    

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
        """Wait for an event with an optional *virtual-time* deadline."""
        if timeout is None:
            return await super().wait_for_event(lp_id, event_type, timeout=None)
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("timeout must be a finite non-negative number")

        event_future = self.create_future()
        timer_future = self.create_future()
        deadline = self.current_time + timeout
        self._event_waiters[event_type].append((lp_id, event_future))
        self._time_waiters.push((deadline, lp_id, timer_future), priority=deadline)
        self._lp_status[lp_id] = BkSysCoLPStatus.WAITING_EVENT
        self._lp_waiting_for[lp_id] = event_type

        try:
            done, _ = await asyncio.wait(
                (event_future, timer_future),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if event_future in done:
                return event_future.result()
            raise asyncio.TimeoutError(
                f"Timeout waiting for {event_type!r} at simulation time {deadline}"
            )
        finally:
            self._event_waiters[event_type] = [
                (lid, future) for lid, future in self._event_waiters[event_type]
                if future is not event_future
            ]
            if not event_future.done():
                event_future.cancel()
            if not timer_future.done():
                timer_future.cancel()
            self._lp_status[lp_id] = BkSysCoLPStatus.READY
            self._lp_waiting_for.pop(lp_id, None)


    def _process_events_at_current_time(self):
        """Reject events targeting an unregistered LP."""
        previous_callback = self._on_event

        def validate_receiver(event):
            if event.receiver_id not in self._lp_instances:
                raise ValueError(
                    f"Unknown receiver LP {event.receiver_id} "
                    f"for event {event.event_type!r}"
                )

            if previous_callback is not None:
                previous_callback(event)

        self._on_event = validate_receiver

        try:
            return super()._process_events_at_current_time()
        finally:
            self._on_event = previous_callback


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
