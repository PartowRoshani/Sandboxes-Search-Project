"""Graph-search algorithms for the weighted sand-grid problem.

BFS/DFS/IDS optimize action count (BFS, IDS only) or find a valid path (DFS),
not the weighted cost. UCS and A* are optimal for the nonnegative edge costs.
RBFS is an optional memory-bounded best-first algorithm with admissible h.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from math import inf
from time import perf_counter
import tracemalloc

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


def heuristic(model: SandGrid, state: int) -> int:
    """Admissible: each unopened necessary row boundary costs >=3;
    draining the grid requires >=3 if just one half-unit, else >=5.

    A previously connected boundary may pass sand without an *additional*
    opening, so we don't count it. Side actions cannot move sand down a row.
    """
    if model.is_goal(state):
        return 0
    occ, mask = model.decode(state)
    total = sum(occ)
    h = 3 if total == 1 else 5
    any_above = False
    for row in range(model.rows - 1):
        any_above = any_above or any(occ[row * model.cols + col] > 0
                                     for col in range(model.cols))
        if any_above and not any(mask & (1 << (row * model.cols + col))
                                 for col in range(model.cols)):
            h += 3
    return h


def _reconstruct(parent: dict[int, tuple[int, int]], goal: int) -> list[int]:
    actions = []
    s = goal
    while s in parent:
        s, action = parent[s]
        actions.append(action)
    actions.reverse()
    return actions


def search(model: SandGrid, initial: int, algorithm: str = 'astar',
           max_expansions: int | None = None, max_seconds: float | None = None,
           max_depth: int = 60, measure_memory: bool = False) -> SearchResult:
    names = {'a*': 'astar', 'a-star': 'astar', 'bfs': 'bfs', 'dfs': 'dfs',
             'ids': 'ids', 'ucs': 'ucs', 'astar': 'astar', 'rbfs': 'rbfs'}
    algo = names.get(algorithm.lower())
    if algo is None:
        raise ValueError(f'algorithm must be one of {sorted(set(names.values()))}')
    started = perf_counter()
    if measure_memory:
        tracemalloc.start()
    expansions = 0
    generated = 0
    max_frontier = 1
    status = 'not_found'
    result_actions: list[int] = []
    result_cost: int | None = None
    goal = 0

    def stop() -> str | None:
        if max_expansions is not None and expansions >= max_expansions:
            return 'expansion_limit'
        if max_seconds is not None and perf_counter() - started >= max_seconds:
            return 'timeout'
        return None

    try:
        if model.is_goal(initial):
            status, result_cost = 'found', 0
        elif algo in ('ucs', 'astar'):
            serial = count()
            frontier: list[tuple[int, int, int, int]] = []
            best = {initial: 0}
            parents: dict[int, tuple[int, int]] = {}
            heappush(frontier, (heuristic(model, initial) if algo == 'astar' else 0,
                                next(serial), 0, initial))
            while frontier:
                if (s := stop()) is not None:
                    status = s
                    break
                _, _, g, state = heappop(frontier)
                if g != best[state]:
                    continue
                if state == goal:
                    status, result_cost = 'found', g
                    result_actions = _reconstruct(parents, state)
                    break
                expansions += 1
                for nxt, action, step_cost in model.successors(state):
                    generated += 1
                    alt = g + step_cost
                    if alt < best.get(nxt, inf):
                        best[nxt] = alt
                        parents[nxt] = (state, action)
                        f = alt + (heuristic(model, nxt) if algo == 'astar' else 0)
                        heappush(frontier, (f, next(serial), alt, nxt))
                max_frontier = max(max_frontier, len(frontier))
        elif algo in ('bfs', 'dfs'):
            frontier = deque([initial]) if algo == 'bfs' else [initial]
            visited = {initial}
            parents = {}
            while frontier:
                if (s := stop()) is not None:
                    status = s
                    break
                state = frontier.popleft() if algo == 'bfs' else frontier.pop()
                if state == goal:
                    status = 'found'
                    result_actions = _reconstruct(parents, state)
                    result_cost = model.trace(initial, result_actions)[-1]['total_cost']
                    break
                expansions += 1
                for nxt, action, _ in model.successors(state):
                    generated += 1
                    if nxt not in visited:
                        visited.add(nxt)
                        parents[nxt] = (state, action)
                        frontier.append(nxt)
                max_frontier = max(max_frontier, len(frontier))
        elif algo == 'ids':
            # Depth-limited graph DFS; the depth limit grows one unit at a time.
            # Iterative loop avoids recursion limits and is exhaustive up to max_depth.
            exhausted_by_limit = False
            for depth_limit in range(max_depth + 1):
                if status == 'found':
                    break
                work: list[tuple[int, list[int], int, frozenset[int]]] = [
                    (initial, [], 0, frozenset([initial]))]
                while work:
                    max_frontier = max(max_frontier, len(work))
                    if (s := stop()) is not None:
                        status = s
                        break
                    state, path, depth, path_set = work.pop()
                    if state == goal:
                        result_actions = path
                        result_cost = model.trace(initial, path)[-1]['total_cost']
                        status = 'found'
                        break
                    if depth == depth_limit:
                        exhausted_by_limit = True
                        continue
                    expansions += 1
                    neighbors = list(model.successors(state))
                    generated += len(neighbors)
                    for nxt, action, _ in reversed(neighbors):
                        if nxt not in path_set:
                            work.append((nxt, path + [action], depth + 1,
                                         path_set | {nxt}))
                if status in ('timeout', 'expansion_limit', 'found'):
                    break
            if status == 'not_found' and exhausted_by_limit:
                status = 'depth_limit'
        elif algo == 'rbfs':
            # RBFS follows Russell-Norvig's f-limit recursion, with path-cycle
            # checks and a resource limit. Best-first but can re-expand states.
            class LimitReached(Exception):
                pass
            path_actions: list[int] = []
            path_set = {initial}
            def visit(state: int, g: int, node_f: int, f_limit: float):
                nonlocal expansions, generated, max_frontier
                if (s := stop()) is not None:
                    raise LimitReached(s)
                if state == goal:
                    return True, node_f, g
                expansions += 1
                children = []
                for nxt, action, cost in model.successors(state):
                    generated += 1
                    if nxt not in path_set:
                        score = max(g + cost + heuristic(model, nxt), node_f)
                        children.append([score, nxt, action, cost])
                if not children:
                    return False, inf, None
                max_frontier = max(max_frontier, len(children) + len(path_set))
                while True:
                    children.sort(key=lambda item: item[0])
                    best_child = children[0]
                    if best_child[0] > f_limit:
                        return False, best_child[0], None
                    alternative = children[1][0] if len(children) > 1 else inf
                    _, nxt, action, cost = best_child
                    path_set.add(nxt)
                    path_actions.append(action)
                    found, returned_f, found_g = visit(nxt, g + cost, best_child[0],
                                                        min(f_limit, alternative))
                    if found:
                        return True, returned_f, found_g
                    path_actions.pop()
                    path_set.remove(nxt)
                    best_child[0] = returned_f
            try:
                found, _, found_g = visit(initial, 0, heuristic(model, initial), inf)
                if found:
                    status = 'found'
                    result_actions = path_actions[:]
                    result_cost = found_g
            except LimitReached as err:
                status = str(err)
            except RecursionError:
                status = 'recursion_limit'
    finally:
        peak = tracemalloc.get_traced_memory()[1] if measure_memory else None
        if measure_memory:
            tracemalloc.stop()
    return SearchResult(algo, status == 'found', status, result_cost,
                        result_actions, expansions, generated, max_frontier,
                        perf_counter() - started, peak)


def greedy(model: SandGrid, initial: int) -> SearchResult:
    """Professor's baseline: never open a side gate; process each column top-down.

    Skip empty cells and already open vertical doors. Make repeated top-down
    passes if necessary. This is NOT heuristic best-first greedy search.
    """
    started = perf_counter()
    state = initial
    actions: list[int] = []
    total_cost = 0
    expanded = 0
    for col in range(model.cols):
        while True:
            occ, _ = model.decode(state)
            if not any(occ[row * model.cols + col] for row in range(model.rows)):
                break
            before_pass = state
            for row in range(model.rows):
                idx = row * model.cols + col
                action = model.down_ids[idx]
                result = model.step(state, action)
                if result is None:
                    continue
                state, cost = result
                actions.append(action)
                total_cost += cost
                expanded += 1
            if state == before_pass:
                raise RuntimeError('greedy made no progress; check flow model')
    assert model.is_goal(state)
    return SearchResult('greedy', True, 'found', total_cost, actions,
                        expanded, expanded, 1, perf_counter() - started)
