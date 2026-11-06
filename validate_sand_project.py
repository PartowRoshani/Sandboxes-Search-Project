"""Independent consistency checks for the sand-grid project.

Save this file in your project root, next to main.py and the sandgrid/ folder.
Run:
    python validate_sand_project.py
or:
    python validate_sand_project.py --steps results/my_full_run/professor/ucs_steps.json

No third-party packages required.
"""
from __future__ import annotations

import argparse
import heapq
import json
from collections import defaultdict
from itertools import product
from pathlib import Path

from sandgrid.model import SandGrid
from sandgrid.search import greedy, heuristic, search


PROFESSOR_GRID = [[1, 0], [0, 1], [0, 1], [1, 0]]


def check_teacher_and_ucs(steps_path: Path) -> None:
    model = SandGrid(4, 2)
    initial = model.from_display(PROFESSOR_GRID, convention="full-is-1")
    baseline = greedy(model, initial)
    ucs = search(model, initial, "ucs", max_seconds=60)
    astar = search(model, initial, "astar", max_seconds=60)

    assert baseline.found and baseline.cost == 47, (
        f"Teacher's baseline should be 47; got {baseline.cost}"
    )
    assert ucs.found and astar.found, "UCS and A* must find a solution"
    assert ucs.cost == astar.cost == 34, (
        f"Expected 34 for the current model; got UCS={ucs.cost}, A*={astar.cost}"
    )
    print(f"[PASS] Professor example: Greedy={baseline.cost}, UCS={ucs.cost}, A*={astar.cost}")

    data = json.loads(steps_path.read_text(encoding="utf-8"))
    assert data["algorithm"] == "ucs" and data["status"] == "found"
    assert data["initial_grid"] == model.to_display(initial)
    assert data["steps"][0]["number"] == 0
    assert data["steps"][0]["grid"] == model.to_display(initial)
    state = initial
    total = 0
    persistence_only = []
    for expected in data["steps"][1:]:
        matching = [action.id for action in model.actions if action.label == expected["action"]]
        assert len(matching) == 1, ("Unknown/ambiguous action", expected["action"])
        before_grid = model.to_display(state)
        before_mask = model.decode(state)[1]
        step = model.step(state, matching[0])
        assert step is not None, ("Invalid step", expected["number"])
        state, cost = step
        total += cost
        assert expected["grid"] == model.to_display(state), ("Grid mismatch", expected["number"])
        assert expected["open_vertical_mask"] == model.decode(state)[1], ("Mask mismatch", expected["number"])
        assert expected["step_cost"] == cost, ("Action cost mismatch", expected["number"])
        assert expected["total_cost"] == total, ("Total cost mismatch", expected["number"])
        if before_grid == expected["grid"] and before_mask != expected["open_vertical_mask"]:
            persistence_only.append(expected["number"])
    assert total == 34 and model.is_goal(state)
    print(f"[PASS] All {len(data['steps']) - 1} UCS steps replay; final grid empty; total cost={total}")
    print(f"[INFO] Actions that establish a connection without moving sand: {persistence_only}")
    print("[INFO] The teacher's Greedy=47 calculation also requires such persistent connections.")


def check_small_states() -> None:
    model = SandGrid(3, 2)
    states = []
    for occupancies in product(range(3), repeat=model.n):
        for mask in range(1 << model.vertical_edges):
            if model.valid_mask(occupancies, mask):
                states.append(model.encode(occupancies, mask))

    backward = defaultdict(list)
    transitions = 0
    inconsistent = []
    for source in states:
        before, _ = model.decode(source)
        hs = heuristic(model, source)
        for dest, action_id, cost in model.successors(source):
            transitions += 1
            after, _ = model.decode(dest)
            action = model.actions[action_id]
            assert model.valid_mask(*model.decode(dest)), ("Invalid persistent gate", source, dest)
            assert cost == (1 if action.kind == "side" else 1 + 2 * (before[action.src] + after[action.src]))
            if action.kind == "side" or action.dst is not None:
                assert sum(before) == sum(after), ("Sand disappeared within grid", source, dest)
            else:
                assert sum(after) < sum(before), ("Bottom opening failed to drain", source, dest)
            if hs > cost + heuristic(model, dest):
                inconsistent.append((source, dest, hs, cost, heuristic(model, dest)))
            backward[dest].append((source, cost))

    optimal = {0: 0}
    heap = [(0, 0)]
    while heap:
        cost, current = heapq.heappop(heap)
        if optimal[current] != cost:
            continue
        for predecessor, edge_cost in backward[current]:
            new_cost = cost + edge_cost
            if new_cost < optimal.get(predecessor, float("inf")):
                optimal[predecessor] = new_cost
                heapq.heappush(heap, (new_cost, predecessor))

    assert len(optimal) == len(states), "Some valid states cannot reach the goal"
    violations = [(state, heuristic(model, state), optimal[state])
                  for state in states if heuristic(model, state) > optimal[state]]
    assert not violations, ("A* heuristic overestimates", violations[:3])
    assert not inconsistent, ("A* heuristic is inconsistent", inconsistent[:3])
    print(f"[PASS] 3x2 exhaustive audit: {len(states)} valid states, {transitions} transitions")
    print("[PASS] Sand conservation, edge costs, persistent gates, admissibility and consistency")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify sand-grid model and teacher example")
    parser.add_argument("--steps", type=Path,
                        default=Path("results/my_full_run/professor/ucs_steps.json"),
                        help="Path to professor UCS step-by-step JSON")
    args = parser.parse_args()
    if not args.steps.is_file():
        parser.error(f"Steps file not found: {args.steps}")
    check_teacher_and_ucs(args.steps)
    check_small_states()
    print("All independent checks passed.")


if __name__ == "__main__":
    main()
