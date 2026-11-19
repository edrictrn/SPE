"""Plot results from a completed study directory (requires matplotlib)."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def plot(directory):
    data = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    rows = data["summary"]
    names = list(dict.fromkeys(row["case_id"] for row in rows))

    figure, (overhead, response) = plt.subplots(1, 2, figsize=(13, 6), layout="constrained")
    for name in names:
        results = sorted((row for row in rows if row["case_id"] == name
                          and row["mode"] == "paired"
                          and row["metric"] == "wall_ratio_async_over_seq"),
                         key=lambda row: row["arrival_rate"])
        if results:
            overhead.plot([row["arrival_rate"] for row in results],
                          [row["mean"] for row in results], marker="o", label=name)
    overhead.axhline(1, color="gray", linestyle="--")
    overhead.set(xlabel="Arrival rate", ylabel="Asyncio / sequential wall time",
                 title="Paired runtime comparison")
    overhead.legend(fontsize="small", ncols=2)

    for name in ("mm1", "tandem", "mm1-overload"):
        results = sorted((row for row in rows if row["case_id"] == name
                          and row["mode"] == "asyncio" and row["metric"] == "response_time"
                          and row["ci95_low"] is not None), key=lambda row: row["arrival_rate"])
        if results:
            response.errorbar([row["arrival_rate"] for row in results],
                              [row["mean"] for row in results],
                              yerr=[row["mean"] - row["ci95_low"] for row in results],
                              marker="o", capsize=4, label=name)
    response.set(xlabel="Arrival rate", ylabel="Mean response (simulation time)",
                 title="Response time with 95% confidence intervals")
    if response.has_data():
        response.legend()
    for axis in (overhead, response):
        axis.grid(alpha=0.2)
    figure.savefig(directory / "comparison.png", dpi=180)
    plt.close(figure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    plot(parser.parse_args().results)
