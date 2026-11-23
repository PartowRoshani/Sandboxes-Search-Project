"""Connect the new path-score local search to an existing SandGrid checkout.

Extract the archive into the project root (alongside run_project.py) and run:
    python apply_path_local_search.py

Does not modify SandGrid physics, original graph-search algorithms, or examples.
Safe to rerun. Supports both the base project and the previous local-search add-on.
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
SEARCH = ROOT / 'sandgrid' / 'search.py'
BENCHMARK = ROOT / 'sandgrid' / 'benchmark.py'
CLI = ROOT / 'sandgrid' / 'cli.py'
README = ROOT / 'README.md'
DOCS = ROOT / 'docs' / 'path_local_search.md'


def replace_search_dispatch(text: str) -> str:
    old = "if algo in ('hillclimb', 'anneal'):"
    new = "if algo in ('hillclimb', 'anneal', 'genetic'):"
    if new in text:
        return text
    if old in text:
        return text.replace(old, new, 1)
    needle = "    if algo not in ('random', 'dfs', 'bfs', 'ids', 'ucs', 'astar', 'rbfs'):"
    if needle not in text:
        raise RuntimeError('Cannot find the algorithm dispatch anchor in sandgrid/search.py')
    injection = """    if algo in ('hillclimb', 'anneal', 'genetic'):
        from .local_search import local_search
        return local_search(model, initial, algorithm=algo,
                            max_expansions=max_expansions,
                            max_seconds=max_seconds,
                            random_seed=random_seed,
                            measure_memory=measure_memory)
"""
    return text.replace(needle, injection + needle, 1)


def replace_benchmark(text: str) -> str:
    match = re.search(r'^(ALGORITHMS\s*=\s*\()([^\n]*)(\))\s*$', text, flags=re.M)
    if not match:
        print('Note: no ALGORITHMS tuple in benchmark.py; check benchmark configuration manually.')
        return text
    items = match.group(2)
    if "'genetic'" in items or '"genetic"' in items:
        return text
    for name in ('hillclimb', 'anneal', 'genetic'):
        if f"'{name}'" not in items and f'"{name}"' not in items:
            items += f", '{name}'"
    return text[:match.start(2)] + items + text[match.end(2):]


def replace_cli(text: str) -> str:
    # Supports the original CLI and the earlier Hill Climbing / SA add-on.
    old = "if args.algorithm == 'random' else None),"
    earlier = "if args.algorithm in ('random', 'hillclimb', 'anneal') else None),"
    new = "if args.algorithm in ('random', 'hillclimb', 'anneal', 'genetic') else None),"
    if new not in text:
        if earlier in text:
            text = text.replace(earlier, new)
        elif old in text:
            text = text.replace(old, new)
        else:
            print('Note: CLI random-seed dispatch not found; review CLI argument forwarding.')
    text = text.replace('Seed for Random algorithm action ordering (defaults to --seed)',
                        'Seed for Random and local-search algorithms (defaults to --seed)')
    text = text.replace('Compare all eight algorithms on identical grid',
                        'Compare available algorithms on identical grid')
    return text


def main() -> None:
    for required in (SEARCH, ROOT / 'sandgrid' / 'model.py',
                     ROOT / 'sandgrid' / 'local_search.py'):
        if not required.exists():
            raise SystemExit(f'Missing {required.relative_to(ROOT)}; extract into project root.')

    # Compute all changes BEFORE modifying any file. A mismatch in the search
    # dispatch should not leave a half-patched project.
    modifications = {SEARCH: replace_search_dispatch(SEARCH.read_text(encoding='utf-8'))}
    if BENCHMARK.exists():
        modifications[BENCHMARK] = replace_benchmark(BENCHMARK.read_text(encoding='utf-8'))
    if CLI.exists():
        modifications[CLI] = replace_cli(CLI.read_text(encoding='utf-8'))
    if README.exists() and DOCS.exists():
        text = README.read_text(encoding='utf-8')
        marker = '## Local Search مبتنی بر دنبالهٔ اکشن (Path Score)'
        if marker not in text:
            text = text.rstrip() + '\n\n' + DOCS.read_text(encoding='utf-8').strip() + '\n'
        modifications[README] = text

    for path, new_text in modifications.items():
        if path.read_text(encoding='utf-8') != new_text:
            path.write_text(new_text, encoding='utf-8')
            print('Updated:', path.relative_to(ROOT))
        else:
            print('Already configured:', path.relative_to(ROOT))
    print('Ready. Test: python -m pytest -q tests/test_path_local_search.py')


if __name__ == '__main__':
    main()
