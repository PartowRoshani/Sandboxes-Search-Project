"""Command-line entry point: python -m sandgrid.cli --help"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .model import SandGrid
from .search import greedy, search
from .visualize import save_html, save_gif

PROFESSOR_EXAMPLE = [[1, 0], [0, 1], [0, 1], [1, 0]]


def _model_and_initial(args) -> tuple[SandGrid, int]:
    if args.example == 'professor':
        model = SandGrid(4, 2)
        initial = model.from_display(PROFESSOR_EXAMPLE, 'full-is-1')
    else:
        model = SandGrid(args.rows, args.cols)
        if args.grid is not None:
            initial = model.from_display(json.loads(args.grid), args.convention)
        else:
            initial = model.random_state(args.seed)
    return model, initial


def _add_initial(parser):
    parser.add_argument('--example', choices=['professor'], help='Teacher\'s 4x2 binary example')
    parser.add_argument('--rows', type=int, default=5)
    parser.add_argument('--cols', type=int, default=2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--grid', help='JSON matrix such as [[0,1],[0.5,0]]')
    parser.add_argument('--convention', choices=['empty-is-1', 'full-is-1'],
                        default='empty-is-1')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='sandgrid', description='Sand-grid AI search assignment')
    cmds = parser.add_subparsers(dest='command', required=True)
    solve = cmds.add_parser('solve', help='Solve one specified or random grid')
    _add_initial(solve)
    solve.add_argument('--algorithm', default='astar',
                       choices=['greedy', 'dfs', 'bfs', 'ids', 'ucs', 'astar', 'rbfs'])
    solve.add_argument('--html', help='Output offline animated HTML file')
    solve.add_argument('--gif', help='Output looping animated GIF')
    solve.add_argument('--json-out', help='Output machine-readable solution JSON')
    solve.add_argument('--limit-seconds', type=float, default=30)
    solve.add_argument('--limit-expansions', type=int, default=500000)
    solve.add_argument('--max-depth', type=int, default=30)
    compare = cmds.add_parser('compare', help='Compare all search methods on one grid')
    _add_initial(compare)
    compare.add_argument('--limit-seconds', type=float, default=2)
    compare.add_argument('--limit-expansions', type=int, default=100000)
    compare.add_argument('--max-depth', type=int, default=20)
    analyze = cmds.add_parser('analyze', help='Exact exhaustive 3**N optimal-cost analysis')
    analyze.add_argument('--rows', type=int, default=5)
    analyze.add_argument('--cols', type=int, default=2)
    analyze.add_argument('--output', default='results/exhaustive_5x2')
    analyze.add_argument('--no-plots', action='store_true')
    bench = cmds.add_parser('benchmark', help='Per-grid runtime/memory comparison, resumable')
    bench.add_argument('--rows', type=int, default=5)
    bench.add_argument('--cols', type=int, default=2)
    bench.add_argument('--count', type=int, default=30)
    bench.add_argument('--all', action='store_true', help='EVERY 3**N grid (can be very slow)')
    bench.add_argument('--seed', type=int, default=42)
    bench.add_argument('--algorithms', nargs='+', choices=['greedy','dfs','bfs','ids','ucs','astar','rbfs'],
                       default=['greedy','dfs','bfs','ids','ucs','astar','rbfs'])
    bench.add_argument('--limit-seconds', type=float, default=0.35)
    bench.add_argument('--limit-expansions', type=int, default=30000)
    bench.add_argument('--max-depth', type=int, default=20)
    bench.add_argument('--output', default='results/benchmark.csv')
    bench.add_argument('--no-resume', action='store_true')
    args = parser.parse_args(argv)

    if args.command == 'analyze':
        from .batch import compute_all_optimal, write_full_analysis
        model = SandGrid(args.rows, args.cols)
        batch = compute_all_optimal(model)
        summary = write_full_analysis(batch, args.output, make_plots=not args.no_plots)
        print(json.dumps({k:v for k,v in summary.items() if not k.startswith('ratio_histogram')},
                         ensure_ascii=False, indent=2))
        return 0
    if args.command == 'benchmark':
        from .benchmark import benchmark, summarize
        model = SandGrid(args.rows, args.cols)
        stats = benchmark(model, args.output, count=args.count, all_states=args.all,
                          seed=args.seed, algorithms=tuple(args.algorithms),
                          max_seconds=args.limit_seconds,
                          max_expansions=args.limit_expansions, max_depth=args.max_depth,
                          resume=not args.no_resume)
        report = summarize(args.output, str(Path(args.output).with_name('benchmark_summary.csv')))
        print(json.dumps(stats, indent=2))
        for row in report:
            print(row)
        return 0

    model, initial = _model_and_initial(args)
    print('Grid (statement convention: 0=full, 0.5=half, 1=empty):')
    print(model.cell_string(initial))
    if args.command == 'compare':
        print('\nAlgorithm    Status               Cost     Actions    Expanded   Time (s)')
        print('-' * 75)
        for name in ('greedy','dfs','bfs','ids','ucs','astar','rbfs'):
            result = (greedy(model, initial) if name == 'greedy' else
                      search(model, initial, name, max_seconds=args.limit_seconds,
                             max_expansions=args.limit_expansions, max_depth=args.max_depth))
            print(f'{name:10}   {result.status:18}   {str(result.cost):6}   '
                  f'{result.action_count:7}   {result.expanded:8}   {result.elapsed_sec:.4f}')
        return 0

    result = greedy(model, initial) if args.algorithm == 'greedy' else search(
        model, initial, args.algorithm, max_seconds=args.limit_seconds,
        max_expansions=args.limit_expansions, max_depth=args.max_depth)
    print(f'\nAlgorithm={result.algorithm}, status={result.status}, '
          f'cost={result.cost}, actions={len(result.actions)}, expanded={result.expanded}')
    if not result.found:
        print('No confirmed solution within resource limits.', file=sys.stderr)
        return 2
    trace = model.trace(initial, result.actions)
    for k, a in enumerate(result.actions, 1):
        row = trace[k]
        print(f"{k:2} {model.actions[a].label:27} +{row['step_cost']:2} "
              f"total={row['total_cost']:3}")
    if args.html:
        print('Animation saved:', save_html(model, initial, result.actions, args.html,
                                            title=f'Sand-grid {result.algorithm.upper()} solution'))
    if args.gif:
        print('GIF saved:', save_gif(model, initial, result.actions, args.gif))
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(rows=model.rows, cols=model.cols,
                       initial_grid=model.to_display(initial),
                       algorithm=result.algorithm, status=result.status,
                       cost=result.cost, actions=[model.actions[a].label for a in result.actions],
                       steps=[dict(step=k, grid=model.to_display(t['state']),
                                   cost=t['step_cost'], total=t['total_cost'])
                              for k,t in enumerate(trace)])
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        print('JSON saved:', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
