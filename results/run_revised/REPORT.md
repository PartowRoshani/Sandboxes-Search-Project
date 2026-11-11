# Sand-grid project — generated evaluation report

Generated (UTC): 2026-11-11T10:27:23+00:00
Python: `3.11.1`; OS: `Windows 10`

## Coverage and interpretation

- Input/display convention: 1=full, 0.5=half, 0=empty, including the professor example.
- Down cost = 1 + 4 × (sand amount before + sand amount after). Side cost = 1.
- DFS/BFS/IDS/UCS are compulsory; A*/RBFS, animation and exhaustive plots are bonus.
- BFS/IDS minimize action count, while UCS/A* minimize weighted cost.
- Revised model: blocked vertical AND directed horizontal gates remain open; each closes after sand passes.
- A horizontal transfer moves at most 0.5 full-box units; triggered transfers are automatic.
- Water/concrete extension is NOT implemented.
- Automated test suite in this run: PASSED.

## Comparison on identical initial grids

| Grid | Algorithm | Status | Cost | Actions | Side | Expanded | Seconds | Peak Python KiB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| professor | greedy | found | 66 | 10 | 0 | 10 | 0.0141 | 1.4 |
| professor | dfs | found | 64 | 24 | 4 | 24 | 0.0090 | 27.6 |
| professor | bfs | timeout | — | — | — | 3993 | 2.0022 | 1426.9 |
| professor | ids | timeout | — | — | — | 3255 | 2.0007 | 19.5 |
| professor | ucs | timeout | — | — | — | 4082 | 2.0050 | 1651.7 |
| professor | astar | timeout | — | — | — | 3286 | 2.0032 | 1382.6 |
| professor | rbfs | timeout | — | — | — | 2211 | 2.0005 | 8.8 |
| random_5x2 | greedy | found | 48 | 10 | 0 | 10 | 0.0010 | 1.5 |
| random_5x2 | dfs | found | 46 | 16 | 1 | 16 | 0.0053 | 10.9 |
| random_5x2 | bfs | found | 56 | 10 | 0 | 917 | 0.2963 | 110.8 |
| random_5x2 | ids | timeout | — | — | — | 3931 | 2.0001 | 14.3 |
| random_5x2 | ucs | found | 40 | 10 | 0 | 1350 | 0.5100 | 131.8 |
| random_5x2 | astar | found | 40 | 10 | 0 | 1054 | 0.4720 | 146.4 |
| random_5x2 | rbfs | timeout | — | — | — | 3148 | 2.0006 | 8.7 |

A limited run is not a proof of failure or nonexistence of a solution.
The action count is not the same as weighted cost.
Memory uses `tracemalloc` (not operating-system RSS); timing includes profiling overhead.
Per-step solutions and offline HTML animations are saved beside each comparison.

## Exact exhaustive evaluation (3×2)

- Initial grids: 729.
- Valid modeled states (including open gates): 120,193.
- Mean Greedy / optimum (excluding zero/zero): 1.312325.
- Fraction Greedy optimal: 13.7174%.
- Method: exact reverse Dijkstra on the revised one-shot gate model.
- Files: `exhaustive_3x2_revised/all_states.csv` and its three analysis plots.
- This is not a per-algorithm time/memory benchmark.

## Individual-algorithm benchmark on multiple grids

Random sample size: 5 (seed=42), max 2.0s per non-Greedy run, max 100000 expansions, IDS depth at most 20.

| Algorithm | Runs | Solved | Timeout | Other limit | Median seconds | Median KiB |
|---|---:|---:|---:|---:|---:|---:|
| greedy | 5 | 5 | 0 | 0 | 0.001619 | 1.76 |
| dfs | 5 | 5 | 0 | 0 | 0.011954 | 24.07 |
| bfs | 5 | 1 | 4 | 0 | 2.001514 | 299.91 |
| ids | 5 | 1 | 4 | 0 | 2.000298 | 15.2 |
| ucs | 5 | 1 | 4 | 0 | 2.002611 | 620.49 |
| astar | 5 | 1 | 4 | 0 | 2.001543 | 287.07 |
| rbfs | 5 | 0 | 5 | 0 | 2.001042 | 8.48 |

Charts include success rate and medians for time, memory, expansions.
Median time/space include successful and resource-limited runs.
Do not compare these medians without checking success rates.
Exact-optimality comparisons for this 5x2 sample require an exact 5x2 analysis.

## Optional full 59,049 × algorithm benchmark

NOT RUN. Enable explicitly with `--full-benchmark`; this is optional and can be resource intensive.

## Submission prerequisites

- Add the FULL verbatim transcripts of every AI conversation yourself.
- Fill in student/course details and review the interpretation with the instructor.
- The generated files and source code do not include the optional water/concrete model.
