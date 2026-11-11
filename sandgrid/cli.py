"""Command-line interface: python main.py solve|compare|analyze|benchmark."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .model import SandGrid
from .search import greedy, search
from .visualize import save_html, save_gif
from .benchmark import ALGORITHMS

PROFESSOR_EXAMPLE = [[1, 0], [0, 1], [0, 1], [1, 0]]


def _model_and_initial(args) -> tuple[SandGrid, int]:
    if args.example == 'professor':
        model = SandGrid(4, 2)
        return model, model.from_display(PROFESSOR_EXAMPLE)
    model = SandGrid(args.rows, args.cols)
    if args.grid is not None:
        return model, model.from_display(json.loads(args.grid), args.convention)
    return model, model.random_state(args.seed)


def _add_initial(parser):
    parser.add_argument('--example', choices=['professor'], help='Professor 4x2 example')
    parser.add_argument('--rows', type=int, default=5)
    parser.add_argument('--cols', type=int, default=2)
    parser.add_argument('--seed', type=int, default=42,
                        help='Random initial-grid seed, if --grid not supplied')
    parser.add_argument('--random-seed', type=int, default=None,
                        help='Seed for Random algorithm action ordering (defaults to --seed)')
    parser.add_argument('--grid', help='JSON matrix, e.g. [[1,0],[0.5,1]]')
    parser.add_argument('--convention', choices=['full-is-1','empty-is-1'],
                        default='full-is-1',
                        help='Input format; default 1=full, 0=empty')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='sandgrid',
                                     description='Sand-grid search with continuous-flow gates')
    cmds = parser.add_subparsers(dest='command', required=True)
    solve = cmds.add_parser('solve', help='Solve a grid')
    _add_initial(solve)
    solve.add_argument('--algorithm', default='astar', choices=ALGORITHMS)
    solve.add_argument('--heuristic', choices=['basic','relax','ml','ml-tie'],
                       default='basic', help='Heuristic for A* / RBFS; ml-tie is A* only')
    solve.add_argument('--ml-model', help='Trained model file for ml and ml-tie')
    solve.add_argument('--html', help='Save interactive offline HTML')
    solve.add_argument('--gif', help='Save looping GIF')
    solve.add_argument('--json-out', help='Save steps to JSON')
    solve.add_argument('--limit-seconds', type=float, default=30)
    solve.add_argument('--limit-expansions', type=int, default=500000)
    solve.add_argument('--max-depth', type=int, default=30)
    compare = cmds.add_parser('compare', help='Compare all eight algorithms on identical grid')
    _add_initial(compare)
    compare.add_argument('--heuristic', choices=['basic','relax','ml','ml-tie'], default='basic')
    compare.add_argument('--ml-model', help='Trained ML model for A*')
    compare.add_argument('--limit-seconds', type=float, default=2)
    compare.add_argument('--limit-expansions', type=int, default=100000)
    compare.add_argument('--max-depth', type=int, default=20)
    analyze = cmds.add_parser('analyze', help='Exact analysis of all initial grids, for small sizes')
    analyze.add_argument('--rows', type=int, default=3)
    analyze.add_argument('--cols', type=int, default=2)
    analyze.add_argument('--output', default='results/exhaustive_3x2_continuous')
    analyze.add_argument('--max-states', type=int, default=250000)
    analyze.add_argument('--no-plots', action='store_true')
    bench = cmds.add_parser('benchmark', help='Independent runtime/memory measurements')
    bench.add_argument('--rows', type=int, default=5)
    bench.add_argument('--cols', type=int, default=2)
    bench.add_argument('--count', type=int, default=30)
    bench.add_argument('--all', action='store_true', help='All 3**N grids; potentially very slow')
    bench.add_argument('--seed', type=int, default=42)
    bench.add_argument('--random-seed', type=int, default=None,
                            help='Base seed for Random action ordering')
    bench.add_argument('--algorithms', nargs='+', choices=ALGORITHMS, default=list(ALGORITHMS))
    bench.add_argument('--limit-seconds', type=float, default=.35)
    bench.add_argument('--limit-expansions', type=int, default=30000)
    bench.add_argument('--max-depth', type=int, default=20)
    bench.add_argument('--output', default='results/benchmark.csv')
    bench.add_argument('--no-resume', action='store_true')
    args = parser.parse_args(argv)

    if args.command == 'analyze':
        from .batch import BatchTooLarge, compute_all_optimal, write_full_analysis
        model = SandGrid(args.rows, args.cols)
        try:
            result = compute_all_optimal(model, max_states=args.max_states)
        except BatchTooLarge as exc:
            print('Exact analysis skipped:', exc, file=sys.stderr)
            return 2
        summary = write_full_analysis(result, args.output,
                                      make_plots=not args.no_plots)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    if args.command == 'benchmark':
        from .benchmark import benchmark, summarize
        model = SandGrid(args.rows, args.cols)
        stats = benchmark(model, args.output, count=args.count, all_states=args.all,
                          seed=args.seed, algorithms=tuple(args.algorithms),
                          max_seconds=args.limit_seconds,
                          max_expansions=args.limit_expansions,
                          max_depth=args.max_depth, resume=not args.no_resume,
                          random_seed=args.random_seed)
        dest = Path(args.output).with_name('benchmark_summary.csv')
        report = summarize(args.output, dest)
        print(json.dumps(stats, indent=2))
        for row in report:
            print(row)
        return 0

    model, initial = _model_and_initial(args)
    print('Grid (1=full, 0.5=half, 0=empty):')
    print(model.cell_string(initial))
    if args.command == 'compare':
        print('\nAlgorithm  Status             Cost   Actions  Expanded   Time (s)')
        print('-'*67)
        for algorithm in ALGORITHMS:
            answer = (greedy(model, initial) if algorithm=='greedy' else
                      search(model, initial, algorithm,
                             max_seconds=args.limit_seconds,
                             max_expansions=args.limit_expansions,
                             max_depth=args.max_depth,
                             heuristic_name=(args.heuristic if algorithm == 'astar' else
                                             args.heuristic if algorithm == 'rbfs' and
                                             args.heuristic in ('basic', 'relax') else 'basic'),
                             ml_model_path=args.ml_model,
                             random_seed=(args.random_seed if args.random_seed is not None
                                          else args.seed)))
            print(f'{algorithm:10} {answer.status:18} {str(answer.cost):6} '
                  f'{answer.action_count:7} {answer.expanded:9} '
                  f'{answer.elapsed_sec:.4f}')
        return 0
    result = (greedy(model, initial) if args.algorithm == 'greedy' else
              search(model, initial, args.algorithm,
                     max_seconds=args.limit_seconds,
                     max_expansions=args.limit_expansions,
                     max_depth=args.max_depth,
                     heuristic_name=args.heuristic if args.algorithm in ('astar','rbfs') else 'basic',
                     ml_model_path=args.ml_model,
                     random_seed=(args.random_seed if args.random_seed is not None
                                  else args.seed)))
    print(f'Algorithm={result.algorithm}, status={result.status}, cost={result.cost}, '
          f'actions={result.action_count}, expanded={result.expanded}')
    if not result.found:
        print('No confirmed solution within resource limits.', file=sys.stderr)
        return 2
    trace = model.trace(initial, result.actions)
    for idx, action_id in enumerate(result.actions, 1):
        item = trace[idx]
        print(f'{idx:2} {model.actions[action_id].label:32} '
              f'+{item["step_cost"]:2} total={item["total_cost"]:3}')
    if args.html:
        print('HTML saved:', save_html(model, initial, result.actions,
                                      args.html, title=f'Sand-grid {result.algorithm.upper()}'))
    if args.gif:
        print('GIF saved:', save_gif(model, initial, result.actions, args.gif))
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = dict(model_version=model.MODEL_VERSION, rows=model.rows, cols=model.cols,
                    display_convention='1=full,0.5=half,0=empty',
                    initial_grid=model.to_display(initial), algorithm=result.algorithm,
                    heuristic=(args.heuristic if args.algorithm in ('astar', 'rbfs') else None),
                    random_seed=((args.random_seed if args.random_seed is not None else args.seed)
                                 if args.algorithm == 'random' else None),
                    cost=result.cost, actions=[model.actions[a].label for a in result.actions],
                    steps=[dict(step=k, grid=model.to_display(t['state']),
                                open_gate_mask=model.decode(t['state'])[1],
                                cost=t['step_cost'], total=t['total_cost'],
                                flow_events=t.get('flow_events', []),
                                closed_gate_bits=t.get('closed_gate_bits', []))
                           for k,t in enumerate(trace)])
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        print('JSON saved:', path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
