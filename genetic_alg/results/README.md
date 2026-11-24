
# Sandboxes Search Project – Genetic Algorithm

## Exercise 3 – Local Search

In this exercise, I implemented a Genetic Algorithm (GA) to solve the Sandboxes problem. The goal is to find a valid sequence of actions that empties all sandboxes while minimizing the total path cost.

The implementation uses the same SandGrid model and rules from the previous exercises, without water and concrete.

## Problem Representation

Unlike the previous search algorithms, each candidate solution represents a sequence of actions instead of just the current grid state.

Each chromosome has a fixed length. All chromosomes are evaluated from the same initial state. If the goal is reached before the end of the sequence, the remaining actions are ignored.

## Fitness Function

The fitness function evaluates each chromosome based on:

- Whether the goal is reached.
- The minimum conflict number observed during the sequence.
- The path cost required to reach that minimum conflict.
- The validity of the executed actions.

The conflict number represents the number of sandboxes that still contain sand.

Invalid action sequences receive a fitness of zero. Complete solutions receive a large fitness value, and cheaper solutions receive higher scores.

I used a logarithmic transformation of the path cost to control its effect on the fitness function. The implementation also supports linear and square root transformations for further experiments.

## Genetic Algorithm

The algorithm follows the Darwinian approach discussed in class.

The main steps are:

1. Generate a random initial population using legal actions.
2. Evaluate the fitness of each chromosome.
3. Select parents using Roulette Wheel Selection.
4. Generate children using crossover.
5. Apply random mutations.
6. Transfer the two best chromosomes directly to the next generation.
7. Add new random individuals to maintain population diversity.
8. Repeat until the stopping condition is reached.

Both single-point and two-point crossover are supported. Mutation can replace a random action or swap two actions.

Invalid offspring are not repaired.

## Experimental Results

I initially tested chromosomes with a length of 50. For the instructor's example, I later reduced the chromosome length to 18.

The instructor's initial grid is:

```text
1 0
0 1
0 1
1 0
```

The Genetic Algorithm was compared with all eight algorithms implemented in the previous exercises.

| Algorithm | Best Cost | Median Cost | Median Time (s) | Successful Runs |
|---|---:|---:|---:|---:|
| Greedy | 47 | 47 | 0.0002 | 1/1 |
| Random | 45 | 61 | 0.0018 | 5/5 |
| DFS | 47 | 47 | 0.0011 | 1/1 |
| BFS | 47 | 47 | 0.2322 | 1/1 |
| IDS | 47 | 47 | 4.5483 | 1/1 |
| UCS | 34 | 34 | 2.0326 | 1/1 |
| A* | 34 | 34 | 2.3712 | 1/1 |
| RBFS | — | — | 27.5154 | 0/1 |
| Genetic Algorithm | 37 | 41 | 1.2679 | 5/5 |

The Genetic Algorithm found a valid solution in all five runs with chromosome length 18.

Its best cost was 37, compared with the optimal cost of 34 found by UCS and A*. Although GA did not reach the optimal cost, it found better solutions than several previous algorithms.

## Harder Benchmark

I also tested the Genetic Algorithm on a harder initial grid, where reaching the goal was more difficult.

In this experiment, the conflict number was useful for evaluating chromosomes that could not completely empty the grid.

I also compared the full Genetic Algorithm with a version without crossover to investigate the effect of crossover on solution quality and success rate.

## Project Structure

| File | Description |
|---|---|
| `core.py` | Main Genetic Algorithm |
| `fitness.py` | Fitness, goal test and conflict number |
| `operators.py` | Selection, crossover and mutation |
| `experiments.py` | Experimental evaluation |
| `dashboard.py` | Interactive result visualization |
| `cli.py` | Command-line interface |
| `tests/` | Unit and integration tests |
| `results/` | Experimental results and dashboards |

## Installation

Run the following commands from the root directory of the repository:

```bash
python -m pip install -r requirements.txt
python -m pip install -r genetic_alg/requirements.txt
```

## Running the Algorithm

Run the Genetic Algorithm on the instructor's example:

```bash
python -m genetic_alg solve --example professor --population 50 --length 18 --generations 100 --seed 42
```

Compare GA with the previous search algorithms:

```bash
python -m genetic_alg compare --example professor --population 50 --length 18 --generations 100 --repeats 5 --seed 42 --ga-seconds 30 --baseline-seconds 30 --output genetic_alg/results/professor_length18
```

Compare different cost transformations:

```bash
python -m genetic_alg study --example professor --transforms log linear sqrt --population 50 --length 18 --generations 100 --repeats 5 --seed 42
```

Run the tests:

```bash
python -m unittest discover -s genetic_alg/tests -v
```

## Dashboards and Results

The experiments generate interactive HTML dashboards containing:

- Solution cost comparison
- Execution time comparison
- Success rates
- Fitness convergence
- Conflict number
- Valid and invalid chromosomes
- Population diversity

The results are also saved as CSV and JSON files. The HTML dashboards can be opened directly in a browser without an internet connection.

All source code and experimental results for Exercise 3 are available in the [genetic_alg directory](https://github.com/PartowRoshani/Sandboxes-Search-Project/tree/main/genetic_alg).

## Conclusion

The Genetic Algorithm successfully finds valid action sequences and improves their cost over successive generations.

The experiments showed that chromosome length, fitness design, selection, crossover and mutation affect the final results. However, unlike UCS and A*, the Genetic Algorithm does not guarantee an optimal solution.

## Project Information

- **Course:** Artificial Intelligence
- **Student:** Partow Roshani
- **Instructor:** Dr. Katanforoush
- **Exercise:** 3 – Local Search and Genetic Algorithm
- **Semester:** First semester, 1405–1406