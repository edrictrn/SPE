"""Shared discrete-event mechanics for Markovian queueing models."""

from collections import deque
from dataclasses import dataclass
import math
import random

from .distributions import ExponentialSampler
from .events import EXTERNAL_ARRIVAL, SERVICE_COMPLETE, TRANSFER_ARRIVAL, QueueEvent


@dataclass
class Customer:
    customer_id: int
    arrival_time: float
    service_start_time: float | None = None
    departure_time: float | None = None
    service_time: float | None = None


class QueueingModel:
    """Event driven queue with a shared virtual clock and observable state.

    ``capacity`` is total population (service plus waiting), or ``None`` for
    unbounded capacity. ``servers=None`` denotes infinitely many servers.
    """

    def __init__(self, arrival_rate, service_rate, servers=1, capacity=None,
                 seed=None, rng=None, event_queue=None, station_id="station"):
        for name, value in (("arrival_rate", arrival_rate), ("service_rate", service_rate)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if servers is not None and (not isinstance(servers, int) or servers < 1):
            raise ValueError("servers must be a positive integer or None")
        if capacity is not None and (not isinstance(capacity, int) or capacity < 1):
            raise ValueError("capacity must be a positive integer or None")
        if servers is not None and capacity is not None and capacity < servers:
            raise ValueError("capacity must be at least the server count")
        if rng is not None and seed is not None:
            raise ValueError("provide either rng or seed, not both")
        self.arrival_rate, self.service_rate = float(arrival_rate), float(service_rate)
        self.servers, self.capacity = servers, capacity
        self.station_id = station_id
        self.rng = rng if rng is not None else random.Random(seed)
        self.arrival_sampler = ExponentialSampler(arrival_rate, rng=self.rng)
        self.service_sampler = ExponentialSampler(service_rate, rng=self.rng)
        self.event_queue = event_queue
        self.now = 0.0
        self._events = []
        self._sequence = 0
        self._next_customer_id = 0
        self._queue = deque()
        self._busy = {}
        self.customers = {}
        self.observations = []
        self.attempted_arrivals = self.accepted_arrivals = self.blocked_arrivals = self.departures = 0
        self.event_counts = {EXTERNAL_ARRIVAL: 0, TRANSFER_ARRIVAL: 0, SERVICE_COMPLETE: 0}
        self._last_state_time = 0.0
        self._last_run_time = 0.0
        self._area_system = self._area_queue = self._area_busy = 0.0
        self._schedule_arrival(self.arrival_sampler.sample())

    def _push(self, event):
        if self.event_queue is not None:
            self.event_queue.push(event)
        else:
            self._sequence += 1
            order = {SERVICE_COMPLETE: 0, TRANSFER_ARRIVAL: 1, EXTERNAL_ARRIVAL: 2}
            import heapq
            heapq.heappush(self._events, (event.timestamp, order.get(event.event_type, 3), self._sequence, event))

    def _pop(self):
        if self.event_queue is not None:
            return self.event_queue.pop()
        import heapq
        return heapq.heappop(self._events)[3] if self._events else None

    def _peek(self):
        if self.event_queue is not None:
            return self.event_queue.peek()
        return self._events[0][3] if self._events else None

    def _schedule_arrival(self, at):
        self._push(QueueEvent(at, EXTERNAL_ARRIVAL, self._next_customer_id, self.station_id))

    @property
    def queue_length(self): return len(self._queue)
    @property
    def busy_servers(self): return len(self._busy)
    @property
    def system_population(self): return len(self._queue) + len(self._busy)

    def state(self):
        """Return a snapshot suitable for DEV3 observation consumers."""
        return {"time": self.now, "system_population": self.system_population,
                "queue_length": self.queue_length, "busy_servers": self.busy_servers,
                "attempted_arrivals": self.attempted_arrivals,
                "accepted_arrivals": self.accepted_arrivals,
                "blocked_arrivals": self.blocked_arrivals, "departures": self.departures}

    def _integrate(self, until):
        dt = until - self._last_state_time
        if dt < 0: raise RuntimeError("simulation time cannot move backwards")
        self._area_system += dt * self.system_population
        self._area_queue += dt * self.queue_length
        self._area_busy += dt * self.busy_servers
        self._last_state_time = until

    def _start_service(self, customer, server):
        customer.service_start_time = self.now
        customer.service_time = self.service_sampler.sample()
        self._busy[server] = customer.customer_id
        self._push(QueueEvent(self.now + customer.service_time, SERVICE_COMPLETE,
                              customer.customer_id, self.station_id,
                              payload={"server": server}))

    def _arrival(self, event):
        self.attempted_arrivals += 1
        cid = event.customer_id
        self._next_customer_id = max(self._next_customer_id, cid + 1)
        if self.capacity is not None and self.system_population >= self.capacity:
            self.blocked_arrivals += 1
        else:
            customer = self.customers.get(cid)
            if customer is None:
                customer = Customer(cid, self.now)
                self.customers[cid] = customer
            self.accepted_arrivals += 1
            if self.servers is None:
                self._start_service(customer, cid)
            else:
                server = next((i for i in range(self.servers) if i not in self._busy), None)
                if server is None: self._queue.append(cid)
                else: self._start_service(customer, server)
        if event.event_type == EXTERNAL_ARRIVAL:
            self._schedule_arrival(self.now + self.arrival_sampler.sample())

    def _complete(self, event):
        cid = event.customer_id
        server = event.payload["server"]
        if self._busy.get(server) != cid: raise RuntimeError("invalid service completion")
        del self._busy[server]
        customer = self.customers[cid]
        customer.departure_time = self.now
        self.departures += 1
        self.observations.append({"customer_id": cid, "arrival_time": customer.arrival_time,
                                  "service_start_time": customer.service_start_time,
                                  "departure_time": self.now,
                                  "waiting_time": customer.service_start_time - customer.arrival_time,
                                  "service_time": customer.service_time,
                                  "sojourn_time": self.now - customer.arrival_time})
        if self._queue:
            next_cid = self._queue.popleft()
            self._start_service(self.customers[next_cid], server)

    def _process_event(self, event):
        """Apply one already-dequeued event at its timestamp."""
        self._integrate(event.timestamp)
        self.now = event.timestamp
        self.event_counts[event.event_type] = self.event_counts.get(event.event_type, 0) + 1
        if event.event_type in (EXTERNAL_ARRIVAL, TRANSFER_ARRIVAL):
            self._arrival(event)
        elif event.event_type == SERVICE_COMPLETE:
            self._complete(event)

    def run(self, until, max_events=None):
        """Process events through ``until`` and return time-weighted metrics."""
        if not math.isfinite(until) or until < self.now: raise ValueError("until must be finite and >= current time")
        if max_events is not None and (not isinstance(max_events, int) or max_events < 0):
            raise ValueError("max_events must be a nonnegative integer or None")
        count = 0
        while (event := self._peek()) is not None and event.timestamp <= until:
            if max_events is not None and count >= max_events: break
            event = self._pop()
            self._process_event(event)
            count += 1
        stopped_early = (max_events is not None and count >= max_events
                         and self._peek() is not None and self._peek().timestamp <= until)
        if not stopped_early:
            self._integrate(until)
            self.now = until
        self._last_run_time = self.now
        return {**self.state(), "events_processed": count,
                "average_system_population": self._area_system / self.now if self.now else 0.0,
                "average_queue_length": self._area_queue / self.now if self.now else 0.0,
                "average_busy_servers": self._area_busy / self.now if self.now else 0.0,
                "server_utilization": self._area_busy / (self.now * self.servers) if self.now and self.servers else None,
                "event_counts": dict(self.event_counts), "customer_observations": tuple(self.observations)}

    def schedule_transfer(self, customer_id, at, destination_station):
        """Schedule the same customer identity as a transfer arrival."""
        if at < self.now: raise ValueError("transfer cannot be scheduled in the past")
        self._push(QueueEvent(at, TRANSFER_ARRIVAL, customer_id, self.station_id,
                              destination_station))

    def register_with_dispatcher(self, dispatcher, lp_id=0):
        """Register this model as a framework LP using Dev1's event clock.

        Register the returned LP with a BkiTevSim sequential dispatcher, then
        let ``dispatcher.run()`` own event ordering, delivery, and virtual time.
        The dispatcher calls ``initialize`` at run start. Model metrics remain
        available on this object; call ``finish(until)`` to integrate through
        the requested horizon after the dispatcher stops.
        """
        from bkitevsim.core import Event, BkSysLogicalProcess

        model = self

        class QueueingLP(BkSysLogicalProcess):
            def initialize(self):
                pending = []
                while model._peek() is not None:
                    pending.append(model._pop())
                model.event_queue = _DispatcherQueue(self, dispatcher, Event)
                for queue_event in pending:
                    model._push(queue_event)

            def handle_event(self, framework_event):
                queue_event = framework_event.payload["queueing_event"]
                model._process_event(queue_event)

        lp = QueueingLP(lp_id)
        dispatcher.register_lp(lp)
        return lp

    def finish(self, until):
        """Integrate model state through ``until`` after dispatcher execution."""
        if not math.isfinite(until) or until < self.now:
            raise ValueError("until must be finite and >= current time")
        self._integrate(until)
        self.now = until
        self._last_run_time = until
        return self.metrics()

    def metrics(self):
        """Return cumulative state and time-weighted observations."""
        duration = self.now
        return {**self.state(),
                "average_system_population": self._area_system / duration if duration else 0.0,
                "average_queue_length": self._area_queue / duration if duration else 0.0,
                "average_busy_servers": self._area_busy / duration if duration else 0.0,
                "server_utilization": self._area_busy / (duration * self.servers)
                    if duration and self.servers else None,
                "event_counts": dict(self.event_counts),
                "customer_observations": tuple(self.observations)}


class _DispatcherQueue:
    """Queueing event adapter that schedules framework Events via its LP."""
    def __init__(self, lp, dispatcher, event_class):
        self.lp, self.dispatcher, self.event_class = lp, dispatcher, event_class

    def push(self, event):
        framework_event = self.event_class(
            timestamp=event.timestamp, sender_id=self.lp.lp_id,
            receiver_id=self.lp.lp_id, event_type=event.event_type,
            payload={"queueing_event": event})
        self.lp.send_event(framework_event)

    def pop(self):
        return None

    def peek(self):
        return None
