
import unittest

from bkitevsim.core import Event
from spe_core.event_queue import EventQueue


class TestSpeEventQueue(unittest.TestCase):

    def test_timestamp_order(self):
        queue = EventQueue()

        queue.push(Event(1024, 0, 1, "A"))
        queue.push(Event(1023, 0, 1, "B"))

        self.assertEqual(
            [queue.pop().timestamp, queue.pop().timestamp],
            [1023, 1024]
        )

    def test_priority_at_same_timestamp(self):
        queue = EventQueue()

        for event_type in (
            "EXTERNAL_ARRIVAL",
            "TRANSFER_ARRIVAL",
            "SERVICE_COMPLETE"
        ):
            queue.push(Event(5, 0, 1, event_type))

        actual = [queue.pop().event_type for _ in range(3)]

        self.assertEqual(actual, [
            "SERVICE_COMPLETE",
            "TRANSFER_ARRIVAL",
            "EXTERNAL_ARRIVAL"
        ])

    def test_stable_for_same_priority(self):
        queue = EventQueue()

        for i in range(3):
            queue.push(Event(
                7, 0, 1,
                "SERVICE_COMPLETE",
                payload={"id": i}
            ))

        actual = [queue.pop().payload["id"] for _ in range(3)]

        self.assertEqual(actual, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
