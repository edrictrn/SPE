"""Regression tests for asynchronous communication and task failures."""
import unittest

from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess
from spe_core.coroutine_loop import SpeCoEventLoop


def simulate(models, end_time=1.0):
    sim = Simulation(SimulationOptions(end_time=end_time), models=models)
    return sim


class EarlyBufferedLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.received = None
        self.buffer_left = None

    async def coroutine_run(self):
        self.send_event(Event(0.1, self.lp_id, self.lp_id, "MESSAGE", {"seq": 1}))
        await self.wait_until(0.2)
        self.received = await self.wait_for("MESSAGE", timeout=0.4)
        self.buffer_left = len(self._pending_events)


class TwoMessagesLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.received = []

    async def coroutine_run(self):
        self.send_event(Event(0.1, self.lp_id, self.lp_id, "MESSAGE", {"seq": 1}))
        self.send_event(Event(0.15, self.lp_id, self.lp_id, "OTHER", {"seq": 0}))
        self.send_event(Event(0.2, self.lp_id, self.lp_id, "MESSAGE", {"seq": 2}))
        await self.wait_until(0.3)
        self.received.append((await self.wait_for("MESSAGE", timeout=0.5)).payload["seq"])
        self.received.append((await self.wait_for("MESSAGE", timeout=0.5)).payload["seq"])
        self.received.append((await self.wait_for("OTHER", timeout=0.5)).payload["seq"])


class ImmediateWaitLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.got = None
        self.buffer_left = None

    async def coroutine_run(self):
        self.send_event(Event(0.1, self.lp_id, self.lp_id, "MESSAGE"))
        self.got = await self.wait_for("MESSAGE", timeout=0.4)
        self.buffer_left = len(self._pending_events)


class CrashingHandlerLP(BkSysCoLogicalProcess):
    async def coroutine_run(self):
        self.send_event(Event(0.1, self.lp_id, self.lp_id, "BOOM"))
        await self.wait_until(0.5)

    def handle_event(self, event):
        raise RuntimeError("handler crash")


class RequesterLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.received_at = None
        self.trace = None

    async def coroutine_run(self):
        self.send_event(Event(0.1, self.lp_id, 1, "REQUEST", {"request_id": 42}))
        reply = await self.wait_for("REPLY", timeout=0.6)
        self.received_at = reply.timestamp
        self.trace.append(("reply", reply.timestamp))


class WorkerLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.trace = None

    async def coroutine_run(self):
        request = await self.wait_for("REQUEST", timeout=0.5)
        self.trace.append(("request", request.timestamp))
        await self.wait_until(0.3)
        self.send_event(Event(self._event_loop.current_time, self.lp_id, 0, "REPLY", request.payload))


class IndependentLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.trace = None

    async def coroutine_run(self):
        await self.wait_until(0.2)
        self.trace.append(("independent", self._event_loop.current_time))




class AtDeadlineLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.received = None

    async def coroutine_run(self):
        self.send_event(Event(0.5, self.lp_id, self.lp_id, "MESSAGE"))
        self.received = await self.wait_for("MESSAGE", timeout=0.5)


class BufferNoTimeoutLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id):
        super().__init__(lp_id)
        self.received = None

    async def coroutine_run(self):
        self.send_event(Event(0.1, self.lp_id, self.lp_id, "MESSAGE"))
        await self.wait_until(0.2)
        self.received = await self.wait_for("MESSAGE")


class TestAsyncRegressions(unittest.TestCase):
    def test_message_at_deadline_is_delivered_before_timeout(self):
        sim = simulate({"lp": AtDeadlineLP})
        lp = sim.create_lp(0, "lp")
        sim.dispatcher = SpeCoEventLoop(end_time=1)
        sim.run()
        self.assertAlmostEqual(lp.received.timestamp, 0.5)

    def test_buffered_message_without_timeout(self):
        sim = simulate({"lp": BufferNoTimeoutLP})
        lp = sim.create_lp(0, "lp")
        sim.dispatcher = SpeCoEventLoop(end_time=1)
        sim.run()
        self.assertAlmostEqual(lp.received.timestamp, 0.1)

    def test_message_buffered_before_wait_is_consumed(self):
        sim = simulate({"lp": EarlyBufferedLP})
        lp = sim.create_lp(0, "lp")
        sim.dispatcher = SpeCoEventLoop(end_time=1)
        sim.run()
        self.assertIsNotNone(lp.received)
        self.assertAlmostEqual(lp.received.timestamp, 0.1)
        self.assertEqual(lp.buffer_left, 0)

    def test_buffered_message_fifo_and_other_type(self):
        sim = simulate({"lp": TwoMessagesLP})
        lp = sim.create_lp(0, "lp")
        sim.dispatcher = SpeCoEventLoop(end_time=1)
        sim.run()
        self.assertEqual(lp.received, [1, 2, 0])

    def test_direct_waiter_receives_event_only_once(self):
        sim = simulate({"lp": ImmediateWaitLP})
        lp = sim.create_lp(0, "lp")
        sim.dispatcher = SpeCoEventLoop(end_time=1)
        sim.run()
        self.assertIsNotNone(lp.got)
        self.assertEqual(lp.buffer_left, 0)

    def test_handle_event_failure_is_propagated(self):
        sim = simulate({"lp": CrashingHandlerLP})
        sim.create_lp(0, "lp")
        sim.dispatcher = SpeCoEventLoop(end_time=1)
        with self.assertRaisesRegex(RuntimeError, "handler crash"):
            sim.run()

    def test_other_lp_progresses_while_requester_waits(self):
        sim = simulate({"requester": RequesterLP, "worker": WorkerLP, "other": IndependentLP})
        requester = sim.create_lp(0, "requester")
        worker = sim.create_lp(1, "worker")
        independent = sim.create_lp(2, "other")
        trace = []
        requester.trace = worker.trace = independent.trace = trace
        sim.dispatcher = SpeCoEventLoop(end_time=1)
        stats = sim.run()
        self.assertEqual(trace, [("request", 0.1), ("independent", 0.2), ("reply", 0.3)])
        self.assertAlmostEqual(requester.received_at, 0.3)
        self.assertEqual(stats["events_processed"], 2)


if __name__ == "__main__":
    unittest.main()
