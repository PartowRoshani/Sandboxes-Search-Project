"""Self-contained unit tests; no repository code modified or copied."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import random
import tempfile
import unittest

from genetic_alg.core import GeneticAlgorithm, GAConfig
from genetic_alg.fitness import (conflict_number, evaluate_sequence,
                                 fitness_function, goal_test)
from genetic_alg.operators import crossover, mutate, roulette_select, scale_fitnesses
from genetic_alg.dashboard import build_dashboard
from genetic_alg.experiments import write_rows, COLUMNS


@dataclass
class FakeAction:
    kind: str
    label: str


class TinyGrid:
    """Two occupied cells; actions 0/1 drain each, action 2 waits at cost 1."""
    MODEL_VERSION = "toy-test-v1"
    rows = 1
    cols = 2
    actions = [FakeAction("down", "drain left"),
               FakeAction("down", "drain right"),
               FakeAction("side", "wait")]
    def decode(self, state):
        return [state & 1, (state >> 1) & 1], 0
    def is_goal(self, state):
        return state == 0
    def step(self, state, action):
        if action == 0 and state & 1:
            return state & ~1, 5
        if action == 1 and state & 2:
            return state & ~2, 1
        if action == 2 and state:
            return state, 1
        return None
    def successors(self, state):
        for aid in range(len(self.actions)):
            outcome = self.step(state, aid)
            if outcome is not None:
                yield outcome[0], aid, outcome[1]


class TestFitness(unittest.TestCase):
    def setUp(self):
        self.model = TinyGrid()

    def test_sequence_goal_and_discard_suffix(self):
        evaluated = evaluate_sequence(self.model, 3, (0, 1, 0, 0))
        self.assertTrue(evaluated.solved)
        self.assertTrue(evaluated.valid)
        self.assertEqual(evaluated.actions, (0, 1))
        self.assertEqual(evaluated.path_cost, 6)
        self.assertTrue(goal_test(self.model, 3, (0, 1)))

    def test_illegal_executed_action_must_get_zero(self):
        bad = evaluate_sequence(self.model, 3, (0, 0, 1))
        self.assertFalse(bad.valid)
        self.assertEqual(bad.fitness, 0.0)
        self.assertEqual(bad.invalid_at, 1)
        self.assertFalse(goal_test(self.model, 3, (0, 0, 1)))

    def test_minimum_conflict_uses_corresponding_prefix_cost(self):
        item = evaluate_sequence(self.model, 3, (0, 2))
        self.assertFalse(item.solved)
        self.assertEqual(item.min_conflict, 1)
        self.assertEqual(item.cost_at_min_conflict, 5)  # Not 6; the wait is irrelevant
        self.assertEqual(item.path_cost, 6)
        self.assertEqual(item.actions, (0,))

    def test_fitness_goal_beats_non_goal_and_never_negative(self):
        partial = fitness_function(self.model, 3, (0,))
        solved = fitness_function(self.model, 3, (0, 1))
        self.assertLess(partial, solved)
        self.assertGreaterEqual(partial, 0)
        self.assertGreater(solved, 100_000)
        self.assertEqual(conflict_number(self.model, 3, "half_units"), 2)
        self.assertEqual(conflict_number(self.model, 3, "occupied"), 2)

    def test_solved_lower_cost_is_fitter(self):
        faster = evaluate_sequence(self.model, 3, (0, 1))
        slower = evaluate_sequence(self.model, 3, (2, 0, 1))
        self.assertGreater(faster.fitness, slower.fitness)
        for penalty in ("linear", "sqrt", "log", "none"):
            item = evaluate_sequence(self.model, 3, (0, 1), cost_transform=penalty)
            self.assertTrue(item.solved)

    def test_empty_initial_state_succeeds(self):
        item = evaluate_sequence(self.model, 0, (200, 200))
        self.assertTrue(item.solved)
        self.assertEqual(item.actions, ())
        self.assertEqual(item.path_cost, 0)


class TestOperators(unittest.TestCase):
    def test_crossover_preserves_length_and_genes(self):
        a, b = tuple(range(20)), tuple(range(20, 40))
        for method in ("one_point", "two_point"):
            x, y = crossover(a, b, random.Random(3), method)
            self.assertEqual(len(x), 20)
            self.assertEqual(len(y), 20)
            self.assertEqual(sorted(x + y), sorted(a + b))

    def test_selection_scaling_preserves_goal_cost_pressure(self):
        weights = scale_fitnesses([0.0, 100123.0, 100124.0, 100125.0])
        self.assertEqual(weights[0], 0)
        self.assertGreater(weights[3], weights[2])
        self.assertGreater(weights[2], weights[1])
        self.assertGreater(weights[3] / weights[1], 10)

    def test_mutation_and_selection(self):
        gene = (0, 1, 2, 0, 1)
        changed = mutate(gene, 3, random.Random(1))
        self.assertEqual(sum(x != y for x, y in zip(gene, changed)), 1)
        self.assertEqual(len(mutate(gene, 3, random.Random(2), "swap")), len(gene))
        r = random.Random(10)
        winners = [roulette_select([(1,), (2,)], [0, 10], r) for _ in range(100)]
        self.assertEqual(winners, [(2,)] * 100)
        self.assertIn(roulette_select([(1,), (2,)], [0, 0], r), [(1,), (2,)])


class TestGA(unittest.TestCase):
    def test_reproducible_solution_elitism_and_goal_replay(self):
        cfg = GAConfig(population_size=24, chromosome_length=16,
                       generations=12, seed=18, elitism=2, immigrant_fraction=0.1)
        r1 = GeneticAlgorithm(TinyGrid(), 3, cfg).run()
        r2 = GeneticAlgorithm(TinyGrid(), 3, cfg).run()
        self.assertTrue(r1.found)
        self.assertEqual(r1.cost, r2.cost)
        self.assertEqual(r1.actions, r2.actions)
        self.assertEqual([x["best_fitness"] for x in r1.history],
                         [x["best_fitness"] for x in r2.history])
        self.assertTrue(all(a["best_fitness"] <= b["best_fitness"]
                            for a, b in zip(r1.history, r1.history[1:])))
        self.assertTrue(goal_test(TinyGrid(), 3, r1.actions))
        self.assertEqual(r1.cost, 6)

    def test_early_target_cost(self):
        cfg = GAConfig(population_size=20, chromosome_length=12,
                       generations=200, seed=1, target_cost=6)
        result = GeneticAlgorithm(TinyGrid(), 3, cfg).run()
        self.assertTrue(result.found)
        self.assertLess(result.generations_completed, cfg.generations)

    def test_offline_dashboard_from_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "comparison.csv"
            dash_path = Path(tmp) / "dashboard.html"
            rows = [dict(model_version="toy-test-v1", initial_code=3,
                         algorithm="genetic", status="found", found=1,
                         cost=6, action_count=2, elapsed_sec=.01, run_id=0),
                    dict(model_version="toy-test-v1", initial_code=3,
                         algorithm="ucs", status="timeout", found=0,
                         cost="", action_count="", elapsed_sec=.02, run_id=0)]
            write_rows(csv_path, rows, COLUMNS)
            build_dashboard(csv_path, None, dash_path)
            html = dash_path.read_text(encoding="utf-8")
            self.assertIn("Search Methods", html)
            self.assertIn("GENETIC", html)
            self.assertIn("UCS", html)
            self.assertIn("plotly", html.lower())


if __name__ == "__main__":
    unittest.main()
