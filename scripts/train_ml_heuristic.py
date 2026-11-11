#!/usr/bin/env python3
"""Train a shape-specific ML heuristic on exact reverse-Dijkstra labels.

Run from the project root:
    python scripts/train_ml_heuristic.py --rows 3 --cols 2 --output results/ml_3x2

Test groups are separated by occupancy pattern, including all gate masks for
that pattern. This avoids same-occupancy leakage between train and test.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit

from sandgrid.batch import compute_all_optimal
from sandgrid.heuristics import ml_features
from sandgrid.model import SandGrid


def main() -> None:
    p = argparse.ArgumentParser(description='ML remaining-cost estimator for sand-grid')
    p.add_argument('--rows', type=int, default=3)
    p.add_argument('--cols', type=int, default=2)
    p.add_argument('--output', type=Path, default=Path('results/ml_3x2'))
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--trees', type=int, default=30)
    p.add_argument('--max-states', type=int, default=250_000)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    m = SandGrid(a.rows, a.cols)
    batch = compute_all_optimal(m, progress=True, max_states=a.max_states)
    states = np.asarray(batch['states'], dtype=np.int64)
    X = np.asarray([ml_features(m, int(s)) for s in states], dtype=np.float32)
    y = np.asarray(batch['distances'], dtype=np.float64)
    groups = states % m.base  # one base-3 occupancy code per group
    tr, te = next(GroupShuffleSplit(n_splits=1, test_size=0.2,
                                     random_state=a.seed).split(X, y, groups))
    regressor = RandomForestRegressor(n_estimators=a.trees, random_state=a.seed,
                                      max_depth=18, n_jobs=-1, min_samples_leaf=1)
    regressor.fit(X[tr], y[tr])
    # Avoid parallel-job overhead when A* requests one prediction at a time.
    regressor.n_jobs = 1
    prediction = np.maximum(0.0, regressor.predict(X[te]))
    error = prediction - y[te]
    metrics = {
        'model_version': m.MODEL_VERSION,
        'rows': m.rows, 'cols': m.cols, 'seed': a.seed,
        'all_stable_states': len(states),
        'train_states': len(tr), 'test_states': len(te),
        'train_occupancy_groups': len(np.unique(groups[tr])),
        'test_occupancy_groups': len(np.unique(groups[te])),
        'mae': round(float(mean_absolute_error(y[te], prediction)), 6),
        'rmse': round(float(np.sqrt(mean_squared_error(y[te], prediction))), 6),
        'r2': round(float(r2_score(y[te], prediction)), 6),
        'overestimate_fraction': round(float(np.mean(error > 1e-8)), 6),
        'max_overestimate': round(float(max(0, np.max(error))), 6),
        'note': ('Direct use in A* is NOT guaranteed admissible. '
                 'ml-tie uses admissible relaxation as the primary A* key.'),
    }
    model_file = a.output / 'heuristic_ml.joblib'
    joblib.dump({
        'model_version': m.MODEL_VERSION, 'rows': m.rows, 'cols': m.cols,
        'regressor': regressor,
    }, model_file)
    with (a.output / 'test_predictions.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['state', 'occupancy_code', 'optimal_cost', 'ml_prediction',
                         'signed_error', 'overestimate'])
        for idx, pred in zip(te, prediction):
            err = float(pred - y[idx])
            writer.writerow([int(states[idx]), int(groups[idx]), int(y[idx]),
                             round(float(pred), 6), round(err, 6), int(err > 1e-8)])
    heldout_codes = sorted(int(code) for code in np.unique(groups[te]))
    train_codes = sorted(int(code) for code in np.unique(groups[tr]))
    assert not (set(heldout_codes) & set(train_codes))
    (a.output / 'dataset_split.json').write_text(json.dumps({
        'model_version': m.MODEL_VERSION,
        'rows': m.rows, 'cols': m.cols, 'seed': a.seed,
        'split_type': 'GroupShuffleSplit by occupancy code',
        'train_occupancy_codes': train_codes,
        'test_occupancy_codes': heldout_codes,
    }, indent=2), encoding='utf-8')
    (a.output / 'test_initial_codes.json').write_text(
        json.dumps({'rows': m.rows, 'cols': m.cols,
                    'model_version': m.MODEL_VERSION,
                    'heldout_closed_gate_initial_codes': heldout_codes}, indent=2),
        encoding='utf-8')
    (a.output / 'metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    print(json.dumps(metrics, indent=2))
    print('Model saved:', model_file)


if __name__ == '__main__':
    main()
