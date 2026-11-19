"""M/M/n/n Erlang loss model."""
from ..base import QueueingModel
from ..analytics import mnn as analytical


class MMNN(QueueingModel):
    """M/M/n/n with n servers and no waiting room."""
    def __init__(self, arrival_rate, service_rate, n, **kwargs):
        super().__init__(arrival_rate, service_rate, servers=n, capacity=n, **kwargs)
        self.n = n

    def analytical(self): return analytical(self.arrival_rate, self.service_rate, self.n)
