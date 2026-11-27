"""Independent experiments; all old algorithms are called read-only."""
from __future__ import annotations
import csv
import json
from dataclasses import asdict, replace
from pathlib import Path
import random
import tracemalloc
from typing import Any

from .core import GAConfig, GeneticAlgorithm, GAResult

ALGORITHMS = ("greedy", "random", "dfs", "bfs", "ids", "ucs", "astar", "rbfs")
COLUMNS = (
    "model_version", "rows", "cols", "initial_code", "algorithm", "run_id", "seed",
    "status", "found", "cost", "action_count", "side_action_count", "elapsed_sec",
    "expanded", "generated", "max_frontier", "peak_python_bytes",
    "ga_fitness", "ga_min_conflict", "ga_cost_at_min_conflict",
    "ga_generations_completed", "ga_evaluations", "ga_unique_evaluations",
    "chromosome_length", "population_size", "cost_transform", "conflict_mode",
    "time_limit_sec", "max_expansions", "max_depth",
    "evolution_mode", "mutation_attempts", "mutation_trials",
    "lethal_mutations", "mutation_fallbacks",
)


def write_rows(path: str | Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def _memory_call(func, *, measure_memory: bool = False):
    """Time the real algorithm without tracing; optionally profile a *second* run.

    The returned algorithm result (and its own elapsed_sec) always comes from
    the uninstrumented execution. Python-tracked peak memory, when requested,
    comes from a separate repeat and MUST NOT be interpreted as RAM usage of
    the timed execution. Runs with time caps can take different paths.
    """
    result = func()
    if not measure_memory:
        return result, ""  # Missing measurement, not zero bytes.
    tracemalloc.start()
    try:
        func()  # Separate profile run: not used for result/elapsed_sec.
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return result, peak


def baseline_run(model, initial: int, algorithm: str, seed: int, run_id: int,
                 *, max_seconds: float, max_expansions: int, max_depth: int,
                 measure_memory: bool = False) -> dict:
    from sandgrid.search import search, greedy
    if algorithm not in ALGORITHMS:
        raise ValueError(f"unknown baseline algorithm: {algorithm}")
    # Reuse the actual search implementations. Do not reimplement their rules.
    if algorithm == "greedy":
        result, peak = _memory_call(lambda: greedy(model, initial),
                                    measure_memory=measure_memory)
    else:
        result, peak = _memory_call(lambda: search(
            model, initial, algorithm,
            max_seconds=max_seconds, max_expansions=max_expansions,
            max_depth=max_depth, random_seed=seed, measure_memory=False),
            measure_memory=measure_memory)
    return {
        "model_version": model.MODEL_VERSION, "rows": model.rows, "cols": model.cols,
        "initial_code": initial, "algorithm": algorithm, "run_id": run_id,
        "seed": seed if algorithm == "random" else "",
        "status": result.status, "found": int(result.found),
        "cost": result.cost if result.found else "",
        "action_count": result.action_count if result.found else "",
        "side_action_count": sum(model.actions[a].kind == "side" for a in result.actions)
            if result.found else "",
        "elapsed_sec": round(result.elapsed_sec, 6), "expanded": result.expanded,
        "generated": result.generated, "max_frontier": result.max_frontier,
        "peak_python_bytes": peak, "time_limit_sec": max_seconds if algorithm != "greedy" else "",
        "max_expansions": max_expansions if algorithm != "greedy" else "",
        "max_depth": max_depth if algorithm != "greedy" else "",
    }


def ga_run(model, initial: int, config: GAConfig, run_id: int = 0,
           *, measure_memory: bool = False) -> tuple[dict, list[dict], GAResult]:
    result, peak = _memory_call(lambda: GeneticAlgorithm(model, initial, config).run(),
                                measure_memory=measure_memory)
    row = {
        "model_version": model.MODEL_VERSION, "rows": model.rows, "cols": model.cols,
        "initial_code": initial, "algorithm": "genetic", "run_id": run_id,
        "seed": config.seed, "status": result.status, "found": int(result.found),
        "cost": result.cost if result.found else "",
        "action_count": result.action_count if result.found else "",
        "side_action_count": sum(model.actions[a].kind == "side" for a in result.actions)
            if result.found else "", "elapsed_sec": round(result.elapsed_sec, 6),
        "expanded": "", "generated": "", "max_frontier": "",  # GA has no graph frontier
        "peak_python_bytes": peak, "ga_fitness": round(result.fitness, 6),
        "ga_min_conflict": result.best_min_conflict,
        "ga_cost_at_min_conflict": result.best_cost_at_min_conflict,
        "ga_generations_completed": result.generations_completed,
        "ga_evaluations": result.evaluations,
        "ga_unique_evaluations": result.unique_evaluations,
        "chromosome_length": config.chromosome_length,
        "population_size": config.population_size,
        "cost_transform": config.cost_transform, "conflict_mode": config.conflict_mode,
        "time_limit_sec": config.max_seconds if config.max_seconds is not None else "",
        "evolution_mode": config.evolution_mode,
        "mutation_attempts": config.mutation_attempts if config.evolution_mode == "classroom" else "",
        **{k: result.history[-1][k] if config.evolution_mode == "classroom" else ""
           for k in ("mutation_trials", "lethal_mutations", "mutation_fallbacks")},
    }
    history = [dict(initial_code=initial, run_id=run_id, seed=config.seed,
                    algorithm="genetic", cost_transform=config.cost_transform,
                    conflict_mode=config.conflict_mode, evolution_mode=config.evolution_mode,
                    **item)
               for item in result.history]
    return row, history, result


def write_solution(model, initial: int, result: GAResult,
                   output: str | Path, stem: str = "genetic") -> None:
    """Actual executable route and original project visualization (if solved)."""
    dest = Path(output)
    dest.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "model_version": model.MODEL_VERSION, "initial_code": initial,
        "initial_grid": model.to_display(initial), "rows": model.rows, "cols": model.cols,
        "algorithm": "genetic", "configuration": asdict(result.config),
        "status": result.status, "found": result.found,
        "cost": result.cost, "fitness": result.fitness,
        "min_conflict": result.best_min_conflict,
        "cost_at_min_conflict": result.best_cost_at_min_conflict,
        "generations_completed": result.generations_completed,
        "evaluations": result.evaluations,
        "chromosome": list(result.chromosome),
        "executed_action_ids": result.actions,
        "executed_actions": [model.actions[a].label for a in result.actions],
    }
    if result.found:
        trace = model.trace(initial, result.actions)
        assert model.is_goal(trace[-1]["state"]), "GA route did not reach the goal"
        assert trace[-1]["total_cost"] == result.cost, "GA route cost does not match"
        data["steps"] = [dict(step=i, grid=model.to_display(t["state"]),
                             open_gate_mask=model.decode(t["state"])[1],
                             cost=t["step_cost"], total=t["total_cost"],
                             action=t["action"], flow_events=t.get("flow_events", []))
                         for i, t in enumerate(trace)]
        from sandgrid.visualize import save_html
        save_html(model, initial, result.actions,
                  str(dest / f"{stem}_route.html"), title="Genetic Algorithm - SandGrid")
    (dest / f"{stem}_solution.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def compare_one(model, initial: int, config: GAConfig, *, repeats: int = 3,
                include_baselines: bool = True, baseline_seconds: float = 5.0,
                max_expansions: int = 100000, max_depth: int = 30,
                baseline_algorithms: tuple[str, ...] = ALGORITHMS,
                measure_memory: bool = False) -> tuple[list[dict], list[dict], GAResult]:
    """All algorithms see exactly the same initial state and model version."""
    if repeats < 1:
        raise ValueError("repeats must be >=1")
    comparison: list[dict] = []
    history: list[dict] = []
    if include_baselines:
        for algorithm in baseline_algorithms:
            count = repeats if algorithm == "random" else 1
            for run_id in range(count):
                trial_seed = config.seed + run_id
                comparison.append(baseline_run(
                    model, initial, algorithm, trial_seed, run_id,
                    max_seconds=baseline_seconds, max_expansions=max_expansions,
                    max_depth=max_depth, measure_memory=measure_memory))
    best: GAResult | None = None
    for run_id in range(repeats):
        trial_cfg = replace(config, seed=config.seed + run_id)
        row, rows_history, result = ga_run(model, initial, trial_cfg, run_id,
                                           measure_memory=measure_memory)
        comparison.append(row)
        history.extend(rows_history)
        if best is None or result.fitness > best.fitness:
            best = result
    assert best is not None
    return comparison, history, best


def save_experiment(model, initial: int, comparison: list[dict], history: list[dict],
                    best: GAResult, output: str | Path) -> None:
    dest = Path(output)
    dest.mkdir(parents=True, exist_ok=True)
    write_rows(dest / "comparison.csv", comparison, COLUMNS)
    hist_columns = ("initial_code", "algorithm", "run_id", "seed", "cost_transform",
                    "conflict_mode", "generation", "best_fitness", "mean_fitness",
                    "median_fitness", "best_cost", "best_min_conflict",
                    "best_cost_at_min_conflict", "solved_count", "valid_count",
                    "invalid_count", "unique_genomes", "elapsed_sec",
                    "evolution_mode", "mutation_trials", "lethal_mutations", "mutation_fallbacks")
    write_rows(dest / "ga_history.csv", history, hist_columns)
    (dest / "run_config.json").write_text(json.dumps({
        "model_version": model.MODEL_VERSION, "initial_code": initial,
        "initial_grid": model.to_display(initial), "config": asdict(best.config),
        "comparison_rows": len(comparison), "history_rows": len(history)
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    write_solution(model, initial, best, dest)
