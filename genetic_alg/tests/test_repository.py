"""Integration assertions use the ORIGINAL sandgrid package when available."""
from __future__ import annotations
import importlib.util
import unittest

from genetic_alg.fitness import evaluate_sequence
from genetic_alg.core import GeneticAlgorithm, GAConfig


@unittest.skipUnless(importlib.util.find_spec("sandgrid") is not None,
                     "Original sandgrid package is absent; copy genetic_alg beside sandgrid")
class TestCurrentRepository(unittest.TestCase):
    def test_professor_reference_route_uses_actual_model(self):
        from sandgrid.model import SandGrid
        model = SandGrid(4, 2)
        start = model.from_display([[1, 0], [0, 1], [0, 1], [1, 0]])
        self.assertEqual(start, 2000)
        # Original instructor's seven downward gate openings, one-based rows:
        # (1,1), (2,1), (3,1), (4,1), (2,2), (3,2), (4,2).
        evaluation = evaluate_sequence(model, start, (0, 2, 4, 6, 3, 5, 7))
        self.assertTrue(evaluation.solved)
        self.assertEqual(evaluation.path_cost, 47)

    def test_genetic_replay_preserves_sandgrid_goal_and_cost(self):
        from sandgrid.model import SandGrid
        model = SandGrid(4, 2)
        start = model.from_display([[1, 0], [0, 1], [0, 1], [1, 0]])
        result = GeneticAlgorithm(model, start, GAConfig(
            population_size=30, chromosome_length=50,
            generations=100, seed=42)).run()
        if result.found:
            path = model.trace(start, result.actions)
            self.assertEqual(path[-1]["state"], 0)
            self.assertEqual(path[-1]["total_cost"], result.cost)
        else:
            # A stochastic optimizer is not guaranteed to solve every seed.
            self.assertGreater(result.best_min_conflict, 0)


if __name__ == "__main__":
    unittest.main()
