#!/usr/bin/env python3
"""Estimate effective branching factor from sand-grid search result CSVs.

Examples:
    python scripts/calc_effective_branching.py --input results/project_with_random/professor/comparison.csv --output results/bstar_professor.csv
    python scripts/calc_effective_branching.py --input results/final_heuristics/comparison_all_seeds.csv --output results/bstar_heuristics.csv

Convention: 'expanded' excludes the goal node in sandgrid.search; therefore
N_effective = expanded + 1 (including the goal). Solve
    1 + b + ... + b**depth = N_effective.

'generated' in sandgrid.search counts successor transitions, including duplicates;
it is also reported for transparency, not as a unique-node count.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from collections import defaultdict
from statistics import mean, median


def estimated_bstar(node_count: int, depth: int) -> float | None:
    """Return positive root of sum(b**k, k=0..depth) == node_count.

    This is a tree-equivalent estimate for a graph search. No estimate is
    reported for depth 0 or impossible/insufficient counts.
    """
    if depth <= 0 or node_count < 2:
        return None
    lo, hi = 0.0, 2.0

    def cumulative(b: float) -> float:
        s, term = 1.0, 1.0
        for _ in range(depth):
            term *= b
            s += term
            if s > node_count * 2:
                break
        return s

    while cumulative(hi) < node_count:
        hi *= 2.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if cumulative(mid) < node_count:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def analyze(source: Path) -> list[dict]:
    rows: list[dict] = []
    with source.open(newline='', encoding='utf-8-sig') as f:
        for record in csv.DictReader(f):
            if record.get('status') != 'found':
                continue
            depth_text = record.get('action_count', '')
            if not depth_text:
                continue
            depth = int(depth_text)
            if depth == 0:  # goal was already empty
                continue
            expanded = int(record['expanded'])
            generated_text = record.get('generated', '')
            generated = int(generated_text) if generated_text else None
            # In this project's search.py the goal is found BEFORE expanded++.
            b_expanded = estimated_bstar(expanded + 1, depth)
            b_generated = estimated_bstar(generated + 1, depth) if generated is not None else None
            rows.append({
                'example_or_code': record.get('example', record.get('initial_code', '')),
                'method': record.get('method', record.get('algorithm', '')),
                'status': record['status'],
                'depth': depth,
                'expanded': expanded,
                'generated': '' if generated is None else generated,
                'bstar_expanded': '' if b_expanded is None else f'{b_expanded:.6f}',
                'bstar_generated': '' if b_generated is None else f'{b_generated:.6f}',
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description='Estimate effective branching factor b* from completed sand-grid searches')
    parser.add_argument('--input', required=True, type=Path, help='Comparison CSV file')
    parser.add_argument('--output', type=Path, help='Optional output CSV')
    parser.add_argument('--summary-output', type=Path, help='Optional per-method averages and medians')
    args = parser.parse_args()
    rows = analyze(args.input)
    for r in rows:
        print(f"{str(r['method']):18} d={r['depth']:<3} expanded={r['expanded']:<7} "
              f"b*(expanded)={str(r['bstar_expanded']):>8} "
              f"b*(generated)={str(r['bstar_generated']):>8}")
    print(f'Completed solutions analyzed: {len(rows)}')
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        columns = ('example_or_code', 'method', 'status', 'depth', 'expanded',
                   'generated', 'bstar_expanded', 'bstar_generated')
        with args.output.open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        print(f'Saved: {args.output}')
    if args.summary_output:
        grouped = defaultdict(list)
        for r in rows:
            if r['bstar_expanded']:
                grouped[r['method']].append(float(r['bstar_expanded']))
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_output.open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(('method', 'solved_count', 'mean_bstar_expanded', 'median_bstar_expanded'))
            for method, values in grouped.items():
                writer.writerow((method, len(values), f'{mean(values):.6f}', f'{median(values):.6f}'))
        print(f'Saved: {args.summary_output}')


if __name__ == '__main__':
    main()
