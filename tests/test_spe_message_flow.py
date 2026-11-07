
import unittest

from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess

from spe_core.coroutine_loop import SpeCoEventLoop


class SenderLP(BkSysCoLogicalProcess):

    async def coroutine_run(self):
        self.send_event(Event(
            timestamp=0.2,
            sender_id=self.lp_id,
            receiver_id=1,
            event_type="MESSAGE",
            payload={"request_id": 42}
        ))


class ReceiverLP(BkSysCoLogicalProcess):

    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.result = None

    async def coroutine_run(self):
        event = await self.wait_for("MESSAGE")

        self.result = (
            event.timestamp,
            event.payload["request_id"]
        )


class TestMessageFlow(unittest.TestCase):

    def test_async_message_delivery(self):
        sim = Simulation(
            SimulationOptions(end_time=1),
            models={
                "sender": SenderLP,
                "receiver": ReceiverLP
            }
        )

        sim.create_lp(0, "sender")
        receiver = sim.create_lp(1, "receiver")

        sim.dispatcher = SpeCoEventLoop(end_time=1)

        stats = sim.run()

        self.assertEqual(receiver.result, (0.2, 42))
        self.assertEqual(stats["events_processed"], 1)


if __name__ == "__main__":
    unittest.main()
