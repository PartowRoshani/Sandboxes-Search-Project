# Sandboxes Search Project — Continuous-Flow Sand Grid

**Artificial Intelligence course project · Sand-only problem · Week 2 revised model**

This repository implements a weighted search problem in which sand must be emptied from an `R × C` grid by opening vertical and horizontal gates. It includes the instructor-defined column-wise Greedy baseline, seven other search methods, exact small-grid analysis, heuristic design by relaxation, machine-learning experiments, and reproducible evaluation scripts.

This README documents **the revised sand-only model** (`continuous-flow-v2-full-is-1`). The earlier model's results must not be mixed with results from this version. Water and concrete are outside the scope of this README and the reported experiments.

| Project information | Value |
| --- | --- |
| Student | Partow Roshani |
| Instructor | Dr. Katanforoush |
| Course | Artificial Intelligence |
| Academic year | 1405–1406, first semester |
| Repository | [PartowRoshani/Sandboxes-Search-Project](https://github.com/PartowRoshani/Sandboxes-Search-Project) |

## 1. Installation and quick verification

Python **3.11** is the version used in the submitted Windows experiments; Python 3.10+ is required by the source syntax.

From the project root, run:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-heuristics.txt
python -m pytest -v tests
```

`requirements-heuristics.txt` installs scikit-learn and joblib for the optional ML experiments. The latest reported integrated run passed **40 tests**; test counts may change when more tests are added.

Check the available commands and flags:

```powershell
python main.py --help
python main.py solve --help
python main.py compare --help
python run_project.py --help
```

### Quick experiment

```powershell
python main.py solve --example professor --algorithm greedy
python main.py solve --example professor --algorithm ucs
python main.py solve --example professor --algorithm astar --heuristic relax
python main.py compare --example professor --random-seed 42 --limit-seconds 10
```

For the revised instructor example, the reference costs are **Greedy = 47** and **UCS / optimal A* = 34**. If the code produces different costs, verify that the current model and search files are being used before interpreting the results.

## 2. Grid values, states and goal

The **default external convention is `1 = full`, `0.5 = half-full`, `0 = empty`**. This applies to CLI inputs, printed grids, HTML and GIF output.

| Displayed value | Sand amount | Internal half-unit value |
| ---: | --- | ---: |
| `1` | Full, 1 unit | `2` |
| `0.5` | Half-full, 0.5 unit | `1` |
| `0` | Empty | `0` |

For efficient exact transitions, the implementation stores half-units as integers. A complete search state includes **both cell occupancies and the statuses of persistent open vertical and directed horizontal gates**. Consequently, the same occupancy grid with different open gates represents different search states.

All gates are initially closed. The goal is to remove **all** sand, with minimum **total weighted action cost**. When every cell is empty, the state is normalized to the goal encoding `0`.

### Legal actions and continuous flow

- **Downward gates:** Each cell has a gate below it. Opening a gate in the final row empties sand out of the grid. Opening an internal gate can move sand into the cell below.
- **Blocked vertical gate:** If the receiving cell is full, the gate can still be opened and remains open. As soon as downstream space becomes available, sand flows automatically through it.
- **Continuous vertical flow:** A vertical gate remains available during the continuous flow associated with its opening. When temporarily blocked by a full destination, it can wait for space to become available. The bottom exit can discharge successive incoming sand portions during the same flow event. The connection closes when its continuous flow is complete.
- **Directed horizontal gates:** A horizontal gate may be opened only from a **full** source cell. At most **0.5 unit** moves per opening. A blocked gate can remain open until the receiving cell has capacity; after its half-unit transfer, it closes.
- **Automatic cascades:** Opening one gate may activate previously opened gates. The simulator settles the cascade to a stable state before returning the next search state. Automatic transfers do **not** incur a new gate-opening action cost.

A vertical gate-opening action has the cost

$$
C_{\mathrm{down}} = 1 + 4\bigl(s_{\mathrm{before}} + s_{\mathrm{after}}\bigr),
$$

where the two amounts refer to the **source cell of the gate being opened**, before and after the complete automatic settling caused by that action, and are measured in units of sand (`0`, `0.5`, `1`). A horizontal gate-opening action costs

$$
C_{\mathrm{side}} = 1.
$$

A gate's cost is charged **once per opening**, not once per automatic sand-transfer event. All costs are positive.

## 3. Implemented algorithms

| CLI name | Method | Objective / caveat |
| --- | --- | --- |
| `greedy` | Instructor-defined column-wise, vertical-only baseline | Fixed reference policy; not Greedy Best-First Search; no optimality guarantee |
| `random` | Randomized depth-first graph search with visited-state tracking | Random action order, no repeated complete states during exploration; no optimality guarantee |
| `dfs` | Depth-First Search | Finds a feasible route when successful; not weighted-cost optimal |
| `bfs` | Breadth-First Search | Minimum number of actions, not minimum weighted cost |
| `ids` | Iterative Deepening Search | Minimum depth when completed within a sufficient depth limit |
| `ucs` | Uniform-Cost Search | Minimum weighted cost when completed |
| `astar` | A* graph search | Minimum weighted cost with an admissible heuristic and correct graph-search handling |
| `rbfs` | Recursive Best-First Search | Memory-conscious heuristic search; may repeat work or hit resource limits |

The term **Greedy** is specific to the assignment: process each column independently, identify its highest sand-containing cell, open only the downward gates needed to move sand toward the exit, and continue until the column is empty. **Never open a horizontal gate** in this baseline. Its cost is used for the required Greedy/optimal comparisons.

The `random` implementation shuffles legal action orders using a configurable random seed, records visited **full states** (occupancy plus gate mask), and can backtrack from an unsuccessful branch. It is therefore more precisely described as **randomized DFS without revisiting states**, rather than a memoryless random walk.

## 4. Instructor's 4 × 2 example

The initial grid is

```text
1  0
0  1
0  1
1  0
```

Greedy uses the following seven downward gate openings (1-based row/column coordinates):

| Step | Open gate below | Action cost | Cumulative cost |
| ---: | --- | ---: | ---: |
| 1 | `(1,1)` | 5 | 5 |
| 2 | `(2,1)` | 5 | 10 |
| 3 | `(3,1)` | 9 | 19 |
| 4 | `(4,1)` — exit | 5 | 24 |
| 5 | `(2,2)` | 9 | 33 |
| 6 | `(3,2)` | 9 | 42 |
| 7 | `(4,2)` — exit | 5 | **47** |

UCS and A* find a solution of weighted cost **34** (10 actions). Thus, on this example, `47 / 34 ≈ 1.3824`.

A separate, reproducible `random` run with `--random-seed 42` produced cost **45** in **11 actions**. Random output depends on the seed. In `run_project.py`, a reproducible *per-initial-state derived seed* is used; thus the same top-level seed can result in a different Random route from a direct `main.py solve` call. In one integrated run it produced cost **63** (21 actions).

### Generate solution animations

```powershell
python main.py solve --example professor --algorithm ucs --html results/professor_ucs.html --gif results/professor_ucs.gif --json-out results/professor_ucs_steps.json
python main.py solve --example professor --algorithm random --random-seed 42 --html results/random_professor.html --gif results/random_professor.gif
```

Open the generated `.html` files in a browser. They show gate status, sand quantities, and direct/automatic transfer events.

### Custom grid

```powershell
python main.py solve --rows 2 --cols 2 --grid '[[1,0],[0.5,1]]' --algorithm astar --heuristic relax
```

## 5. Heuristics: Basic, relaxation and machine learning

A* prioritizes states using

$$
f(s)=g(s)+h(s),
$$

where `g` is accumulated actual cost and `h` estimates the cost of emptying all **remaining** sand.

### Basic lower bound

The baseline heuristic estimates only a minimum unavoidable exit cost:

- `0` for an empty grid;
- `3` if exactly one half-unit of sand remains;
- `5` if at least one full unit of sand remains.

It is safe but often weak because it ignores the positions of the sand and the row boundaries.

### Relaxation heuristic (recommended for optimal A*)

The revised relaxation uses a minimum exit charge plus minimum unavoidable costs of crossing row boundaries:

$$
h_{\mathrm{relax}}(s)=E(s)+\sum_{r=1}^{R-1}L_r(s).
$$

For each boundary, let `Q_r` be the total remaining sand above it. Then `L_r = 0` if no sand is above it **or** if a vertical gate on that boundary is already open. If all vertical gates on the boundary are closed, `L_r = 3` when `Q_r = 0.5`, and `L_r = 5` when `Q_r ≥ 1`. The exit lower bound `E` is `0`, `3` or `5` by the same total-amount rule as Basic.

**Admissibility argument:** Every remaining unit above a row boundary must eventually cross that boundary. When no gate on a required boundary is open, at least one opening is unavoidable. The relaxation charges only a lower bound on the total opening cost at that boundary, independently of other boundaries, and ignores any additional horizontal movement or gate openings. At least one bottom exit cost is also unavoidable. Since these requirements correspond to distinct gate openings, their sum is a lower bound on the cost of a complete solution under the implemented continuous-flow rules. The implementation was also checked empirically for admissibility and consistency on the enumerated small state graphs (including the **11,242** stable states of 3 × 2); such checks complement, but do not replace, the model-specific argument.

For the initial instructor example, `h_basic = 5`, `h_relax = 20`, and the exact optimal cost is `34`. In one like-for-like search comparison, A* expanded **5,326** states with Basic and **2,963** with Relaxation, finding cost `34` in both cases.

The classroom formula `5 × (# full cells) + 3 × (# half-full cells)` is available as a comparison idea, but is **not generally admissible** in this model: a previously open vertical connection can let several cells empty in one continuous paid opening. It is not used as the guaranteed-optimal A* key.

### Machine-learned heuristic

Training labels are exact remaining costs `h*(s)` from reverse Dijkstra on the 3 × 2 augmented-state graph. A `RandomForestRegressor` is trained on cell occupancies, gate-mask information and aggregated sand quantities. Training and test groups are separated by initial **occupancy pattern** using `GroupShuffleSplit`.

Four A*/UCS search configurations are used alongside the UCS reference:

- `astar --heuristic basic` — baseline admissible A*;
- `astar --heuristic relax` — relaxation-based admissible A*;
- `astar --heuristic ml` — direct learned estimate, **no optimality guarantee**;
- `astar --heuristic ml-tie` — relaxation as the primary A* key, ML only for tie-breaking; preserves the optimality guarantee of the relaxation-based primary key.

The saved 3 × 2 model is **not** a validated heuristic for arbitrary grid sizes such as the instructor's 4 × 2 example.

### Train and evaluate

```powershell
python scripts/train_ml_heuristic.py --rows 3 --cols 2 --seed 42 --trees 30 --output results/ml_3x2
python scripts/compare_heuristics.py --model results/ml_3x2/heuristic_ml.joblib --count 20 --seconds 20 --output results/heuristic_comparison
```

Final multi-seed experiment (3 independent splits, 20 held-out initial grids per split):

```powershell
python scripts/final_heuristic_study.py --seeds 42,43,44 --count 20 --repeats 1 --trees 30 --seconds 20 --output results/final_heuristics
```

Memory-profiling run, using a separate output folder and a larger runtime limit:

```powershell
python scripts/final_heuristic_study.py --seeds 42,43,44 --count 20 --repeats 1 --trees 30 --seconds 60 --measure-memory --output results/final_heuristics_memory_60s
```

Reported results from the **unprofiled** 60-test comparison:

| Method | Mean expanded states | Mean search time (s) | Optimal / completed |
| --- | ---: | ---: | ---: |
| UCS | 959.8 | 0.0602 | 60/60 |
| A* Basic | 876.9 | 0.0575 | 60/60 |
| **A* Relaxation** | **626.5** | **0.0451** | **60/60** |
| A* ML Direct | 14.8 | 0.0345 | **53/60** |
| A* ML Safe Tie | 559.2 | 0.8628 | 60/60 |

`ML Direct` reached the goal in all 60 runs but returned a **suboptimal cost in 7**; this is why its low node count does not establish superiority. The measured ML inference overhead can also outweigh reductions in expansions. `tracemalloc` values represent **Python-tracked allocations**, not total process RAM; use the separate memory experiment for those measurements, not for fair timing comparison.

## 6. Exact analysis and required assignment plots

For a 3 × 2 grid there are `3^6 = 729` possible initial occupancy patterns (all gates initially closed). With persistent gate states included, the revised model's graph contains **11,242 stable states** and **73,694 weighted transitions**. Reverse Dijkstra computes exact optimal remaining costs from the goal.

The exhaustive analysis gives:

| Statistic | Revised 3 × 2 model |
| --- | ---: |
| Initial grids | 729 |
| Nonempty grids with defined Greedy/optimum ratio | 728 |
| Mean Greedy/optimal ratio | **1.165741** |
| Median Greedy/optimal ratio | **1.173913** |
| Largest observed ratio | **1.483871** |
| Fraction where Greedy is optimal | **19.2044%** |

Run:

```powershell
python main.py analyze --rows 3 --cols 2 --output results/exhaustive_3x2
```

The three required plots in `results/exhaustive_3x2/` are:

1. `histogram_ratio.png` — histogram **with frequencies** for `Greedy_opt_ratio = greedy_cost / optimal_cost` (the empty grid's `0/0` is excluded).
2. `scatter_costs.png` — x-axis: Greedy solution cost; y-axis: optimal cost.
3. `scatter_actions.png` — x-axis: number of actions in a selected optimal solution; y-axis: number of **horizontal/side (type-b)** actions in that solution.

For a 5 × 2 grid there are `3^10 = 59,049` initial patterns, but the enlarged augmented-state graph is much larger. Exhaustive 5 × 2 reverse-Dijkstra results **from the older gate model are not valid for this revision**. The included implementation limits graph enumeration for safety; a benchmark on sampled 5 × 2 grids is not an exhaustive analysis.

## 7. Random baseline: multiple seeds

To measure the variability of Random, it was run on the instructor example with seeds 1–30. The reported sample had **mean cost 58.07**, **minimum 46**, **maximum 67**, **sample standard deviation 4.93**, and **mean 17.07 actions**. These are outcomes for **one initial grid**, not a general performance claim.

For a reproducible rerun in **PowerShell**:

```powershell
New-Item -ItemType Directory -Force results/random_seeds | Out-Null
foreach ($seed in 1..30) {
    python main.py solve --example professor --algorithm random --random-seed $seed --json-out "results/random_seeds/seed_${seed}.json"
}
```

Random does not optimize cost; statistical claims should use multiple seeds and, for broader conclusions, several different initial grids.

## 8. Effective branching factor, b*

For a completed search with a solution depth `d` and a chosen search-node count `N`, estimate the effective branching factor numerically from

$$
N+1 = 1+b^*+(b^*)^2+\cdots+(b^*)^d.
$$

`calc_effective_branching.py` uses numerical bisection and reports two versions where the CSV provides the inputs:

- `b*(generated)`: closer to the usual **generated-node** textbook convention;
- `b*(expanded)`: an **expanded-state proxy** when generated counts are absent.

The two definitions must be labelled distinctly; they are not interchangeable. An apparent `b* ≈ 1` for a path-like DFS/Random run does not imply an optimal route.

```powershell
python scripts/calc_effective_branching.py --input results/project_with_random/professor/comparison.csv --output results/bstar_professor.csv
python scripts/calc_effective_branching.py --input results/final_heuristics/comparison_all_seeds.csv --output results/bstar_heuristics.csv --summary-output results/bstar_summary.csv
```

For the instructor example, the expanded-based values were **BFS 2.872**, **UCS 2.236**, **A* Basic 2.222**, and **A* Relaxation 2.084** (the latter from the separate Relaxation comparison). For the 60-test heuristic study, mean expanded-based values were:

| Method | Mean `b*(expanded)` |
| --- | ---: |
| UCS | 2.252 |
| A* Basic | 2.177 |
| A* Relaxation | **1.955** |
| A* ML Direct | 1.180 |
| A* ML Safe Tie | 1.870 |

For a formal report, interpret these alongside **solution cost, time, depth and completeness**; a smaller effective branching factor alone does not imply admissibility or optimality.

## 9. End-to-end evaluation and generated files

Run the model tests, professor comparison, 3 × 2 exact analysis, reproducible 5 × 2 samples and generate the dashboard:

```powershell
python run_project.py --analysis-rows 3 --analysis-cols 2 --sample-size 5 --seconds 10 --seed 42 --random-seed 42 --output results/project_with_random
```

Examples of generated outputs (under the selected `--output` directory):

```text
results/project_with_random/
├── REPORT.md
├── dashboard.html
├── professor/
│   ├── comparison.csv
│   └── *_steps.json
├── exhaustive_3x2_revised/
│   ├── all_states.csv
│   ├── summary.json
│   ├── histogram_ratio.png
│   ├── scatter_costs.png
│   └── scatter_actions.png
├── benchmark_sample.csv
├── benchmark_sample_summary.csv
└── *.png
```

Only runs that **completed successfully** can be used as observed solution costs; `timeout` and `expansion_limit` must be reported as resource-limit outcomes, not as proof that no solution exists. For some sampled 5 × 2 runs, UCS may not finish within the search limit, so a Greedy/optimum ratio must not be reported for those samples.

### Results and reproducibility notes

- Model version: `continuous-flow-v2-full-is-1`; display convention: `1 = full`, `0.5 = half`, `0 = empty`.
- Start states have **all gates closed**; later search states can contain open gates.
- The ML model and its train/test split are tied to the **3 × 2** state representation.
- Search limits (`--seconds`, `--expansions`, `--depth` or their CLI equivalents) constrain runtime; timeouts are not correctness failures.
- Training time and loading time are excluded from the logged **search** time in the reported ML comparison; inference time **is included**.
- Measured memory via `tracemalloc` is not equivalent to the total operating-system resident memory.
- Use a **new output directory** for each experimental configuration to avoid mixing data from different models, limits or profiling settings.

## 10. Repository structure and assignment deliverables

```text
Sandboxes-Search-Project/
├── main.py                          # solve / compare / analyze / benchmark
├── run_project.py                   # integrated runner, tables, plots, dashboard
├── requirements.txt                 # simulation, plotting and testing
├── requirements-heuristics.txt      # scikit-learn, joblib
├── sandgrid/
│   ├── model.py                     # environment, continuous flow, gate states/costs
│   ├── search.py                    # Greedy, Random, DFS, BFS, IDS, UCS, A*, RBFS
│   ├── heuristics.py                # Basic, Relaxation, ML integration
│   ├── batch.py                     # exact reverse-Dijkstra analysis
│   ├── benchmark.py                 # repeatable comparisons
│   ├── visualize.py                 # HTML and GIF traces
│   ├── cli.py                       # command-line interface
│   └── reporting.py                 # reports and dashboard
├── scripts/
│   ├── train_ml_heuristic.py
│   ├── compare_heuristics.py
│   ├── final_heuristic_study.py
│   └── calc_effective_branching.py
├── tests/                            # model, search, heuristic and Random tests
├── docs/                             # design and assignment reports
└── results/                          # generated experiment data (may be ignored by Git)
```

The instructor requests the following submission items. Before submitting, **verify that all required files are actually committed to the public repository**, rather than existing only on a local computer:

| Required item | Where to find it / what to include |
| --- | --- |
| Complete source, installation and run scripts | `sandgrid/`, `main.py`, `run_project.py`, `scripts/`, requirements files |
| Environment simulator and A* | `sandgrid/model.py`, `sandgrid/search.py` |
| Relaxation proof or ML training | `sandgrid/heuristics.py`, this README, Week 2 report; optionally ML scripts |
| Cost/time/memory and b* evaluation | benchmark scripts, `scripts/calc_effective_branching.py`, CSV outputs |
| Three required Greedy/optimal plots | `histogram_ratio.png`, `scatter_costs.png`, `scatter_actions.png` from revised 3 × 2 analysis |
| Experimental report | Commit the compiled Week 2 PDF and editable LaTeX source, including figure assets |
| **Full AI conversations** | **Export and include complete prompts and responses** for all project-related chats; summaries alone do not satisfy this requirement |

