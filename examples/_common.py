from queueing import MM1, MM1K, MMInf, MMNN, MMC, MMCK


def show(model, horizon=10000):
    result=model.run(horizon)
    print(type(model).__name__, "state:", model.state())
    print("time averages:", {k: result[k] for k in
          ("average_system_population", "average_queue_length", "average_busy_servers")})
    try: print("analytical:", model.analytical())
    except ValueError as exc: print("analytical steady state unavailable:", exc)


def create(kind):
    return {"mm1": lambda: MM1(2,3,seed=42),
            "mm1k": lambda: MM1K(4,3,5,seed=42),
            "mminf": lambda: MMInf(2,3,seed=42),
            "mnn": lambda: MMNN(4,3,3,seed=42),
            "mmc": lambda: MMC(4,3,2,seed=42),
            "mmck": lambda: MMCK(4,3,2,5,seed=42)}[kind]()
