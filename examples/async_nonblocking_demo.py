"""Small proof of non-blocking LP communication (NOT a performance study).

Run from the repo root: py -m examples.async_nonblocking_demo
"""

from bkitevsim.core import Event, Simulation, SimulationOptions
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess
from spe_core.coroutine_loop import SpeCoEventLoop


TRACE = []


class Client(BkSysCoLogicalProcess):
    async def coroutine_run(self):
        self.send_event(Event(0.1, self.lp_id, 1, "REQUEST", {"id": 42}))
        TRACE.append(("client awaits", 0.1))
        reply = await self.wait_for("REPLY", timeout=0.6)
        TRACE.append(("client receives reply", reply.timestamp))


class Worker(BkSysCoLogicalProcess):
    async def coroutine_run(self):
        request = await self.wait_for("REQUEST")
        TRACE.append(("worker receives request", request.timestamp))
        await self.wait_until(0.3)  # Simulated, not wall-clock, I/O delay.
        self.send_event(Event(0.3, self.lp_id, 0, "REPLY", request.payload))


class IndependentTask(BkSysCoLogicalProcess):
    async def coroutine_run(self):
        await self.wait_until(0.2)
        TRACE.append(("independent task progresses", self._event_loop.current_time))


def main():
    TRACE.clear()
    sim = Simulation(
        SimulationOptions(end_time=1.0),
        models={"client": Client, "worker": Worker, "independent": IndependentTask},
    )
    sim.create_lp(0, "client")
    sim.create_lp(1, "worker")
    sim.create_lp(2, "independent")
    sim.dispatcher = SpeCoEventLoop(end_time=1.0)
    stats = sim.run()
    for label, virtual_time in TRACE:
        print(f"virtual t={virtual_time:.1f}: {label}")
    print("events_processed:", stats["events_processed"])
    print("coroutines_scheduled:", stats["coroutines_scheduled"])
    print("wall_time_seconds:", round(stats["wall_time"], 6))
    print("Note: this only demonstrates cooperative progress, not an async speedup.")


if __name__ == "__main__":
    main()
