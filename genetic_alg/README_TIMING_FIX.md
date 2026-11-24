# Uninstrumented timing and optional memory profiling

This patch changes only the `genetic_alg` extension. Existing `sandgrid` algorithms are still called unchanged.

## Why

Previously `experiments.py` wrapped baseline and genetic calls in `tracemalloc`, so algorithms timed *inside* the calls included the substantial tracing overhead in their `elapsed_sec` values.

## New default

The regular `solve`, `compare`, `benchmark`, and `study` commands time uninstrumented executions. The `peak_python_bytes` CSV field is **blank**, not zero: no Python allocation tracing was performed. Internal algorithm timing remains the source of `elapsed_sec`.

## Optional `--measure-memory`

To collect Python allocation peaks as well, append `--measure-memory` to the command. Each algorithm is then run twice: once normally for route, time, and success data; once under `tracemalloc` for peak Python-tracked allocations. This roughly doubles the number of algorithm calls and the profiled pass may be much slower. A time-capped stochastic run can explore a different set of states on the profiled pass, so the memory peak should be described as an **independent diagnostic**, not as memory measured on the exact timed execution. This does not measure operating-system RAM.

## Example

```powershell
python -m genetic_alg compare `
  --example professor `
  --population 50 `
  --length 50 `
  --generations 100 `
  --repeats 5 `
  --ga-seconds 30 `
  --baseline-seconds 30 `
  --seed 42 `
  --output genetic_alg/results/compare_untraced
```

Tests:

```powershell
python -m unittest discover -s genetic_alg/tests -v
```

Previous results gathered under tracing should not be mixed with the new uninstrumented runtime measurements.
