#!/usr/bin/env python3
"""Run the sand-grid assignment end-to-end and produce a comparable report.

Examples:
    python run_project.py
    python run_project.py --sample-size 25 --seconds 2
    python run_project.py --full-benchmark --seconds 0.5
    python run_project.py --force-analysis --sample-size 10

The optional --full-benchmark triggers 59,049 x 7 independent runs, which can
be lengthy. Results are appended to a resumable CSV; no incomplete run is
reported as a completed full benchmark.
"""
from __future__ import annotations

import argparse
import csv
import json
from html import escape
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
import tracemalloc

from sandgrid.model import SandGrid
from sandgrid.search import greedy, search
from sandgrid.visualize import save_html, save_gif
from sandgrid.benchmark import ALGORITHMS, benchmark, summarize
from sandgrid.reporting import make_dashboard, write_quality_comparison

ROOT = Path(__file__).resolve().parent
PROFESSOR = [[1, 0], [0, 1], [0, 1], [1, 0]]
COMPARISON_FIELDS = (
    'example', 'algorithm', 'status', 'cost', 'optimality_gap', 'action_count',
    'side_action_count', 'down_action_count', 'elapsed_sec', 'peak_python_kib',
    'expanded', 'generated', 'max_frontier', 'goal_verified', 'animation_html',
)


def info(message: str) -> None:
    print(f'[sand-grid] {message}', flush=True)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def write_csv(path: Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(model: SandGrid, initial: int, label: str, destination: Path,
             seconds: float, expansions: int, depth: int, gif: bool) -> list[dict]:
    """Use the SAME grid for all methods; failures stay visible in CSV."""
    destination.mkdir(parents=True, exist_ok=True)
    save_json(destination / 'initial.json', {
        'label': label, 'rows': model.rows, 'cols': model.cols,
        'input_display_convention': '0=full, 0.5=half, 1=empty',
        'initial_grid': model.to_display(initial),
        'initial_base3_code': initial,
        'limits': {'max_seconds': seconds, 'max_expansions': expansions,
                   'max_depth_ids': depth},
    })
    raw = []
    for algo in ALGORITHMS:
        if algo == 'greedy':
            tracemalloc.start()
            start = perf_counter()
            result = greedy(model, initial)
            elapsed = perf_counter() - start
            peak = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            result.elapsed_sec = elapsed
            result.peak_memory_bytes = peak
        else:
            result = search(model, initial, algo, max_seconds=seconds,
                            max_expansions=expansions, max_depth=depth,
                            measure_memory=True)
        animation_path = ''
        side = sum(model.actions[a].kind == 'side' for a in result.actions)
        verified = False
        if result.found:
            trace = model.trace(initial, result.actions)
            verified = model.is_goal(trace[-1]['state']) and trace[-1]['total_cost'] == result.cost
            if not verified:
                raise AssertionError(f'{algo} produced an invalid solution for {label}')
            animation_file = destination / f'{algo}.html'
            save_html(model, initial, result.actions, animation_file,
                      title=f'{label} — {algo.upper()}')
            animation_path = animation_file.name
            if gif and algo in ('ucs', 'astar'):
                save_gif(model, initial, result.actions, destination / f'{algo}.gif')
            save_json(destination / f'{algo}_steps.json', {
                'algorithm': algo, 'status': result.status, 'total_cost': result.cost,
                'initial_grid': model.to_display(initial),
                'steps': [
                    {'number': n, 'action': (model.actions[t['action']].label
                                             if t['action'] is not None else None),
                     'action_kind': (model.actions[t['action']].kind
                                     if t['action'] is not None else None),
                     'step_cost': t['step_cost'], 'total_cost': t['total_cost'],
                     'grid': model.to_display(t['state']),
                     'open_vertical_mask': model.decode(t['state'])[1]}
                    for n, t in enumerate(trace)
                ],
            })
        raw.append((algo, result, side, verified, animation_path))
        info(f'  {label:10s} {algo:6s} {result.status:16s} '
             f'cost={str(result.cost):>4s} actions={result.action_count:>3} '
             f'time={result.elapsed_sec:.3f}s')
    exact = next((res.cost for name, res, _, _, _ in raw
                  if name == 'ucs' and res.found), None)
    if exact is None:
        exact = next((res.cost for name, res, _, _, _ in raw
                      if name == 'astar' and res.found), None)
    output = []
    for algo, result, side, verified, animation_path in raw:
        output.append(dict(
            example=label, algorithm=algo, status=result.status,
            cost=result.cost if result.cost is not None else '',
            optimality_gap=(result.cost-exact if exact is not None and result.found
                            else ''),
            action_count=result.action_count if result.found else '',
            side_action_count=side if result.found else '',
            down_action_count=result.action_count-side if result.found else '',
            elapsed_sec=round(result.elapsed_sec, 6),
            peak_python_kib=round((result.peak_memory_bytes or 0)/1024, 2),
            expanded=result.expanded, generated=result.generated,
            max_frontier=result.max_frontier,
            goal_verified=verified if result.found else '',
            animation_html=animation_path,
        ))
    write_csv(destination / 'comparison.csv', output, COMPARISON_FIELDS)
    save_json(destination / 'comparison.json', {
        'example': label, 'reference_optimal_cost': exact,
        'reference_note': 'UCS/A* only if solved within resource limits',
        'results': output,
    })
    return output


def plot_comparisons(rows: list[dict], directory: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for label in dict.fromkeys(row['example'] for row in rows):
        group = [r for r in rows if r['example'] == label]
        names = [r['algorithm'].upper() for r in group]
        # Only confirmed solutions have costs; timeouts remain empty, not zero.
        values = [float(r['cost']) if r['status'] == 'found' else float('nan') for r in group]
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.bar(names, values)
        ax.set(ylabel='Total weighted cost (solved only)',
               title=f'Cost comparison — {label}')
        ax.tick_params(axis='x', rotation=25)
        for idx, row in enumerate(group):
            if row['status'] != 'found':
                ax.text(idx, 0, row['status'], rotation=90, ha='center',
                        va='bottom', fontsize=8)
        fig.subplots_adjust(left=.12, right=.96, top=.88, bottom=.16)
        fig.savefig(directory / f'{label}_cost_comparison.png', dpi=160)
        plt.close(fig)


def plot_benchmark(csv_file: Path, directory: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with csv_file.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return
    groups = {name: [r for r in rows if r['algorithm'] == name]
              for name in ALGORITHMS}
    names = [name for name in ALGORITHMS if groups[name]]
    xlabels = [n.upper() for n in names]
    solved = [sum(r['status'] == 'found' for r in groups[n]) / len(groups[n]) * 100
              for n in names]
    times = [median(float(r['elapsed_sec']) for r in groups[n]) for n in names]
    memories = [median(int(r['peak_python_bytes'])/1024 for r in groups[n])
                for n in names]
    expanded = [median(int(r['expanded']) for r in groups[n]) for n in names]
    charts = (
        ('benchmark_success_rate.png', solved, 'Solved before limits (%)',
         'Successful searches / attempted searches'),
        ('benchmark_median_time.png', times, 'Seconds (all statuses)',
         'Median elapsed time, including limited runs'),
        ('benchmark_median_memory.png', memories, 'KiB, Python allocations',
         'Median tracemalloc peak; excludes some native allocations'),
        ('benchmark_median_expanded.png', expanded, 'Expanded nodes',
         'Median expanded nodes, including limited runs'),
    )
    for filename, values, ylabel, title in charts:
        fig, ax = plt.subplots(figsize=(9, 4.4))
        ax.bar(xlabels, values)
        ax.set(xlabel='Algorithm', ylabel=ylabel, title=title)
        fig.tight_layout()
        fig.savefig(directory / filename, dpi=160)
        plt.close(fig)


def analyze_59049(directory: Path, force: bool) -> tuple[dict, bool]:
    summary_file = directory / 'summary.json'
    data_file = directory / 'all_states.csv'
    plots = ['histogram_ratio.png', 'scatter_costs.png', 'scatter_actions.png']
    existing = summary_file.exists() and data_file.exists() and all(
        (directory / file).exists() for file in plots)
    if existing and not force:
        summary = json.loads(summary_file.read_text(encoding='utf-8'))
        if (summary.get('grid_rows'), summary.get('grid_cols'),
                summary.get('initial_state_count')) == (5, 2, 59049):
            info('Reusing validated-shape 5×2 exhaustive output (use --force-analysis to recalculate).')
            return summary, True
    from sandgrid.batch import compute_all_optimal, write_full_analysis
    info('Computing exact optimum for all 59,049 closed-gate initial states...')
    data = compute_all_optimal(SandGrid(5, 2))
    summary = write_full_analysis(data, directory)
    return summary, False


def benchmark_csv_count(filepath: Path) -> tuple[int, int]:
    if not filepath.exists():
        return 0, 0
    with filepath.open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    return len(rows), sum(r['status'] == 'found' for r in rows)


def make_report(directory: Path, comparisons: list[dict], args,
                exhaustive: dict | None, reused: bool, test_ok: bool,
                sample_stats: list[dict] | None, full_stats: list[dict] | None,
                full_rows: int) -> None:
    lines = [
        '# Sand-grid project — generated evaluation report', '',
        f'Generated (UTC): {datetime.now(timezone.utc).isoformat(timespec="seconds")}',
        f'Python: `{sys.version.split()[0]}`; OS: `{platform.system()} {platform.release()}`',
        '', '## Coverage and interpretation', '',
        '- Initial grid: 0=full, 0.5=half, 1=empty; professor example uses reversed values.',
        '- Down cost = 1 + 4 × (sand amount before + sand amount after). Side cost = 1.',
        '- DFS/BFS/IDS/UCS are compulsory; A*/RBFS, animation and exhaustive plots are bonus.',
        '- BFS/IDS minimize action count, while UCS/A* minimize weighted cost.',
        '- This code models connected, persistent vertical gates with immediate settling.',
        '- Water/concrete extension is NOT implemented.',
        f'- Automated test suite in this run: {"PASSED" if test_ok else "NOT RUN / FAILED"}.',
        '', '## Comparison on identical initial grids', '',
        '| Grid | Algorithm | Status | Cost | Actions | Side | Expanded | Seconds | Peak Python KiB |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    for row in comparisons:
        lines.append(f"| {row['example']} | {row['algorithm']} | {row['status']} | "
                     f"{row['cost'] or '—'} | {row['action_count'] if row['action_count'] != '' else '—'} | "
                     f"{row['side_action_count'] if row['side_action_count'] != '' else '—'} | "
                     f"{row['expanded']} | {row['elapsed_sec']:.4f} | "
                     f"{row['peak_python_kib']:.1f} |")
    lines.extend(['',
        'A limited run is not a proof of failure or nonexistence of a solution.',
        'The action count is not the same as weighted cost.',
        'Memory uses `tracemalloc` (not operating-system RSS); timing includes profiling overhead.',
        'Per-step solutions and offline HTML animations are saved beside each comparison.',
        '', '## Exhaustive evaluation (5×2 = 3^10 initial grids)', ''])
    if exhaustive is None:
        lines.append('Skipped by --skip-analysis; no 59,049-grid results were generated in this run.')
    else:
        lines.extend([
            f"- Initial states: {exhaustive['initial_state_count']:,}.",
            f"- Distinct modeled states (including connected gates): {exhaustive['valid_state_count']:,}.",
            f"- Mean Greedy / optimum (excluding zero/zero): {exhaustive['mean_greedy_opt_ratio']:.6f}.",
            f"- Fraction Greedy optimal: {exhaustive['fraction_greedy_optimal']:.4%}.",
            '- Method: reverse Dijkstra; yields exact weighted optimum for all initial states.',
            '- Charts: `exhaustive_5x2/histogram_ratio.png`, `exhaustive_5x2/scatter_costs.png`, `exhaustive_5x2/scatter_actions.png`.',
            f'- Source of exhaustive files: {"previously computed, reused" if reused else "computed in this run"}.',
            '- The all-states optimum analysis is NOT a per-algorithm time/memory benchmark.',
        ])
    lines.extend(['', '## Individual-algorithm benchmark on multiple grids', ''])
    if not sample_stats:
        lines.append('Skipped.')
    else:
        lines.extend([
            f"Random sample size: {args.sample_size} (seed={args.seed}), "
            f"max {args.seconds}s per non-Greedy run, "
            f"max {args.expansions} expansions, IDS depth at most {args.depth}.",
            '', '| Algorithm | Runs | Solved | Timeout | Other limit | Median seconds | Median KiB |',
            '|---|---:|---:|---:|---:|---:|---:|',
        ])
        for r in sample_stats:
            lines.append(f"| {r['algorithm']} | {r['runs']} | {r['solved']} | {r['timeout']} | "
                         f"{r['other_limit']} | {r['median_elapsed_sec']} | "
                         f"{r['median_python_memory_kib']} |")
        lines.extend(['', 'Charts include success rate and medians for time, memory, expansions.',
                      'Median time/space include successful and resource-limited runs.',
                      'Do not compare these medians without checking success rates.',
                      'If exhaustive analysis was enabled, benchmark_quality.csv also gives exact optimality gaps on the same sample.'])
    lines.extend(['', '## Optional full 59,049 × algorithm benchmark', ''])
    if args.full_benchmark:
        expected = 59049 * len(ALGORITHMS)
        lines.append(f'CSV records currently present: **{full_rows:,} / {expected:,}**.')
        lines.append('Complete: **' + ('yes' if full_rows == expected else 'no') + '**.')
        lines.append('The CSV is append-only and resumable; each algorithm has a per-run cap.')
        if full_stats:
            lines.append('A separate full-benchmark summary CSV is available, as are figures in `benchmark_full/`.')
    else:
        lines.append('NOT RUN. Enable explicitly with `--full-benchmark`; this is optional and can be resource intensive.')
    lines.extend(['', '## Submission prerequisites', '',
                  '- Add the FULL verbatim transcripts of every AI conversation yourself.',
                  '- Fill in student/course details and review the interpretation with the instructor.',
                  '- The generated files and source code do not include the optional water/concrete model.',
                  ''])
    (directory / 'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Reproduce all required sand-grid outputs and compare algorithms.')
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'project_run',
                        help='Output directory for comparison/benchmark/report')
    parser.add_argument('--sample-size', type=int, default=12,
                        help='Number of 5×2 initial states in individual-algorithm benchmark')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--seconds', type=float, default=1.0,
                        help='Time limit per algorithm per initial grid (Greedy excluded)')
    parser.add_argument('--expansions', type=int, default=100000)
    parser.add_argument('--depth', type=int, default=20)
    parser.add_argument('--full-benchmark', action='store_true',
                        help='Benchmark every algorithm on all 59,049 initial grids; resume enabled')
    parser.add_argument('--reset-full-benchmark', action='store_true',
                        help='Clear earlier full-benchmark CSV and its configuration before starting again')
    parser.add_argument('--force-analysis', action='store_true',
                        help='Recompute exact 59,049-grid optimum even if outputs exist')
    parser.add_argument('--skip-analysis', action='store_true',
                        help='Skip 59,049 optimum calculation/plots')
    parser.add_argument('--skip-benchmark', action='store_true',
                        help='Skip sample benchmark')
    parser.add_argument('--skip-tests', action='store_true')
    parser.add_argument('--gif', action='store_true',
                        help='Create extra GIF for successful UCS/A* demos (HTML always generated)')
    args = parser.parse_args(argv)
    if args.sample_size < 1 or args.seconds <= 0 or args.expansions < 1 or args.depth < 0:
        parser.error('sample-size, seconds, expansions must be positive; depth must be nonnegative')
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    info(f'Writing project results to {directory}')
    test_ok = False
    if not args.skip_tests:
        info('Running automated correctness tests...')
        proc = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'tests'], cwd=ROOT)
        test_ok = proc.returncode == 0
        if not test_ok:
            info('Tests failed: stopping to avoid generating an untrusted report.')
            return 2
    else:
        info('Tests skipped by explicit request.')
    prof_model = SandGrid(4, 2)
    prof_state = prof_model.from_display(PROFESSOR, 'full-is-1')
    gre = greedy(prof_model, prof_state)
    if gre.cost != 47:
        raise AssertionError(f'Professor Greedy example expected cost 47, got {gre.cost}')
    info('Comparing algorithms on the professor example (Greedy=47)...')
    prof_rows = evaluate(prof_model, prof_state, 'professor', directory/'professor',
                         args.seconds, args.expansions, args.depth, args.gif)
    random_model = SandGrid(5, 2)
    initial = random_model.random_state(args.seed)
    info(f'Comparing algorithms on reproducible random 5×2 grid (seed={args.seed})...')
    random_rows = evaluate(random_model, initial, 'random_5x2', directory/'random_5x2',
                           args.seconds, args.expansions, args.depth, args.gif)
    all_rows = prof_rows + random_rows
    write_csv(directory/'algorithm_comparison.csv', all_rows, COMPARISON_FIELDS)
    plot_comparisons(all_rows, directory)
    summary, reused = None, False
    if not args.skip_analysis:
        summary, reused = analyze_59049(directory/'exhaustive_5x2', args.force_analysis)
    sample_summary = None
    if not args.skip_benchmark:
        filepath = directory/'benchmark_sample.csv'
        # Each invocation uses a fresh sample CSV to avoid mixing altered limits.
        if filepath.exists():
            filepath.unlink()
        info(f'Benchmarking all 7 algorithms on {args.sample_size} shared initial grids...')
        benchmark(random_model, filepath, count=args.sample_size, seed=args.seed,
                  max_seconds=args.seconds, max_expansions=args.expansions,
                  max_depth=args.depth, resume=False)
        sample_summary = summarize(filepath, directory/'benchmark_sample_summary.csv')
        plot_benchmark(filepath, directory)
        if summary is not None:
            info('Joining sample runs to exact 59,049-grid optima for quality comparisons...')
            write_quality_comparison(filepath, directory/'exhaustive_5x2'/'all_states.csv', directory)
    full_rows, full_summary = 0, None
    if args.full_benchmark:
        full_path = directory/'benchmark_all_59049.csv'
        config_path = directory/'benchmark_all_config.json'
        config = {'rows': 5, 'cols': 2, 'algorithms': list(ALGORITHMS),
                  'max_seconds': args.seconds, 'max_expansions': args.expansions,
                  'max_depth': args.depth}
        if args.reset_full_benchmark:
            full_path.unlink(missing_ok=True)
            config_path.unlink(missing_ok=True)
        if full_path.exists():
            if not config_path.exists():
                raise SystemExit('Found old full CSV without configuration. '
                                 'Use --reset-full-benchmark to restart safely.')
            prior = json.loads(config_path.read_text(encoding='utf-8'))
            if prior != config:
                raise SystemExit('Full benchmark settings changed! Use the original '
                                 '--seconds/--expansions/--depth to resume, or '
                                 '--reset-full-benchmark to start fresh.')
        else:
            save_json(config_path, config)
        info('Running resumable full per-algorithm benchmark on 59,049 initial grids...')
        benchmark(random_model, full_path, all_states=True, max_seconds=args.seconds,
                  max_expansions=args.expansions, max_depth=args.depth, resume=True)
        full_summary = summarize(full_path, directory/'benchmark_all_summary.csv')
        full_rows, _ = benchmark_csv_count(full_path)
        full_graphs_dir = directory/'benchmark_full'
        full_graphs_dir.mkdir(exist_ok=True)
        plot_benchmark(full_path, full_graphs_dir)
        if summary is not None:
            write_quality_comparison(full_path, directory/'exhaustive_5x2'/'all_states.csv',
                                     full_graphs_dir)
    make_report(directory, all_rows, args, summary, reused, test_ok,
                sample_summary, full_summary, full_rows)
    make_dashboard(directory, all_rows, analyzed=summary is not None,
                   sampled=sample_summary is not None, full_rows=full_rows)
    save_json(directory/'settings.json', {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'python': sys.version.split()[0], 'platform': platform.platform(),
        'random_seed': args.seed, 'sample_size': args.sample_size,
        'seconds': args.seconds, 'expansion_limit': args.expansions,
        'ids_depth_limit': args.depth,
        'exhaustive_skipped': args.skip_analysis, 'exhaustive_reused': reused,
        'full_benchmark_requested': args.full_benchmark,
        'full_benchmark_count': full_rows,
    })
    info(f'FINISHED. Open {directory / "dashboard.html"} and {directory / "REPORT.md"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
