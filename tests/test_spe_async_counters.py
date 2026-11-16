"""Counters that reflect observed async operations, not inferred speedup."""
import asyncio
import unittest
from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess
from spe_core.coroutine_loop import SpeCoEventLoop


class CounterLP(BkSysCoLogicalProcess):
    async def coroutine_run(self):
        self.send_event(Event(0.1, self.lp_id, self.lp_id, "ONE"))
        await self.wait_for("ONE", timeout=0.5)
        self.send_event(Event(0.2, self.lp_id, self.lp_id, "TWO"))
        await self.wait_until(0.3)
        await self.wait_for("TWO", timeout=0.5)
        try:
            await self.wait_for("MISSING", timeout=0.1)
        except asyncio.TimeoutError:
            pass


class TestAsyncCounters(unittest.TestCase):
    def test_counters_track_real_operations(self):
        sim = Simulation(SimulationOptions(end_time=1), models={"counter": CounterLP})
        sim.create_lp(0, "counter")
        sim.dispatcher = SpeCoEventLoop(end_time=1)
        stats = sim.run()
        self.assertEqual(stats["coroutines_scheduled"], 1)
        self.assertEqual(stats["events_processed"], 2)
        self.assertEqual(stats["buffered_event_reads"], 1)
        self.assertEqual(stats["event_waits_registered"], 2)
        self.assertEqual(stats["event_waits_resumed"], 1)
        self.assertEqual(stats["virtual_timeouts"], 1)


if __name__ == "__main__":
    unittest.main()
