# SPE – System Performance Evaluation

## Project Overview

Discrete-Event Simulation (DES) of Queueing Systems.

**Course:** CO3007 – System Performance Evaluation  
**Group:** SPE-CC-00A

## Project Objectives

- Implement six queueing models: M/M/1, M/M/1/K, M/M/∞, M/M/n/n, M/M/c, and M/M/c/K.
- Simulate a queueing network.
- Support event-driven simulation and asynchronous operations.
- Evaluate system performance using simulation experiments.

## Development Responsibilities

- **DEV1:** Event queue, dispatcher, virtual time, and asynchronous operations.
- **DEV2:** Six queueing models and a two-station network. Models expose event
  counts, per-customer waiting/service/sojourn observations, state snapshots,
  and time-integrated population/queue/busy-server metrics.
- **DEV3:** Replications, confidence intervals, experiment design, and final
  statistical reporting. DEV3 can consume the `run()` result dictionary and
  `customer_observations`; it should own aggregation across replications.

## Framework

This project is designed around the lecturer-provided BkiTevSim framework for
CO3007. The local `bkitevsim` package is not included in this checkout. Dev2's
queueing models run independently and accept a Dev1-style `EventQueue` through
`event_queue=`. With BkiTevSim installed, `QueueingModel.register_with_dispatcher`
registers a queue model as a logical process in Dev1's sequential dispatcher.

## Queueing models

| Model | Servers | Waiting capacity | Total capacity |
|---|---:|---:|---:|
| M/M/1 | 1 | Infinite | Infinite |
| M/M/1/K | 1 | K-1 | K |
| M/M/∞ | Infinite | 0 | Infinite |
| M/M/n/n | n | 0 | n |
| M/M/c | c | Infinite | Infinite |
| M/M/c/K | c | K-c | K |

Arrival and service rates are positive rates per unit of simulation time. `K`
includes customers in service and waiting; `c`/`n` is the number of servers.
All single-station queues use FCFS. An integer `seed` makes a model repeatable.
Every `run(until)` processes events through the inclusive horizon and returns
a snapshot. Repeated calls advance the same model. `average_*` values are
time-integrated over elapsed time from time zero.

```python
from queueing import MM1

model = MM1(arrival_rate=2.0, service_rate=3.0, seed=42)
result = model.run(until=10_000)
print(result["average_system_population"], model.analytical())
print(result["customer_observations"][0])
```

Analytical helpers live in `queueing.analytics`. They implement M/M/1, M/M/1/K,
M/M/∞, Erlang B / M/M/n/n, M/M/c, and M/M/c/K birth-death references.
Infinite-capacity steady-state formulas require stability (`λ < μ` for M/M/1;
`λ < cμ` for M/M/c). Finite-capacity models have stationary distributions
without that restriction.

## Examples and tests

Run from the repository root:

```bash
python -m examples.run_mm1
python -m examples.run_mm1k
python -m examples.run_mminf
python -m examples.run_mnn
python -m examples.run_mmc
python -m examples.run_mmck
python -m examples.run_two_station
python -m unittest discover -s tests -v
```

The implementation uses only the Python 3.11 standard library. No pip
dependencies are required. Create a local environment and expose the external
framework directory (adjust the relative path if your checkout differs):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
export PYTHONPATH="../hk261_spe_BKsyspeEvsim${PYTHONPATH:+:$PYTHONPATH}"
python -m unittest discover -s tests -v
```

Without the framework directory, run the standalone subsystem tests with
`python -m unittest tests.test_queueing -v`. Framework source remains external.
Dev2 provides raw Python dictionaries and per-customer observation records; it
does not currently write CSV/JSON files or generate plots. DEV3 can serialize
those returned values using its experiment/export layer.

## Limitations

- The two-station demonstration supports external arrivals to station one and
  probabilistic routing of its completions to station two. It is intentionally
  not a general graph/network DSL.
- Dispatcher integration requires the external BkiTevSim runtime. Dev2 uses its
  `Event(timestamp, sender_id, receiver_id, event_type, payload)` contract and
  registers a logical process with the existing sequential dispatcher.
- A compatibility test observed the external framework's `LadderQueue` return
  timestamp 1024 before timestamp 1023 when those events are enqueued in that
  order. The regression is marked as an expected failure because the framework
  is external and its internal cause has not been verified. SPE's own
  `EventQueue` is tested separately.
- Completed-customer observations are emitted on departure; customers still
  in service or waiting at the horizon remain represented in model state.
