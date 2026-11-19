# SPE – System Performance Evaluation

CO3007 course project, group SPE-CC-00A. This project simulates six queueing
models and a two-station network to compare asynchronous communication
using asyncio with sequential processing.

## How to run

Requires Python 3.11+ and the lecturer's BkiTevSim framework.
Run from `SPE-main` or `spe-dev3`. Adjust the framework path if needed.

```bash
if [ -d spe-dev3/experiments ]; then cd spe-dev3; fi
export PYTHONPATH="$PWD/../../hk261_spe_BKsyspeEvsim${PYTHONPATH:+:$PYTHONPATH}"

# Run tests
python3 -m unittest discover -s tests

# Run experiments in a new results directory each time
mkdir -p results && study_dir=$(mktemp -d results/study.XXXXXX) &&
  python3 -m experiments --out "$study_dir/output"
```

CSV and JSON results are saved in `$study_dir/output`.
To run only M/M/1, add `--case mm1` to the experiment command.

Generate plots in the same terminal using a Python environment with `matplotlib` installed:

```bash
python3 -m experiments.plot "$study_dir/output"
```
