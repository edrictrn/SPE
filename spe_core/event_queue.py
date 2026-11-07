
import heapq
import itertools
import math


class EventQueue:
    """Event queue ordered by timestamp, priority, and insertion order."""

    PRIORITIES = {
        "SERVICE_COMPLETE": 0,
        "TRANSFER_ARRIVAL": 1,
        "EXTERNAL_ARRIVAL": 2,
    }

    def __init__(self):
        self._heap = []
        self._sequence = itertools.count()

    def push(self, event):
        if not math.isfinite(event.timestamp) or event.timestamp < 0:
            raise ValueError("Event timestamp must be finite and nonnegative")

        priority = self.PRIORITIES.get(event.event_type, 3)
        sequence_id = next(self._sequence)

        heapq.heappush(
            self._heap,
            (event.timestamp, priority, sequence_id, event)
        )

    def pop(self):
        if not self._heap:
            return None
        return heapq.heappop(self._heap)[3]

    def peek(self):
        if not self._heap:
            return None
        return self._heap[0][3]

    def is_empty(self):
        return not self._heap

    def __len__(self):
        return len(self._heap)
