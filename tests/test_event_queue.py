
"""Basic SPE event queue edge cases; ordering is covered in test_spe_event_queue."""

import unittest

from spe_core.event_queue import EventQueue


class TestEventQueue(unittest.TestCase):
    def test_empty_queue(self):
        queue = EventQueue()
        self.assertTrue(queue.is_empty())
        self.assertIsNone(queue.peek())
        self.assertIsNone(queue.pop())


if __name__ == "__main__":
    unittest.main()
