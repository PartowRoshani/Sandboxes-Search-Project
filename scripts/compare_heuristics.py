#!/usr/bin/env python3
"""Compare UCS and A* variants on held-out, closed-gate initial grids.

Held-out refers to the *initial occupancy patterns*: intermediate states
visited by a search can share occupancy patterns with training states. The
predictions are computed online, without access to exact test labels.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import random
import sys
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sandgrid.model import SandGrid
from sandgrid.heuristics import choose
from sandgrid.search import search

METHODS = [
    ('UCS', 'ucs', 'basic'),
    ('A* basic', 'astar', 'basic'),
    ('A* relax', 'astar', 'relax'),
    ('A* ML direct', 'astar', 'ml'),
    ('A* ML safe tie', 'astar', 'ml-tie'),
]


def run_benchmark(model_path: Path, output: Path, count: int, seed: int,
                  seconds: float, expansions: int, repeats: int = 1,
                  measure_memory: bool = False) -> tuple[list[dict], list[dict]]:
    if count < 1 or repeats < 1 or seconds <= 0 or expansions < 1:
        raise ValueError('count, repeats, seconds and expansions must be positive')
    split_path = model_path.parent / 'test_initial_codes.json'
    split = json.loads(split_path.read_text(encoding='utf-8'))
    model = SandGrid(split['rows'], split['cols'])
    if split['model_version'] != model.MODEL_VERSION:
        raise ValueError('Model version mismatch; regenerate training data')
    # Data leakage guard: test initial occupancy patterns are disjoint from
    # training occupancy patterns, if the new split manifest is present.
    manifest_path = model_path.parent / 'dataset_split.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        train_codes = set(manifest['train_occupancy_codes'])
        test_codes = set(manifest['test_occupancy_codes'])
        assert train_codes.isdisjoint(test_codes), 'train/test occupancy split overlap'
        assert test_codes == set(split['heldout_closed_gate_initial_codes'])
    output.mkdir(parents=True, exist_ok=True)
    # Warm model loading, but NOT predictions. Search time includes inference.
    choose(model, 'ml', str(model_path))
    codes = [int(c) for c in split['heldout_closed_gate_initial_codes'] if c != 0]
    if not codes:
        raise ValueError('No held-out nonempty initial grids')
    rng = random.Random(seed)
    rng.shuffle(codes)
    codes = codes[:count]
    rows = []
    for repetition in range(1, repeats + 1):
        for index, code in enumerate(codes, 1):
            answers = {}
            for label, algorithm, heuristic in METHODS:
                result = search(model, code, algorithm,
                                heuristic_name=heuristic,
                                ml_model_path=str(model_path) if 'ml' in heuristic else None,
                                max_seconds=seconds, max_expansions=expansions,
                                measure_memory=measure_memory)
                answers[label] = result
            baseline = answers['UCS']
            if baseline.found:
                for label in ('A* basic', 'A* relax', 'A* ML safe tie'):
                    other = answers[label]
                    if other.found and other.cost != baseline.cost:
                        raise AssertionError(
                            f'{label} lost optimality: code={code}, '
                            f'expected={baseline.cost}, actual={other.cost}')
            for label, algorithm, heuristic in METHODS:
                result = answers[label]
                rows.append({
                    'repeat': repetition, 'initial_code': code,
                    'heldout_initial': True, 'method': label,
                    'algorithm': algorithm, 'heuristic': heuristic,
                    'status': result.status,
                    'cost': result.cost if result.found else '',
                    'ucs_optimal_cost': baseline.cost if baseline.found else '',
                    'optimality_gap': (result.cost - baseline.cost
                                       if result.found and baseline.found else ''),
                    'expanded': result.expanded,
                    'elapsed_sec': round(result.elapsed_sec, 6),
                    'peak_python_bytes': (result.peak_memory_bytes if measure_memory else ''),
                    'action_count': result.action_count if result.found else '',
                })
            print(f'[repeat {repetition}/{repeats} grid {index}/{len(codes)}] '
                  f'code={code} UCS={baseline.cost} '
                  f'Relax={answers["A* relax"].cost} '
                  f'ML={answers["A* ML direct"].cost}', flush=True)
    with (output / 'comparison.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for label, _, _ in METHODS:
        subset = [r for r in rows if r['method'] == label]
        solved = [r for r in subset if r['status'] == 'found']
        comparable = [r for r in solved if r['optimality_gap'] != '']
        summary.append({
            'method': label,
            'attempts': len(subset),
            'solved': len(solved),
            'comparable': len(comparable),
            'optimal_fraction_of_comparable': (
                round(sum(r['optimality_gap'] == 0 for r in comparable)
                      / len(comparable), 6) if comparable else None),
            'mean_expanded_all_runs': round(mean(r['expanded'] for r in subset), 2),
            'mean_seconds_all_runs': round(mean(r['elapsed_sec'] for r in subset), 6),
            'median_seconds_all_runs': round(median(r['elapsed_sec'] for r in subset), 6),
            'mean_cost_gap_solved': (
                round(mean(r['optimality_gap'] for r in comparable), 6)
                if comparable else None),
            'median_memory_kib': (round(median(r['peak_python_bytes'] for r in subset)
                                        / 1024, 2) if measure_memory else None),
        })
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    (output / 'experiment.json').write_text(json.dumps({
        'model': str(model_path.resolve()),
        'model_version': model.MODEL_VERSION, 'rows': model.rows, 'cols': model.cols,
        'training_split_seed': json.loads((model_path.parent / 'metrics.json').read_text())['seed'],
        'selection_seed': seed, 'initial_codes': codes,
        'repetitions': repeats, 'seconds_limit': seconds,
        'expansion_limit': expansions, 'measure_memory': measure_memory,
        'initial_states_heldout_by_occupancy': True,
        'intermediate_states_guaranteed_heldout': False,
        'training_and_model_loading_excluded_from_timing': True,
        'online_inference_included_in_timing': True,
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    charts = [
        ('expanded.png', 'mean_expanded_all_runs', 'Expanded states', 'Mean expanded states'),
        ('runtime.png', 'mean_seconds_all_runs', 'Search time', 'Mean seconds'),
    ]
    if measure_memory:
        charts.append(('memory.png', 'median_memory_kib', 'Python peak memory',
                       'Median peak KiB, tracemalloc'))
    for filename, key, title, ylabel in charts:
        fig, ax = plt.subplots(figsize=(9, 4.6))
        ax.bar([r['method'] for r in summary], [r[key] for r in summary])
        ax.set(title=title, ylabel=ylabel)
        ax.tick_params(axis='x', rotation=20)
        fig.tight_layout()
        fig.savefig(output / filename, dpi=160)
        plt.close(fig)
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description='Compare A* on held-out initial grids')
    parser.add_argument('--model', type=Path,
                        default=Path('results/ml_3x2/heuristic_ml.joblib'))
    parser.add_argument('--output', type=Path,
                        default=Path('results/heuristic_comparison'))
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--seconds', type=float, default=15)
    parser.add_argument('--expansions', type=int, default=100_000)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--measure-memory', action='store_true')
    args = parser.parse_args()
    summary, _ = run_benchmark(args.model, args.output, args.count, args.seed,
                               args.seconds, args.expansions, args.repeats,
                               args.measure_memory)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
