"""Finite Poisson arrival generation helpers."""
import math

from .distributions import ExponentialSampler


def poisson_arrivals(rate, horizon, seed=None, max_arrivals=None):
    """Return event times in [0, horizon], using exponential inter-arrivals."""
    if not math.isfinite(horizon) or horizon < 0:
        raise ValueError("horizon must be finite and nonnegative")
    if max_arrivals is not None and (not isinstance(max_arrivals, int) or max_arrivals < 0):
        raise ValueError("max_arrivals must be a nonnegative integer or None")
    sampler=ExponentialSampler(rate, seed=seed)
    times=[]; now=0.0
    while max_arrivals is None or len(times)<max_arrivals:
        now += sampler.sample()
        if now > horizon: break
        times.append(now)
    return times
