"""Run ALL graph searches and path-based local searches on exactly one initial grid.

From repository root:
    python scripts/compare_all_searches.py
    python scripts/compare_all_searches.py --example random --rows 3 --cols 2 --seed 7
    python scripts/compare_all_searches.py --grid '[[1,0],[0,1],[0,1],[1,0]]'

Produces an offline dashboard, CSV/JSON, charts and best-path animations.
The original graph-search algorithms and SandGrid physics are not modified.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
from pathlib import Path
from statistics import median
import sys
from typing import Any

# Allow `python scripts/compare_all_searches.py` from any working directory.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sandgrid.model import SandGrid
from sandgrid.search import greedy, search
from sandgrid.local_search import optimize_paths

PROFESSOR = [[1, 0], [0, 1], [0, 1], [1, 0]]
GRAPH = ('greedy', 'random', 'dfs', 'bfs', 'ids', 'ucs', 'astar', 'rbfs')
LOCAL = ('hillclimb', 'anneal', 'genetic')
ALL = GRAPH + LOCAL
STOCHASTIC = {'random', *LOCAL}


def _args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description='Compare original and local-search algorithms')
    parser.add_argument('--example', choices=('professor', 'random'), default='professor')
    parser.add_argument('--rows', type=int, default=4)
    parser.add_argument('--cols', type=int, default=2)
    parser.add_argument('--grid', help='Explicit JSON matrix, overrides --example and --rows/cols')
    parser.add_argument('--seed', type=int, default=42, help='Random initial grid seed')
    parser.add_argument('--random-seed', type=int, default=42, help='First randomized-search trial seed')
    parser.add_argument('--trials', type=int, default=5, help='Trials per randomized algorithm')
    parser.add_argument('--seconds', type=float, default=8, help='Time limit per graph-search trial')
    parser.add_argument('--expansions', type=int, default=100000)
    parser.add_argument('--max-depth', type=int, default=20)
    parser.add_argument('--local-evaluations', type=int, default=2500)
    parser.add_argument('--local-seconds', type=float, default=10,
                        help='Time limit per local-search trial')
    parser.add_argument('--algorithms', nargs='+', choices=ALL, default=list(ALL))
    parser.add_argument('--output', default=None,
                        help='Directory; default results/all_search_comparison/<example>')
    parser.add_argument('--no-gif', action='store_true', help='Skip GIF to save time/space')
    args = parser.parse_args(argv)
    if args.rows < 1 or args.cols < 1 or args.rows * args.cols > 15:
        parser.error('rows*cols must be between 1 and 15')
    if args.trials < 1 or args.expansions < 1 or args.local_evaluations < 1:
        parser.error('trials, expansions and local-evaluations must be positive')
    if args.seconds <= 0 or args.local_seconds <= 0 or args.max_depth < 0:
        parser.error('seconds and local-seconds must be positive; max-depth >= 0')
    if len(args.algorithms) != len(set(args.algorithms)):
        parser.error('duplicate algorithms are not allowed')
    return args


def make_initial(args) -> tuple[SandGrid, int, str]:
    if args.grid is not None:
        grid = json.loads(args.grid)
        if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
            raise ValueError('--grid must be a nonempty 2D JSON array')
        rows, cols = len(grid), len(grid[0])
        model = SandGrid(rows, cols)
        return model, model.from_display(grid), 'custom'
    if args.example == 'professor':
        model = SandGrid(4, 2)
        return model, model.from_display(PROFESSOR), 'professor'
    model = SandGrid(args.rows, args.cols)
    return model, model.random_state(args.seed), f'random_{args.rows}x{args.cols}_seed{args.seed}'


def state_grid(model: SandGrid, state: int) -> list[list[float]]:
    occupancy, _ = model.decode(state)
    return [[occupancy[r * model.cols + c] / 2 for c in range(model.cols)]
            for r in range(model.rows)]


def save_csv(filename: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]):
    with filename.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def save_initial_image(model: SandGrid, initial: int, destination: Path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    grid = state_grid(model, initial)
    fig, ax = plt.subplots(figsize=(max(4, model.cols * 1.4), max(4.3, model.rows * 1.0)))
    for r, row in enumerate(grid):
        for c, amount in enumerate(row):
            ax.add_patch(Rectangle((c, r), 1, 1, facecolor=('#f2f5f8' if amount == 0 else
                                   '#ead3ac' if amount == 0.5 else '#bc874a'), edgecolor='#465469', linewidth=2))
            ax.text(c + .5, r + .5, f'{amount:g}', ha='center', va='center', fontsize=16, color='#192638')
    ax.set_xlim(0, model.cols)
    ax.set_ylim(model.rows, 0)
    ax.set_aspect('equal')
    ax.set_xticks([i+.5 for i in range(model.cols)], [str(i+1) for i in range(model.cols)])
    ax.set_yticks([i+.5 for i in range(model.rows)], [str(i+1) for i in range(model.rows)])
    ax.tick_params(length=0)
    for spine in ax.spines.values(): spine.set_visible(False)
    ax.set_title(f'Initial Sand Grid ({model.rows} x {model.cols})', fontsize=13)
    fig.tight_layout()
    fig.savefig(destination, dpi=150)
    plt.close(fig)


def run_one(model: SandGrid, initial: int, algorithm: str, seed: int, args) -> dict[str, Any]:
    """Save the confirmed executed prefix; never confuse an unfinished path with a solution."""
    local_details: dict[str, Any] = {}
    if algorithm in LOCAL:
        o = optimize_paths(model, initial, algorithm,
                           max_evaluations=args.local_evaluations,
                           max_seconds=args.local_seconds,
                           random_seed=seed)
        e = o.evaluation
        found, status = bool(e.found_goal), 'found' if e.found_goal else 'not_found'
        actions = list(e.executed_actions)
        cost = e.path_cost if found else None
        effort, effort_type = o.evaluations, 'path_evaluations'
        elapsed, peak = o.elapsed_sec, o.peak_memory_bytes
        local_details = dict(score=e.score, chromosome=list(o.best_path),
                             chromosome_length=len(o.best_path),
                             goal_index_0based=e.goal_index,
                             goal_step=(e.goal_index + 1 if e.goal_index is not None else None),
                             valid_actions=len(actions), invalid_attempts=e.invalid_attempts,
                             remaining_half_units=e.remaining_units,
                             attempted_path_cost=e.path_cost)
        expected_state = e.final_state
        expected_total = e.path_cost
    else:
        r = (greedy(model, initial) if algorithm == 'greedy' else
             search(model, initial, algorithm, max_seconds=args.seconds,
                    max_expansions=args.expansions, max_depth=args.max_depth,
                    heuristic_name='basic', random_seed=seed))
        found, status, actions, cost = r.found, r.status, list(r.actions), r.cost
        effort, effort_type = r.expanded, 'expanded_nodes'
        elapsed, peak = r.elapsed_sec, r.peak_memory_bytes
        expected_state = 0 if found else None
        expected_total = cost if found else None
    trace = model.trace(initial, actions)
    if expected_state is not None and trace[-1]['state'] != expected_state:
        raise AssertionError(f'{algorithm}: trace and final state differ')
    if expected_total is not None and trace[-1]['total_cost'] != expected_total:
        raise AssertionError(f'{algorithm}: trace and path cost differ')
    if found != model.is_goal(trace[-1]['state']):
        raise AssertionError(f'{algorithm}: incorrect Goal flag')
    return dict(algorithm=algorithm, seed=seed, status=status, found=bool(found),
                cost=cost, action_count=len(actions),
                side_action_count=sum(model.actions[a].kind == 'side' for a in actions),
                elapsed_sec=elapsed, effort=effort, effort_type=effort_type,
                peak_memory_bytes=peak, actions=actions, details=local_details)


def _median(vals: list[float | int]):
    return round(median(vals), 6) if vals else None


def render_charts(summary: list[dict[str, Any]], outdir: Path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    names = [r['algorithm'] for r in summary]
    ys = list(range(len(names)))
    bar_width = max(7, len(names) * .62)
    # Unsolved algorithms appear as explicit N/A labels, never as zero-cost solutions.
    fig, ax = plt.subplots(figsize=(10, bar_width))
    known = [i for i, r in enumerate(summary) if r['best_cost'] is not None]
    unknown = [i for i, r in enumerate(summary) if r['best_cost'] is None]
    if known:
        ax.barh(known, [summary[i]['best_cost'] for i in known], color='#608bb3')
        for i in known:
            ax.text(summary[i]['best_cost']+.5, i, str(summary[i]['best_cost']), va='center', fontsize=10)
    for i in unknown: ax.text(.4, i, 'No confirmed goal', va='center', color='#ad4b37', fontsize=10)
    ax.set_xlim(0, max([summary[i]['best_cost'] for i in known] + [2])*1.30)
    ax.set_yticks(ys, names); ax.invert_yaxis()
    ax.set_xlabel('Best confirmed solution path cost (lower = better)')
    ax.set_title('Cost comparison - same initial state')
    ax.grid(axis='x', alpha=.2); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(outdir/'cost_comparison.png', dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, bar_width))
    times = [r['median_time_sec'] for r in summary]
    ax.barh(ys, times, color='#7d9c78')
    ax.set_yticks(ys, names); ax.invert_yaxis()
    ax.set_xlabel('Median wall time per trial (seconds; lower = faster)')
    ax.set_title('Runtime comparison - same machine and initial state')
    ax.grid(axis='x', alpha=.2); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(outdir/'time_comparison.png', dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, bar_width))
    rates = [r['success_rate_percent'] for r in summary]
    ax.barh(ys, rates, color='#ae9674')
    ax.set_xlim(0, 110); ax.set_xticks([0,20,40,60,80,100])
    ax.set_yticks(ys, names); ax.invert_yaxis()
    for i,r in enumerate(summary): ax.text(min(rates[i]+1,101), i, f'{r["solved"]}/{r["runs"]}', va='center')
    ax.set_xlabel('Success rate (%)')
    ax.set_title('Goal reached within resource limits')
    ax.grid(axis='x', alpha=.2); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(outdir/'success_rate.png', dpi=160); plt.close(fig)


def render_dashboard(outdir: Path, initial_info: dict, summary: list[dict], trials: list[dict]):
    esc = lambda x: html.escape(str(x))
    def fmt(x, n=5): return '—' if x is None else (f'{x:.{n}f}' if isinstance(x,float) else esc(x))
    rows = []
    for r in summary:
        name = r['algorithm']
        note = f'{r["solved"]}/{r["runs"]}'
        anim = f'<a href="animations/{esc(name)}.html">View interactive path</a>' if r['animation_html'] else '—'
        gif = f'<a href="animations/{esc(name)}.gif">GIF</a>' if r['animation_gif'] else '—'
        rows.append('<tr>' + ''.join(f'<td>{v}</td>' for v in (
            f'<strong>{esc(name)}</strong>', esc(note), fmt(r['best_cost']),
            fmt(r['median_success_cost']), fmt(r['median_time_sec'],4),
            fmt(r['median_work_units'],0), esc(r['work_unit']),
            fmt(r['best_seed']), anim, gif)) + '</tr>')
    body = f'''<!doctype html><html lang="en"><head><meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Sand Grid — All Search Comparison</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;background:#f5f7fb;color:#233344;margin:auto;max-width:1240px;padding:24px}}
h1{{font-size:1.7rem}}h2{{font-size:1.2rem;margin-top:28px}}.meta{{display:flex;gap:12px;flex-wrap:wrap}}
.meta span{{background:white;padding:10px 14px;border-radius:8px;border:1px solid #dce4ed}}.panel{{background:white;padding:15px;border:1px solid #dce4ed;border-radius:11px;margin-top:18px}}
img{{max-width:100%;height:auto}}.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:12px}}
.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #e5eaf1;padding:10px;text-align:left;white-space:nowrap}}th{{background:#eff4f9}}
a{{color:#275c9a}}.note{{color:#617184;font-size:.9rem;line-height:1.7}}</style></head><body>
<h1>Sand Grid — Search Algorithm Comparison</h1>
<div class="meta"><span>Initial: {esc(initial_info['label'])}</span><span>Grid: {initial_info['rows']} × {initial_info['cols']}</span>
<span>Initial code: {initial_info['initial_code']}</span><span>Goal: completely empty</span></div>
<p class="note">All algorithms start from the exact same initial state. Failed or timed-out methods are marked as unsolved, not assigned cost 0.
Local Search uses random 30–35-gene paths. Graph expansions and evaluated path candidates are different work units and must not be directly equated.</p>
<div class="panel"><h2>Initial state</h2><img src="initial.png" style="max-width:360px" alt="Initial grid"/>
<pre>{esc(json.dumps(initial_info['initial_grid'],ensure_ascii=False))}</pre></div>
<h2>Comparison</h2><div class="panel table-wrap"><table><thead><tr><th>Algorithm</th><th>Successes</th><th>Best cost</th>
<th>Median solved cost</th><th>Median time (s)</th><th>Median work</th><th>Work unit</th><th>Best seed</th><th>Interactive</th><th>GIF</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="charts"><div class="panel"><img src="cost_comparison.png" alt="Cost comparison"/></div>
<div class="panel"><img src="time_comparison.png" alt="Time comparison"/></div>
<div class="panel"><img src="success_rate.png" alt="Success rates"/></div></div>
<p class="note">For randomized algorithms, best cost is the minimum among successful trials; median solved cost includes only successful trials.
The success rate uses all attempted trials. Timing includes algorithm execution, not chart creation.
HTML shows the flow within each action; GIF shows one frame per valid action. Paths that did not reach Goal are labeled partial.</p>
<div class="panel"><a href="comparison.csv">Download aggregated CSV</a> · <a href="trials.csv">All trials CSV</a> ·
<a href="comparison.json">Detailed JSON</a> · <a href="initial.json">Initial state JSON</a></div></body></html>'''
    (outdir/'dashboard.html').write_text(body,encoding='utf-8')


def render_report(outdir: Path, info: dict, summary: list[dict[str, Any]]):
    """Short report with all actual measurements and their experimental limits."""
    def display(value):
        return 'N/A' if value is None else str(value)
    lines = [
        '# Sand Grid — Unified Search Comparison', '',
        f"- Initial grid: `{info['label']}` ({info['rows']}×{info['cols']}); internal code `{info['initial_code']}`",
        f"- Initial occupancy (1=full, 0.5=half, 0=empty): `{info['initial_grid']}`",
        f"- Graph limits: `{info['graph_limits']}`",
        f"- Local-search limits: `{info['local_limits']}`",
        f"- Randomized algorithms: `{info['trials_per_randomized_algorithm']}` runs per algorithm, starting at seed `{info['random_search_first_seed']}`",
        '', '## Measurements', '',
        '| Algorithm | Solved / runs | Best path cost | Median solved cost | Median time (s) | Work | Work unit | Gap vs UCS |',
        '|---|---:|---:|---:|---:|---:|---|---:|'
    ]
    for r in summary:
        lines.append('| '+' | '.join([
            r['algorithm'],f"{r['solved']}/{r['runs']}",display(r['best_cost']),
            display(r['median_success_cost']),display(r['median_time_sec']),
            display(r['median_work_units']),r['work_unit'],display(r.get('gap_vs_ucs'))])+' |')
    lines += ['', '## Interpretation', '',
        '- A successful run reaches the exact zero-sand Goal state. A failed or timed-out run has **no confirmed solution cost**.',
        '- UCS gives the weighted-cost optimum only if it completes successfully. Its value is the reference for `gap_vs_ucs`.',
        '- BFS/IDS target minimum number of actions, not necessarily minimum weighted path cost.',
        '- Local Search maximizes path fitness over random candidate sequences of 30–35 action IDs. A candidate stops evaluating at its first Goal.',
        '- `expanded_nodes` in graph search and `path_evaluations` in Local Search are **different work units**, so compare their values only within the same category.',
        '- For stochastic algorithms, the minimum cost over trials is not a typical cost; use `median_success_cost` and the success rate together.',
        '- Wall-clock times vary by hardware. For a scientific comparison, rerun all algorithms on one machine with the same initial code and limits.',
        '', '## Output files', '',
        '- `dashboard.html`: offline summary and links to the step-by-step animations',
        '- `comparison.csv`: one aggregated row per method',
        '- `trials.csv`: every trial with seed, goal flag, runtime and measured work',
        '- `initial.json`, `initial.png`: exact shared starting state',
        '- `cost_comparison.png`, `time_comparison.png`, `success_rate.png`: charts',
        '- `animations/*_best.json`: selected action IDs, trace, and local candidate metadata',
        '- `animations/*.html` and `animations/*.gif`: visual output for methods with an executed path',
        '', 'These values come from this experiment and are not borrowed from earlier project reports.', '']
    (outdir/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    args = _args(argv)
    model, initial, label = make_initial(args)
    outdir = Path(args.output) if args.output else ROOT / 'results' / 'all_search_comparison' / label
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir/'animations').mkdir(parents=True, exist_ok=True)
    info = dict(label=label, rows=model.rows, cols=model.cols, initial_code=initial,
                initial_grid=state_grid(model,initial), model_version=getattr(model,'MODEL_VERSION','SandGrid'),
                display_convention='1=full; 0.5=half; 0=empty',
                random_grid_seed=(args.seed if label.startswith('random_') else None),
                random_search_first_seed=args.random_seed, local_path_length=[30,35],
                algorithms=args.algorithms, trials_per_randomized_algorithm=args.trials,
                graph_limits=dict(seconds=args.seconds,expansions=args.expansions,max_depth=args.max_depth),
                local_limits=dict(seconds=args.local_seconds,evaluations=args.local_evaluations))
    (outdir/'initial.json').write_text(json.dumps(info,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'Initial grid {label}: code={initial} | {model.rows}x{model.cols}')
    for row in info['initial_grid']: print(' '.join(f'{x:g}' for x in row))
    save_initial_image(model, initial, outdir/'initial.png')

    trials: list[dict] = []
    summary: list[dict] = []
    from sandgrid.visualize import save_html, save_gif
    for algorithm in args.algorithms:
        runs = args.trials if algorithm in STOCHASTIC else 1
        observations = []
        for trial in range(runs):
            seed = args.random_seed + trial
            r = run_one(model, initial, algorithm, seed, args)
            observations.append(r)
            trials.append(dict(algorithm=algorithm, trial=trial+1, seed=seed,
                               status=r['status'], found=int(r['found']),
                               cost=r['cost'] if r['found'] else None,
                               action_count=r['action_count'], side_action_count=r['side_action_count'],
                               elapsed_sec=round(r['elapsed_sec'],8), effort=r['effort'],
                               work_unit=r['effort_type'], score=r['details'].get('score'),
                               chromosome_length=r['details'].get('chromosome_length'),
                               goal_step=r['details'].get('goal_step'),
                               invalid_attempts=r['details'].get('invalid_attempts'),
                               remaining_half_units=r['details'].get('remaining_half_units')))
            print(f'{algorithm:10} trial={trial+1:02d} status={r["status"]:17} '
                  f'cost={str(r["cost"]):>4} actions={r["action_count"]:>2} '
                  f'time={r["elapsed_sec"]:.3f}s')
        solved = [r for r in observations if r['found']]
        # If no solved paths, pick best path_score as the partial visualization.
        if solved:
            chosen = min(solved,key=lambda r:(r['cost'],r['elapsed_sec']))
        elif algorithm in LOCAL:
            chosen = max(observations,key=lambda r:r['details']['score'])
        else:
            chosen = observations[0]
        goal_count = len(solved)
        costs = [r['cost'] for r in solved]
        work_unit = chosen['effort_type']
        # Any nonempty prefix can be visualized, as can an initially solved empty path.
        can_visualize = bool(chosen['actions']) or model.is_goal(initial)
        html_rel, gif_rel = None, None
        if can_visualize:
            title = f'{algorithm.upper()} — {"Goal reached" if chosen["found"] else "PARTIAL (not solved)"} — cost {chosen["cost"] if chosen["found"] else "N/A"}'
            html_path = outdir/'animations'/f'{algorithm}.html'
            save_html(model, initial, chosen['actions'], html_path, title=title)
            html_rel = str(html_path.relative_to(outdir))
            if not args.no_gif:
                gif_path = outdir/'animations'/f'{algorithm}.gif'
                save_gif(model, initial, chosen['actions'], gif_path)
                gif_rel = str(gif_path.relative_to(outdir))
        details_path = outdir/'animations'/f'{algorithm}_best.json'
        details_path.write_text(json.dumps(dict(algorithm=algorithm, seed=chosen['seed'],
                    found=chosen['found'], status=chosen['status'],
                    cost=chosen['cost'], executed_action_ids=chosen['actions'],
                    executed_action_labels=[model.actions[i].label for i in chosen['actions']],
                    trace=[dict(step=k,grid=state_grid(model,t['state']),total_cost=t['total_cost'],
                                action_id=t['action'],step_cost=t['step_cost'],
                                flow_events=t.get('flow_events',[]))
                           for k,t in enumerate(model.trace(initial,chosen['actions']))],
                    local_path_data=chosen['details']),indent=2,ensure_ascii=False),encoding='utf-8')
        summary.append(dict(algorithm=algorithm, runs=runs, solved=goal_count,
                            success_rate_percent=round(100*goal_count/runs,2),
                            best_cost=min(costs) if costs else None,
                            median_success_cost=_median(costs),
                            median_time_sec=_median([r['elapsed_sec'] for r in observations]),
                            median_work_units=_median([r['effort'] for r in observations]),
                            work_unit=work_unit,best_seed=chosen['seed'],
                            best_status=chosen['status'],best_actions=len(chosen['actions']),
                            best_score=chosen['details'].get('score'),
                            animation_html=html_rel,animation_gif=gif_rel,
                            result_json=str(details_path.relative_to(outdir))))

    # UCS is a valid optimal cost reference only if it actually solved this state.
    reference = next((r['best_cost'] for r in summary if r['algorithm']=='ucs' and r['best_cost'] is not None),None)
    if reference is not None:
        for r in summary:
            r['gap_vs_ucs'] = (r['best_cost']-reference if r['best_cost'] is not None else None)
    else:
        for r in summary: r['gap_vs_ucs'] = None
    save_csv(outdir/'trials.csv', trials, tuple(trials[0]) if trials else ('algorithm',))
    save_csv(outdir/'comparison.csv',summary,tuple(summary[0]) if summary else ('algorithm',))
    (outdir/'comparison.json').write_text(json.dumps(dict(initial=info,summary=summary,trials=trials),
                                                      indent=2,ensure_ascii=False),encoding='utf-8')
    render_charts(summary,outdir)
    render_dashboard(outdir,info,summary,trials)
    render_report(outdir,info,summary)
    print(f'\nDONE: {outdir.resolve()}')
    print('Open dashboard.html or inspect comparison.csv / trials.csv')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
