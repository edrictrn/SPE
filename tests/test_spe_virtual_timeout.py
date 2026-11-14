
import asyncio
import unittest

from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess
from spe_core.coroutine_loop import SpeCoEventLoop


class TimeoutLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.timed_out_at = None

    async def coroutine_run(self):
        try:
            await self.wait_for("MESSAGE", timeout=0.5)
        except asyncio.TimeoutError:
            self.timed_out_at = self._event_loop.current_time


class EarlyMessageLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.received_at = None

    async def coroutine_run(self):
        self.send_event(Event(
            timestamp=0.2,
            sender_id=self.lp_id,
            receiver_id=self.lp_id,
            event_type="MESSAGE"
        ))

        event = await self.wait_for("MESSAGE", timeout=0.5)
        self.received_at = event.timestamp


class TestVirtualTimeout(unittest.TestCase):

    def test_timeout_uses_simulation_time(self):
        sim = Simulation(
            SimulationOptions(end_time=1),
            models={"timeout": TimeoutLP}
        )

        lp = sim.create_lp(0, "timeout")
        sim.dispatcher = SpeCoEventLoop(end_time=1)

        sim.run()

        self.assertIsNotNone(
            lp.timed_out_at,
            "Timeout never fired"
        )
        self.assertAlmostEqual(lp.timed_out_at, 0.5)

    def test_event_before_deadline(self):
        sim = Simulation(
            SimulationOptions(end_time=1),
            models={"message": EarlyMessageLP}
        )

        lp = sim.create_lp(0, "message")
        sim.dispatcher = SpeCoEventLoop(end_time=1)

        sim.run()

        self.assertAlmostEqual(lp.received_at, 0.2)


if __name__ == "__main__":
    unittest.main()
