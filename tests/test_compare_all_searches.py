"""Tests for the unified local/graph comparison script."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

from sandgrid.model import SandGrid
from sandgrid.search import greedy

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'compare_all_searches.py'
spec = importlib.util.spec_from_file_location('compare_all_searches', SCRIPT)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def params(**overrides):
    defaults = dict(example='professor', grid=None, rows=4, cols=2, seed=42,
                    random_seed=42, trials=2, seconds=8.0,
                    expansions=100000, max_depth=20,
                    local_evaluations=150, local_seconds=10.0)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_professor_initial_grid_and_exact_state_code():
    model, initial, label = comparison.make_initial(params())
    assert (model.rows, model.cols, initial, label) == (4, 2, 2000, 'professor')
    assert comparison.state_grid(model, initial) == [[1,0],[0,1],[0,1],[1,0]]


def test_random_state_same_seed_and_custom_grid():
    a = comparison.make_initial(params(example='random',rows=3,cols=2,seed=7))
    b = comparison.make_initial(params(example='random',rows=3,cols=2,seed=7))
    assert a[1] == b[1]
    model, initial, label = comparison.make_initial(params(grid='[[1,0.5],[0,1]]'))
    assert label == 'custom'
    assert comparison.state_grid(model,initial) == [[1,.5],[0,1]]


def test_graph_result_is_verified():
    model, initial, _ = comparison.make_initial(params())
    result = comparison.run_one(model, initial, 'greedy', 42, params())
    assert result['found'] and result['status'] == 'found'
    assert result['cost'] == greedy(model, initial).cost == 47
    assert result['effort_type'] == 'expanded_nodes'
    assert model.trace(initial, result['actions'])[-1]['state'] == 0


def test_local_result_and_chromosome_metadata():
    model, initial, _ = comparison.make_initial(params())
    result = comparison.run_one(model, initial, 'hillclimb', 42, params(local_evaluations=180))
    assert result['effort_type'] == 'path_evaluations'
    assert 30 <= result['details']['chromosome_length'] <= 35
    assert result['details']['valid_actions'] == len(result['actions'])
    trace = model.trace(initial, result['actions'])
    assert result['found'] == model.is_goal(trace[-1]['state'])
    assert result['details']['attempted_path_cost'] == trace[-1]['total_cost']
    assert result['cost'] is None or result['cost'] == trace[-1]['total_cost']


def test_cost_chart_and_dashboard_mark_unsolved(tmp_path):
    summary = [dict(algorithm='greedy', runs=1, solved=1, best_cost=47,
                    median_success_cost=47, median_time_sec=.1, median_work_units=7,
                    work_unit='expanded_nodes', best_seed=42, animation_html=None,
                    animation_gif=None, success_rate_percent=100),
               dict(algorithm='ids', runs=1, solved=0, best_cost=None,
                    median_success_cost=None, median_time_sec=2.0, median_work_units=90,
                    work_unit='expanded_nodes', best_seed=42, animation_html=None,
                    animation_gif=None, success_rate_percent=0)]
    comparison.render_charts(summary, tmp_path)
    info = dict(label='professor', rows=4, cols=2, initial_code=2000,
                initial_grid=[[1,0],[0,1],[0,1],[1,0]])
    comparison.render_dashboard(tmp_path, info, summary, [])
    assert (tmp_path / 'cost_comparison.png').is_file()
    assert (tmp_path / 'success_rate.png').is_file()
    assert (tmp_path / 'time_comparison.png').is_file()
    dashboard = (tmp_path / 'dashboard.html').read_text()
    assert '<strong>ids</strong>' in dashboard
    assert '0/1' in dashboard
    assert '—' in dashboard
