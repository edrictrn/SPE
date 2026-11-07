
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

    def schedule_event(self, event):
        # Reject events scheduled in the past
        if event.timestamp < self.current_time:
            raise ValueError(
                f"Cannot schedule event at t={event.timestamp}; "
                f"current time is {self.current_time}"
            )

        super().schedule_event(event)

    def _advance_time_to_next_event(self):
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
