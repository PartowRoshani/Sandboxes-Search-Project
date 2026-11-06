# Sand-grid project — generated evaluation report

Generated (UTC): 2026-11-06T18:02:29+00:00
Python: `3.11.1`; OS: `Windows 10`

## Coverage and interpretation

- Initial grid: 0=full, 0.5=half, 1=empty; professor example uses reversed values.
- Down cost = 1 + 4 × (sand amount before + sand amount after). Side cost = 1.
- DFS/BFS/IDS/UCS are compulsory; A*/RBFS, animation and exhaustive plots are bonus.
- BFS/IDS minimize action count, while UCS/A* minimize weighted cost.
- This code models connected, persistent vertical gates with immediate settling.
- Water/concrete extension is NOT implemented.
- Automated test suite in this run: PASSED.

## Comparison on identical initial grids

| Grid | Algorithm | Status | Cost | Actions | Side | Expanded | Seconds | Peak Python KiB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| professor | greedy | found | 47 | 7 | 0 | 7 | 0.0008 | 1.0 |
| professor | dfs | found | 64 | 24 | 4 | 24 | 0.0117 | 22.5 |
| professor | bfs | found | 47 | 7 | 0 | 1788 | 0.8986 | 580.7 |
| professor | ids | timeout | — | — | — | 8264 | 5.0004 | 19.5 |
| professor | ucs | found | 34 | 10 | 3 | 3709 | 1.6526 | 639.5 |
| professor | astar | found | 34 | 10 | 3 | 2551 | 1.4649 | 621.3 |
| professor | rbfs | timeout | — | — | — | 6159 | 5.0003 | 8.9 |
| random_5x2 | greedy | found | 38 | 8 | 0 | 8 | 0.0013 | 1.1 |
| random_5x2 | dfs | found | 46 | 16 | 1 | 16 | 0.0061 | 7.5 |
| random_5x2 | bfs | found | 38 | 8 | 0 | 500 | 0.1857 | 72.8 |
| random_5x2 | ids | timeout | — | — | — | 3516 | 5.0017 | 13.1 |
| random_5x2 | ucs | found | 34 | 8 | 0 | 585 | 0.9710 | 60.8 |
| random_5x2 | astar | found | 34 | 8 | 0 | 456 | 1.0377 | 61.8 |
| random_5x2 | rbfs | timeout | — | — | — | 4229 | 5.0002 | 8.0 |

A limited run is not a proof of failure or nonexistence of a solution.
The action count is not the same as weighted cost.
Memory uses `tracemalloc` (not operating-system RSS); timing includes profiling overhead.
Per-step solutions and offline HTML animations are saved beside each comparison.

## Exhaustive evaluation (5×2 = 3^10 initial grids)

- Initial states: 59,049.
- Distinct modeled states (including connected gates): 326,041.
- Mean Greedy / optimum (excluding zero/zero): 1.263581.
- Fraction Greedy optimal: 1.9120%.
- Method: reverse Dijkstra; yields exact weighted optimum for all initial states.
- Charts: `exhaustive_5x2/histogram_ratio.png`, `exhaustive_5x2/scatter_costs.png`, `exhaustive_5x2/scatter_actions.png`.
- Source of exhaustive files: computed in this run.
- The all-states optimum analysis is NOT a per-algorithm time/memory benchmark.

## Individual-algorithm benchmark on multiple grids

Random sample size: 30 (seed=42), max 5.0s per non-Greedy run, max 100000 expansions, IDS depth at most 30.

| Algorithm | Runs | Solved | Timeout | Other limit | Median seconds | Median KiB |
|---|---:|---:|---:|---:|---:|---:|
| greedy | 30 | 30 | 0 | 0 | 0.002504 | 1.1 |
| dfs | 30 | 30 | 0 | 0 | 0.044137 | 19.5 |
| bfs | 30 | 8 | 22 | 0 | 5.002372 | 498.11 |
| ids | 30 | 2 | 28 | 0 | 5.000844 | 17.53 |
| ucs | 30 | 8 | 22 | 0 | 5.004307 | 733.88 |
| astar | 30 | 8 | 22 | 0 | 5.004989 | 614.81 |
| rbfs | 30 | 0 | 30 | 0 | 5.002118 | 8.94 |

Charts include success rate and medians for time, memory, expansions.
Median time/space include successful and resource-limited runs.
Do not compare these medians without checking success rates.
If exhaustive analysis was enabled, benchmark_quality.csv also gives exact optimality gaps on the same sample.

## Optional full 59,049 × algorithm benchmark

NOT RUN. Enable explicitly with `--full-benchmark`; this is optional and can be resource intensive.

## Submission prerequisites

- Add the FULL verbatim transcripts of every AI conversation yourself.
- Fill in student/course details and review the interpretation with the instructor.
- The generated files and source code do not include the optional water/concrete model.
