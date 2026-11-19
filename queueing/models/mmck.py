"""M/M/c/K: c servers and K total places."""
from ..base import QueueingModel
from ..analytics import mmck as analytical


class MMCK(QueueingModel):
    """M/M/c/K with K >= c and total capacity including service."""
    def __init__(self, arrival_rate, service_rate, c, K, **kwargs):
        super().__init__(arrival_rate, service_rate, servers=c, capacity=K, **kwargs)
        self.c, self.K = c, K

    def analytical(self): return analytical(self.arrival_rate, self.service_rate, self.c, self.K)
