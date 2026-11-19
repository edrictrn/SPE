"""Reproducible two-station tandem network example."""

import math
import random

from ..base import Customer, QueueingModel


class TwoStationNetwork:
    """External Poisson traffic routed through station one and optionally two.

    Stations are separate queueing models sharing one timestamp-ordered event
    heap. All external customers enter station one; completed station-one
    customers are sent to station two with probability ``routing_probability``.
    """
    def __init__(self, arrival_rate, service_rate_1, service_rate_2,
                 routing_probability=1.0, seed=None, servers_1=1, servers_2=1,
                 capacity_1=None, capacity_2=None):
        if not 0 <= routing_probability <= 1: raise ValueError("routing probability must be in [0, 1]")
        if not all(map(math.isfinite, (arrival_rate, service_rate_1, service_rate_2))):
            raise ValueError("rates must be finite")
        if arrival_rate <= 0 or service_rate_1 <= 0 or service_rate_2 <= 0:
            raise ValueError("rates must be positive")
        import heapq
        self._heap=[]
        self._rng=random.Random(seed)
        self._adapter=_HeapAdapter(self._heap)
        self.station_1=QueueingModel(arrival_rate,service_rate_1,servers_1,capacity_1,
                                    rng=self._rng,event_queue=self._adapter,station_id="station_1")
        self.station_2=QueueingModel(arrival_rate,service_rate_2,servers_2,capacity_2,
                                    rng=self._rng,event_queue=self._adapter,station_id="station_2")
        # Initial arrival belongs only to station one; station two's default
        # generator is removed and its arrival rate disabled for network runs.
        self._heap.clear()
        self.station_1._schedule_arrival(self.station_1.arrival_sampler.sample())
        self.routing_probability=routing_probability
        self.route_draws=random.Random(None if seed is None else seed+1)
        self.now=0.0; self._sequence=0

    def run(self, until, max_events=None):
        import heapq
        if until < self.now or not math.isfinite(until):
            raise ValueError("until must be finite and >= current time")
        if max_events is not None and (not isinstance(max_events, int) or max_events < 0):
            raise ValueError("max_events must be a nonnegative integer or None")
        events=0; routed=[]
        while self._heap and self._heap[0][0] <= until and (max_events is None or events<max_events):
            _,_,_,event=heapq.heappop(self._heap)
            model=self.station_1 if event.source_station=="station_1" else self.station_2
            model._integrate(event.timestamp); model.now=event.timestamp
            model.event_counts[event.event_type]=model.event_counts.get(event.event_type,0)+1
            if event.event_type in ("EXTERNAL_ARRIVAL","TRANSFER_ARRIVAL"):
                model._arrival(event)
            elif event.event_type=="SERVICE_COMPLETE":
                model._complete(event)
                if model is self.station_1 and self.route_draws.random()<self.routing_probability:
                    # Model two accepts the customer at the same time, with
                    # the original ID and original arrival time preserved.
                    self.station_2.customers[event.customer_id]=Customer(
                        event.customer_id, event.timestamp)
                    self.station_2._push(type(event)(event.timestamp,"TRANSFER_ARRIVAL",event.customer_id,
                                                      "station_2","station_2"))
                    routed.append(event.customer_id)
            events+=1; self.now=event.timestamp
        stopped_early = (max_events is not None and events >= max_events
                         and self._heap and self._heap[0][0] <= until)
        if not stopped_early:
            for model in (self.station_1,self.station_2):
                model._integrate(until); model.now=until
            self.now=until
        return {"time":self.now,"events_processed":events,"station_1":self.station_1.state(),
                "station_2":self.station_2.state(),"routed_customer_ids":tuple(routed),
                "station_1_metrics":self.station_1.metrics(),
                "station_2_metrics":self.station_2.metrics(),
                "station_1_observations":tuple(self.station_1.observations),
                "station_2_observations":tuple(self.station_2.observations)}


class _HeapAdapter:
    """Dev1-like event queue wrapper over a shared heap."""
    def __init__(self, heap): self.heap=heap; self.sequence=0
    def push(self,event):
        import heapq
        priority={"SERVICE_COMPLETE":0,"TRANSFER_ARRIVAL":1,"EXTERNAL_ARRIVAL":2}.get(event.event_type,3)
        self.sequence+=1; heapq.heappush(self.heap,(event.timestamp,priority,self.sequence,event))
    def pop(self):
        import heapq
        return heapq.heappop(self.heap)[3] if self.heap else None
    def peek(self): return self.heap[0][3] if self.heap else None
