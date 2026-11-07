
from bkitevsim.dispatchers.sequential_eventdispatcher import (
    SequentialEventDispatcher
)

from spe_core.event_queue import EventQueue


class SpeSequentialDispatcher(SequentialEventDispatcher):
    """Sequential dispatcher using the SPE event queue."""

    def __init__(
        self,
        end_time=float("inf"),
        bucket_width=1.0
    ):
        super().__init__(
            end_time=end_time,
            bucket_width=bucket_width
        )

        # Replace the framework's LadderQueue
        self.event_queue = EventQueue()

    def schedule_event(self, event):
        # Prevent scheduling events in the past
        if event.timestamp < self.current_time:
            raise ValueError(
                f"Cannot schedule event at t={event.timestamp}. "
                f"Current simulation time is {self.current_time}."
            )

        # Reuse the framework's scheduling method
        super().schedule_event(event)
