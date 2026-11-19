"""Compatibility checks against observed behavior of the external framework."""

import unittest

from bkitevsim.core import Event
from bkitevsim.queues import LadderQueue


class TestFrameworkCompatibility(unittest.TestCase):
    # Observed external compatibility failure; the framework's internal cause
    # has not been verified. Keep the regression assertion intact.
    @unittest.expectedFailure
    def test_ladder_queue_timestamp_order_across_bucket_rollover(self):
        """Regression retained from Dev1's original test commit (751b0fc)."""
        queue = LadderQueue()
        queue.push(Event(1023, 0, 1, "A"))
        queue.push(Event(1024, 0, 1, "B"))

        first = queue.pop()
        second = queue.pop()

        self.assertEqual(first.timestamp, 1023)
        self.assertEqual(second.timestamp, 1024)

    def test_ladder_queue_supported_operations_within_bucket(self):
        queue = LadderQueue()
        later = Event(0.75, 0, 1, "LATER")
        earlier = Event(0.25, 0, 1, "EARLIER")
        queue.push(later)
        queue.push(earlier)

        self.assertEqual(queue.size(), 2)
        self.assertEqual(queue.peek(), earlier)
        self.assertEqual(queue.peek_timestamp(), 0.25)
        self.assertEqual(queue.pop(), earlier)
        self.assertEqual(queue.pop(), later)
        self.assertTrue(queue.is_empty())


if __name__ == "__main__":
    unittest.main()
