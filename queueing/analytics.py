"""Steady-state analytical references for supported M/M models."""

import math


def _rates(lam, mu):
    if not math.isfinite(lam) or lam <= 0 or not math.isfinite(mu) or mu <= 0:
        raise ValueError("arrival and service rates must be finite and positive")


def mm1(lam, mu):
    _rates(lam, mu)
    if lam >= mu: raise ValueError("M/M/1 steady state requires lambda < mu")
    rho = lam / mu
    return {"utilization": rho, "L": rho/(1-rho), "Lq": rho*rho/(1-rho),
            "W": 1/(mu-lam), "Wq": rho/(mu-lam)}


def mm1k(lam, mu, K):
    _rates(lam, mu)
    if not isinstance(K, int) or K < 1: raise ValueError("K must be a positive integer")
    log_rho = math.log(lam) - math.log(mu)
    log_weights = [n * log_rho for n in range(K + 1)]
    max_log = max(log_weights)
    scaled = [math.exp(value - max_log) for value in log_weights]
    normalizer = sum(scaled)
    probs = [value / normalizer for value in scaled]
    p0 = probs[0]
    blocking = probs[-1]; eff = lam*(1-blocking); L=sum(n*p for n,p in enumerate(probs))
    Lq = L - (1 - p0)
    return {"state_probabilities": tuple(probs), "P0": p0, "blocking_probability": blocking,
            "effective_arrival_rate": eff, "L": L, "Lq": Lq,
            "W": L/eff if eff else 0.0, "Wq": Lq/eff if eff else 0.0}


def mminf(lam, mu):
    _rates(lam, mu); return {"L": lam/mu, "Lq": 0.0, "W": 1/mu, "Wq": 0.0}


def erlang_b(lam, mu, n):
    _rates(lam, mu)
    if not isinstance(n, int) or n < 1: raise ValueError("n must be a positive integer")
    a=lam/mu; b=1.0
    for i in range(1,n+1): b=a*b/(i+a*b)
    return b


def mnn(lam, mu, n):
    b=erlang_b(lam,mu,n); eff=lam*(1-b)
    return {"blocking_probability":b,"effective_arrival_rate":eff,"utilization":eff/(n*mu),"L":eff/mu,"Lq":0.0,"W":1/mu,"Wq":0.0}


def mmc(lam, mu, c):
    _rates(lam,mu)
    if not isinstance(c,int) or c<1: raise ValueError("c must be a positive integer")
    a=lam/mu; rho=lam/(c*mu)
    if rho>=1: raise ValueError("M/M/c steady state requires lambda < c*mu")
    terms=[a**n/math.factorial(n) for n in range(c)]
    tail=a**c/(math.factorial(c)*(1-rho))
    p0=1/(sum(terms)+tail); pw=tail*p0; Lq=pw*rho/(1-rho)
    L=Lq+a; Wq=Lq/lam; W=Wq+1/mu
    return {"P0":p0,"probability_wait":pw,"utilization":rho,"Lq":Lq,"L":L,"Wq":Wq,"W":W}


def mmck(lam,mu,c,K):
    _rates(lam,mu)
    if not isinstance(c,int) or c<1 or not isinstance(K,int) or K<c: raise ValueError("require integer K >= c >= 1")
    log_weights=[0.0]
    for n in range(1,K+1):
        log_weights.append(log_weights[-1]+math.log(lam)-math.log(min(n,c)*mu))
    scale=max(log_weights)
    weights=[math.exp(value-scale) for value in log_weights]
    total=sum(weights); probs=[weight/total for weight in weights]
    L=sum(n*p for n,p in enumerate(probs)); Lq=sum(max(0,n-c)*p for n,p in enumerate(probs))
    block=probs[K]; eff=lam*(1-block)
    return {"state_probabilities":tuple(probs),"P0":probs[0],"blocking_probability":block,
            "effective_arrival_rate":eff,"L":L,"Lq":Lq,"W":L/eff if eff else 0.0,
            "Wq":Lq/eff if eff else 0.0,"utilization":(L-Lq)/(c)}
