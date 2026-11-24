"""Regression checks for lexicographic conflict-first fitness scoring."""
import unittest

from genetic_alg.fitness import evaluate_sequence
from genetic_alg.tests.test_genetic import TinyGrid


class TestFitnessPriority(unittest.TestCase):
    def setUp(self):
        self.model = TinyGrid()

    def test_fewer_conflicts_always_beats_more_conflicts(self):
        for transform in ("log", "linear", "sqrt", "none"):
            with self.subTest(transform=transform):
                no_progress = evaluate_sequence(self.model, 3, (), cost_transform=transform)
                expensive_progress = evaluate_sequence(self.model, 3, (0,), cost_transform=transform)
                self.assertEqual(no_progress.min_conflict, 2)
                self.assertEqual(expensive_progress.min_conflict, 1)
                self.assertGreater(expensive_progress.fitness, no_progress.fitness)

    def test_same_conflict_lower_cost_is_preferred(self):
        for transform in ("log", "linear", "sqrt"):
            with self.subTest(transform=transform):
                expensive = evaluate_sequence(self.model, 3, (0,), cost_transform=transform)
                cheap = evaluate_sequence(self.model, 3, (1,), cost_transform=transform)
                self.assertEqual(expensive.min_conflict, cheap.min_conflict)
                self.assertGreater(cheap.fitness, expensive.fitness)

    def test_invalid_is_zero_and_goal_outscores_non_goal(self):
        invalid = evaluate_sequence(self.model, 3, (0, 0))
        partial = evaluate_sequence(self.model, 3, (1,))
        solved = evaluate_sequence(self.model, 3, (0, 1))
        self.assertEqual(invalid.fitness, 0.0)
        self.assertGreater(solved.fitness, partial.fitness)
        self.assertTrue(solved.solved)

    def test_min_conflict_cost_still_matches_earliest_prefix(self):
        result = evaluate_sequence(self.model, 3, (0, 2))
        self.assertEqual(result.min_conflict, 1)
        self.assertEqual(result.cost_at_min_conflict, 5)
        self.assertEqual(result.actions, (0,))


if __name__ == "__main__":
    unittest.main()
