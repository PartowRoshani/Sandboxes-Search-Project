"""Checks for relaxation, exact optimality and an ML safety counterexample."""
import pytest

from sandgrid.batch import compute_all_optimal
from sandgrid.heuristics import basic, relaxation, count_unsafe
from sandgrid.model import SandGrid
from sandgrid.search import greedy, search


@pytest.mark.parametrize('rows,cols', [(1, 2), (2, 2), (3, 2)])
def test_relax_is_admissible_and_consistent_on_every_stable_state(rows, cols):
    m = SandGrid(rows, cols)
    b = compute_all_optimal(m, progress=False, max_states=20_000)
    assert relaxation(m, 0) == 0
    for i, s in enumerate(b['states']):
        s = int(s)
        h = relaxation(m, s)
        exact = int(b['distances'][i])
        assert basic(m, s) <= h <= exact, (s, h, exact)
        for nxt, action, cost in m.successors(s):
            assert h <= cost + relaxation(m, nxt), (s, action, nxt, cost)


def test_count_proposal_has_counterexample_with_preopened_gate():
    m = SandGrid(2, 1)
    s = m.encode([2, 2], 1)  # blocked gate was opened in an earlier step
    assert count_unsafe(m, s) == 10
    exit_action = m.down_ids[1]
    assert m.step(s, exit_action) == (0, 5)
    assert count_unsafe(m, s) > 5


def test_professor_baseline_and_astar_relax_reproduce_known_costs():
    m = SandGrid(4, 2)
    start = m.from_display([[1, 0], [0, 1], [0, 1], [1, 0]])
    g = greedy(m, start)
    u = search(m, start, 'ucs', max_seconds=30)
    a = search(m, start, 'astar', heuristic_name='relax', max_seconds=30)
    assert (g.cost, g.action_count) == (47, 7)
    assert u.found and a.found and u.cost == a.cost == 34
    assert relaxation(m, start) == 20
