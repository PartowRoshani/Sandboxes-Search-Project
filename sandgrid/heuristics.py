"""Heuristics for the continuous-flow sand-grid model.

'basic' and 'relax' are safe lower bounds under MODEL_VERSION
continuous-flow-v2-full-is-1. The count heuristic is intentionally
*not* admissible, and is included only for a classroom comparison.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import Callable

from .model import SandGrid


def basic(model: SandGrid, state: int) -> int:
    """Minimal unavoidable exit expense."""
    if model.is_goal(state):
        return 0
    occ, _ = model.decode(state)
    return 3 if sum(occ) == 1 else 5


def relaxation(model: SandGrid, state: int) -> int:
    """Row-boundary relaxation with existing open vertical gates.

    Boundary r contributes 0 if no sand is above it or some vertical gate
    on that boundary is open. Otherwise at least 3 cost is necessary for
    a half-unit above, or 5 for one or more full units above.

    This is a lower bound on the whole remaining cost, not a simulated
    strategy. Always include the unavoidable bottom-exit lower bound.
    """
    if model.is_goal(state):
        return 0
    occ, mask = model.decode(state)
    total = sum(occ)
    estimate = 3 if total == 1 else 5
    sand_above = 0
    boundary_bits = (1 << model.cols) - 1
    for row in range(model.rows - 1):
        offset = row * model.cols
        sand_above += sum(occ[offset:offset + model.cols])
        already_open = bool(mask & (boundary_bits << offset))
        if sand_above and not already_open:
            estimate += 3 if sand_above == 1 else 5
    return estimate


def count_unsafe(model: SandGrid, state: int) -> int:
    """Classroom 5*full+3*half formula (not admissible in general)."""
    occ, _ = model.decode(state)
    return 5 * occ.count(2) + 3 * occ.count(1)


def ml_features(model: SandGrid, state: int) -> list[float]:
    """Fixed-size feature vector for one grid shape and model version."""
    occ, mask = model.decode(state)
    bits = [float(bool(mask & (1 << i))) for i in range(model.gate_count)]
    row_sums = [float(sum(occ[r*model.cols:(r+1)*model.cols]))
                for r in range(model.rows)]
    return [*map(float, occ), *bits, *row_sums, float(sum(occ))]


@lru_cache(maxsize=8)
def _read_own_joblib(path: str):
    import joblib
    return joblib.load(path)


class LearnedHeuristic:
    """Predict remaining cost with batched, per-search memoized inference.

    Only load joblib artifacts produced by this project's training script:
    joblib/pickle is not safe for untrusted files.
    """
    def __init__(self, model: SandGrid, path: str | Path):
        saved = _read_own_joblib(str(Path(path).resolve()))
        expected = (model.rows, model.cols, model.MODEL_VERSION)
        actual = (saved['rows'], saved['cols'], saved['model_version'])
        if actual != expected:
            raise ValueError(f'ML model is for {actual}; current grid is {expected}. '
                             'Train a separate ML model for this grid shape.')
        self.model = model
        self.regressor = saved['regressor']
        self.regressor.n_jobs = 1
        self.prediction_cache: dict[int, float] = {}

    def predict_many(self, states) -> list[float]:
        """Batch unseen states, retaining their order; do not time training/loading.

        The cache belongs to one search. The same state is evaluated only once
        in a search, and the model never gets access to exact test labels.
        """
        import numpy as np
        requested = [int(s) for s in states]
        missing = list(dict.fromkeys(
            s for s in requested
            if s not in self.prediction_cache and not self.model.is_goal(s)
        ))
        if missing:
            matrix = np.asarray([ml_features(self.model, s) for s in missing],
                                dtype=np.float32)
            estimated = self.regressor.predict(matrix)
            for s, value in zip(missing, estimated):
                self.prediction_cache[s] = max(0.0, float(value))
        return [0.0 if self.model.is_goal(s)
                else self.prediction_cache[s] for s in requested]

    def __call__(self, state: int) -> float:
        return self.predict_many([state])[0]


def choose(model: SandGrid, name: str = 'basic',
           ml_model_path: str | Path | None = None) -> Callable[[int], float]:
    if name == 'basic':
        return lambda state: basic(model, state)
    if name == 'relax':
        return lambda state: relaxation(model, state)
    if name in ('ml', 'ml-tie'):
        if ml_model_path is None:
            raise ValueError('--ml-model is required for ML heuristics')
        return LearnedHeuristic(model, ml_model_path)
    raise ValueError('Heuristic must be basic, relax, ml, or ml-tie')
