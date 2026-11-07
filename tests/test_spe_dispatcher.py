
import unittest

from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_process import BkSysLogicalProcess

from spe_core.dispatcher import SpeSequentialDispatcher


class RecordingLP(BkSysLogicalProcess):

    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.received = []

    def initialize(self):
        events = [
            (1024, "EXTERNAL_ARRIVAL"),
            (1023, "EXTERNAL_ARRIVAL"),
            (1023, "SERVICE_COMPLETE"),
        ]

        for timestamp, event_type in events:
            self.send_event(Event(
                timestamp=timestamp,
                sender_id=self.lp_id,
                receiver_id=self.lp_id,
                event_type=event_type
            ))

    def handle_event(self, event):
        self.received.append(
            (event.timestamp, event.event_type)
        )


class BackwardEventLP(BkSysLogicalProcess):

    def initialize(self):
        self.send_event(Event(5, self.lp_id, self.lp_id, "NOW"))

    def handle_event(self, event):
        self.send_event(Event(4, self.lp_id, self.lp_id, "PAST"))


class TestSpeDispatcher(unittest.TestCase):

    def test_simulation_event_order(self):
        sim = Simulation(
            SimulationOptions(end_time=1030),
            models={"recording": RecordingLP}
        )

        lp = sim.create_lp(0, "recording")

        sim.dispatcher = SpeSequentialDispatcher(end_time=1030)
        stats = sim.run()

        self.assertEqual(lp.received, [
            (1023, "SERVICE_COMPLETE"),
            (1023, "EXTERNAL_ARRIVAL"),
            (1024, "EXTERNAL_ARRIVAL")
        ])

        self.assertEqual(stats["events_processed"], 3)

    def test_reject_past_event(self):
        sim = Simulation(
            SimulationOptions(end_time=20),
            models={"backward": BackwardEventLP}
        )

        sim.create_lp(0, "backward")
        sim.dispatcher = SpeSequentialDispatcher(end_time=20)

        with self.assertRaises(ValueError):
            sim.run()


if __name__ == "__main__":
    unittest.main()
