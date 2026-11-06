# Sand-grid project — generated evaluation report

Generated (UTC): 2026-11-06T17:49:23+00:00
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
| professor | greedy | found | 47 | 7 | 0 | 7 | 0.0138 | 1.0 |
| professor | dfs | found | 64 | 24 | 4 | 24 | 0.0117 | 20.2 |
| professor | bfs | found | 47 | 7 | 0 | 1788 | 0.8973 | 580.7 |
| professor | ids | timeout | — | — | — | 3088 | 2.0004 | 17.6 |
| professor | ucs | found | 34 | 10 | 3 | 3709 | 1.5607 | 639.6 |
| professor | astar | found | 34 | 10 | 3 | 2551 | 1.5384 | 541.0 |
| professor | rbfs | timeout | — | — | — | 2382 | 2.0014 | 8.8 |
| random_5x2 | greedy | found | 38 | 8 | 0 | 8 | 0.0007 | 1.1 |
| random_5x2 | dfs | found | 46 | 16 | 1 | 16 | 0.0055 | 7.5 |
| random_5x2 | bfs | found | 38 | 8 | 0 | 500 | 0.1841 | 72.8 |
| random_5x2 | ids | timeout | — | — | — | 3750 | 2.0003 | 14.6 |
| random_5x2 | ucs | found | 34 | 8 | 0 | 585 | 0.2121 | 60.8 |
| random_5x2 | astar | found | 34 | 8 | 0 | 456 | 0.2065 | 61.8 |
| random_5x2 | rbfs | timeout | — | — | — | 2724 | 2.0002 | 9.9 |

A limited run is not a proof of failure or nonexistence of a solution.
The action count is not the same as weighted cost.
Memory uses `tracemalloc` (not operating-system RSS); timing includes profiling overhead.
Per-step solutions and offline HTML animations are saved beside each comparison.

## Exhaustive evaluation (5×2 = 3^10 initial grids)

Skipped by --skip-analysis; no 59,049-grid results were generated in this run.

## Individual-algorithm benchmark on multiple grids

Random sample size: 5 (seed=42), max 2.0s per non-Greedy run, max 100000 expansions, IDS depth at most 20.

| Algorithm | Runs | Solved | Timeout | Other limit | Median seconds | Median KiB |
|---|---:|---:|---:|---:|---:|---:|
| greedy | 5 | 5 | 0 | 0 | 0.000577 | 1.1 |
| dfs | 5 | 5 | 0 | 0 | 0.010256 | 18.59 |
| bfs | 5 | 3 | 2 | 0 | 1.172788 | 412.84 |
| ids | 5 | 2 | 3 | 0 | 2.000435 | 19.68 |
| ucs | 5 | 2 | 3 | 0 | 2.001336 | 716.51 |
| astar | 5 | 3 | 2 | 0 | 1.868644 | 605.95 |
| rbfs | 5 | 0 | 5 | 0 | 2.000855 | 9.31 |

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
