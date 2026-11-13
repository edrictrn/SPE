"""M/M/c: c servers and an unbounded FCFS queue."""
from ..base import QueueingModel
from ..analytics import mmc as analytical


class MMC(QueueingModel):
    """M/M/c; analytical steady state requires lambda < c*mu."""
    def __init__(self, arrival_rate, service_rate, c, **kwargs):
        super().__init__(arrival_rate, service_rate, servers=c, capacity=None, **kwargs)
        self.c = c

    def analytical(self): return analytical(self.arrival_rate, self.service_rate, self.c)
