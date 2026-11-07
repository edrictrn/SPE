
import unittest

from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess

from spe_core.coroutine_loop import SpeCoEventLoop


class RecordingCoLP(BkSysCoLogicalProcess):

    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.received = []

    async def coroutine_run(self):
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

        await self.wait_until(1025)

    def handle_event(self, event):
        self.received.append(
            (event.timestamp, event.event_type)
        )


class TimerCoLP(BkSysCoLogicalProcess):

    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.wake_time = None

    async def coroutine_run(self):
        self.wake_time = await self.wait_until(0.5)


class TestSpeCoroutine(unittest.TestCase):

    def test_coroutine_event_order(self):
        sim = Simulation(
            SimulationOptions(end_time=1030),
            models={"recording": RecordingCoLP}
        )

        lp = sim.create_lp(0, "recording")

        sim.dispatcher = SpeCoEventLoop(end_time=1030)

        stats = sim.run()

        self.assertEqual(lp.received, [
            (1023, "SERVICE_COMPLETE"),
            (1023, "EXTERNAL_ARRIVAL"),
            (1024, "EXTERNAL_ARRIVAL")
        ])

        self.assertEqual(stats["events_processed"], 3)

    def test_virtual_time_wait(self):
        sim = Simulation(
            SimulationOptions(end_time=1),
            models={"timer": TimerCoLP}
        )

        lp = sim.create_lp(0, "timer")

        sim.dispatcher = SpeCoEventLoop(end_time=1)

        stats = sim.run()

        self.assertAlmostEqual(lp.wake_time, 0.5)
        self.assertEqual(stats["events_processed"], 0)


if __name__ == "__main__":
    unittest.main()
