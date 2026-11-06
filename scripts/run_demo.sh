#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m sandgrid solve --example professor --algorithm ucs \
  --html results/example_4x2_ucs.html --json-out results/example_4x2_ucs.json
