# Exercise 3: 100 random initial states

This benchmark adds the mandatory evaluation requested for Exercise 3. It does not modify the GA or the original search algorithms.

## Install and run

Place these files in the repository containing both `sandgrid/` and the updated `genetic_alg/` (Classroom patch). From the repository root:

```bash
python -m pip install -r requirements.txt
python -m pip install -r genetic_alg/requirements.txt
python -m unittest discover -s genetic_alg/tests -v
python -m genetic_alg.benchmark_100
```

The benchmark defaults to 100 distinct non-goal 4x2 initial states, sampled uniformly without replacement from the original model's initial code range using seed 42. The initial gates are closed. Each case uses one Classroom GA run (population 50, length 18, 100 generations, log cost, mutation 0.30, crossover 0.85, two elites, 10% immigrants and 10 mutation attempts). Its independent random seed is `42 + 1000 * case_id`. The GA never receives the UCS cost. The original UCS is used as the reference, with a 120-second and 2-million-expansion limit per case and a nonbinding depth ceiling. A failed reference is not counted as an optimum. Goal routes and costs are replay-checked against the original model.

An optional three-case smoke test uses a separate folder and must not be reported as the final 100-case result:

```bash
python -m genetic_alg.benchmark_100 --count 3 --output genetic_alg/results/benchmark_smoke
```

To resume after interruption:

```bash
python -m genetic_alg.benchmark_100 --resume
```

If UCS did not finish some cases, retain all GA results and retry only unresolved references with larger limits:

```bash
python -m genetic_alg.benchmark_100 --resume --retry-reference --ucs-seconds 300 --ucs-expansions 5000000
```

Do not change the sampling seed or GA configuration on resume. Use a new output folder for a different experiment. Reference limits are recorded per case. The checkpoint is saved after each completed pair.

## Outputs

`genetic_alg/results/benchmark_100/` contains:

- `comparison.csv`: one row per problem, including initial grid, both costs, routes, statuses, runtimes, GA minimum conflict and corresponding cost, optimality and ratio.
- `summary.json`: counts, success rates, optimality rates and mean ratios.
- `experiment_config.json`: sampled codes and settings.
- `checkpoint.json`: resumable records.
- `dashboard.html`: offline result dashboard with outcomes and per-case cost ratios.

## Metrics

Success rate is the number of GA successes divided by 100. The percentage of optimal GA successes is the number of solved GA routes whose cost equals UCS divided by all GA successes. The percentage of optimal routes among all 100 is also recorded. Both percentages require a reference for every GA success.

The successful-only mean is the arithmetic mean of each successful GA cost divided by its matched UCS optimum. If GA fails, no goal cost exists: for the all-case mean, the explicit convention is to assign positive infinity to that failed goal cost. If any GA fails and all reference costs are known, the all-case mean is infinity. This is a convention, not a finite estimate; the report should state it. A missing UCS reference leaves the all-case mean unresolved. Undefined/infinite numbers are serialized as JSON null with a separate status field. Partial observed-pair metrics are explicitly labelled and must not be substituted for final metrics. Empty initial grids are excluded to avoid division by zero.

The submitted 100-case evaluation is complete only after 100 cases and all 100 UCS references are recorded. The benchmark source and test results do not replace real experimental outputs.
