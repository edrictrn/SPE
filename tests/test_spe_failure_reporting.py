import unittest

from bkitevsim.core import Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess
from spe_core.coroutine_loop import SpeCoEventLoop


class CrashingLP(BkSysCoLogicalProcess):

    async def coroutine_run(self):
        raise RuntimeError("test crash")


class TestFailureReporting(unittest.TestCase):

    def test_coroutine_exception_is_reported(self):
        sim = Simulation(
            SimulationOptions(end_time=1),
            models={"crash": CrashingLP}
        )

        sim.create_lp(0, "crash")
        sim.dispatcher = SpeCoEventLoop(end_time=1)

        with self.assertRaisesRegex(RuntimeError, "test crash"):
            sim.run()


if __name__ == "__main__":
    unittest.main()