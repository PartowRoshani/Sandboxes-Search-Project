"""Small demonstration of a 30--35-action chromosome and its score."""
from pathlib import Path
from random import Random
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sandgrid.model import SandGrid
from sandgrid.local_search import PathScorer, random_path


def main():
    model = SandGrid(4, 2)
    initial = model.from_display([[1, 0], [0, 1], [0, 1], [1, 0]])
    rng = Random(42)
    path = random_path(model, initial, rng)
    result = PathScorer(model, initial).path_score(path)
    print('path:', path)
    print('length:', len(path), 'goal:', result.found_goal)
    print('goal_index:', result.goal_index, 'path_cost:', result.path_cost)
    print('score:', round(result.score, 3), 'remaining_half_units:', result.remaining_units)
    print('invalid_attempts:', result.invalid_attempts)
    print('executed_actions:', list(result.executed_actions))


if __name__ == '__main__':
    main()
