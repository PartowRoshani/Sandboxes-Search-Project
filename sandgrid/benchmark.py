"""Repeatable per-initial-state runtime/memory benchmark with CSV checkpointing."""
from __future__ import annotations

import csv
from pathlib import Path
import random
import tracemalloc

from .model import SandGrid
from .search import greedy, search

ALGORITHMS = ('greedy', 'dfs', 'bfs', 'ids', 'ucs', 'astar', 'rbfs')
FIELDS = ('initial_code', 'algorithm', 'status', 'found', 'cost', 'action_count',
          'side_action_count', 'elapsed_sec', 'expanded', 'generated',
          'max_frontier', 'peak_python_bytes')


def benchmark(model: SandGrid, filepath: str | Path, count: int = 30,
              all_states: bool = False, seed: int = 42,
              algorithms: tuple[str, ...] = ALGORITHMS,
              max_seconds: float = 0.5, max_expansions: int = 50000,
              max_depth: int = 30, resume: bool = True) -> dict:
    """Record per-run metrics, including timeouts; append to CSV incrementally.

    The initial states are ALWAYS closed-gate grids (0..3**n-1).
    `--all` may require many hours, depending on limits and hardware.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    if all_states:
        codes = range(model.base)
    else:
        rnd = random.Random(seed)
        codes = rnd.sample(range(model.base), min(count, model.base))
    done: set[tuple[int, str]] = set()
    if resume and path.exists():
        with path.open(encoding='utf-8', newline='') as f:
            for row in csv.DictReader(f):
                done.add((int(row['initial_code']), row['algorithm']))
    elif path.exists():
        path.unlink()
    new = not path.exists()
    stats = {'completed': 0, 'skipped_existing': 0, 'timeouts': 0, 'failures': 0}
    with path.open('a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        for code in codes:
            for algorithm in algorithms:
                if (code, algorithm) in done:
                    stats['skipped_existing'] += 1
                    continue
                if algorithm == 'greedy':
                    tracemalloc.start()
                    result = greedy(model, code)
                    result.peak_memory_bytes = tracemalloc.get_traced_memory()[1]
                    tracemalloc.stop()
                else:
                    result = search(model, code, algorithm,
                                    max_expansions=max_expansions,
                                    max_seconds=max_seconds,
                                    max_depth=max_depth,
                                    measure_memory=True)
                num_side = sum(model.actions[a].kind == 'side' for a in result.actions)
                writer.writerow(dict(initial_code=code, algorithm=algorithm,
                                     status=result.status, found=int(result.found),
                                     cost=result.cost if result.cost is not None else '',
                                     action_count=result.action_count,
                                     side_action_count=num_side,
                                     elapsed_sec=f'{result.elapsed_sec:.6f}',
                                     expanded=result.expanded, generated=result.generated,
                                     max_frontier=result.max_frontier,
                                     peak_python_bytes=result.peak_memory_bytes or 0))
                f.flush()  # safe restart after interruption
                stats['completed'] += 1
                if result.status == 'timeout':
                    stats['timeouts'] += 1
                elif result.status not in ('found', 'timeout'):
                    stats['failures'] += 1
            if stats['completed'] and stats['completed'] % 100 == 0:
                print(f"  benchmark rows completed: {stats['completed']}", flush=True)
    return stats


def summarize(filepath: str | Path, destination: str | Path) -> list[dict]:
    """Summarize completed and timeout-limited measurements; never hide failures."""
    from statistics import median
    by_algo: dict[str, list[dict]] = {}
    with Path(filepath).open(encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            by_algo.setdefault(row['algorithm'], []).append(row)
    report = []
    for algo, rows in by_algo.items():
        success = [r for r in rows if r['status'] == 'found']
        times = [float(r['elapsed_sec']) for r in rows]
        memory = [int(r['peak_python_bytes']) for r in rows]
        report.append(dict(algorithm=algo, runs=len(rows), solved=len(success),
                           timeout=sum(r['status'] == 'timeout' for r in rows),
                           other_limit=sum(r['status'] not in ('found', 'timeout') for r in rows),
                           median_elapsed_sec=round(median(times), 6),
                           max_elapsed_sec=round(max(times), 6),
                           median_python_memory_kib=round(median(memory)/1024, 2),
                           max_python_memory_kib=round(max(memory)/1024, 2),
                           median_expanded=median(int(r['expanded']) for r in rows)))
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=report[0].keys() if report else ['algorithm'])
        writer.writeheader()
        writer.writerows(report)
    return report
