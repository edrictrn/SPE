import asyncio
import unittest

from bkitevsim.core import Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess, BkSysFuture
from spe_core.coroutine_loop import SpeCoEventLoop


class WaitingLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.cancelled_at = None

    async def coroutine_run(self):
        try:
            await self.wait_for("NEVER", timeout=0.8)
        except asyncio.CancelledError:
            self.cancelled_at = self._event_loop.current_time
            raise


class CancellingLP(BkSysCoLogicalProcess):
    async def coroutine_run(self):
        await self.wait_until(0.2)
        self._event_loop._lp_coroutines[0].cancel()


class TestFutureCancellation(unittest.TestCase):
    def test_future_resolves(self):
        async def scenario():
            loop = SpeCoEventLoop(end_time=1)
            future = loop.create_future()
            self.assertIsInstance(future, BkSysFuture)

            async def consumer():
                return await future

            task = asyncio.create_task(consumer())
            await asyncio.sleep(0)
            future.set_result(42)
            return await task

        self.assertEqual(asyncio.run(scenario()), 42)

    def test_cancellation_removes_event_waiter(self):
        sim = Simulation(
            SimulationOptions(end_time=1),
            models={"waiting": WaitingLP, "canceller": CancellingLP},
        )
        waiting = sim.create_lp(0, "waiting")
        sim.create_lp(1, "canceller")
        sim.dispatcher = SpeCoEventLoop(end_time=1)

        sim.run()

        self.assertAlmostEqual(waiting.cancelled_at, 0.2)
        self.assertEqual(sim.dispatcher._event_waiters["NEVER"], [])


if __name__ == "__main__":
    unittest.main()
