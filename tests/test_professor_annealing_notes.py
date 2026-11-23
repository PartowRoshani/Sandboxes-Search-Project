"""Focused tests for the professor's annotated Simulated Annealing slide."""
import math
import pytest
from sandgrid.local_search import annealing_temperature, optimize_paths


class SolvedGrid:
    """Minimal legal model whose initial state is already a goal."""
    def __init__(self):
        self.actions = [object()]

    @staticmethod
    def is_goal(state):
        return state == 0

    @staticmethod
    def successors(state):
        return iter(())

    @staticmethod
    def trace(initial, actions):
        assert initial == 0 and not actions
        return [{'state': 0, 'total_cost': 0}]


def test_professor_temperature_schedule():
    assert annealing_temperature(0) == 10
    assert annealing_temperature(1) == pytest.approx(9)
    assert annealing_temperature(2) == pytest.approx(8.1)
    assert annealing_temperature(3, 5, .95) == pytest.approx(5 * .95**3)
    assert annealing_temperature(3, 10, .8) == pytest.approx(10 * .8**3)


def test_professor_stale_termination_returns_best_before_budget():
    result = optimize_paths(SolvedGrid(), 0, 'anneal',
                            max_evaluations=1000,
                            max_seconds=None,
                            anneal_max_stale=2,
                            random_seed=42)
    # Initial path plus 3 non-improving neighbors: stale 1,2,3 then stop.
    assert result.evaluations == 4
    assert result.evaluation.found_goal
    assert result.evaluation.path_cost == 0
    assert result.evaluation.score == 1_000_000


def test_invalid_annealing_config():
    with pytest.raises(ValueError):
        annealing_temperature(0, 10, 1.0)
    with pytest.raises(ValueError):
        optimize_paths(SolvedGrid(), 0, 'anneal', anneal_max_stale=-1)
