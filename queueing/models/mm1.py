"""M/M/1: one server and an unbounded FCFS queue."""
from ..base import QueueingModel
from ..analytics import mm1 as analytical


class MM1(QueueingModel):
    """M/M/1 model; ``capacity=None`` means infinite total capacity."""
    def __init__(self, arrival_rate, service_rate, **kwargs):
        super().__init__(arrival_rate, service_rate, servers=1, capacity=None, **kwargs)

    def analytical(self): return analytical(self.arrival_rate, self.service_rate)
