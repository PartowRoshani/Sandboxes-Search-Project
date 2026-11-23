#!/usr/bin/env bash
# Run from any directory. Uses the existing repository's sandgrid model.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m unittest discover -s genetic_alg/tests -v
python -m genetic_alg compare --example professor --population 50 --length 50 \
  --generations 1000 --repeats 3 --ga-seconds 5 --baseline-seconds 5 --seed 42 \
  --output genetic_alg/results/professor_compare
python -m genetic_alg study --example professor --transforms log linear sqrt \
  --population 50 --length 50 --generations 1000 --repeats 3 --ga-seconds 5 --seed 42 \
  --output genetic_alg/results/fitness_study
python -m genetic_alg benchmark --rows 3 --cols 2 --count 5 --repeats 2 \
  --population 50 --length 50 --generations 1000 --ga-seconds 3 \
  --baseline-seconds 3 --seed 42 --output genetic_alg/results/benchmark_3x2
echo "Open the dashboard.html file in each results folder."
