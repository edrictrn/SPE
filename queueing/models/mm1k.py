"""M/M/1/K: one server with K total places."""
from ..base import QueueingModel
from ..analytics import mm1k as analytical


class MM1K(QueueingModel):
    """M/M/1/K with K including customers in service and waiting."""
    def __init__(self, arrival_rate, service_rate, K, **kwargs):
        super().__init__(arrival_rate, service_rate, servers=1, capacity=K, **kwargs)
        self.K = K

    def analytical(self): return analytical(self.arrival_rate, self.service_rate, self.K)
