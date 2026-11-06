# Sandboxes Search Project

**Solving a weighted sand-grid problem with uninformed and informed search algorithms**

A Python implementation of the Sand Grid search problem for an Artificial Intelligence course. The project models the movement of sand through a grid of connected boxes, searches for a sequence of gate-opening actions that empties the grid, and evaluates solution quality, runtime, and memory usage.

The repository includes the **original sand-only problem** and a separate, optional **water-and-concrete extension**. Both modes can generate algorithm comparisons, interactive visualizations, CSV results, charts, and an HTML dashboard.

**Student:** Partow Roshani  
**Instructor:** Dr. Katanforoush  
**Course:** Artificial Intelligence  
**Academic year:** 1405–1406, first semester

## 1. Problem Overview

The environment is an `r × c` grid. Each cell can hold one of three amounts of sand:

| Input value | Meaning | Actual amount of sand |
| --- | --- | --- |
| `0` | Full | `1` |
| `0.5` | Half-full | `0.5` |
| `1` | Empty | `0` |

Two types of gate-opening actions are available:

- **Vertical gate:** Sand can move downward into the next cell or leave the grid through its bottom boundary. Under the implemented model, a vertical connection can remain open while the lower cell is full and the upper cell contains sand.
- **Side gate:** A full cell can move half a unit of sand to an adjacent cell if that cell has sufficient capacity. A half-full cell cannot initiate a side transfer.

The objective is to remove all sand while minimizing **total weighted cost**, not necessarily the number of actions.

### Action Costs

For a vertical action:

\[
C_{\text{down}} = 1 + 4(s_{\text{before}} + s_{\text{after}})
\]

Here, `s_before` and `s_after` are the amounts of sand in the upper/source cell, before and after the action. Each amount is in `{0, 0.5, 1}`.

For a side action:

\[
C_{\text{side}} = 1
\]

**Modeling note:** A vertical gate may establish a persistent connection even if its lower cell is already full and no sand moves immediately. This is an explicit modeling choice consistent with the instructor's worked Greedy cost, but the precise physical interpretation should be confirmed against the assignment specification.

The instructor's worked example also uses the opposite numerical convention (`1 = full`); the built-in `professor` example handles this conversion.

## 2. Implemented Algorithms

| Algorithm | Approach | Optimization guarantee when search completes |
| --- | --- | --- |
| **Greedy** | Instructor-defined baseline; processes columns using only vertical gates | No weighted-cost optimality guarantee |
| **DFS** | Depth-first search | Finds a path, not necessarily an optimal one |
| **BFS** | Breadth-first search | Minimum number of actions |
| **IDS** | Iterative deepening depth-first search | Minimum number of actions within a sufficient depth limit |
| **UCS** | Uniform-cost search | Minimum total weighted cost |
| **A\*** | A* search with a lower-bound heuristic | Minimum total weighted cost when the heuristic is admissible |
| **RBFS** | Recursive best-first search | Memory-conscious best-first search; may revisit states |

All search methods use the same state-transition rules within each problem mode. The sand-only state records cell occupancy and persistent vertical gates. The water extension also records concrete formation.

## 3. Requirements and Installation

- Python **3.10 or newer**
- NumPy, Matplotlib, and Pillow
- pytest for running the test suite

From the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

On Windows, use `py` instead of `python` if necessary. On Linux or macOS, the Python command may be `python3`.

The tested combined version passes **19 automated tests**.

## 4. Quick Start: Original Sand-Only Problem

### Short Verification Run

```bash
python run_project.py --skip-analysis --sample-size 5 --seconds 2 --depth 20 --output results/quick_run
```

This produces algorithm comparisons, solution traces, HTML animations, charts, and a summary report without running the exhaustive 59,049-state analysis.

### Full Standard Experiment

```bash
python run_project.py --sample-size 30 --seconds 5 --expansions 100000 --depth 30 --gif --output results/full_run
```

This additionally computes exact optimal costs for **all 59,049 initial 5×2 sand grids**, generates the required three exhaustive-analysis plots, and benchmarks the algorithms on **30 shared random grids**.

Open `results/full_run/dashboard.html` in a browser to browse the output. The dashboard and HTML animations work offline.

### Run Individual Algorithms

```bash
# Solve the instructor's example using uniform-cost search
python main.py solve --example professor --algorithm ucs

# Compare all algorithms on the same example
python main.py compare --example professor --limit-seconds 5

# Analyze all 5x2 initial sand grids
python main.py analyze --rows 5 --cols 2 --output results/exhaustive_5x2

# Solve a custom 2x2 grid (0 = full, 1 = empty)
python main.py solve --rows 2 --cols 2 --grid '[[0,1],[0.5,0]]' --algorithm astar
```

Use `python main.py --help` and `python run_project.py --help` for more options.

## 5. Optional Water-and-Concrete Extension

The extension has its own runner and does **not** change the original sand-only experiments.

In the proposed water model:

- Water occupies fixed, specified cells and does not flow independently.
- A wet cell turns into **permanent concrete** when the first `0.5` unit of sand enters it, either vertically or sideways.
- Concrete blocks further movement through that cell.
- Forming a concrete cell adds a **one-time cost of 10** to the action responsible for the reaction.
- The goal is to remove all **free sand**; water and concrete may remain.
- The original vertical/side action costs still apply, with the concrete penalty added when applicable.

These reaction and flow rules are **proposed assumptions**, not fully specified physical rules from the original assignment.

### Short Water Experiment

```bash
python run_water_project.py --skip-analysis --sample-size 5 --seconds 2 --depth 20 --output results/water_quick_run
```

### Full Water Experiment

```bash
python run_water_project.py --sample-size 30 --seconds 5 --depth 30 --gif --output results/water_full_run
```

The default water locations in the 5×2 experiment are `(2,2)` and `(4,1)`, using **1-based row and column coordinates**.

With these two cells reserved for water, the other eight cells can each have three initial sand states:

\[
3^{10-2} = 6,561
\]

The exhaustive water experiment therefore covers **6,561 legal initial sand configurations for this fixed water layout**, not every possible placement of water in the grid.

To change water locations:

```bash
python run_water_project.py --water-cells '1,2;3,1' --sample-size 15 --seconds 3 --output results/water_custom
```

For the water mode, a Greedy result can have status `blocked` if concrete prevents further progress without side gates. A blocked or timed-out execution is not reported as a completed solution.

See [README_WATER_FA.md](README_WATER_FA.md) and [the water model specification](docs/water_extension_model_fa.md) for detailed options and assumptions.

## 6. Experimental Results

### Instructor's Sand-Only Example

For the 4×2 worked example, the reproduced results are:

| Algorithm | Solution cost | Actions | Side actions | Expanded states |
| --- | ---: | ---: | ---: | ---: |
| Greedy | 47 | 7 | 0 | 7 |
| DFS | 64 | 24 | 4 | 24 |
| BFS | 47 | 7 | 0 | 1,788 |
| IDS | Timeout | — | — | 8,264 |
| UCS | **34** | 10 | 3 | 3,709 |
| A* | **34** | 10 | 3 | 2,551 |
| RBFS | Timeout | — | — | 6,159 |

These results used a **five-second per-search time limit**. UCS and A* found a lower-cost path than the instructor-defined Greedy baseline. All ten actions of the UCS solution were replayed and verified against the transition model.

### Exhaustive Sand-Only Analysis

| Measure | Result |
| --- | ---: |
| Initial 5×2 grids | 59,049 |
| Valid augmented states, including persistent gates | 326,041 |
| Mean Greedy / optimal cost ratio (excluding `0/0`) | **1.263581** |
| Initial grids on which Greedy is optimal | **1.9120%** |

Exact optimum costs were obtained using **reverse Dijkstra search** over the modeled state graph. This is **not** equivalent to running and timing all seven algorithms independently on 59,049 grids.

### Exhaustive Water Analysis (Default Fixed Water Layout)

| Measure | Result |
| --- | ---: |
| Legal initial sand grids | 6,561 |
| Valid augmented states | 60,516 |
| Solvable initial states | 6,561 |
| States solved by vertical-only Greedy | 648 |
| States where Greedy becomes blocked | 5,913 |

For the water extension, the mean Greedy/optimal ratio of **1.026795** applies **only to states solved by both methods with positive optimal cost**. It does not describe the blocked cases.

Runtime and memory measurements depend on hardware, execution limits, and profiling overhead. `tracemalloc` reports peak Python-tracked allocations, not total operating-system process memory.

## 7. Generated Files

Each end-to-end runner writes to its configured `--output` directory. Typical results include:

```text
results/full_run/
├── dashboard.html
├── REPORT.md
├── settings.json
├── algorithm_comparison.csv
├── professor/
│   ├── comparison.csv
│   ├── ucs.html
│   └── ucs_steps.json
├── random_5x2/
├── exhaustive_5x2/
│   ├── all_states.csv
│   ├── summary.json
│   ├── histogram_ratio.png
│   ├── scatter_costs.png
│   └── scatter_actions.png
├── benchmark_sample.csv
├── benchmark_sample_summary.csv
└── benchmark_*.png
```

The water runner has a similar layout under `results/water_full_run/`, including `professor_water/`, `random_water_5x2/`, `water_small_2x2/`, and `exhaustive_water_5x2/`.

Successful solutions include JSON step traces and browser-based animations. GIFs are generated when `--gif` is enabled.

The three exhaustive-analysis charts show:

1. A histogram of `Greedy cost / optimal cost`.
2. A scatter plot of Greedy cost against optimal cost.
3. A scatter plot of total actions against side actions in a selected optimal path.

## 8. Repository Structure

```text
.
├── main.py
├── run_project.py
├── run_water_project.py
├── validate_water_project.py
├── sandgrid/
│   ├── model.py
│   ├── search.py
│   ├── batch.py
│   ├── benchmark.py
│   ├── visualize.py
│   ├── water_model.py
│   ├── water_greedy.py
│   ├── water_analysis.py
│   ├── water_visualize.py
│   └── water_reporting.py
├── tests/
├── docs/
├── scripts/
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 9. Reproducibility and Limitations

- The sand-only and water/concrete models are deliberately separate.
- The instructor's worked example uses a different display convention; use the built-in `professor` input to reproduce its reported results.
- Persistent vertical connections, instantaneous settling, and water reactions follow the documented implementation assumptions.
- BFS and IDS target action count, whereas UCS and A* target weighted cost.
- `timeout` means an execution limit was reached, **not** that the grid is unsolvable.
- The all-state analyses compute exact optimum costs. Full per-algorithm runtime/memory benchmarking is a separate optional, potentially expensive experiment (`--full-benchmark`) and is **not claimed as completed** here.
- The project report, source code, generated results, and any required verbatim AI-assistance transcripts should be included in the final course submission.

<<<<<<< HEAD
## 10. Documentation

- [Original problem statement](docs/problem_original.md)
- [Sand-only modeling decisions](docs/proposed_model.md)
- [Evaluation notes](docs/evaluation_report.md)
- [Water/concrete model (Persian)](docs/water_extension_model_fa.md)
- [Water runner guide (Persian)](README_WATER_FA.md)
- [Submission checklist](docs/submission_checklist.md)
=======

>>>>>>> 1eabc84064fe724cbeababae7546eb016b8ed03f

**Project repository:** https://github.com/PartowRoshani/Sandboxes-Search-Project
