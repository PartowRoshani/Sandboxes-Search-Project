"""Compare three path-score algorithms against Greedy and UCS on professor grid.

Run from the project root:
    python scripts/compare_path_local_search.py --trials 10 --evaluations 2500
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
from statistics import median

from sandgrid.model import SandGrid
from sandgrid.search import greedy, search
from sandgrid.local_search import optimize_paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trials', type=int, default=10)
    parser.add_argument('--evaluations', type=int, default=2500)
    parser.add_argument('--output', default='results/path_local_search_comparison.csv')
    args = parser.parse_args()
    if args.trials <= 0:
        parser.error('--trials must be positive')
    model = SandGrid(4, 2)
    initial = model.from_display([[1, 0], [0, 1], [0, 1], [1, 0]])
    baseline, optimal = greedy(model, initial), search(model, initial, 'ucs')
    print('Greedy cost:', baseline.cost, '| UCS optimal cost:', optimal.cost)
    rows = []
    for algorithm in ('hillclimb', 'anneal', 'genetic'):
        costs = []
        success = 0
        for seed in range(args.trials):
            run = optimize_paths(model, initial, algorithm,
                                 random_seed=seed,
                                 max_evaluations=args.evaluations,
                                 max_seconds=None)
            outcome = run.evaluation
            success += outcome.found_goal
            if outcome.found_goal:
                costs.append(outcome.path_cost)
            rows.append({'algorithm': algorithm, 'seed': seed,
                         'found': outcome.found_goal,
                         'cost': outcome.path_cost if outcome.found_goal else '',
                         'score': round(outcome.score, 4),
                         'evaluations': run.evaluations,
                         'elapsed_sec': round(run.elapsed_sec, 5),
                         'chromosome_length': len(run.best_path),
                         'executed_actions': len(outcome.executed_actions),
                         'goal_index': outcome.goal_index if outcome.goal_index is not None else '',
                         'remaining_half_units': outcome.remaining_units})
        print(f'{algorithm}: success {success}/{args.trials}, '
              f'best cost {min(costs) if costs else "N/A"}, '
              f'median success cost {median(costs) if costs else "N/A"}')
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print('Saved:', destination)


if __name__ == '__main__':
    main()
