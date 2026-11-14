
import unittest

from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess
from spe_core.coroutine_loop import SpeCoEventLoop


class SenderLP(BkSysCoLogicalProcess):
    async def coroutine_run(self):
        self.send_event(Event(
            timestamp=0.2,
            sender_id=self.lp_id,
            receiver_id=999,  # LP này không tồn tại
            event_type="MESSAGE",
        ))


class TestCommunicationFailure(unittest.TestCase):

    def test_message_to_unknown_receiver(self):
        sim = Simulation(
            SimulationOptions(end_time=1),
            models={"sender": SenderLP},
        )

        sim.create_lp(0, "sender")
        sim.dispatcher = SpeCoEventLoop(end_time=1)

        with self.assertRaisesRegex(ValueError, "999"):
            sim.run()


if __name__ == "__main__":
    unittest.main()
