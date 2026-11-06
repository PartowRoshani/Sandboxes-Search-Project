"""One reverse Dijkstra computes exact optimum for ALL 3**(rows*cols)
initial grids (closed gates) simultaneously, not 59049 separate UCS calls.

The state graph also includes legal persistent-gate states. This batch routine
is designed for at most 10 boxes, with 5x2 as its main 59,049-state example.
"""
from __future__ import annotations

from array import array
import csv
from heapq import heappop, heappush
from pathlib import Path
from time import perf_counter
import json
import math

import numpy as np

from .model import SandGrid
from .search import greedy


class BatchTooLarge(ValueError):
    pass


def compute_all_optimal(model: SandGrid, progress: bool = True) -> dict:
    if model.n > 10:
        raise BatchTooLarge('batch solver is restricted to at most 10 boxes')
    started = perf_counter()
    states = array('I')
    # Include every occupancy combined with EVERY valid subset of open gates.
    for code in range(model.base):
        work = code
        occ = []
        for _ in range(model.n):
            work, digit = divmod(work, 3)
            occ.append(digit)
        eligible = 0
        for i in range(model.vertical_edges):
            if occ[i] > 0 and occ[i + model.cols] == 2:
                eligible |= 1 << i
        submask = eligible
        while True:
            states.append(code + model.base * submask)
            if submask == 0:
                break
            submask = (submask - 1) & eligible
    state_index = {s: idx for idx, s in enumerate(states)}
    n = len(states)
    if progress:
        print(f'Enumerated {n:,} physically valid states, {model.base:,} initial states.', flush=True)
    source = array('I')
    target = array('I')
    weights = array('B')
    action_ids = array('B')
    for idx, state in enumerate(states):
        for nxt, action, cost in model.successors(state):
            source.append(idx)
            target.append(state_index[nxt])
            weights.append(cost)
            action_ids.append(action)
        if progress and (idx + 1) % 100000 == 0:
            print(f'  Built edges for {idx+1:,}/{n:,} states', flush=True)
    edges = len(target)
    if progress:
        print(f'Graph has {edges:,} directed weighted transitions.', flush=True)

    src_np = np.frombuffer(source, dtype=np.uint32)
    target_np = np.frombuffer(target, dtype=np.uint32)
    cost_np = np.frombuffer(weights, dtype=np.uint8)
    action_np = np.frombuffer(action_ids, dtype=np.uint8)
    # Reverse adjacency CSR sorted by forward target.
    permutation = np.argsort(target_np, kind='stable')
    counts = np.bincount(target_np, minlength=n)
    offsets = np.empty(n+1, dtype=np.int64)
    offsets[0] = 0
    np.cumsum(counts, out=offsets[1:])
    rev_sources = src_np[permutation]
    rev_costs = cost_np[permutation]
    rev_actions = action_np[permutation]
    del permutation, counts, source, target, weights, action_ids

    INF = np.iinfo(np.int32).max
    distance = np.full(n, INF, dtype=np.int32)
    policy_next = np.full(n, -1, dtype=np.int32)
    policy_action = np.full(n, -1, dtype=np.int16)
    action_count = np.zeros(n, dtype=np.int16)
    side_count = np.zeros(n, dtype=np.int16)
    goal_index = state_index[0]
    distance[goal_index] = 0
    heap = [(0, goal_index)]
    settled = 0
    while heap:
        d, node = heappop(heap)
        if d != int(distance[node]):
            continue
        settled += 1
        if node != goal_index:
            nxt = int(policy_next[node])
            action_count[node] = action_count[nxt] + 1
            side_count[node] = side_count[nxt] + (
                model.actions[int(policy_action[node])].kind == 'side')
        start, end = int(offsets[node]), int(offsets[node+1])
        for j in range(start, end):
            pred = int(rev_sources[j])
            nd = d + int(rev_costs[j])
            if nd < int(distance[pred]):
                distance[pred] = nd
                policy_next[pred] = node
                policy_action[pred] = int(rev_actions[j])
                heappush(heap, (nd, pred))
        if progress and settled % 100000 == 0:
            print(f'  Reverse Dijkstra settled {settled:,}/{n:,} states', flush=True)
    if settled != n:
        raise AssertionError(f'{n-settled} states cannot reach the empty goal')
    if progress:
        print(f'All optima done after {perf_counter()-started:.2f}s.', flush=True)
    return dict(model=model, states=states, state_index=state_index,
                distances=distance, action_count=action_count,
                side_count=side_count, policy_action=policy_action,
                policy_next=policy_next, valid_states=n, graph_edges=edges,
                elapsed_sec=perf_counter()-started)


def reconstruct_optimal(batch: dict, initial: int) -> list[int]:
    model: SandGrid = batch['model']
    if initial not in batch['state_index']:
        raise ValueError('initial state not in graph')
    idx = batch['state_index'][initial]
    out = []
    while batch['states'][idx] != 0:
        action = int(batch['policy_action'][idx])
        if action < 0:
            raise AssertionError('missing shortest path')
        out.append(action)
        idx = int(batch['policy_next'][idx])
    assert model.trace(initial, out)[-1]['state'] == 0
    return out


def write_full_analysis(batch: dict, destination: str | Path,
                        make_plots: bool = True, progress: bool = True) -> dict:
    import sys
    try:
        import resource
    except ImportError:  # Windows has no resource module
        resource = None
    output = Path(destination)
    output.mkdir(parents=True, exist_ok=True)
    m: SandGrid = batch['model']
    optimum = np.empty(m.base, dtype=np.int32)
    greedy_cost = np.empty(m.base, dtype=np.int32)
    actions = np.empty(m.base, dtype=np.int16)
    sides = np.empty(m.base, dtype=np.int16)
    greedy_actions = np.empty(m.base, dtype=np.int16)
    for initial in range(m.base):
        idx = batch['state_index'][initial]  # all initial masks zero
        optimum[initial] = batch['distances'][idx]
        actions[initial] = batch['action_count'][idx]
        sides[initial] = batch['side_count'][idx]
        answer = greedy(m, initial)
        greedy_cost[initial] = answer.cost
        greedy_actions[initial] = answer.action_count
        if progress and (initial+1) % 15000 == 0:
            print(f'  Baseline computed for {initial+1:,}/{m.base:,} grids', flush=True)
    assert np.all(greedy_cost >= optimum), 'greedy unexpectedly below optimum!'
    positive = optimum > 0
    ratios = np.divide(greedy_cost[positive], optimum[positive])
    goal_idx = batch['state_index'][0]
    with (output/'all_states.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['base3_initial_code','greedy_cost','optimal_cost',
                         'greedy_opt_ratio','optimal_action_count','optimal_side_count',
                         'greedy_action_count','optimal_action_ids'])
        for i in range(m.base):
            node_idx = batch['state_index'][i]
            policy_path: list[str] = []
            while node_idx != goal_idx:
                policy_path.append(str(int(batch['policy_action'][node_idx])))
                node_idx = int(batch['policy_next'][node_idx])
            writer.writerow([i, int(greedy_cost[i]), int(optimum[i]),
                             f'{greedy_cost[i]/optimum[i]:.6f}' if optimum[i] else '',
                             int(actions[i]), int(sides[i]), int(greedy_actions[i]),
                             ';'.join(policy_path)])
    ratio_hist, ratio_edges = np.histogram(ratios, bins=40)
    summary = {
        'grid_rows': m.rows, 'grid_cols': m.cols,
        'initial_state_count': m.base,
        'valid_state_count': batch['valid_states'],
        'graph_edges': batch['graph_edges'],
        'reverse_dijkstra_elapsed_sec': round(batch['elapsed_sec'], 3),
        'process_peak_rss_megabytes': (
            round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss /
                  (1024 * 1024 if sys.platform == 'darwin' else 1024), 1)
            if resource is not None else None),
        'zero_cost_initials_excluded_from_ratio': int((~positive).sum()),
        'mean_greedy_opt_ratio': round(float(np.mean(ratios)), 6),
        'median_greedy_opt_ratio': round(float(np.median(ratios)), 6),
        'max_greedy_opt_ratio': round(float(np.max(ratios)), 6),
        'fraction_greedy_optimal': round(float(np.mean(greedy_cost == optimum)), 6),
        'mean_optimal_cost': round(float(np.mean(optimum)), 5),
        'mean_greedy_cost': round(float(np.mean(greedy_cost)), 5),
        'ratio_histogram_counts': ratio_hist.tolist(),
        'ratio_histogram_bin_edges': [round(float(x), 5) for x in ratio_edges],
        'plot2_definition': 'Optimal policy tie-break via reverse Dijkstra: x=all actions, y=side actions',
        'display_convention': '0=full, 0.5=half, 1=empty; internal 2=full, 1=half, 0=empty',
    }
    (output/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    if make_plots:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(ratios, bins=40, edgecolor='white', linewidth=0.4)
        ax.set(xlabel='Greedy cost / optimal cost', ylabel='Number of initial grids',
               title=f'Greedy / optimal cost ratio ({m.rows} x {m.cols}, excluding empty grid)')
        fig.tight_layout()
        fig.savefig(output/'histogram_ratio.png', dpi=170)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.scatter(greedy_cost, optimum, s=4, alpha=.11, rasterized=True)
        lo, hi = 0, int(greedy_cost.max())
        ax.plot([lo, hi], [lo, hi], linestyle='--', linewidth=1, label='equal cost')
        ax.set(xlabel='Greedy solution cost', ylabel='Optimal solution cost',
               title='Greedy cost vs optimum')
        ax.legend()
        fig.tight_layout()
        fig.savefig(output/'scatter_costs.png', dpi=170)
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.scatter(actions, sides, s=5, alpha=.12, rasterized=True)
        ax.set(xlabel='Number of actions (optimal path)',
               ylabel='Number of side actions (optimal path)',
               title='Action count vs side-action count')
        fig.tight_layout()
        fig.savefig(output/'scatter_actions.png', dpi=170)
        plt.close(fig)
    return summary
