"""Generate a self-contained interactive HTML dashboard (real CSV runs only)."""
from __future__ import annotations
from collections import defaultdict
from html import escape
from pathlib import Path
from statistics import median
import json

from .experiments import read_rows


def _float(value):
    if value is None or str(value).strip() in ("", "None", "nan"):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _is_solved(row):
    return str(row.get("status", "")).lower() == "found" or str(row.get("found", "")).lower() in ("true", "1")


def build_dashboard(comparison_csv: str | Path, history_csv: str | Path | None,
                    output_html: str | Path, *, title: str = "SandGrid | Search Methods",
                    study_csv: str | Path | None = None) -> Path:
    try:
        import plotly.graph_objects as go
        from plotly.io import to_html
    except ImportError as ex:
        raise RuntimeError("Install visualization dependencies: pip install -r genetic_alg/requirements.txt") from ex

    rows = read_rows(comparison_csv)
    if not rows:
        raise ValueError("comparison.csv contains no actual experiment data")
    histories = read_rows(history_csv) if history_csv and Path(history_csv).exists() else []
    studies = read_rows(study_csv) if study_csv and Path(study_csv).exists() else []
    by_algo: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_algo[row["algorithm"]].append(row)
    algorithms = sorted(by_algo, key=lambda x: (x == "genetic", x))
    multi_grid = len({r.get("initial_code", "") for r in rows}) > 1
    best_for_state: dict[str, float] = {}
    for row in rows:
        v = _float(row.get("cost"))
        if _is_solved(row) and v is not None:
            code = row.get("initial_code", "")
            best_for_state[code] = min(best_for_state.get(code, float("inf")), v)
    statistics: dict[str, dict] = {}
    for algo in algorithms:
        sample = by_algo[algo]
        solved = [r for r in sample if _is_solved(r) and _float(r.get("cost")) is not None]
        times = [_float(r.get("elapsed_sec")) for r in sample]
        times = [v for v in times if v is not None]
        costs = [_float(r["cost"]) for r in solved]
        lengths = [_float(r.get("action_count")) for r in solved]
        ratios = [_float(r["cost"]) / best_for_state[r.get("initial_code", "")]
                  for r in solved if best_for_state.get(r.get("initial_code", ""), 0) > 0]
        statistics[algo] = dict(
            runs=len(sample), solved=len(solved),
            success_pct=round(100 * len(solved) / len(sample), 1),
            median_cost=median(costs) if costs else None,
            best_cost=min(costs) if costs else None,
            median_ratio=median(ratios) if ratios else None,
            median_actions=median(v for v in lengths if v is not None) if any(v is not None for v in lengths) else None,
            median_time=median(times) if times else None,
            timeout=sum(r.get("status") == "timeout" for r in sample),
        )

    palette = {"genetic": "#13a89e", "ucs": "#6e66d8", "astar": "#4c8ac7", "greedy": "#ed9f50"}
    default_color = "#7387a4"
    charts = []

    def add_chart(heading: str, chart, note: str = ""):
        chart.update_layout(
            template="plotly_white", font=dict(family="Arial, sans-serif", size=12),
            height=350, margin=dict(l=55, r=22, t=42, b=55),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            hoverlabel=dict(bgcolor="white"))
        charts.append((heading, chart, note))

    labels = [a.upper() if a != "genetic" else "Genetic" for a in algorithms]
    colors = [palette.get(a, default_color) for a in algorithms]

    if multi_grid:
        first_values = [statistics[a]["median_ratio"] for a in algorithms]
        first_title = "Median cost / best observed cost (per grid)"
        first_note = ("Matched by initial_code, only solved runs with a nonzero reference cost. "
                      "A ratio of 1 is best observed, not necessarily proven optimal. Unsolved runs appear in the success-rate chart.")
        y_title = "Median per-grid cost ratio"
    else:
        first_values = [statistics[a]["best_cost"] for a in algorithms]
        first_title = "Lowest observed solution cost"
        first_note = "Only confirmed solved routes are included; lower is better. Observed minimum is not necessarily optimal."
        y_title = "Weighted action cost"
    fig = go.Figure(go.Bar(x=labels, y=first_values,
                           marker_color=colors,
                           text=[round(v, 3) if v is not None else "" for v in first_values],
                           textposition="outside", hovertemplate="%{x}: %{y}<extra></extra>"))
    fig.update_layout(yaxis_title=y_title)
    observed = [v for v in first_values if v is not None]
    if observed and max(observed) > 0:
        # Reserve space for the value labels above the bars.
        fig.update_yaxes(range=[0, max(observed) * 1.20])
    fig.update_traces(cliponaxis=False)
    add_chart(first_title, fig, first_note)

    fig = go.Figure(go.Bar(x=labels, y=[statistics[a]["success_pct"] for a in algorithms],
                           marker_color=colors, text=[f'{statistics[a]["success_pct"]}%' for a in algorithms],
                           textposition="outside"))
    fig.update_layout(yaxis_title="Completed runs (%)", yaxis_range=[0, 115])
    add_chart("Success rate", fig, "Resource limits and run counts affect completion rates.")

    fig = go.Figure(go.Bar(x=labels, y=[statistics[a]["median_time"] for a in algorithms],
                           marker_color=colors))
    fig.update_layout(yaxis_title="Elapsed search time (seconds)")
    add_chart("Median runtime", fig, "All attempts, including timeouts, are included; compare limits and measurement settings.")

    fig = go.Figure(go.Bar(x=labels, y=[statistics[a]["median_actions"] for a in algorithms],
                           marker_color=colors))
    fig.update_layout(yaxis_title="Actions to goal")
    add_chart("Median successful route length", fig, "Number of paid openings, not weighted cost.")

    fig = go.Figure()
    for algo in algorithms:
        x = [_float(r.get("action_count")) for r in by_algo[algo] if _is_solved(r)]
        y = [_float(r.get("cost")) for r in by_algo[algo] if _is_solved(r)]
        points = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
        if points:
            fig.add_trace(go.Scatter(x=[p[0] for p in points], y=[p[1] for p in points],
                                     name=algo.upper(), mode="markers",
                                     marker=dict(color=palette.get(algo, default_color), size=9, opacity=.7)))
    fig.update_layout(xaxis_title="Actions", yaxis_title="Weighted cost")
    add_chart("Cost versus route length", fig, "Each dot is one successful run; repeated seeds remain separate points.")

    if histories:
        groups = defaultdict(list)
        for row in histories:
            if row.get("algorithm", "genetic") == "genetic":
                key = (row.get("initial_code", ""), row.get("run_id", ""), row.get("seed", ""), row.get("cost_transform", ""))
                groups[key].append(row)
        fig = go.Figure()
        for key, seq in sorted(groups.items(), key=lambda item: str(item[0])):
            seq.sort(key=lambda r: int(r["generation"]))
            label = f"Seed {key[2]} ({key[3]})"
            fig.add_trace(go.Scatter(x=[int(r["generation"]) for r in seq],
                                     y=[_float(r["best_fitness"]) for r in seq],
                                     mode="lines", name=label))
        fig.update_layout(xaxis_title="Generation", yaxis_title="Best fitness in generation")
        add_chart("Fitness evolution", fig, "Generational maximum; elitism normally keeps the maximum nondecreasing.")

        fig = go.Figure()
        for key, seq in sorted(groups.items(), key=lambda item: str(item[0])):
            seq.sort(key=lambda r: int(r["generation"]))
            fig.add_trace(go.Scatter(x=[int(r["generation"]) for r in seq],
                                     y=[_float(r["best_min_conflict"]) for r in seq],
                                     mode="lines", name=f"Seed {key[2]}"))
        fig.update_layout(xaxis_title="Generation", yaxis_title="Minimum occupied cells")
        add_chart("Conflict reduction", fig, "A conflict of zero corresponds to an empty sand grid.")

        fig = go.Figure()
        for key, seq in sorted(groups.items(), key=lambda item: str(item[0])):
            seq.sort(key=lambda r: int(r["generation"]))
            fig.add_trace(go.Scatter(x=[int(r["generation"]) for r in seq],
                                     y=[_float(r["best_cost"]) for r in seq],
                                     mode="lines", name=f"Seed {key[2]}"))
        fig.update_layout(xaxis_title="Generation", yaxis_title="Best solved-route cost")
        add_chart("Solved path cost by generation", fig, "Gaps indicate a generation with no solved individual; the global best may still exist.")

        fig = go.Figure()
        first_key, first_seq = next(iter(sorted(groups.items(), key=lambda item: str(item[0]))))
        first_seq.sort(key=lambda r: int(r["generation"]))
        fig.add_trace(go.Scatter(x=[int(r["generation"]) for r in first_seq],
                                 y=[_float(r["valid_count"]) for r in first_seq],
                                 name="Valid chromosomes", mode="lines"))
        fig.add_trace(go.Scatter(x=[int(r["generation"]) for r in first_seq],
                                 y=[_float(r["unique_genomes"]) for r in first_seq],
                                 name="Unique genomes", mode="lines"))
        fig.update_layout(xaxis_title="Generation", yaxis_title="Count")
        add_chart("Population validity and diversity", fig, f"Shown for seed {first_key[2]}.")

    if studies:
        fig = go.Figure()
        modes = sorted({r.get("cost_transform", "") for r in studies})
        for mode in modes:
            costs = [_float(r.get("cost")) for r in studies
                     if r.get("cost_transform") == mode and _is_solved(r)]
            fig.add_trace(go.Box(y=[v for v in costs if v is not None], name=mode,
                                 boxpoints="all", jitter=0.35, pointpos=-1.5))
        fig.update_layout(yaxis_title="Successful route cost")
        add_chart("Fitness transform ablation", fig,
                  "Compare linear/log/sqrt using equal initial states, seeds and budgets; unsuccessful runs are not assigned a fake cost.")

    # Offline bundled Plotly: no CDN or external internet needed.
    chunks = []
    for index, (heading, fig, note) in enumerate(charts):
        plot = to_html(fig, include_plotlyjs="inline" if index == 0 else False,
                       full_html=False, config={"displaylogo": False, "responsive": True})
        chunks.append(f'<article class="panel"><h2>{escape(heading)}</h2>{plot}'
                      f'<p class="note">{escape(note)}</p></article>')

    summary_rows = "".join(
        f'<tr><td><b>{escape(algo.upper())}</b></td><td>{s["runs"]}</td><td>{s["solved"]}</td>'
        f'<td>{s["success_pct"]}%</td>'
        f'<td>{round(s["median_ratio"], 3) if s["median_ratio"] is not None else "—"}'
        f'</td><td>{round(s["median_actions"], 2) if s["median_actions"] is not None else "—"}'
        f'</td><td>{round(s["median_time"], 4) if s["median_time"] is not None else "—"}</td>'
        f'<td>{s["timeout"]}</td></tr>'
        if multi_grid else
        f'<tr><td><b>{escape(algo.upper())}</b></td><td>{s["runs"]}</td><td>{s["solved"]}</td>'
        f'<td>{s["success_pct"]}%</td>'
        f'<td>{s["best_cost"] if s["best_cost"] is not None else "—"}</td>'
        f'<td>{round(s["median_cost"], 2) if s["median_cost"] is not None else "—"}</td>'
        f'<td>{round(s["median_time"], 4) if s["median_time"] is not None else "—"}</td>'
        f'<td>{s["timeout"]}</td></tr>'
        for algo, s in ((a, statistics[a]) for a in algorithms))
    grid_codes = sorted({r.get("initial_code", "unknown") for r in rows})
    model_versions = sorted({r.get("model_version", "unknown") for r in rows})
    notice = ""
    if len(model_versions) != 1 or "" in model_versions or "unknown" in model_versions:
        notice = "WARNING: some rows have missing or inconsistent model versions. Verify that datasets were produced by the same SandGrid rules."
    out = Path(output_html)
    out.parent.mkdir(parents=True, exist_ok=True)
    route_link = '<a href="genetic_route.html">Open GA route visualization</a>' if (out.parent / "genetic_route.html").exists() else ""
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f7fb;color:#1a2c44;font-family:Inter,Segoe UI,Arial,sans-serif}}
header{{background:linear-gradient(110deg,#112843,#244e70);padding:34px max(32px,calc((100vw - 1250px)/2));color:white}}
header h1{{font-size:29px;margin:0 0 8px;font-weight:730}}header p{{color:#cfe3ed;margin:4px 0;font-size:14px}}
main{{max-width:1260px;margin:auto;padding:26px 22px 60px}}.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px;margin-bottom:24px}}
.tile{{background:white;border:1px solid #dce5ef;border-radius:15px;padding:20px;box-shadow:0 3px 11px #17283d0b}}
.tile .num{{font-size:28px;font-weight:700;color:#0e4d73}}.tile .lbl{{font-size:12px;color:#587089;margin-top:7px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:18px}}.panel{{min-width:0;background:#fff;padding:18px 18px 12px;border:1px solid #dce5ef;border-radius:15px;box-shadow:0 3px 11px #17283d0b}}
.panel .plotly-graph-div{{width:100% !important;max-width:100%}}
.panel h2{{font-size:17px;margin:6px 0 0}}.note{{font-size:12px;line-height:1.5;color:#6a7d92;margin:0 12px 14px}}
.tablewrap{{overflow:auto;background:white;border:1px solid #dce5ef;border-radius:15px;margin-bottom:24px}}table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{padding:13px 15px;text-align:left;border-bottom:1px solid #ebeff5;white-space:nowrap}}th{{background:#eaf0f6;color:#354d66;font-size:12px}}
.alert{{border-left:4px solid #df8b51;background:#fff5ec;padding:12px 18px;margin-bottom:22px;font-size:13px}}
a{{color:#18b9a5}}footer{{font-size:12px;color:#65788e;margin-top:24px;line-height:1.7}}
@media(max-width:550px){{.grid{{grid-template-columns:1fr}}header{{padding:26px 24px}}main{{padding:18px 12px}}.panel{{padding:12px}}}}
</style></head><body>
<header><h1>{escape(title)}</h1><p>Actual recorded runs · SandGrid model: {escape(', '.join(model_versions))}</p><p>{len(grid_codes)} initial grids · {len(rows)} algorithm attempts · {len(algorithms)} algorithms</p></header>
<main>{f'<div class="alert">{escape(notice)}</div>' if notice else ''}
<section class="tiles"><div class="tile"><div class="num">{len(rows)}</div><div class="lbl">Total attempts</div></div>
<div class="tile"><div class="num">{sum(_is_solved(r) for r in rows)}</div><div class="lbl">Confirmed solutions</div></div>
<div class="tile"><div class="num">{len(algorithms)}</div><div class="lbl">Algorithms compared</div></div>
<div class="tile"><div class="num">{len(grid_codes)}</div><div class="lbl">Initial states</div></div></section>
<div class="tablewrap"><table><thead><tr><th>Algorithm</th><th>Runs</th><th>Solved</th><th>Success</th><th>{"Median cost ratio" if multi_grid else "Best cost"}</th><th>{"Median actions" if multi_grid else "Median cost"}</th><th>Median time (s)</th><th>Timeouts</th></tr></thead><tbody>{summary_rows}</tbody></table></div>
{f'<p>{route_link}</p>' if route_link else ''}
<section class="grid">{''.join(chunks)}</section>
<footer>Costs are weighted action costs. Failed and timed-out searches have no solution cost, not cost zero.\nAlgorithm runtimes are only directly comparable with matching machine, budgets and profiling settings; GA evaluates populations while graph searches expand states.\nThe dashboard reads experiment CSVs only; it does not contain fabricated demonstration measurements.</footer>
</main>
<script>
// Plotly creates each chart while the HTML is still being parsed. The first
// chart can initially occupy the full grid width; resize after all panels exist.
(function () {{
  let scheduled = false;
  function fitCharts() {{
    scheduled = false;
    if (!window.Plotly) return;
    document.querySelectorAll('.panel .plotly-graph-div').forEach(function (chart) {{
      const available = Math.floor(chart.getBoundingClientRect().width);
      if (available > 0 && chart._fullLayout &&
          Math.abs(chart._fullLayout.width - available) > 2) {{
        Plotly.Plots.resize(chart);
      }}
    }});
  }}
  function scheduleFit() {{
    if (!scheduled) {{
      scheduled = true;
      window.requestAnimationFrame(fitCharts);
    }}
  }}
  window.addEventListener('load', function () {{
    scheduleFit();
    if (window.ResizeObserver) {{
      const observer = new ResizeObserver(scheduleFit);
      document.querySelectorAll('.panel').forEach(function (panel) {{
        observer.observe(panel);
      }});
    }}
  }});
  window.addEventListener('resize', scheduleFit);
}})();
</script>
</body></html>'''
    out.write_text(html, encoding="utf-8")
    return out
