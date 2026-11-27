# Sandboxes Search Project – Genetic Algorithm

## Exercise 3 – Local Search

In this exercise, I implemented a Genetic Algorithm (GA) to solve the Sandboxes problem. The goal is to find a valid sequence of actions that empties all sandboxes while minimizing the total path cost.

The implementation uses the same SandGrid simulation model as the previous exercises, without water and concrete.

## Problem Representation

Each chromosome represents a fixed-length sequence of actions. Unlike the previous search algorithms, the candidate solution contains the history of actions used to reach a state.

All chromosomes in a run are evaluated from the same initial state. If the goal is reached before the end of a sequence, the remaining actions are ignored and the path cost is calculated only up to the goal.

The initial population is generated randomly using legal actions.

## Fitness Function

The conflict number is the number of sandboxes that still contain sand. For each sequence, I record the minimum conflict number reached during execution and the path cost at its first occurrence.

The fitness function is defined as follows:

```text
Invalid sequence:  F = 0
Incomplete route: F = 1000 / (1 + h + q(C))
Complete solution: F = 100000 + 1000 / (1 + p(C_goal))

q(C) = p(C) / (1 + p(C))
```

Here, `h` is the minimum conflict number, `C` is its corresponding path cost, and `C_goal` is the cost of reaching the goal.

The default cost transformation is `p(C) = ln(1 + C)`. Linear and square root transformations are also supported.

The normalized cost penalty is less than 1, so reducing the integer conflict number has priority over reducing cost for incomplete routes. Complete solutions always receive a higher fitness than incomplete routes, and cheaper complete solutions receive higher scores. The objective is to maximize fitness.

## Genetic Algorithm

The implementation follows the Darwinian approach discussed in class. The main steps are:

1. Generate a random initial population.
2. Evaluate each chromosome.
3. Create a mating pool using Roulette Wheel Selection with replacement and scaled fitness weights.
4. Generate children using crossover.
5. Apply random mutations.
6. Keep the two best individuals unchanged through elitism.
7. Add random individuals (10% of the population by default).
8. Repeat until the stopping condition is reached.

Both single-point and two-point crossover are supported. Mutation randomly replaces an action or swaps two actions.

In the final `classroom` mode, a lethal mutation receives zero fitness and is rejected. Another random mutation is attempted, up to 10 times by default. If no valid mutation is found, a valid original child or parent is kept when possible; otherwise a new random sequence is generated. No local learning or fitness-based repair is used. Invalid crossover offspring that are not mutated may still receive zero fitness during evaluation.

The original implementation is also available as `legacy` mode for comparison.

## Instructor's Example

The initial grid is:

```text
1 0
0 1
0 1
1 0
```

I initially used chromosomes of length 50, then reduced the length to 18 for this example. The final comparison used a population of 50, 100 generations and five GA runs with seeds 42–46.

| Algorithm | Best Cost | Median Cost | Median Time (s) | Successful Runs |
|---|---:|---:|---:|---:|
| Greedy | 47 | 47 | 0.0001 | 1/1 |
| Random | 45 | 61 | 0.0015 | 5/5 |
| DFS | 47 | 47 | 0.0010 | 1/1 |
| BFS | 47 | 47 | 0.1799 | 1/1 |
| IDS | 47 | 47 | 2.6606 | 1/1 |
| UCS | 34 | 34 | 1.0262 | 1/1 |
| A* | 34 | 34 | 0.8998 | 1/1 |
| RBFS | — | — | 14.0446 | 0/1 |
| GA (Classroom) | 39 | 43 | 1.2147 | 5/5 |

The final GA solved all five runs. Its best cost was 39, compared with the optimal cost of 34 found by UCS and A*. It found cheaper solutions than several of the previous algorithms, but did not find the optimal solution in this example.

### Legacy vs. Classroom

| Metric | Legacy | Classroom |
|---|---:|---:|
| Successful runs | 5/5 | 5/5 |
| Best cost | 37 | 39 |
| Median cost | 41 | 43 |
| Mean cost | 40.8 | 42.2 |
| Median time (s) | 1.8093 | 1.2147 |

The Classroom version follows the project requirements more closely. For seed 42, the average proportion of valid chromosomes increased from 75.74% to 89.35%. However, the final costs were slightly higher in this comparison. The two modes can also perform different numbers of fitness evaluations.

### Cost Transformation Study

I compared three cost transformations in Classroom mode with chromosome length 18.

| Transformation | Successful Runs | Best Cost | Mean Cost |
|---|---:|---:|---:|
| Linear | 5/5 | 39 | 41.6 |
| Log | 5/5 | 39 | 42.2 |
| Square root | 5/5 | 39 | 42.2 |

Linear performed slightly better in this experiment. Five runs are not enough to establish that it is generally better.

## Harder Benchmark

Before the Classroom changes, I also tested GA on a harder initial grid and compared the full algorithm with a version without crossover over 30 random seeds.

| Metric | Full GA | No Crossover |
|---|---:|---:|
| Successful runs | 10/30 | 7/30 |
| Success rate | 33.33% | 23.33% |
| Best solved cost | 67 | 73 |
| Final minimum conflict = 0 | 10 | 7 |
| Final minimum conflict = 1 | 15 | 16 |
| Final minimum conflict = 2 | 5 | 7 |

The full GA found more complete solutions in this experiment. The conflict number was useful for comparing incomplete routes. These are historical results, and the CSV does not contain the corresponding path costs for incomplete routes.

## Final Benchmark – 100 Random Problems

I evaluated the final Classroom GA against UCS on 100 distinct, nonempty 4 × 2 initial grids, sampled randomly without replacement using seed 42. Both algorithms used the same initial grid for each problem. UCS provided the optimal path cost, which was not given to GA.

The benchmark uses the following default GA settings:

| Parameter | Value |
|---|---:|
| Population | 50 |
| Chromosome length | 18 |
| Generations | 100 |
| Mutation rate | 0.30 |
| Crossover rate | 0.85 |
| Elites | 2 |
| Random immigrants | 10% |
| Mutation attempts | 10 |
| Cost transformation | Log |

### Results

| Metric | Result |
|---|---:|
| Distinct initial states | 100 |
| GA successful runs | 100/100 (100%) |
| UCS successful runs | 100/100 (100%) |
| GA optimal solutions | 29/100 (29%) |
| GA nonoptimal solutions | 71 |
| Mean GA / optimal cost (all cases) | 1.104319 |
| Mean GA / optimal cost (successful GA cases) | 1.104319 |
| Mean GA path cost | 37.37 |
| Mean UCS path cost | 33.41 |
| Median GA time (s) | 2.3505 |
| Median UCS time (s) | 0.3350 |

The percentage of optimal GA solutions is calculated among successful GA runs. For each solved case, the cost ratio is `GA_path_cost / UCS_path_cost`. The reported means are arithmetic means of the individual ratios, not ratios of the mean costs.

GA solved every problem in this sample and found the optimal cost in 29% of them. Its solutions cost 10.43% more than the optimum on average. Both requested mean ratios are equal because every case was solved. UCS was faster in 85 cases and GA was faster in 15 cases.

For failed GA runs, the benchmark treats the goal cost as infinite when calculating the all-case mean. If the UCS optimum is unknown, the corresponding ratio is left unresolved. Neither situation occurred in this experiment.

## Project Structure

| File or Directory | Description |
|---|---|
| `../sandgrid/` | Simulation environment and previous search algorithms |
| `core.py` | Main genetic algorithm |
| `fitness.py` | Sequence evaluation, goal test, conflict number and fitness |
| `operators.py` | Selection, mating pool, crossover and mutation |
| `experiments.py` | Experimental evaluation |
| `benchmark_100.py` | Evaluation on 100 different random initial states |
| `dashboard.py` | HTML result visualization |
| `cli.py` | Command-line interface |
| `run_all.sh`, `run_all.ps1` | Experiment scripts |
| `run_benchmark_100.ps1` | Windows benchmark script |
| `tests/` | Unit and integration tests |
| `results/` | Experimental results, configurations and dashboards |
| `Sand_Project_Exercise3.pdf` | Project report |
| `GPTConversationLink.txt` | AI conversation references |

## Installation

Run these commands from the root directory of the repository:

```bash
python -m pip install -r requirements.txt
python -m pip install -r genetic_alg/requirements.txt
```

## Running the Algorithm

Run GA on the instructor's example:

```bash
python -m genetic_alg solve --example professor --population 50 --length 18 --generations 100 --seed 42 --evolution-mode classroom
```

Compare GA with the previous search algorithms:

```bash
python -m genetic_alg compare --example professor --population 50 --length 18 --generations 100 --repeats 5 --seed 42 --baseline-seconds 30 --evolution-mode classroom --output genetic_alg/results/classroom_length18
```

Run the original GA for comparison:

```bash
python -m genetic_alg compare --example professor --no-baselines --population 50 --length 18 --generations 100 --repeats 5 --seed 42 --evolution-mode legacy --output genetic_alg/results/legacy_recheck18
```

Compare cost transformations:

```bash
python -m genetic_alg study --example professor --transforms log linear sqrt --population 50 --length 18 --generations 100 --repeats 5 --seed 42 --evolution-mode classroom --output genetic_alg/results/classroom_fitness_study
```

Run the final 100-problem benchmark:

```bash
python -m genetic_alg.benchmark_100
```

Resume an interrupted benchmark:

```bash
python -m genetic_alg.benchmark_100 --resume
```

Run the tests:

```bash
python -m unittest discover -s genetic_alg/tests -v
```

## Dashboards and Results

The experiments save results as CSV and JSON files and generate HTML dashboards that can be opened offline. The final benchmark writes the following files to `results/benchmark_100/`:

- `comparison.csv`: individual results, path costs, runtimes and cost ratios.
- `summary.json`: success rate, optimality rate and mean cost ratios.
- `experiment_config.json`: experiment settings and sampled initial states.
- `checkpoint.json`: saved progress for resuming the benchmark.
- `dashboard.html`: summary charts and per-case results.

The main GA dashboards also show fitness convergence, conflict number, chromosome validity and population diversity.

All source code, documentation and experimental results for Exercise 3 are organized in the [genetic_alg directory](https://github.com/PartowRoshani/Sandboxes-Search-Project/tree/main/genetic_alg).

## Conclusion

GA successfully found valid action sequences in all 100 random test problems, but only 29 solutions had the optimal cost. Unlike UCS, GA does not guarantee an optimal solution. The results also show that changing the chromosome length, genetic operators and fitness design can affect the quality of the solutions.

## Project Information

- **Course:** Artificial Intelligence
- **Student:** Partow Roshani
- **Instructor:** Dr. Katanforoush
- **Exercise:** 3 – Local Search and Genetic Algorithm
- **Semester:** First semester, 1405–1406
