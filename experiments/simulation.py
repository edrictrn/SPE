"""Run the same request/reply protocol on asyncio and a sequential baseline."""

from collections import deque
from random import Random
from statistics import fmean
from time import perf_counter

from bkitevsim.core import Event
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess
from queueing import MM1, MM1K, MMC, MMCK, MMInf, MMNN
from queueing.events import EXTERNAL_ARRIVAL, SERVICE_COMPLETE, TRANSFER_ARRIVAL, QueueEvent
from queueing.generators import poisson_arrivals
from spe_core.coroutine_loop import SpeCoEventLoop
from spe_core.event_queue import EventQueue

REPLY = "REQUEST_RESULT"
SOURCE = 0


def make_stations(case, seed, send):
    rate, service = case["arrival_rate"], case["service_rate"]

    def options(station):
        return {"rng": Random(f"{seed}:service:{station}"),
                "station_id": str(station), "event_queue": StationEvents(send, station)}

    constructors = {
        "mm1": (MM1, ()), "mm1k": (MM1K, (case.get("capacity"),)),
        "mminf": (MMInf, ()), "mmnn": (MMNN, (case.get("servers"),)),
        "mmc": (MMC, (case.get("servers"),)),
        "mmck": (MMCK, (case.get("servers"), case.get("capacity"))),
    }
    if case["model"] == "tandem":
        return {1: MM1(rate, service, **options(1)),
                2: MM1(rate, case["service_rate_2"], **options(2))}
    constructor, args = constructors[case["model"]]
    return {1: constructor(rate, service, *args, **options(1))}


class StationEvents:
    """Forward service events to the scheduler and let the workload own arrivals."""

    def __init__(self, send, station):
        self.send = send
        self.station = station

    def push(self, event):
        if event.event_type == SERVICE_COMPLETE:
            self.send(Event(event.timestamp, self.station, self.station,
                            SERVICE_COMPLETE, event))


class Endpoint(BkSysCoLogicalProcess):
    # The protocol dispatches application events via the scheduler callback.
    def handle_event(self, event):
        pass

    async def coroutine_run(self):
        pass


class Requester(Endpoint):
    def __init__(self, protocol):
        super().__init__(SOURCE)
        self.protocol = protocol

    async def coroutine_run(self):
        self.protocol.submit_workload()
        while True:
            self.protocol.waiting = True
            await self.wait_for(REPLY)
            self.protocol.waiting = False
            while self.protocol.mailbox:
                self.protocol.receive(self.protocol.mailbox.popleft())


class Protocol:
    def __init__(self, case, seed, duration, send, mode, trace):
        self.send = send
        self.mode = mode
        self.stations = make_stations(case, seed, send)
        self.arrivals = poisson_arrivals(case["arrival_rate"], duration, seed=seed)
        self.pending = set()
        self.replies = {}
        self.mailbox = deque()
        self.waiting = False
        self.arrivals_while_waiting = 0
        self.trace = [] if trace else None

    def record(self, time, action, customer, station=None):
        if self.trace is not None:
            self.trace.append({"time": time, "action": action, "customer_id": customer,
                               "station": station, "outstanding": len(self.pending),
                               "requester_waiting": self.waiting})

    def submit_workload(self):
        for customer, timestamp in enumerate(self.arrivals):
            event = QueueEvent(timestamp, EXTERNAL_ARRIVAL, customer, "1")
            self.send(Event(timestamp, SOURCE, 1, EXTERNAL_ARRIVAL, event))

    def receive(self, message):
        customer, outcome = message.payload
        self.pending.remove(customer)
        self.replies[customer] = outcome
        self.record(message.timestamp, "resume" if self.mode == "asyncio" else "reply",
                    customer, message.sender_id)

    def dispatch(self, message):
        if message.event_type == REPLY:
            self.record(message.timestamp, "notify_" + message.payload[1],
                        message.payload[0], message.sender_id)
            if self.mode == "asyncio":
                self.mailbox.append(message)
            else:
                self.receive(message)
            return

        station, event = message.receiver_id, message.payload
        model = self.stations[station]
        customer = event.customer_id
        if message.event_type == EXTERNAL_ARRIVAL:
            if self.waiting and self.pending:
                self.arrivals_while_waiting += 1
            self.pending.add(customer)
        self.record(message.timestamp, message.event_type, customer, station)
        blocked = model.blocked_arrivals
        model._process_event(event)

        if model.blocked_arrivals > blocked:
            self.send(Event(event.timestamp, station, SOURCE, REPLY, (customer, "rejected")))
        elif message.event_type == SERVICE_COMPLETE:
            if station == 1 and 2 in self.stations:
                transfer = QueueEvent(event.timestamp, TRANSFER_ARRIVAL, customer, "1", "2")
                self.send(Event(event.timestamp, 1, 2, TRANSFER_ARRIVAL, transfer))
            else:
                self.send(Event(event.timestamp, station, SOURCE, REPLY, (customer, "completed")))


def summarize(protocol, duration):
    stations = {station: model.finish(duration) for station, model in protocol.stations.items()}
    first = stations[1]
    arrivals = first["attempted_arrivals"]
    rejected = sum(item["blocked_arrivals"] for item in stations.values())
    last = stations[max(stations)]
    completed = last["departures"]
    unfinished = sum(item["system_population"] for item in stations.values())
    expected = {item["customer_id"]: "completed" for item in last["customer_observations"]}
    if (arrivals != len(protocol.arrivals) or arrivals != rejected + completed + unfinished
            or len(protocol.pending) != unfinished
            or len(protocol.replies) != completed + rejected
            or any(protocol.replies.get(cid) != status for cid, status in expected.items())
            or sum(value == "rejected" for value in protocol.replies.values()) != rejected):
        raise RuntimeError("Request conservation or completion delivery check failed")

    first_records = {item["customer_id"]: item for item in first["customer_observations"]}
    waits, responses = [], []
    for item in last["customer_observations"]:
        initial = first_records[item["customer_id"]]
        waits.append(item["waiting_time"] + (initial["waiting_time"] if 2 in stations else 0))
        responses.append(item["departure_time"] - initial["arrival_time"])

    result = {
        "arrivals": arrivals, "rejected": rejected, "completed": completed, "unfinished": unfinished,
        "waiting_time": fmean(waits) if waits else None,
        "response_time": fmean(responses) if responses else None,
        "throughput": completed / duration, "rejection_probability": rejected / arrivals if arrivals else None,
        "average_queue_length": first["average_queue_length"] if 2 not in stations else None,
        "server_utilization": first["server_utilization"] if 2 not in stations else None,
    }
    if 2 in stations:
        for station, item in stations.items():
            for key in ("average_queue_length", "server_utilization"):
                result[f"station_{station}_{key}"] = item[key]
    return result


def simulate(case, seed, duration, mode, trace=False):
    if mode not in ("asyncio", "sequential"):
        raise ValueError(f"Unknown execution mode: {mode}")
    started = perf_counter()
    if mode == "asyncio":
        loop = SpeCoEventLoop(end_time=duration)
        protocol = Protocol(case, seed, duration, loop.schedule_event, mode, trace)
        requester = Requester(protocol)
        for endpoint in (requester, *(Endpoint(station) for station in protocol.stations)):
            endpoint.set_event_loop(loop)
            loop.register_lp(endpoint)
        loop._on_event = protocol.dispatch  # The framework swallows exceptions in LP handlers.
        count = loop.run()["events_processed"]
    else:
        events = EventQueue()
        protocol = Protocol(case, seed, duration, events.push, mode, trace)
        protocol.submit_workload()
        count = 0
        while (event := events.peek()) is not None and event.timestamp <= duration:
            protocol.dispatch(events.pop())
            count += 1
    elapsed = perf_counter() - started
    result = summarize(protocol, duration)
    result.update(events_processed=count, notifications=len(protocol.replies),
                  wall_seconds=elapsed, events_per_second=count / elapsed if elapsed else None,
                  arrivals_while_waiting=protocol.arrivals_while_waiting if mode == "asyncio" else None)
    try:
        reference = protocol.stations[1].analytical() if 2 not in protocol.stations else None
    except ValueError:
        reference = None
    return result, reference, protocol.trace
