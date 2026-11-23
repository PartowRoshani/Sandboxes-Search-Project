"""CLI entrypoint: python -m genetic_alg <solve|compare|benchmark|study|dashboard>."""
from __future__ import annotations
import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path
import random

from .core import GAConfig, GeneticAlgorithm
from .dashboard import build_dashboard
from .experiments import (ALGORITHMS, COLUMNS, compare_one, ga_run, read_rows,
                          save_experiment, write_rows, write_solution)

PROFESSOR_GRID = [[1, 0], [0, 1], [0, 1], [1, 0]]
HISTORY_COLUMNS = ("initial_code", "algorithm", "run_id", "seed", "cost_transform",
                   "conflict_mode", "generation", "best_fitness", "mean_fitness",
                   "median_fitness", "best_cost", "best_min_conflict",
                   "best_cost_at_min_conflict", "solved_count", "valid_count",
                   "invalid_count", "unique_genomes", "elapsed_sec")


def model_and_initial(args):
    from sandgrid.model import SandGrid
    if getattr(args, "example", None) == "professor":
        model = SandGrid(4, 2)
        return model, model.from_display(PROFESSOR_GRID)
    model = SandGrid(args.rows, args.cols)
    if args.grid is not None:
        initial = model.from_display(json.loads(args.grid))
    else:
        initial = model.random_state(seed=args.seed)
    return model, initial


def config_from_args(args, seed: int | None = None, transform: str | None = None) -> GAConfig:
    return GAConfig(population_size=args.population,
                    chromosome_length=args.length, generations=args.generations,
                    crossover_rate=args.crossover_rate, mutation_rate=args.mutation_rate,
                    elitism=args.elitism, immigrant_fraction=args.immigrants,
                    crossover_method=args.crossover, mutation_method=args.mutation,
                    cost_transform=transform or args.cost_transform,
                    conflict_mode=args.conflict,
                    seed=args.seed if seed is None else seed,
                    max_seconds=args.ga_seconds, target_cost=args.target_cost)


def _save_and_report(model, initial, comparison, history, best, output,
                     study_rows=None):
    out = Path(output)
    save_experiment(model, initial, comparison, history, best, out)
    if study_rows is not None:
        write_rows(out / "fitness_study.csv", study_rows, COLUMNS)
    html = build_dashboard(out / "comparison.csv", out / "ga_history.csv",
                           out / "dashboard.html",
                           title="SandGrid · Genetic Algorithm and Search Baselines",
                           study_csv=(out / "fitness_study.csv" if study_rows is not None else None))
    print(f"Report folder: {out.resolve()}")
    print(f"Dashboard: {html.resolve()}")
    print(f"Genetic result: status={best.status} cost={best.cost} actions={best.action_count} "
          f"fitness={best.fitness:.4f} min_conflict={best.best_min_conflict} "
          f"generations={best.generations_completed}")


def solve_command(args):
    model, initial = model_and_initial(args)
    config = config_from_args(args)
    row, hist, best = ga_run(model, initial, config)
    _save_and_report(model, initial, [row], hist, best, args.output)
    print("Executed action IDs:", best.actions)
    if best.found:
        print("Verified goal route saved to genetic_solution.json and genetic_route.html")
    else:
        print("No complete solution: reported prefix attains minimum conflict, NOT a goal path")


def _import_baselines(args, model, initial):
    if not args.baseline_csv:
        return []
    existing = read_rows(args.baseline_csv)
    matching = [r for r in existing if r.get("initial_code") == str(initial)
                and r.get("algorithm") in ALGORITHMS]
    if not matching:
        raise ValueError("baseline CSV has no matching initial_code")
    for row in matching:
        version = row.get("model_version", "")
        if version and version != model.MODEL_VERSION:
            raise ValueError(f"baseline model version {version!r} differs from current {model.MODEL_VERSION!r}")
        if not version and not args.confirm_same_model:
            raise ValueError("Baseline CSV has no model_version. Pass --confirm-same-model "
                             "ONLY after checking the CSV uses the current revised model.")
        row["model_version"] = model.MODEL_VERSION
        row["rows"] = model.rows
        row["cols"] = model.cols
        row.setdefault("run_id", "imported")
    return matching


def compare_command(args):
    model, initial = model_and_initial(args)
    cfg = config_from_args(args)
    old_rows, history, best = compare_one(
        model, initial, cfg, repeats=args.repeats,
        include_baselines=not args.no_baselines,
        baseline_seconds=args.baseline_seconds,
        max_expansions=args.max_expansions, max_depth=args.max_depth)
    old_rows.extend(_import_baselines(args, model, initial))
    _save_and_report(model, initial, old_rows, history, best, args.output)


def benchmark_command(args):
    from sandgrid.model import SandGrid
    if args.example or args.grid:
        raise ValueError("benchmark uses sampled initial grids; use compare for --example/--grid")
    model = SandGrid(args.rows, args.cols)
    rng = random.Random(args.seed)
    codes = rng.sample(range(model.base), min(args.count, model.base))
    all_rows, all_hist = [], []
    for idx, initial in enumerate(codes, 1):
        cfg = config_from_args(args, seed=args.seed + 1000 * idx)
        comparison, history, _ = compare_one(
            model, initial, cfg, repeats=args.repeats,
            include_baselines=not args.no_baselines,
            baseline_seconds=args.baseline_seconds,
            max_expansions=args.max_expansions, max_depth=args.max_depth)
        all_rows.extend(comparison)
        all_hist.extend(history)
        print(f"Grid {idx}/{len(codes)} (code {initial}): "
              f"{sum(r['algorithm']=='genetic' and r['found']==1 for r in comparison)} "
              f"of {args.repeats} GA runs solved", flush=True)
    out = Path(args.output)
    write_rows(out / "comparison.csv", all_rows, COLUMNS)
    write_rows(out / "ga_history.csv", all_hist, HISTORY_COLUMNS)
    dash = build_dashboard(out / "comparison.csv", out / "ga_history.csv",
                           out / "dashboard.html", title="SandGrid · Multi-grid Genetic Benchmark")
    (out / "experiment_config.json").write_text(json.dumps({
        "model_version": model.MODEL_VERSION, "grid_codes": codes,
        "rows": model.rows, "cols": model.cols, "repeats": args.repeats,
        "config": {k: v for k, v in vars(args).items() if k != "func"}}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Dashboard:", dash.resolve())


def study_command(args):
    model, initial = model_and_initial(args)
    modes = list(dict.fromkeys(args.transforms))
    rows: list[dict] = []
    history: list[dict] = []
    incumbent = None
    for mode in modes:
        for i in range(args.repeats):
            # Identical seed across transforms to make comparison paired.
            config = config_from_args(args, seed=args.seed + i, transform=mode)
            row, hist, result = ga_run(model, initial, config, run_id=i)
            rows.append(row)
            history.extend(hist)
            # Fitness magnitudes use different cost transforms: compare the
            # actual solved-route cost when choosing which path to replay.
            if incumbent is None or (result.found and
                    (not incumbent.found or result.cost < incumbent.cost)) or (
                    not result.found and not incumbent.found and
                    result.best_min_conflict < incumbent.best_min_conflict):
                incumbent = result
            print(f"transform={mode:6} seed={config.seed:3} "
                  f"status={result.status:9} cost={result.cost}", flush=True)
    assert incumbent is not None
    _save_and_report(model, initial, rows, history, incumbent, args.output, study_rows=rows)
    print("Paired transform comparisons are in fitness_study.csv.")


def dashboard_command(args):
    path = build_dashboard(args.comparison, args.history, args.output,
                           study_csv=args.study, title=args.title)
    print("Dashboard:", path.resolve())


def _add_initial(parser):
    parser.add_argument("--example", choices=("professor",), help="4x2 instructor grid")
    parser.add_argument("--rows", type=int, default=3)
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--grid", help='Display grid JSON, e.g. "[[1,0],[0.5,1]]"')
    parser.add_argument("--seed", type=int, default=42)


def _add_ga(parser):
    parser.add_argument("--population", type=int, default=50)
    parser.add_argument("--length", type=int, default=50, help="Fixed chromosome action slots (50 or 100)")
    parser.add_argument("--generations", type=int, default=1000)
    parser.add_argument("--crossover-rate", type=float, default=0.85)
    parser.add_argument("--mutation-rate", type=float, default=0.30)
    parser.add_argument("--elitism", type=int, default=2)
    parser.add_argument("--immigrants", type=float, default=0.10, help="Fraction of new random individuals per generation")
    parser.add_argument("--crossover", choices=("one_point", "two_point"), default="one_point")
    parser.add_argument("--mutation", choices=("replace", "swap"), default="replace")
    parser.add_argument("--cost-transform", choices=("log", "linear", "sqrt", "none"), default="log")
    parser.add_argument("--conflict", choices=("occupied", "half_units"), default="occupied")
    parser.add_argument("--ga-seconds", type=float, default=None, help="Optional GA wall-time cap")
    parser.add_argument("--target-cost", type=int, default=None,
                        help="Known target cost, if available; does not imply a proven bound")
    parser.add_argument("--output", default="genetic_alg/results/latest")


def _add_baselines(parser):
    parser.add_argument("--repeats", type=int, default=3, help="Repeated GA and Random seeds")
    parser.add_argument("--no-baselines", action="store_true", help="Do not rerun the eight old algorithms")
    parser.add_argument("--baseline-seconds", type=float, default=5.0)
    parser.add_argument("--max-expansions", type=int, default=100000)
    parser.add_argument("--max-depth", type=int, default=30)


def main(argv=None):
    p = argparse.ArgumentParser(description="Genetic Algorithm extension for SandGrid")
    subs = p.add_subparsers(dest="command", required=True)
    solve = subs.add_parser("solve", help="GA only, with replay and GA dashboard")
    _add_initial(solve); _add_ga(solve)
    solve.set_defaults(func=solve_command)
    compare = subs.add_parser("compare", help="GA versus the eight original methods")
    _add_initial(compare); _add_ga(compare); _add_baselines(compare)
    compare.add_argument("--baseline-csv", help="Existing sandgrid benchmark CSV to import")
    compare.add_argument("--confirm-same-model", action="store_true",
                         help="Explicitly confirm versionless older CSV matches current revised SandGrid rules")
    compare.set_defaults(func=compare_command)
    benchmark = subs.add_parser("benchmark", help="Several identical sampled initial grids for every algorithm")
    _add_initial(benchmark); _add_ga(benchmark); _add_baselines(benchmark)
    benchmark.add_argument("--count", type=int, default=5)
    benchmark.set_defaults(func=benchmark_command)
    study = subs.add_parser("study", help="Matched-seed log vs linear vs sqrt fitness ablation")
    _add_initial(study); _add_ga(study)
    study.add_argument("--transforms", nargs="+", choices=("log", "linear", "sqrt", "none"),
                       default=("log", "linear", "sqrt"))
    study.add_argument("--repeats", type=int, default=5)
    study.set_defaults(func=study_command)
    dash = subs.add_parser("dashboard", help="Rebuild offline HTML from recorded experiment CSVs")
    dash.add_argument("--comparison", required=True)
    dash.add_argument("--history", default=None)
    dash.add_argument("--study", default=None)
    dash.add_argument("--output", default="genetic_alg/results/dashboard.html")
    dash.add_argument("--title", default="SandGrid · Search Algorithms Dashboard")
    dash.set_defaults(func=dashboard_command)
    args = p.parse_args(argv)
    if getattr(args, "repeats", 1) < 1 or getattr(args, "count", 1) < 1:
        p.error("--repeats and --count must be >= 1")
    try:
        args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        p.error(str(exc))
    return 0
