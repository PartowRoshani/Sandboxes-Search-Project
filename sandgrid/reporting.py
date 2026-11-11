"""Offline HTML results dashboard and optional comparisons to exact optima."""
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
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_quality_comparison(benchmark_file: Path, optima_file: Path,
                             destination: Path):
    """Join per-run results to exact optima from the SAME physics model.

    Caller is responsible for checking grid dimensions and model versions.
    Only solved runs have a defined cost gap.
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
            raise AssertionError(f'algorithm cost below exact optimum for initial={code}')
        rows.append({
            'initial_code': code, 'algorithm': r['algorithm'],
            'status': r['status'], 'cost': cost if solved else '',
            'optimal_cost': best,
            'cost_gap': cost-best if solved else '',
            'cost_ratio': f'{cost/best:.6f}' if solved and best else '',
            'action_count': r['action_count'],
            'side_action_count': r['side_action_count'],
            'elapsed_sec': r['elapsed_sec'],
            'peak_python_bytes': r['peak_python_bytes'],
            'expanded': r['expanded'],
        })
    write_rows(destination/'benchmark_quality.csv', rows, fields)
    summary = []
    for algorithm in ALGORITHMS:
        group = [r for r in rows if r['algorithm'] == algorithm]
        successes = [r for r in group if r['status'] == 'found']
        gaps = [int(r['cost_gap']) for r in successes]
        summary.append({
            'algorithm': algorithm, 'attempted': len(group), 'solved': len(successes),
            'optimal_solutions': sum(g == 0 for g in gaps),
            'mean_gap_solved_only': round(sum(gaps)/len(gaps),4) if gaps else '',
            'median_gap_solved_only': round(median(gaps),4) if gaps else '',
        })
    write_rows(destination/'benchmark_quality_summary.csv', summary,
               ('algorithm','attempted','solved','optimal_solutions',
                'mean_gap_solved_only','median_gap_solved_only'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9,4.6))
    values = [float(r['mean_gap_solved_only']) if r['mean_gap_solved_only'] != ''
              else 0 for r in summary]
    ax.bar([r['algorithm'].upper() for r in summary], values)
    ax.set(title='Mean additional cost (solved runs only)',
           ylabel='Found cost - exact optimal cost')
    fig.tight_layout()
    fig.savefig(destination/'benchmark_quality_gap.png',dpi=170)
    plt.close(fig)
    return summary


def make_dashboard(directory: Path, comparisons: list[dict],
                   analyzed: bool, sampled: bool, full_rows: int) -> Path:
    """Build offline HTML with links to run artifacts; caller adds exact panel."""
    directory.mkdir(parents=True, exist_ok=True)
    content = ['<h1>Sand Grid — Comparison of Search Algorithms</h1>',
               '<p>Input values: <strong>1=full, 0.5=half, 0=empty</strong>. '
               'Greedy is the vertical-only column-wise baseline. '
               'A timeout is not evidence that no solution exists.</p>',
               '<p><a href="REPORT.md">Report</a> · '
               '<a href="algorithm_comparison.csv">All comparisons (CSV)</a> · '
               '<a href="settings.json">Settings (JSON)</a></p>']
    for example in dict.fromkeys(row['example'] for row in comparisons):
        content.append(f'<section><h2>{escape(example)}</h2>')
        content.append(f'<p><a href="{escape(example)}/initial.json">Initial grid</a> · '
                       f'<a href="{escape(example)}/comparison.csv">Details CSV</a></p>')
        content.append('<table><thead><tr><th>Algorithm</th><th>Status</th><th>Cost</th>'
                       '<th>Optimality gap</th><th>Actions</th><th>Side actions</th>'
                       '<th>Expanded</th><th>Time (s)</th><th>Python KiB</th>'
                       '<th>Animation</th></tr></thead><tbody>')
        for row in (r for r in comparisons if r['example'] == example):
            raw = [row['algorithm'].upper(),row['status'],str(row['cost']),
                   str(row['optimality_gap']),str(row['action_count']),
                   str(row['side_action_count']),str(row['expanded']),
                   f"{row['elapsed_sec']:.4f}",f"{row['peak_python_kib']:.1f}"]
            content.append('<tr>'+''.join(f'<td>{escape(v) if v else "—"}</td>'
                                            for v in raw))
            animation = (f'<a href="{escape(example)}/{escape(row["animation_html"])}">View</a>'
                         if row['animation_html'] else '—')
            content.append(f'<td>{animation}</td></tr>')
        content.append('</tbody></table>')
        content.append(f'<img src="{escape(example)}_cost_comparison.png" '
                       f'alt="Cost comparison for {escape(example)}"></section>')
    if sampled:
        content += ['<section><h2>Benchmarks</h2>',
                    '<p><a href="benchmark_sample.csv">Benchmark records</a> · '
                    '<a href="benchmark_sample_summary.csv">Summary</a></p>']
        for name in ('benchmark_success_rate.png','benchmark_median_time.png',
                     'benchmark_median_memory.png','benchmark_median_expanded.png'):
            content.append(f'<img src="{name}" alt="{name}">')
        if (directory/'benchmark_quality.csv').exists():
            content.append('<p><a href="benchmark_quality.csv">Exact quality comparison</a></p>')
            content.append('<img src="benchmark_quality_gap.png" alt="Quality gaps">')
        content.append('</section>')
    if full_rows:
        count=59049*len(ALGORITHMS)
        content.append(f'<section><h2>Full benchmark: {full_rows:,}/{count:,} runs</h2>')
        content.append('<p><a href="benchmark_all_59049.csv">Recorded results</a></p>')
        for name in ('benchmark_success_rate.png','benchmark_median_time.png',
                     'benchmark_median_memory.png','benchmark_median_expanded.png'):
            content.append(f'<img src="benchmark_full/{name}" alt="{name}">')
        content.append('</section>')
    content.append('<p class="note">Timing includes memory tracing. '
                   'Peak Python memory excludes some native allocations. '
                   'The exact reverse-Dijkstra analysis is a different experiment '
                   'from a per-algorithm benchmark.</p>')
    css='''<style>:root{font-family:system-ui,-apple-system,sans-serif;color:#203047;background:#f3f6fb}
    body{max-width:1210px;margin:auto;padding:20px}section{background:white;border:1px solid #dce4ee;
    padding:19px;margin:20px 0;border-radius:12px;overflow-x:auto}table{border-collapse:collapse;
    width:100%;min-width:800px;font-size:14px}th,td{border-bottom:1px solid #e5eaf1;
    padding:9px;text-align:left}th{background:#f0f4fc}img{width:min(100%,520px);
    margin:14px 12px 0 0}a{color:#2053a2}.note{color:#5a6a80;font-size:14px}</style>'''
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Sand Grid — Search Experiments</title>'+css+'</head><body>'
            +''.join(content)+'</body></html>')
    target = directory/'dashboard.html'
    target.write_text(html, encoding='utf-8')
    return target
