"""Regression tests for randomized, cycle-free sand-grid graph search."""
from __future__ import annotations

import csv

from sandgrid.benchmark import ALGORITHMS, benchmark, random_seed_for_state
from sandgrid.model import SandGrid
from sandgrid.search import greedy, search


def _check_solution(model: SandGrid, initial: int, result):
    assert result.algorithm == 'random'
    assert result.found and result.status == 'found'
    trace = model.trace(initial, result.actions)
    states = [entry['state'] for entry in trace]
    assert len(states) == len(set(states)), 'Repeated *full* state on final path'
    assert model.is_goal(states[-1])
    assert trace[-1]['total_cost'] == result.cost
    return states


def test_random_completes_all_initial_2x2_without_repeated_states():
    model = SandGrid(2, 2)
    for initial in range(model.base):
        result = search(model, initial, 'random', random_seed=random_seed_for_state(19, initial),
                        max_expansions=20000, max_seconds=3)
        _check_solution(model, initial, result)


def test_seed_reproduces_path_and_different_seeds_can_change_it():
    model = SandGrid(4, 2)
    initial = model.from_display([[1, 0], [0, 1], [0, 1], [1, 0]])
    once = search(model, initial, 'random', random_seed=42, max_seconds=5)
    twice = search(model, initial, 'random', random_seed=42, max_seconds=5)
    _check_solution(model, initial, once)
    assert once.actions == twice.actions
    assert once.cost == twice.cost
    assert len({tuple(search(model, initial, 'random', random_seed=s, max_seconds=5).actions)
                for s in range(6)}) > 1
    assert greedy(model, initial).cost == 47  # existing assignment baseline unchanged


def test_random_honors_expansion_limit():
    model = SandGrid(2, 2)
    initial = model.from_display([[1, 0], [0, 1]])
    result = search(model, initial, 'random', random_seed=7, max_expansions=1)
    assert not result.found
    assert result.status == 'expansion_limit'
    assert result.cost is None and not result.actions


def test_benchmark_registers_random_and_keeps_reference_solutions(tmp_path):
    model = SandGrid(1, 2)
    assert 'random' in ALGORITHMS
    file = tmp_path / 'benchmark.csv'
    stats = benchmark(model, file, count=5, seed=14,
                      algorithms=('random', 'ucs'), max_seconds=3,
                      max_expansions=10000, resume=False)
    assert stats['completed'] == 10
    with file.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    by_grid = {}
    for row in rows:
        by_grid.setdefault(int(row['initial_code']), {})[row['algorithm']] = row
    assert len(by_grid) == 5
    for entries in by_grid.values():
        assert entries['random']['status'] == 'found'
        assert entries['ucs']['status'] == 'found'
        assert int(entries['random']['cost']) >= int(entries['ucs']['cost'])
