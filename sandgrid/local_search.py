"""Path-based Local Search for the existing SandGrid model.

Every candidate is a random sequence of 30--35 action IDs. The authoritative
SandGrid.step() function applies each attempted action in order. Evaluation
ends at the FIRST goal, ignoring the remaining tail. Invalid attempted gate
openings are skipped (and penalized only if the path ultimately fails).

Both single-trajectory optimizers and Genetic Algorithm maximize the same
path_score() function. No greedy completion / automatic repair is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import exp
from random import Random
from time import perf_counter
from typing import TYPE_CHECKING, Sequence
import tracemalloc

if TYPE_CHECKING:
    from .model import SandGrid
    from .search import SearchResult

MIN_PATH_LENGTH = 30
MAX_PATH_LENGTH = 35
GOAL_BONUS = 1_000_000.0
REMAINING_UNIT_PENALTY = 1_000.0
INVALID_ACTION_PENALTY = 2.0

# Professor's handwritten Simulated Annealing schedule:
# initial T = 10, then T <- 0.9 * T after each evaluated neighbor.
# The slide also mentions 0.8 and 0.95 as possible cooling factors.
DEFAULT_ANNEAL_T0 = 10.0
DEFAULT_ANNEAL_ALPHA = 0.90
DEFAULT_ANNEAL_MAX_STALE = 450


def annealing_temperature(step: int, initial_temperature: float = DEFAULT_ANNEAL_T0,
                          cooling_rate: float = DEFAULT_ANNEAL_ALPHA) -> float:
    """T(t) = T0 * cooling_rate**t, exactly as annotated on the slide."""
    if step < 0 or initial_temperature <= 0 or not 0 < cooling_rate < 1:
        raise ValueError('invalid annealing schedule parameters')
    return initial_temperature * (cooling_rate ** step)


@dataclass(frozen=True)
class PathEvaluation:
    score: float
    found_goal: bool
    path_cost: int
    executed_actions: tuple[int, ...]
    final_state: int
    goal_index: int | None  # Zero-based index in the original chromosome.
    invalid_attempts: int
    remaining_units: int  # Number of half-units of sand left.


class PathScorer:
    """Bind the SandGrid and initial state so the public method is path_score(path)."""

    def __init__(self, model: SandGrid, initial: int):
        self.model = model
        self.initial = initial

    def path_score(self, path: Sequence[int]) -> PathEvaluation:
        """Replay a chromosome, stopping immediately at goal (at any index).

        Goal: score = GOAL_BONUS / (1 + actual_cost), always positive.
        No goal: negative score; less remaining sand is strictly preferred to
        lower cost or fewer invalid actions in the 30--35-action search range.

        Illegal attempted openings are ignored, not charged as successful moves.
        This is essential because uniform random chromosomes usually contain
        invalid gate openings. Only executed legal actions count toward cost.
        """
        model = self.model
        state = self.initial
        cost = 0
        executed: list[int] = []
        invalid_count = 0
        goal_index: int | None = None

        # An already solved initial state should not execute any actions.
        if not model.is_goal(state):
            for index, action_id in enumerate(path):
                if not isinstance(action_id, int) or not 0 <= action_id < len(model.actions):
                    raise ValueError(f'invalid action ID at path[{index}]: {action_id!r}')
                transition = model.step(state, action_id)
                if transition is None:
                    invalid_count += 1
                    continue
                state, step_cost = transition
                cost += step_cost
                executed.append(action_id)
                if model.is_goal(state):
                    goal_index = index
                    break

        goal = model.is_goal(state)
        remaining = 0 if goal else sum(model.decode(state)[0])
        if goal:
            score = GOAL_BONUS / (1.0 + cost)
        else:
            # Negative values supply a useful gradient toward the goal;
            # remaining sand dominates cost and invalid-action penalties.
            score = -(REMAINING_UNIT_PENALTY * remaining + cost
                      + INVALID_ACTION_PENALTY * invalid_count)
        return PathEvaluation(score, goal, cost, tuple(executed), state,
                              goal_index, invalid_count, remaining)


def path_score(path: Sequence[int], model: SandGrid, initial: int) -> PathEvaluation:
    """One-shot helper; use PathScorer(model, initial).path_score(path) in loops."""
    return PathScorer(model, initial).path_score(path)


def random_path(model: SandGrid, initial: int, rng: Random,
                min_length: int = MIN_PATH_LENGTH,
                max_length: int = MAX_PATH_LENGTH,
                guided_probability: float = 0.65) -> list[int]:
    """Sample a 30--35-gene chromosome; sometimes choose legal random actions.

    Guided actions are still chosen randomly. Unrestricted action choices
    preserve exploration, while legal choices make success more probable.
    Filling after the goal is deliberate: the scorer ignores that tail.
    """
    if not (1 <= min_length <= max_length):
        raise ValueError('length range must satisfy 1 <= min_length <= max_length')
    if not 0 <= guided_probability <= 1:
        raise ValueError('guided_probability must be in [0, 1]')
    if not model.actions:
        raise ValueError('model has no actions')
    length = rng.randint(min_length, max_length)
    state = initial
    result: list[int] = []
    for _ in range(length):
        legal = []
        if not model.is_goal(state) and rng.random() < guided_probability:
            legal = [aid for _nxt, aid, _cost in model.successors(state)]
        action_id = rng.choice(legal) if legal else rng.randrange(len(model.actions))
        result.append(action_id)
        if not model.is_goal(state):
            next_state = model.step(state, action_id)
            if next_state is not None:
                state = next_state[0]
    return result


def _prefix_state(scorer: PathScorer, path: Sequence[int], index: int) -> int:
    state = scorer.initial
    for action_id in path[:index]:
        if scorer.model.is_goal(state):
            break
        transition = scorer.model.step(state, action_id)
        if transition is not None:
            state = transition[0]
    return state


def mutate_path(path: Sequence[int], scorer: PathScorer, rng: Random,
                min_length: int = MIN_PATH_LENGTH,
                max_length: int = MAX_PATH_LENGTH,
                goal_index: int | None = None) -> list[int]:
    """Replace, swap, relocate, shift, insert or delete while respecting length."""
    proposal = list(path)
    n = len(proposal)
    if not (min_length <= n <= max_length):
        raise ValueError('path length is outside configured bounds')

    active = n if goal_index is None else min(n, goal_index + 1)
    operation = rng.randrange(6)
    if operation == 0 or (n == 1):  # Replace with a random, often legal, gene.
        i = rng.randrange(active)
        state = _prefix_state(scorer, proposal, i)
        possible = [aid for _nxt, aid, _cost in scorer.model.successors(state)]
        proposal[i] = (rng.choice(possible) if possible and rng.random() < .75
                       else rng.randrange(len(scorer.model.actions)))
    elif operation == 1:  # Swap two genes; one preferably in the active prefix.
        i, j = rng.randrange(active), rng.randrange(n)
        proposal[i], proposal[j] = proposal[j], proposal[i]
    elif operation == 2:  # Relocate a gene.
        i = rng.randrange(active)
        gene = proposal.pop(i)
        proposal.insert(rng.randrange(n), gene)
    elif operation == 3:  # Replace a short contiguous active block.
        start = rng.randrange(active)
        for index in range(start, min(n, start + rng.randint(2, 4))):
            proposal[index] = rng.randrange(len(scorer.model.actions))
    elif operation == 4 and n < max_length:  # Insert at a random position.
        i = rng.randrange(active + 1)
        state = _prefix_state(scorer, proposal, i)
        possible = [aid for _nxt, aid, _cost in scorer.model.successors(state)]
        gene = (rng.choice(possible) if possible and rng.random() < .7
                else rng.randrange(len(scorer.model.actions)))
        proposal.insert(i, gene)
    elif operation == 5 and n > min_length:  # Delete one gene.
        del proposal[rng.randrange(active)]
    else:  # Bounds prevent insertion/deletion, perform a replacement.
        proposal[rng.randrange(active)] = rng.randrange(len(scorer.model.actions))

    assert min_length <= len(proposal) <= max_length
    return proposal


def crossover_paths(parent_a: Sequence[int], parent_b: Sequence[int],
                    rng: Random, min_length: int = MIN_PATH_LENGTH,
                    max_length: int = MAX_PATH_LENGTH) -> list[int]:
    """One-point crossover with a valid chromosome length."""
    cut_a = rng.randrange(len(parent_a) + 1)
    cut_b = rng.randrange(len(parent_b) + 1)
    child = list(parent_a[:cut_a]) + list(parent_b[cut_b:])
    target = rng.randint(min_length, max_length)
    if len(child) > target:
        child = child[:target]
    while len(child) < target:
        # Parents already hold only valid action IDs.
        source = parent_a if rng.random() < .5 else parent_b
        child.append(rng.choice(source))
    return child


@dataclass(frozen=True)
class OptimizationResult:
    algorithm: str
    best_path: tuple[int, ...]
    evaluation: PathEvaluation
    evaluations: int
    elapsed_sec: float
    max_population: int
    peak_memory_bytes: int | None = None


def optimize_paths(model: SandGrid, initial: int, algorithm: str = 'anneal',
                   *, max_evaluations: int = 2500, max_seconds: float | None = 10.0,
                   random_seed: int = 42,
                   min_length: int = MIN_PATH_LENGTH,
                   max_length: int = MAX_PATH_LENGTH,
                   population_size: int = 60,
                   guided_probability: float = .65,
                   stop_on_first_goal: bool = False,
                   measure_memory: bool = False,
                   anneal_initial_temperature: float = DEFAULT_ANNEAL_T0,
                   anneal_cooling_rate: float = DEFAULT_ANNEAL_ALPHA,
                   anneal_max_stale: int = DEFAULT_ANNEAL_MAX_STALE) -> OptimizationResult:
    """Maximize path_score using Hill Climbing, Annealing, or Genetic Algorithm.

    All candidates are random sequences of length min_length..max_length.
    Return the best evaluated path, even when no candidate reaches the goal.
    """
    name = {'hill_climbing': 'hillclimb', 'hill-climbing': 'hillclimb',
            'simulated_annealing': 'anneal', 'ga': 'genetic'}.get(algorithm, algorithm)
    if name not in ('hillclimb', 'anneal', 'genetic'):
        raise ValueError('algorithm must be hillclimb, anneal, or genetic')
    if max_evaluations < 1:
        raise ValueError('max_evaluations must be positive')
    if max_seconds is not None and max_seconds <= 0:
        raise ValueError('max_seconds must be positive or None')
    if not (1 <= min_length <= max_length):
        raise ValueError('invalid path length range')
    if population_size < 2:
        raise ValueError('population_size must be at least 2')
    if not 0 <= guided_probability <= 1:
        raise ValueError('guided_probability must be in [0, 1]')
    if anneal_initial_temperature <= 0:
        raise ValueError('anneal_initial_temperature must be positive')
    if not 0 < anneal_cooling_rate < 1:
        raise ValueError('anneal_cooling_rate must be strictly between 0 and 1')
    if anneal_max_stale < 0:
        raise ValueError('anneal_max_stale must be nonnegative')

    rng = Random(random_seed)
    scorer = PathScorer(model, initial)
    started = perf_counter()
    evaluations = 0
    max_population = 1
    best: tuple[tuple[int, ...], PathEvaluation] | None = None
    if measure_memory:
        tracemalloc.start()

    def allowed() -> bool:
        return (evaluations < max_evaluations and
                (max_seconds is None or perf_counter() - started < max_seconds))

    def evaluate(candidate: Sequence[int]) -> tuple[tuple[int, ...], PathEvaluation]:
        nonlocal evaluations, best
        result = (tuple(candidate), scorer.path_score(candidate))
        evaluations += 1
        if best is None or result[1].score > best[1].score:
            best = result
        return result

    def random_candidate() -> list[int]:
        return random_path(model, initial, rng, min_length, max_length,
                           guided_probability)

    try:
        if name in ('hillclimb', 'anneal'):
            current = evaluate(random_candidate())
            stagnation = 0  # Hill Climbing's unchanged restart counter.
            stale = 0       # Professor's Simulated Annealing counter.
            cooling_step = 0
            while allowed():
                if stop_on_first_goal and best is not None and best[1].found_goal:
                    break

                # Slide: T <- schedule(t), with T0=10 and alpha=0.9.
                # A mathematically zero/underflowed temperature ends annealing.
                if name == 'anneal':
                    temperature = annealing_temperature(
                        cooling_step, anneal_initial_temperature, anneal_cooling_rate)
                    if temperature <= 0.0:
                        break

                candidate = mutate_path(current[0], scorer, rng, min_length,
                                        max_length, current[1].goal_index)
                previous_best_score = best[1].score
                proposal = evaluate(candidate)
                delta = proposal[1].score - current[1].score
                if name == 'hillclimb':
                    accept = delta > 0
                else:
                    # Slide: better next -> accept, stale=0.
                    # Otherwise stale++ and accept with probability exp(delta/T).
                    if delta > 0:
                        accept = True
                        stale = 0
                    else:
                        stale += 1
                        accept = rng.random() < exp(delta / temperature)
                if accept:
                    current = proposal

                if name == 'anneal':
                    # Slide: T <- 0.9*T (equivalent to T0*pow(0.9,t)).
                    cooling_step += 1
                    # Slide's EXTRA handwritten termination:
                    # if stale > max_stale: return best.
                    # Break returns the GLOBAL best stored by evaluate(), not
                    # necessarily the most recently accepted current path.
                    if stale > anneal_max_stale:
                        break
                else:
                    stagnation = (0 if best[1].score > previous_best_score
                                  else stagnation + 1)
                    if stagnation >= 220 and allowed():
                        # Hill Climbing restart, unchanged by the SA slide.
                        if rng.random() < .5:
                            restart = random_candidate()
                        else:
                            restart = list(best[0])
                            for _ in range(rng.randint(2, 6)):
                                restart = mutate_path(restart, scorer, rng,
                                                      min_length, max_length)
                        current = evaluate(restart)
                        stagnation = 0
        else:
            population: list[tuple[tuple[int, ...], PathEvaluation]] = []
            while len(population) < population_size and (allowed() or not population):
                population.append(evaluate(random_candidate()))
                if stop_on_first_goal and best[1].found_goal:
                    break
            max_population = len(population)

            def tournament() -> tuple[tuple[int, ...], PathEvaluation]:
                sample = rng.choices(population, k=min(3, len(population)))
                return max(sample, key=lambda item: item[1].score)

            while allowed() and not (stop_on_first_goal and best[1].found_goal):
                population.sort(key=lambda item: item[1].score, reverse=True)
                elite_count = min(len(population), max(1, len(population) // 10))
                next_generation = population[:elite_count]
                while len(next_generation) < population_size and allowed():
                    parent_a, parent_b = tournament(), tournament()
                    child = crossover_paths(parent_a[0], parent_b[0], rng,
                                            min_length, max_length)
                    if rng.random() < .9:
                        child = mutate_path(child, scorer, rng, min_length,
                                            max_length)
                    next_generation.append(evaluate(child))
                    if stop_on_first_goal and best[1].found_goal:
                        break
                population = next_generation
                max_population = max(max_population, len(population))

        assert best is not None
        path, evaluation = best
        # Validate the *executed* prefix with the original model, not a
        # reimplementation of the sand physics or weighted costs.
        trace = model.trace(initial, list(evaluation.executed_actions))
        if (trace[-1]['state'] != evaluation.final_state or
                trace[-1]['total_cost'] != evaluation.path_cost or
                model.is_goal(trace[-1]['state']) != evaluation.found_goal):
            raise AssertionError('path scorer and SandGrid.trace disagree')
        return OptimizationResult(name, path, evaluation, evaluations,
                                  perf_counter() - started, max_population,
                                  (tracemalloc.get_traced_memory()[1]
                                   if measure_memory else None))
    finally:
        if measure_memory:
            tracemalloc.stop()


def local_search(model: SandGrid, initial: int, algorithm: str = 'anneal',
                 *, max_expansions: int | None = 2500,
                 max_seconds: float | None = 10.0,
                 random_seed: int = 42,
                 measure_memory: bool = False) -> SearchResult:
    """Compatibility wrapper for sandgrid.search.search(...).

    The SearchResult actions contain executed, legal actions only. If none of
    the 30--35-gene paths reaches the goal, report 'not_found', never fake a
    completed solution. `expanded` is the number of evaluated chromosomes.
    """
    from .search import SearchResult

    outcome = optimize_paths(
        model, initial, algorithm,
        max_evaluations=2500 if max_expansions is None else max_expansions,
        max_seconds=max_seconds, random_seed=random_seed,
        measure_memory=measure_memory)
    result = outcome.evaluation
    return SearchResult(outcome.algorithm, result.found_goal,
                        'found' if result.found_goal else 'not_found',
                        result.path_cost if result.found_goal else None,
                        list(result.executed_actions) if result.found_goal else [],
                        outcome.evaluations, outcome.evaluations,
                        outcome.max_population, outcome.elapsed_sec,
                        outcome.peak_memory_bytes)
