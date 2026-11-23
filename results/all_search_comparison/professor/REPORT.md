# Sand Grid — Unified Search Comparison

- Initial grid: `professor` (4×2); internal code `2000`
- Initial occupancy (1=full, 0.5=half, 0=empty): `[[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [1.0, 0.0]]`
- Graph limits: `{'seconds': 8.0, 'expansions': 100000, 'max_depth': 20}`
- Local-search limits: `{'seconds': 10, 'evaluations': 2500}`
- Randomized algorithms: `5` runs per algorithm, starting at seed `42`

## Measurements

| Algorithm | Solved / runs | Best path cost | Median solved cost | Median time (s) | Work | Work unit | Gap vs UCS |
|---|---:|---:|---:|---:|---:|---|---:|
| greedy | 1/1 | 47 | 47 | 0.000358 | 7 | expanded_nodes | 13 |
| random | 5/5 | 45 | 61 | 0.003291 | 21 | expanded_nodes | 11 |
| dfs | 1/1 | 47 | 47 | 0.000987 | 7 | expanded_nodes | 13 |
| bfs | 1/1 | 47 | 47 | 0.267105 | 2473 | expanded_nodes | 13 |
| ids | 1/1 | 47 | 47 | 2.931159 | 26514 | expanded_nodes | 13 |
| ucs | 1/1 | 34 | 34 | 0.584567 | 5661 | expanded_nodes | 0 |
| astar | 1/1 | 34 | 34 | 0.542443 | 5326 | expanded_nodes | 0 |
| rbfs | 0/1 | N/A | N/A | 8.000593 | 41082 | expanded_nodes | N/A |
| hillclimb | 5/5 | 34 | 37 | 0.709346 | 2500 | path_evaluations | 0 |
| anneal | 5/5 | 34 | 36 | 0.290841 | 1075 | path_evaluations | 0 |
| genetic | 5/5 | 38 | 39 | 0.790834 | 2500 | path_evaluations | 4 |

## Interpretation

- A successful run reaches the exact zero-sand Goal state. A failed or timed-out run has **no confirmed solution cost**.
- UCS gives the weighted-cost optimum only if it completes successfully. Its value is the reference for `gap_vs_ucs`.
- BFS/IDS target minimum number of actions, not necessarily minimum weighted path cost.
- Local Search maximizes path fitness over random candidate sequences of 30–35 action IDs. A candidate stops evaluating at its first Goal.
- `expanded_nodes` in graph search and `path_evaluations` in Local Search are **different work units**, so compare their values only within the same category.
- For stochastic algorithms, the minimum cost over trials is not a typical cost; use `median_success_cost` and the success rate together.
- Wall-clock times vary by hardware. For a scientific comparison, rerun all algorithms on one machine with the same initial code and limits.

## Output files

- `dashboard.html`: offline summary and links to the step-by-step animations
- `comparison.csv`: one aggregated row per method
- `trials.csv`: every trial with seed, goal flag, runtime and measured work
- `initial.json`, `initial.png`: exact shared starting state
- `cost_comparison.png`, `time_comparison.png`, `success_rate.png`: charts
- `animations/*_best.json`: selected action IDs, trace, and local candidate metadata
- `animations/*.html` and `animations/*.gif`: visual output for methods with an executed path

These values come from this experiment and are not borrowed from earlier project reports.
