"""JSON-configured paired experiment with per-run results and 95% intervals."""

import argparse
import csv
import json
import math
import platform
from pathlib import Path
from statistics import fmean, stdev
import sys

from .simulation import simulate

# Two-sided Student t critical values (0.975 quantile) for df 1 through 30.
T975 = (
    12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
    2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
    2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
)
TIMING_FIELDS = {"wall_seconds", "events_per_second", "arrivals_while_waiting"}


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as output:
        columns = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(output, columns)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def intervals(rows, case, mode):
    for key in rows[0]:
        values = [row[key] for row in rows if row[key] is not None]
        if not values:
            continue
        n = len(values)
        mean = fmean(values)
        half = T975[n - 2] * stdev(values) / math.sqrt(n) if n > 1 else None
        yield {"case_id": case["id"], "arrival_rate": case["arrival_rate"],
               "overload": case.get("overload", False), "mode": mode,
               "metric": key, "n": n, "mean": mean,
               "ci95_low": mean - half if half is not None else None,
               "ci95_high": mean + half if half is not None else None}


def reference_metrics(case, reference):
    if reference is None:
        return {}
    rejection = reference.get("blocking_probability", 0)
    return {
        "waiting_time": reference["Wq"], "response_time": reference["W"],
        "average_queue_length": reference["Lq"], "server_utilization": reference.get("utilization"),
        "throughput": case["arrival_rate"] * (1 - rejection), "rejection_probability": rejection,
    }


def run_study(config, output, selected):
    duration, seeds = config["duration"], config["seeds"]
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and positive")
    if not 2 <= len(seeds) <= 31 or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("provide 2–31 distinct integer seeds")
    cases = [
        dict(case, arrival_rate=rate)
        for case in config["cases"] if not selected or case["id"] in selected
        for rate in case["arrival_rates"]
    ]
    keys = {(case["id"], case["arrival_rate"]) for case in cases}
    if not cases or len(keys) != len(cases) or set(selected) - {case["id"] for case in cases}:
        raise ValueError("case selection must resolve to unique case IDs and rates")

    raw, summaries = [], []
    first_async = None
    for case in cases:
        by_mode = {"asyncio": [], "sequential": [], "paired": []}
        for index, seed in enumerate(seeds):
            pair = {}
            modes = ("asyncio", "sequential") if index % 2 == 0 else ("sequential", "asyncio")
            for mode in modes:
                metrics, reference, _ = simulate(case, seed, duration, mode)
                pair[mode] = metrics
                by_mode[mode].append(metrics)
                raw.append({"case_id": case["id"], "model": case["model"], "mode": mode,
                            "seed": seed, "duration": duration, "arrival_rate": case["arrival_rate"],
                            "service_rate": case["service_rate"], "service_rate_2": case.get("service_rate_2"),
                            "servers": case.get("servers"), "capacity": case.get("capacity"),
                            "overload": case.get("overload", False), **metrics})
            for key in pair["asyncio"].keys() - TIMING_FIELDS:
                if pair["asyncio"][key] != pair["sequential"][key]:
                    raise RuntimeError(f"Simulation mismatch: {case['id']} seed={seed} metric={key}")
            async_time, seq_time = (pair[mode]["wall_seconds"] for mode in ("asyncio", "sequential"))
            by_mode["paired"].append({"wall_ratio_async_over_seq": async_time / seq_time,
                                      "wall_difference_seconds": async_time - seq_time})
            if first_async is None:
                first_async = (case, seed)
        expected = reference_metrics(case, reference)
        for mode, rows in by_mode.items():
            for row in intervals(rows, case, mode):
                theory = expected.get(row["metric"])
                row["steady_state_reference"] = theory if mode != "paired" else None
                summaries.append(row)

    case, seed = first_async
    _, _, trace = simulate(case, seed, duration, "asyncio", trace=True)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "runs.csv", raw)
    write_csv(output / "summary.csv", summaries)
    write_json(output / "results.json", {
        "config": config, "selected_cases": selected, "python": sys.version,
        "platform": platform.platform(), "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: None)(),
        "runs": raw, "summary": summaries,
        "trace": {"case_id": case["id"], "arrival_rate": case["arrival_rate"], "seed": seed, "events": trace},
    })
    print(f"{len(cases)} configurations, {len(raw)} runs -> {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("study.json"))
    parser.add_argument("--out", type=Path, required=True, help="New directory for the run")
    parser.add_argument("--case", action="append", default=[], help="Repeat to select multiple case IDs")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must be a new directory")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    run_study(config, args.out, args.case)


if __name__ == "__main__":
    main()
