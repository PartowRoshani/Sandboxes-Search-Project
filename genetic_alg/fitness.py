"""Evaluate complete action histories from the SAME initial state.

Do not use a final SandGrid state alone as a chromosome: path cost and action
legality depend on the entire prefix. All transition rules come from sandgrid.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import log1p, sqrt
from typing import Sequence


@dataclass(frozen=True)
class Evaluation:
    fitness: float
    solved: bool
    valid: bool
    actions: tuple[int, ...]  # Executed prefix to goal, or the min-conflict state
    min_conflict: int
    cost_at_min_conflict: int
    path_cost: int  # Cost of executed prefix (including when invalid)
    executed_count: int
    invalid_at: int | None
    final_state: int


def conflict_number(model, state: int, mode: str = "occupied") -> int:
    """Nonnegative conflicts. Sand-grid decode returns occupancies 0,1,2."""
    occ, _ = model.decode(state)
    if mode == "occupied":
        return sum(v > 0 for v in occ)
    if mode == "half_units":
        return sum(occ)
    raise ValueError("conflict mode must be 'occupied' or 'half_units'")


def cost_penalty(cost: int, transform: str = "log") -> float:
    if cost < 0:
        raise ValueError("path costs must be nonnegative")
    if transform == "log":
        return log1p(cost)
    if transform == "linear":
        return float(cost)
    if transform == "sqrt":
        return sqrt(cost)
    if transform == "none":
        return 0.0
    raise ValueError("cost transform must be log, linear, sqrt, or none")


def evaluate_sequence(model, initial_state: int, sequence: Sequence[int], *,
                      conflict_mode: str = "occupied", cost_transform: str = "log",
                      goal_bonus: float = 100_000.0,
                      score_scale: float = 1000.0) -> Evaluation:
    """Fitness=0 for any illegal executed action.

    Every evaluation restarts at initial_state; if the goal is achieved at
    index t<n, the unused suffix is ignored. If no goal is reached, score the
    minimum conflict seen over the WHOLE prefix and the path cost to its first
    occurrence (which is also the cheapest occurrence for positive costs).

    Non-goal: score_scale / (1 + min_conflict + q(cost_at_min))
              where q(cost) = p(cost) / (1 + p(cost)) is in [0, 1).
    Goal:     goal_bonus + score_scale / (1 + p(total_goal_cost))

    Because 0 <= q(cost) < 1, a smaller integer min_conflict always
    outranks a larger min_conflict, regardless of nonnegative path cost.
    Within one conflict tier, a lower cost scores higher (except when the
    selected transform is 'none', which deliberately ignores cost).
    With score_scale < goal_bonus, every goal outranks every non-goal.
    """
    if goal_bonus <= score_scale or score_scale <= 0:
        raise ValueError("require goal_bonus > score_scale > 0")
    state = initial_state
    total_cost = 0
    best_conflict = conflict_number(model, state, conflict_mode)
    best_cost = 0
    best_prefix: tuple[int, ...] = ()
    performed: list[int] = []
    if model.is_goal(state):
        return Evaluation(goal_bonus + score_scale, True, True, (), 0, 0, 0, 0, None, state)

    for position, action_id in enumerate(sequence):
        # model.step returns None for illegal moves; unknown IDs are illegal too.
        try:
            transition = model.step(state, action_id)
        except (ValueError, TypeError, IndexError):
            transition = None
        if transition is None:
            return Evaluation(0.0, False, False, tuple(performed), best_conflict,
                              best_cost, total_cost, len(performed), position, state)
        state, step_cost = transition
        if step_cost < 0:
            raise ValueError("negative action costs are not supported")
        performed.append(action_id)
        total_cost += step_cost
        current_conflict = conflict_number(model, state, conflict_mode)
        if current_conflict < best_conflict or (current_conflict == best_conflict and total_cost < best_cost):
            best_conflict = current_conflict
            best_cost = total_cost
            best_prefix = tuple(performed)
        if model.is_goal(state):
            fitness = goal_bonus + score_scale / (1.0 + cost_penalty(total_cost, cost_transform))
            return Evaluation(fitness, True, True, tuple(performed), 0,
                              total_cost, total_cost, len(performed), None, state)

    penalty = cost_penalty(best_cost, cost_transform)
    bounded_penalty = penalty / (1.0 + penalty)
    fitness = score_scale / (1.0 + best_conflict + bounded_penalty)
    return Evaluation(fitness, False, True, best_prefix, best_conflict,
                      best_cost, total_cost, len(performed), None, state)


def goal_test(model, initial_state: int, sequence: Sequence[int]) -> bool:
    """Goal test on an ACTION SEQUENCE (rather than a state)."""
    return evaluate_sequence(model, initial_state, sequence).solved


def fitness_function(model, initial_state: int, sequence: Sequence[int], **kwargs) -> float:
    return evaluate_sequence(model, initial_state, sequence, **kwargs).fitness
