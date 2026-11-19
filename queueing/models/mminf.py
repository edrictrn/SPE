"""M/M/infinity: infinite servers and no waiting."""
from ..base import QueueingModel
from ..analytics import mminf as analytical


class MMInf(QueueingModel):
    """M/M/∞ model; every arrival starts service immediately."""
    def __init__(self, arrival_rate, service_rate, **kwargs):
        super().__init__(arrival_rate, service_rate, servers=None, capacity=None, **kwargs)

    def analytical(self): return analytical(self.arrival_rate, self.service_rate)
