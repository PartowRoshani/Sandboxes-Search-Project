#!/usr/bin/env python3
"""Repeatable smoke tests and CSV comparisons for the sand-only search model.

Run from the repository root:
    python scripts/test_algorithms.py --seconds 3 --random-count 2
"""
from __future__ import annotations

import argparse
import csv
import sys
import tracemalloc
from pathlib import Path
from time import perf_counter

# Allow execution with `python scripts/test_algorithms.py` without pip installation.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sandgrid.model import SandGrid
from sandgrid.search import greedy, search

ALGORITHMS = ("greedy", "dfs", "bfs", "ids", "ucs", "astar", "rbfs")
PROFESSOR_GRID = [[1, 0], [0, 1], [0, 1], [1, 0]]
FIELDS = ("case", "algorithm", "status", "cost", "actions", "side_actions",
          "expanded", "elapsed_sec", "peak_python_kib", "verified")


def verify_solution(model: SandGrid, initial: int, result) -> bool:
    """Replay every reported action and check the goal and total cost."""
    if not result.found:
        assert result.cost is None, "Unsolved run must not claim a final cost"
        return False
    trace = model.trace(initial, result.actions)
    assert len(trace) == len(result.actions) + 1
    assert trace[-1]["total_cost"] == result.cost
    assert model.is_goal(trace[-1]["state"]), "Reported solution is not a goal"
    return True


def evaluate_case(name: str, model: SandGrid, initial: int, args) -> list[dict]:
    rows = []
    solved = {}
    print(f"\nCASE: {name}")
    print(model.cell_string(initial))
    print(f"{'algorithm':10} {'status':16} {'cost':>6} {'moves':>6} {'time(s)':>9} {'verified':>9}")
    for algorithm in ALGORITHMS:
        if algorithm == "greedy":
            tracemalloc.start()
            start = perf_counter()
            try:
                result = greedy(model, initial)
                elapsed = perf_counter() - start
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
        else:
            result = search(
                model, initial, algorithm,
                max_seconds=args.seconds,
                max_expansions=args.expansions,
                max_depth=args.depth,
                measure_memory=True,
            )
            elapsed = result.elapsed_sec
            peak = result.peak_memory_bytes or 0

        verified = verify_solution(model, initial, result)
        side_count = sum(model.actions[a].kind == "side" for a in result.actions)
        rows.append({
            "case": name, "algorithm": algorithm, "status": result.status,
            "cost": result.cost if result.found else "",
            "actions": len(result.actions) if result.found else "",
            "side_actions": side_count if result.found else "",
            "expanded": result.expanded,
            "elapsed_sec": f"{elapsed:.6f}",
            "peak_python_kib": f"{peak / 1024:.2f}",
            "verified": verified,
        })
        print(f"{algorithm:10} {result.status:16} {str(result.cost):>6} "
              f"{len(result.actions) if result.found else '-':>6} "
              f"{elapsed:9.3f} {str(verified):>9}")
        if result.found:
            solved[algorithm] = result

    # These checks are safe even when resource-limited searches time out.
    if "ucs" in solved and "astar" in solved:
        assert solved["ucs"].cost == solved["astar"].cost, \
            "UCS and A* disagree about optimal weighted cost"
    if "bfs" in solved and "ids" in solved:
        assert len(solved["bfs"].actions) == len(solved["ids"].actions), \
            "BFS and IDS disagree about minimum action count"
    if "ucs" in solved:
        for algorithm, result in solved.items():
            assert result.cost >= solved["ucs"].cost, \
                f"{algorithm} beat the UCS optimum"

    if name == "professor_4x2":
        assert solved["greedy"].cost == 47, "Expected professor Greedy cost 47"
        for algorithm in ("ucs", "astar"):
            if algorithm in solved:
                assert solved[algorithm].cost == 34, \
                    f"Expected {algorithm} cost 34 in the implemented model"
    if name == "tiny_2x2":
        for algorithm in ("ucs", "astar"):
            if algorithm in solved:
                assert solved[algorithm].cost == 15
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=3.0,
                        help="Time limit per search algorithm (not Greedy)")
    parser.add_argument("--expansions", type=int, default=100000)
    parser.add_argument("--depth", type=int, default=30,
                        help="Maximum depth for IDS")
    parser.add_argument("--random-count", type=int, default=2,
                        help="Number of reproducible random 3x2 cases")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path,
                        default=Path("results/algorithm_tests.csv"))
    args = parser.parse_args()
    if args.seconds <= 0 or args.expansions <= 0 or args.depth < 0 or args.random_count < 0:
        parser.error("seconds/expansions must be positive, depth/count nonnegative")

    tiny = SandGrid(2, 2)
    professor = SandGrid(4, 2)
    cases = [
        ("tiny_2x2", tiny, tiny.from_display([[1, 0], [0, 1]])),
        ("professor_4x2", professor,
         professor.from_display(PROFESSOR_GRID, convention="full-is-1")),
    ]
    for i in range(args.random_count):
        model = SandGrid(3, 2)
        cases.append((f"random_3x2_seed_{args.seed + i}", model,
                      model.random_state(seed=args.seed + i)))

    all_rows = []
    for name, model, initial in cases:
        all_rows.extend(evaluate_case(name, model, initial, args))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    total = len(all_rows)
    solved_count = sum(r["status"] == "found" for r in all_rows)
    print(f"\nPASS: {solved_count}/{total} searches completed; "
          "all completed paths and cross-checks verified.")
    print("Unfinished searches are recorded as limits, not incorrect solutions.")
    print(f"CSV: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
