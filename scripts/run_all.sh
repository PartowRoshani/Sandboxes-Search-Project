#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q
python -m sandgrid solve --example professor --algorithm ucs --html results/example_4x2_ucs.html
python -m sandgrid analyze --rows 5 --cols 2 --output results/exhaustive_5x2
python -m sandgrid benchmark --rows 5 --cols 2 --count 30 --output results/benchmark_30.csv
