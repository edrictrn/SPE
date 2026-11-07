
import unittest

from bkitevsim.core import Event
from bkitevsim.queues import LadderQueue


class TestEventQueue(unittest.TestCase):

    def test_timestamp_order(self):
        queue = LadderQueue()

        queue.push(Event(1023, 0, 1, "A"))
        queue.push(Event(1024, 0, 1, "B"))

        first = queue.pop()
        second = queue.pop()

        self.assertEqual(first.timestamp, 1023)
        self.assertEqual(second.timestamp, 1024)


if __name__ == "__main__":
    unittest.main()
