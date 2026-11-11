# Sand-grid project — generated evaluation report

Generated (UTC): 2026-11-11T11:46:05+00:00
Python: `3.11.1`; OS: `Windows 10`

## Coverage and interpretation

- Input/display convention: 1=full, 0.5=half, 0=empty, including the professor example.
- Down cost = 1 + 4 × (sand amount before + sand amount after). Side cost = 1.
- DFS/BFS/IDS/UCS are compulsory; A*/RBFS, animation and exhaustive plots are bonus.
- BFS/IDS minimize action count, while UCS/A* minimize weighted cost.
- Continuous-flow model: an internal vertical gate stays open while sand remains behind it; if blocked, it waits for the destination to free up.
- A bottom exit drains all sand arriving during the same paid action; no additional cost is charged for that uninterrupted cascade.
- The assignment Greedy approach is the column-wise, vertical-only baseline, NOT Greedy Best-First Search.
- A horizontal transfer moves at most 0.5 full-box units; triggered transfers are automatic.
- Water/concrete extension is NOT implemented.
- Automated test suite in this run: PASSED.

## Comparison on identical initial grids

| Grid | Algorithm | Status | Cost | Actions | Side | Expanded | Seconds | Peak Python KiB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| professor | greedy | found | 47 | 7 | 0 | 7 | 0.0015 | 1.1 |
| professor | dfs | found | 47 | 7 | 0 | 7 | 0.0203 | 12.7 |
| professor | bfs | found | 47 | 7 | 0 | 2473 | 2.7680 | 620.5 |
| professor | ids | timeout | — | — | — | 5559 | 5.0003 | 5.7 |
| professor | ucs | found | 34 | 10 | 3 | 5661 | 4.3799 | 1320.7 |
| professor | astar | found | 34 | 10 | 3 | 5326 | 4.8582 | 1264.6 |
| professor | rbfs | timeout | — | — | — | 4864 | 5.0002 | 7.2 |
| random_5x2 | greedy | found | 38 | 8 | 0 | 8 | 0.0023 | 1.1 |
| random_5x2 | dfs | found | 38 | 8 | 0 | 8 | 0.0104 | 11.4 |
| random_5x2 | bfs | found | 38 | 8 | 0 | 530 | 0.4821 | 77.9 |
| random_5x2 | ids | timeout | — | — | — | 4895 | 5.0002 | 7.0 |
| random_5x2 | ucs | found | 34 | 8 | 0 | 644 | 0.3999 | 63.0 |
| random_5x2 | astar | found | 34 | 8 | 0 | 620 | 0.4028 | 63.0 |
| random_5x2 | rbfs | timeout | — | — | — | 5947 | 5.0003 | 8.3 |

A limited run is not a proof of failure or nonexistence of a solution.
The action count is not the same as weighted cost.
Memory uses `tracemalloc` (not operating-system RSS); timing includes profiling overhead.
Per-step solutions and offline HTML animations are saved beside each comparison.

## Exact exhaustive evaluation (3×2)

- Initial grids: 729.
- Valid modeled states (including open gates): 11,242.
- Mean Greedy / optimum (excluding zero/zero): 1.165741.
- Fraction Greedy optimal: 19.2044%.
- Method: exact reverse Dijkstra under the continuous-flow gate rules.
- Files: `exhaustive_3x2_revised/all_states.csv` and its three analysis plots.
- This is not a per-algorithm time/memory benchmark.

## Individual-algorithm benchmark on multiple grids

Random sample size: 5 (seed=42), max 5.0s per non-Greedy run, max 100000 expansions, IDS depth at most 20.

| Algorithm | Runs | Solved | Timeout | Other limit | Median seconds | Median KiB |
|---|---:|---:|---:|---:|---:|---:|
| greedy | 5 | 5 | 0 | 0 | 0.004618 | 1.17 |
| dfs | 5 | 5 | 0 | 0 | 0.033911 | 14.58 |
| bfs | 5 | 2 | 3 | 0 | 5.001102 | 300.62 |
| ids | 5 | 2 | 3 | 0 | 5.000616 | 5.38 |
| ucs | 5 | 1 | 4 | 0 | 5.002416 | 604.28 |
| astar | 5 | 2 | 3 | 0 | 5.003371 | 534.32 |
| rbfs | 5 | 0 | 5 | 0 | 5.001574 | 7.53 |

Charts include success rate and medians for time, memory, expansions.
Median time/space include successful and resource-limited runs.
Do not compare these medians without checking success rates.
Exact-optimality comparisons for this 5x2 sample require an exact 5x2 analysis.

## Sample Greedy / UCS quality analysis

Jointly solved grids: 1 / 5.
Ratios with positive optimal cost: 1.
Only completed UCS results count as certified optima.
This is a sample, not a 59,049-grid exhaustive result.
Plots (when at least one nonempty pair is solved): `sample_greedy_ratio_histogram.png`, `sample_greedy_vs_ucs_scatter.png`.

## Optional full 59,049 × algorithm benchmark

NOT RUN. Enable explicitly with `--full-benchmark`; this is optional and can be resource intensive.

## Submission prerequisites

- Add the FULL verbatim transcripts of every AI conversation yourself.
- Fill in student/course details and review the interpretation with the instructor.
- The generated files and source code do not include the optional water/concrete model.
