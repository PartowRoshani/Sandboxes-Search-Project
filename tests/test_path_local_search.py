"""Run from the root of Sandboxes-Search-Project (after installing add-on)."""
from random import Random

import pytest

from sandgrid.model import SandGrid
from sandgrid.search import search, greedy
from sandgrid.local_search import (PathScorer, path_score, random_path,
                                  mutate_path, crossover_paths, optimize_paths)

PROFESSOR = [[1, 0], [0, 1], [0, 1], [1, 0]]


def setup_professor():
    model = SandGrid(4, 2)
    return model, model.from_display(PROFESSOR)


def test_random_paths_have_required_length_and_action_ids():
    model, initial = setup_professor()
    rng = Random(2026)
    paths = [random_path(model, initial, rng) for _ in range(300)]
    assert {len(path) for path in paths} == set(range(30, 36))
    assert all(0 <= aid < len(model.actions) for path in paths for aid in path)


def test_evaluation_stops_at_first_goal_and_ignores_rest():
    model, initial = setup_professor()
    greedy_plan = greedy(model, initial)
    assert len(greedy_plan.actions) < 30
    prefix = greedy_plan.actions
    # The tail contains deliberately invalid action IDs. The scorer MUST stop
    # when it reaches the goal and never try the tail.
    path = prefix + [10**9] * (32 - len(prefix))
    result = PathScorer(model, initial).path_score(path)
    assert result.found_goal
    assert result.goal_index == len(prefix) - 1
    assert result.path_cost == greedy_plan.cost
    assert list(result.executed_actions) == prefix
    assert result.score == pytest.approx(1_000_000 / (1 + greedy_plan.cost))


def test_goal_has_positive_fitness_and_cheaper_goal_is_better():
    model, initial = setup_professor()
    greedy_plan = greedy(model, initial)
    optimum = search(model, initial, algorithm='ucs')
    scorer = PathScorer(model, initial)
    a = scorer.path_score(greedy_plan.actions)
    b = scorer.path_score(optimum.actions)
    assert a.found_goal and b.found_goal
    assert b.path_cost == 34 and a.path_cost == 47
    assert 0 < a.score < b.score
    assert path_score(optimum.actions, model, initial) == b


def test_incomplete_paths_have_differentiated_negative_scores():
    model, initial = setup_professor()
    scorer = PathScorer(model, initial)
    empty = scorer.path_score([])
    one_down = scorer.path_score([model.down_ids[6]])
    invalid = scorer.path_score([model.actions[-1].id] * 5)
    assert not empty.found_goal
    assert empty.score < 0 and one_down.score < 0
    assert one_down.remaining_units < empty.remaining_units
    assert one_down.score > empty.score
    assert invalid.score < 0


def test_mutation_and_crossover_keep_length_bounds():
    model, initial = setup_professor()
    rng = Random(1)
    scorer = PathScorer(model, initial)
    a = random_path(model, initial, rng)
    b = random_path(model, initial, rng)
    for _ in range(120):
        a = mutate_path(a, scorer, rng)
        child = crossover_paths(a, b, rng)
        assert 30 <= len(a) <= 35
        assert 30 <= len(child) <= 35
        assert all(0 <= aid < len(model.actions) for aid in child)


@pytest.mark.parametrize('algorithm', ['hillclimb', 'anneal', 'genetic'])
def test_all_three_algorithms_use_path_score_and_return_valid_results(algorithm):
    model, initial = setup_professor()
    outcome = optimize_paths(model, initial, algorithm,
                             max_evaluations=1200, max_seconds=None,
                             random_seed=42)
    assert outcome.evaluations == 1200
    assert 30 <= len(outcome.best_path) <= 35
    assert outcome.evaluation.found_goal, algorithm
    trace = model.trace(initial, list(outcome.evaluation.executed_actions))
    assert trace[-1]['state'] == 0
    assert trace[-1]['total_cost'] == outcome.evaluation.path_cost
    assert outcome.evaluation.score == pytest.approx(
        1_000_000 / (1 + outcome.evaluation.path_cost))
    wrapped = search(model, initial, algorithm,
                     max_expansions=1200, max_seconds=None, random_seed=42)
    assert wrapped.found and wrapped.status == 'found'
    assert wrapped.cost == outcome.evaluation.path_cost
    assert wrapped.actions == list(outcome.evaluation.executed_actions)
    assert wrapped.expanded == 1200


@pytest.mark.parametrize('algorithm', ['hillclimb', 'anneal', 'genetic'])
def test_seed_is_reproducible(algorithm):
    model, initial = setup_professor()
    args = dict(max_evaluations=180, max_seconds=None, random_seed=781)
    a = optimize_paths(model, initial, algorithm, **args)
    b = optimize_paths(model, initial, algorithm, **args)
    assert (a.best_path, a.evaluation, a.evaluations) == (
        b.best_path, b.evaluation, b.evaluations)


def test_no_goal_does_not_report_success_or_invent_repair():
    model = SandGrid(4, 1)
    initial = model.from_display([[1], [1], [1], [1]])
    outcome = optimize_paths(model, initial, 'genetic', max_evaluations=30,
                             max_seconds=None, min_length=1, max_length=1)
    assert not outcome.evaluation.found_goal
    assert outcome.evaluation.score < 0
    assert outcome.evaluation.remaining_units > 0


def test_already_solved_initial_state():
    model = SandGrid(2, 2)
    outcome = optimize_paths(model, 0, 'anneal', max_evaluations=20,
                             max_seconds=None)
    assert outcome.evaluation.found_goal
    assert outcome.evaluation.path_cost == 0
    assert outcome.evaluation.executed_actions == ()
    assert outcome.evaluation.score == 1_000_000


def test_stop_on_first_goal_option():
    model, initial = setup_professor()
    answer = optimize_paths(model, initial, 'genetic', max_evaluations=500,
                            max_seconds=None, guided_probability=1,
                            stop_on_first_goal=True, random_seed=42)
    assert answer.evaluation.found_goal
    assert answer.evaluations < 500
