"""Random variate helpers used by queueing models."""

import math
import random


def _validate_rate(rate):
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("rate must be finite and positive")


def exponential(rate, rng=None):
    """Sample an exponential duration with the given positive rate."""
    _validate_rate(rate)
    return (rng if rng is not None else random).expovariate(rate)


class ExponentialSampler:
    """Reproducible independent exponential samples."""

    def __init__(self, rate, seed=None, rng=None):
        _validate_rate(rate)
        if rng is not None and seed is not None:
            raise ValueError("provide either rng or seed, not both")
        self.rate = float(rate)
        self.rng = rng if rng is not None else random.Random(seed)

    def sample(self):
        return exponential(self.rate, self.rng)
