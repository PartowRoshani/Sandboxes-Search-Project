"""Exhaustive heuristic correctness checks for the continuous-flow sand-grid model.

Copy this file into tests/test_heuristic_verification.py and run:
    python -m pytest -v -s tests/test_heuristic_verification.py

This is an exhaustive test on the listed grid sizes, not a universal proof for
arbitrarily large grids.
"""
from __future__ import annotations

import pytest

from sandgrid.batch import compute_all_optimal
from sandgrid.model import SandGrid
from sandgrid.search import heuristic


@pytest.mark.parametrize("rows,cols", [(1, 2), (2, 2), (3, 2)])
def test_heuristic_admissible_and_consistent_on_all_stable_states(rows: int, cols: int):
    model = SandGrid(rows, cols)
    batch = compute_all_optimal(model, progress=False, max_states=20_000)
    assert heuristic(model, 0) == 0, "Goal heuristic must be zero"

    states_checked = 0
    edges_checked = 0
    equal_to_exact = 0

    for index, encoded in enumerate(batch["states"]):
        state = int(encoded)
        estimate = heuristic(model, state)
        exact = int(batch["distances"][index])

        # Admissibility: an estimated remaining cost must never exceed the
        # true minimum remaining cost obtained by reverse Dijkstra.
        assert 0 <= estimate <= exact, (
            f"Admissibility violation at state={state}: h={estimate}, h*={exact}, "
            f"occupancy_and_open_gates={model.decode(state)}"
        )
        equal_to_exact += estimate == exact
        states_checked += 1

        # Consistency: the triangle inequality must hold on EVERY legal edge,
        # including edges that trigger automatic cascades and gate closures.
        for successor, action_id, action_cost in model.successors(state):
            next_estimate = heuristic(model, successor)
            assert estimate <= action_cost + next_estimate, (
                f"Consistency violation: state={state} -> {successor}, "
                f"action={action_id}, cost={action_cost}, "
                f"h(state)={estimate}, h(successor)={next_estimate}"
            )
            edges_checked += 1

    assert states_checked == batch["valid_states"]
    assert edges_checked == batch["graph_edges"]
    print(
        f"\n{rows}x{cols}: {states_checked:,} states; "
        f"{edges_checked:,} edges; "
        f"admissibility and consistency both PASS; "
        f"h equals exact cost in {equal_to_exact:,} states"
    )
