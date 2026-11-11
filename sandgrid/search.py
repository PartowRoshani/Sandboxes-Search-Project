"""Graph searches and the professor's column-wise vertical-only baseline.

The assignment calls the baseline 'Greedy', but it is NOT Greedy Best-First
Search: it empties the columns in order, using only downward/exit gates.
BFS/IDS optimize opening count; UCS/A* optimize total weighted cost.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from math import inf
from time import perf_counter
import tracemalloc
import random

from .model import SandGrid


@dataclass
class SearchResult:
    algorithm: str
    found: bool
    status: str
    cost: int | None
    actions: list[int]
    expanded: int
    generated: int
    max_frontier: int
    elapsed_sec: float
    peak_memory_bytes: int | None = None

    @property
    def action_count(self) -> int:
        return len(self.actions)


from .heuristics import basic as heuristic, relaxation, choose


def _reconstruct(parent: dict[int, tuple[int, int]], goal: int) -> list[int]:
    out = []
    while goal in parent:
        goal, a = parent[goal]
        out.append(a)
    out.reverse()
    return out


def greedy(model: SandGrid, initial: int) -> SearchResult:
    """Empty columns independently, scanning from their topmost sand downward.

    Skip a gate that is ALREADY open, since its ongoing flow is free. Restart
    the top-to-bottom scan if sand still remains after reaching the exit.
    Horizontal gates are never opened by this baseline.
    """
    start = perf_counter()
    state = initial
    total = 0
    actions: list[int] = []
    scans = 0
    for col in range(model.cols):
        while True:
            occ, _ = model.decode(state)
            occupied_rows = [r for r in range(model.rows)
                             if occ[r*model.cols+col] > 0]
            if not occupied_rows:
                break
            before_state = state
            for r in range(occupied_rows[0], model.rows):
                src = r*model.cols+col
                occ, mask = model.decode(state)
                gate_id = model.down_ids[src]
                bit = model.gate_bit(gate_id)
                if occ[src] == 0 or (bit is not None and mask & (1 << bit)):
                    continue
                transition = model.step(state, gate_id)
                if transition is None:
                    raise AssertionError('baseline tried an invalid downward opening')
                state, cost = transition
                actions.append(gate_id)
                total += cost
            scans += 1
            if state == before_state:
                raise AssertionError('baseline made no progress while sand remained')
            if scans > 100 * model.n:
                raise AssertionError('baseline scan limit exceeded')
    if state != 0:
        raise AssertionError('column-wise baseline did not empty the grid')
    return SearchResult('greedy', True, 'found', total, actions,
                        len(actions), len(actions), 1, perf_counter()-start)


class _Halt(Exception):
    pass


def search(model: SandGrid, initial: int, algorithm: str = 'astar',
           max_expansions: int | None = None, max_seconds: float | None = None,
           max_depth: int = 60, measure_memory: bool = False,
           heuristic_name: str = 'basic',
           ml_model_path: str | None = None,
           random_seed: int = 42) -> SearchResult:
    aliases = {'a*': 'astar', 'a-star': 'astar'}
    algo = aliases.get(algorithm.lower(), algorithm.lower())
    if algo not in ('random', 'dfs', 'bfs', 'ids', 'ucs', 'astar', 'rbfs'):
        raise ValueError(f'unknown algorithm: {algorithm}')
    if max_seconds is not None and max_seconds <= 0:
        raise ValueError('max_seconds must be positive')
    if max_expansions is not None and max_expansions <= 0:
        raise ValueError('max_expansions must be positive')
    if max_depth < 0:
        raise ValueError('max_depth cannot be negative')
    if heuristic_name not in ('basic', 'relax', 'ml', 'ml-tie'):
        raise ValueError(f'Unknown heuristic {heuristic_name}')
    if heuristic_name == 'ml-tie' and algo == 'rbfs':
        raise ValueError('ml-tie is only supported for A*, not RBFS')
    if algo in ('astar', 'rbfs') and heuristic_name in ('ml', 'ml-tie'):
        learned = choose(model, heuristic_name, ml_model_path)
        h_value = (lambda node: relaxation(model, node)) if heuristic_name == 'ml-tie' else learned
        tie_value = learned if heuristic_name == 'ml-tie' else (lambda node: 0.0)
    elif algo in ('astar', 'rbfs'):
        h_value = choose(model, heuristic_name)
        tie_value = lambda node: 0.0
    else:
        h_value = lambda node: 0
        tie_value = lambda node: 0.0
    start = perf_counter()
    if measure_memory:
        tracemalloc.start()
    expanded, generated, max_frontier = 0, 0, 1
    status = 'not_found'
    found_actions: list[int] = []
    cost: int | None = None

    def check():
        if max_seconds is not None and perf_counter()-start >= max_seconds:
            raise _Halt('timeout')
        if max_expansions is not None and expanded >= max_expansions:
            raise _Halt('expansion_limit')

    try:
        if model.is_goal(initial):
            status, cost = 'found', 0

        elif algo in ('ucs', 'astar'):
            serial = count()
            dist = {initial: 0}
            parent: dict[int, tuple[int,int]] = {}
            pq = [(h_value(initial), tie_value(initial),
                   next(serial), 0, initial)]
            while pq:
                check()
                _, _, _, g, node = heappop(pq)
                if g != dist.get(node):
                    continue
                if model.is_goal(node):
                    status, cost = 'found', g
                    found_actions = _reconstruct(parent, node)
                    break
                expanded += 1
                improved = []
                for nxt, aid, price in model.successors(node):
                    generated += 1
                    cand = g+price
                    if cand < dist.get(nxt, inf):
                        dist[nxt] = cand
                        parent[nxt] = (node, aid)
                        improved.append((nxt, cand))
                # RandomForest predicts small batches much faster than one
                # Python -> sklearn call per successor. Values stay cached
                # for the duration of THIS search only.
                if algo == 'astar' and heuristic_name in ('ml', 'ml-tie'):
                    learned.predict_many(nxt for nxt, _ in improved)
                for nxt, cand in improved:
                    priority = cand + h_value(nxt)
                    heappush(pq, (priority, tie_value(nxt), next(serial), cand, nxt))
                max_frontier = max(max_frontier, len(pq))

        elif algo == 'bfs':
            queue = deque([initial])
            parent = {}
            visited = {initial}
            while queue:
                check()
                node = queue.popleft()
                if model.is_goal(node):
                    found_actions = _reconstruct(parent, node)
                    cost = model.trace(initial, found_actions)[-1]['total_cost']
                    status = 'found'
                    break
                expanded += 1
                for nxt, aid, price in model.successors(node):
                    generated += 1
                    if nxt not in visited:
                        visited.add(nxt)
                        parent[nxt] = (node, aid)
                        queue.append(nxt)
                max_frontier = max(max_frontier, len(queue))

        elif algo == 'random':
            # Seeded randomized depth-first graph search. Every *complete*
            # state (occupancy + open-gate mask) is discovered at most once.
            # Unlike a memoryless random walk, backtracking avoids getting
            # stuck at a local dead end, without inserting loops in the path.
            rng = random.Random(random_seed)
            stack = [initial]
            parent: dict[int, tuple[int, int]] = {}
            visited = {initial}
            while stack:
                check()
                node = stack.pop()
                if model.is_goal(node):
                    found_actions = _reconstruct(parent, node)
                    cost = model.trace(initial, found_actions)[-1]['total_cost']
                    status = 'found'
                    break
                expanded += 1
                children = list(model.successors(node))
                rng.shuffle(children)
                for nxt, aid, _price in children:
                    generated += 1
                    if nxt in visited:
                        continue
                    visited.add(nxt)
                    parent[nxt] = (node, aid)
                    stack.append(nxt)
                max_frontier = max(max_frontier, len(stack))

        elif algo == 'dfs':
            # Iterative stack: avoids Python recursion limits on larger graphs.
            stack = [initial]
            parent = {}
            visited = {initial}
            while stack:
                check()
                node = stack.pop()
                if model.is_goal(node):
                    found_actions = _reconstruct(parent, node)
                    cost = model.trace(initial, found_actions)[-1]['total_cost']
                    status = 'found'
                    break
                expanded += 1
                for nxt, aid, price in reversed(list(model.successors(node))):
                    generated += 1
                    if nxt not in visited:
                        visited.add(nxt)
                        parent[nxt] = (node, aid)
                        stack.append(nxt)
                max_frontier = max(max_frontier, len(stack))

        elif algo == 'ids':
            for depth in range(max_depth + 1):
                check()
                path = {initial}
                trail: list[int] = []

                def dls(node: int, remaining: int) -> bool:
                    nonlocal expanded, generated, max_frontier
                    check()
                    if model.is_goal(node):
                        return True
                    if remaining == 0:
                        return False
                    expanded += 1
                    for nxt, aid, price in model.successors(node):
                        generated += 1
                        if nxt in path:
                            continue
                        path.add(nxt)
                        trail.append(aid)
                        max_frontier = max(max_frontier, len(path))
                        if dls(nxt, remaining-1):
                            return True
                        trail.pop()
                        path.remove(nxt)
                    return False

                if dls(initial, depth):
                    found_actions = trail.copy()
                    cost = model.trace(initial, found_actions)[-1]['total_cost']
                    status = 'found'
                    break
            else:
                status = 'depth_limit'

        else:  # rbfs: recursive best-first search, with path-cycle avoidance.
            path = {initial}
            trail: list[int] = []
            h0 = h_value(initial)

            def rbfs(node: int, g: int, bound: float, f_here: float):
                nonlocal expanded, generated, max_frontier
                check()
                if model.is_goal(node):
                    return trail.copy(), g, f_here
                expanded += 1
                children = []
                for nxt, aid, price in model.successors(node):
                    generated += 1
                    if nxt not in path:
                        h = h_value(nxt)
                        children.append([max(g+price+h, f_here), nxt, aid, price])
                if not children:
                    return None, None, inf
                while True:
                    check()
                    children.sort(key=lambda child: child[0])
                    best = children[0]
                    if best[0] > bound:
                        return None, None, best[0]
                    alternate = children[1][0] if len(children) > 1 else inf
                    path.add(best[1])
                    trail.append(best[2])
                    max_frontier = max(max_frontier, len(path))
                    sol, value, updated = rbfs(best[1], g+best[3],
                                               min(bound, alternate), best[0])
                    trail.pop()
                    path.remove(best[1])
                    best[0] = updated
                    if sol is not None:
                        return sol, value, updated

            found_actions, cost, _ = rbfs(initial, 0, inf, h0)
            if found_actions is not None:
                status = 'found'
            else:
                found_actions = []
    except _Halt as exc:
        status = str(exc)
        found_actions, cost = [], None
    finally:
        peak = None
        if measure_memory:
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
    return SearchResult(algo, status == 'found', status, cost, found_actions,
                        expanded, generated, max_frontier,
                        perf_counter()-start, peak)
