"""Regression tests for batched ML inference and optimality-safe tie breaking."""
from __future__ import annotations

import numpy as np
import pytest

from sandgrid.heuristics import LearnedHeuristic, ml_features
from sandgrid.model import SandGrid
from sandgrid.search import search


class SimpleRegressor:
    def __init__(self):
        self.calls = 0
        self.rows_seen = 0
        self.n_jobs = 1

    def predict(self, inputs):
        self.calls += 1
        self.rows_seen += len(inputs)
        return np.sum(np.asarray(inputs), axis=1) / 4


def test_predict_many_deduplicates_and_keeps_state_order():
    m = SandGrid(2, 1)
    learned = LearnedHeuristic.__new__(LearnedHeuristic)
    learned.model = m
    learned.regressor = SimpleRegressor()
    learned.prediction_cache = {}
    s1, s2 = m.encode([2, 0]), m.encode([0, 2])
    values = learned.predict_many([s1, s2, s1, 0, s2])
    assert values == [values[0], values[1], values[0], 0.0, values[1]]
    assert learned.regressor.calls == 1
    assert learned.regressor.rows_seen == 2
    assert learned(s1) == values[0]
    assert learned.regressor.calls == 1  # cached lookup


def test_ml_safe_tie_preserves_optimality_on_small_grid(tmp_path):
    from sklearn.tree import DecisionTreeRegressor
    import joblib

    m = SandGrid(2, 2)
    example_states = list(range(m.base))
    features = np.array([ml_features(m, s) for s in example_states])
    labels = np.array([s % 13 for s in example_states])
    estimator = DecisionTreeRegressor(random_state=7).fit(features, labels)
    model_file = tmp_path / 'toy.joblib'
    joblib.dump({'model_version': m.MODEL_VERSION,
                 'rows': m.rows, 'cols': m.cols,
                 'regressor': estimator}, model_file)
    for state in [0, 1, 4, 10, 36, 56, 80]:
        ucs = search(m, state, 'ucs', max_seconds=10)
        safe = search(m, state, 'astar', heuristic_name='ml-tie',
                      ml_model_path=str(model_file), max_seconds=10)
        assert ucs.found and safe.found
        assert safe.cost == ucs.cost
