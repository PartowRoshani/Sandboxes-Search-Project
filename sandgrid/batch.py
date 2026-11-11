"""Exact reverse-Dijkstra analysis for the continuous-flow sand gate model.

Both blocked vertical and blocked directed horizontal gates are part of a
state. A full stable-state graph for 5x2 can be much larger than the 59,049
closed-gate initial states, so computation is guarded by a preflight size cap.
A small grid (2x2 or 3x2) is useful for exhaustive correctness analysis.
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


def _eligible_open_mask(model: SandGrid, occ: list[int]) -> int:
    """Bits that MAY be open in a stable state, according to valid_mask.

    A stable open gate retains upstream sand but has a fully occupied
    destination; otherwise it would already have transferred or closed.
    """
    mask = 0
    for bit in range(model.vertical_edges):
        if occ[bit] > 0 and occ[bit + model.cols] == 2:
            mask |= 1 << bit
    for action in model.actions[model.n:]:
        bit = model.gate_bit(action.id)
        assert bit is not None and action.dst is not None
        if occ[action.src] > 0 and occ[action.dst] == 2:
            mask |= 1 << bit
    return mask


def estimate_valid_states(model: SandGrid) -> int:
    """Count stable encoded states without allocating the graph.

    All-empty occupancy has just one canonical state (state 0), irrespective
    of formerly-open gates.
    """
    count = 0
    for code in range(model.base):
        if code == 0:
            count += 1
            continue
        work = code
        occ = []
        for _ in range(model.n):
            work, digit = divmod(work, 3)
            occ.append(digit)
        count += 1 << _eligible_open_mask(model, occ).bit_count()
    return count


def compute_all_optimal(model: SandGrid, progress: bool = True,
                        max_states: int = 250_000) -> dict:
    """Return exact optimal costs from every stable state to the empty grid.

    The graph is enumerated only if preflight estimation fits the state cap.
    Large models should use bounded per-initial-state search rather than
    treating 3**(rows*cols) as the entire augmented state space.
    """
    if max_states < 1:
        raise ValueError('max_states must be positive')
    if model.n > 10:
        raise BatchTooLarge('exhaustive analysis is restricted to at most 10 cells')
    estimated = estimate_valid_states(model)
    if estimated > max_states:
        raise BatchTooLarge(
            f'{model.rows}x{model.cols} has {model.base:,} closed-gate initial grids, '
            f'but {estimated:,} modeled stable states with persistent vertical '
            f'AND horizontal gates. This exceeds max_states={max_states:,}. '
            'Do not reuse old 5x2 reverse-Dijkstra results; '
            'run a 2x2 or 3x2 exact analysis, or use --skip-analysis '
            'for the project runner until a scalable solver is implemented.'
        )
    from array import array
    started = perf_counter()
    states = array('Q')  # Masked state IDs can exceed 32-bit on larger grids.
    for code in range(model.base):
        if code == 0:
            states.append(0)
            continue
        work = code
        occ = []
        for _ in range(model.n):
            work, digit = divmod(work, 3)
            occ.append(digit)
        eligible = _eligible_open_mask(model, occ)
        submask = eligible
        while True:
            states.append(code + model.base * submask)
            if submask == 0:
                break
            submask = (submask - 1) & eligible
    if len(states) != estimated:
        raise AssertionError('stable-state enumeration count disagrees with preflight')
    state_index = {s: idx for idx, s in enumerate(states)}
    n = len(states)
    if progress:
        print(f'Enumerated {n:,} stable states from {model.base:,} initial grids.', flush=True)
    source = array('I')
    target = array('I')
    weights = array('B')
    action_ids = array('B')
    for idx, state in enumerate(states):
        for nxt, action, cost in model.successors(state):
            if nxt not in state_index:
                raise AssertionError(f'generated successor not in stable graph: {state} -> {nxt}')
            source.append(idx)
            target.append(state_index[nxt])
            weights.append(cost)
            action_ids.append(action)
        if progress and (idx + 1) % 50000 == 0:
            print(f'  Built edges for {idx+1:,}/{n:,} states', flush=True)
    edges = len(target)
    if progress:
        print(f'Graph has {edges:,} weighted transitions.', flush=True)

    src_np = np.frombuffer(source, dtype=np.uint32)
    target_np = np.frombuffer(target, dtype=np.uint32)
    cost_np = np.frombuffer(weights, dtype=np.uint8)
    action_np = np.frombuffer(action_ids, dtype=np.uint8)
    permutation = np.argsort(target_np, kind='stable')
    counts = np.bincount(target_np, minlength=n)
    offsets = np.empty(n + 1, dtype=np.int64)
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
        for j in range(int(offsets[node]), int(offsets[node + 1])):
            pred = int(rev_sources[j])
            nd = d + int(rev_costs[j])
            if nd < int(distance[pred]):
                distance[pred] = nd
                policy_next[pred] = node
                policy_action[pred] = int(rev_actions[j])
                heappush(heap, (nd, pred))
        if progress and settled % 50000 == 0:
            print(f'  Reverse Dijkstra settled {settled:,}/{n:,} states', flush=True)
    if settled != n:
        raise AssertionError(f'{n - settled} modeled stable states cannot reach the empty goal')
    if progress:
        print(f'Exact optima computed in {perf_counter()-started:.2f}s.', flush=True)
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
        'model_version': m.MODEL_VERSION,
        'plot2_definition': 'Optimal policy tie-break via reverse Dijkstra: x=all actions, y=side actions',
        'display_convention': '1=full, 0.5=half, 0=empty; internal 2=full, 1=half, 0=empty',
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
