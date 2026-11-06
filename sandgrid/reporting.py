"""Offline results dashboard and quality comparison against exact optima."""
from __future__ import annotations

import csv
from html import escape
from pathlib import Path
from statistics import median

from .benchmark import ALGORITHMS


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_quality_comparison(benchmark_file: Path, optima_file: Path, destination: Path):
    """Compare sampled solved runs to exact optimum from reverse Dijkstra.

    Missing/timeout runs retain an empty gap, not a fictitious cost of zero.
    Mean gaps are conditional on successful solves and need solved counts.
    """
    optimum = {int(r['base3_initial_code']): int(r['optimal_cost'])
               for r in read_rows(optima_file)}
    fields = ('initial_code', 'algorithm', 'status', 'cost', 'optimal_cost',
              'cost_gap', 'cost_ratio', 'action_count', 'side_action_count',
              'elapsed_sec', 'peak_python_bytes', 'expanded')
    rows = []
    for r in read_rows(benchmark_file):
        code = int(r['initial_code'])
        best = optimum[code]
        solved = r['status'] == 'found'
        cost = int(r['cost']) if solved else None
        if solved and cost < best:
            raise AssertionError(f'cost below exact optimum for code={code}')
        rows.append({
            'initial_code': code, 'algorithm': r['algorithm'], 'status': r['status'],
            'cost': cost if solved else '', 'optimal_cost': best,
            'cost_gap': cost - best if solved else '',
            'cost_ratio': f'{cost/best:.5f}' if solved and best else '',
            'action_count': r['action_count'],
            'side_action_count': r['side_action_count'],
            'elapsed_sec': r['elapsed_sec'],
            'peak_python_bytes': r['peak_python_bytes'],
            'expanded': r['expanded'],
        })
    write_rows(destination/'benchmark_quality.csv', rows, fields)
    summary = []
    for algo in ALGORITHMS:
        group = [r for r in rows if r['algorithm'] == algo]
        successes = [r for r in group if r['status'] == 'found']
        gaps = [int(r['cost_gap']) for r in successes]
        summary.append({
            'algorithm': algo, 'attempted': len(group), 'solved': len(successes),
            'optimal_solutions': sum(g == 0 for g in gaps),
            'mean_gap_solved_only': round(sum(gaps)/len(gaps), 4) if gaps else '',
            'median_gap_solved_only': round(median(gaps), 4) if gaps else '',
        })
    write_rows(destination/'benchmark_quality_summary.csv', summary,
               ('algorithm', 'attempted', 'solved', 'optimal_solutions',
                'mean_gap_solved_only', 'median_gap_solved_only'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4.8))
    values = [float(r['mean_gap_solved_only']) if r['mean_gap_solved_only'] != '' else 0
              for r in summary]
    bars = ax.bar([r['algorithm'].upper() for r in summary], values)
    for bar, record in zip(bars, summary):
        if record['mean_gap_solved_only'] == '':
            ax.text(bar.get_x() + bar.get_width()/2, .08, 'No solution',
                    ha='center', va='bottom', fontsize=8, rotation=90)
    ax.set(title='Mean extra cost among solved instances',
           ylabel='Cost minus exact optimum (check solved counts)')
    fig.tight_layout()
    fig.savefig(destination/'benchmark_quality_gap.png', dpi=170)
    plt.close(fig)
    return summary


def make_dashboard(directory: Path, comparisons: list[dict],
                   analyzed: bool, sampled: bool, full_rows: int) -> Path:
    """Build a self-contained, offline HTML overview with animations and plots."""
    body = ['<h1>Sand Grid — Algorithm Comparison</h1>',
            '<p>All algorithms in each table receive the same grid. '
            'A resource limit does not mean no solution exists.</p>',
            '<p><a href="REPORT.md">Report</a> · '
            '<a href="algorithm_comparison.csv">All comparisons (CSV)</a> · '
            '<a href="settings.json">Settings (JSON)</a></p>']
    for example in dict.fromkeys(r['example'] for r in comparisons):
        body += [f'<section><h2>{escape(example)}</h2>',
                 f'<p><a href="{escape(example)}/initial.json">Initial grid</a> · '
                 f'<a href="{escape(example)}/comparison.csv">Details CSV</a></p>',
                 '<table><thead><tr><th>Algorithm</th><th>Status</th><th>Cost</th>'
                 '<th>Gap</th><th>Actions</th><th>Side</th><th>Expanded</th>'
                 '<th>Seconds</th><th>Memory KiB</th><th>Animation</th></tr></thead><tbody>']
        for row in [r for r in comparisons if r['example'] == example]:
            values = [row['algorithm'].upper(), row['status'], str(row['cost']),
                      str(row['optimality_gap']), str(row['action_count']),
                      str(row['side_action_count']), str(row['expanded']),
                      f"{row['elapsed_sec']:.4f}", f"{row['peak_python_kib']:.1f}"]
            cell_text = ''.join(f'<td>{escape(v) if v else "—"}</td>' for v in values)
            animation = (f'<a href="{escape(example)}/{escape(row["animation_html"])}">Play</a>'
                         if row['animation_html'] else '—')
            body.append(f'<tr>{cell_text}<td>{animation}</td></tr>')
        body += ['</tbody></table>',
                 f'<img src="{escape(example)}_cost_comparison.png" '
                 f'alt="Cost comparison {escape(example)}"></section>']
    if analyzed:
        body += ['<section><h2>All 59,049 initial grids (5×2)</h2>',
                 '<p><a href="exhaustive_5x2/all_states.csv">Exact costs and action sequences</a> · '
                 '<a href="exhaustive_5x2/summary.json">Summary</a></p>']
        for name in ('histogram_ratio.png', 'scatter_costs.png', 'scatter_actions.png'):
            body.append(f'<img src="exhaustive_5x2/{name}" alt="{name}">')
        body.append('</section>')
    if sampled:
        body += ['<section><h2>Benchmark: time, memory, success rate, search size</h2>',
                 '<p><a href="benchmark_sample.csv">All sampled runs</a> · '
                 '<a href="benchmark_sample_summary.csv">Statistics</a></p>']
        for name in ('benchmark_success_rate.png', 'benchmark_median_time.png',
                     'benchmark_median_memory.png', 'benchmark_median_expanded.png'):
            body.append(f'<img src="{name}" alt="{name}">')
        if (directory/'benchmark_quality.csv').exists():
            body += ['<p><a href="benchmark_quality.csv">Solution quality details</a> · '
                     '<a href="benchmark_quality_summary.csv">Quality summary</a></p>',
                     '<img src="benchmark_quality_gap.png" alt="Solution gaps">']
        body.append('</section>')
    if full_rows:
        count = 59049 * len(ALGORITHMS)
        body += [f'<section><h2>Full benchmark progress: {full_rows:,} / {count:,}</h2>',
                 '<p><a href="benchmark_all_59049.csv">Full measurements</a> · '
                 '<a href="benchmark_all_summary.csv">Summary</a></p>']
        for name in ('benchmark_success_rate.png', 'benchmark_median_time.png',
                     'benchmark_median_memory.png', 'benchmark_median_expanded.png'):
            body.append(f'<img src="benchmark_full/{name}" alt="{name}">')
        if (directory/'benchmark_full'/'benchmark_quality.csv').exists():
            body += ['<p><a href="benchmark_full/benchmark_quality.csv">Full quality per run</a> · '
                     '<a href="benchmark_full/benchmark_quality_summary.csv">Quality summary</a></p>',
                     '<img src="benchmark_full/benchmark_quality_gap.png" alt="Full cost gaps">']
        body.append('</section>')
    body.append('<p class="note">Time includes memory tracing overhead. '
                'Memory is the peak Python allocation measured by tracemalloc, '
                'not operating-system RSS. Full exact-optimum analysis and full '
                'per-algorithm benchmarking are different experiments.</p>')
    css = '''<style>
    :root{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#152338;background:#f6f8fc}
    body{max-width:1220px;margin:0 auto;padding:24px 18px}a{color:#2255a6}
    h1{margin-bottom:8px}p{line-height:1.6}section{background:#fff;border:1px solid #dfe5ee;
    padding:20px;border-radius:14px;margin:22px 0;overflow-x:auto}
    table{border-collapse:collapse;min-width:870px;width:100%;font-size:14px}
    th,td{border-bottom:1px solid #e6eaf1;padding:10px;text-align:left}
    th{background:#eff4fc}img{width:min(100%,535px);display:inline-block;margin:14px 12px 0 0}
    .note{color:#576980;font-size:14px}</style>'''
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Sand Grid — Search Algorithms</title>'+css+'</head><body>'
            + ''.join(body)+'</body></html>')
    output = directory/'dashboard.html'
    output.write_text(html, encoding='utf-8')
    return output
