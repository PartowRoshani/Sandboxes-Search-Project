"""Regression tests for explicit selection and lethal mutation handling."""
import random
import unittest
from unittest.mock import patch
from genetic_alg.core import GAConfig, GeneticAlgorithm
from genetic_alg.operators import select_population
from genetic_alg.fitness import evaluate_sequence
from genetic_alg.tests.test_genetic import TinyGrid


class TestClassroom(unittest.TestCase):
    def test_mating_pool_size_and_sampling_with_replacement(self):
        pool = select_population([(0,), (1,)], [0, 100], random.Random(1), size=50)
        self.assertEqual(pool, [(1,)] * 50)

    def test_mating_pool_all_zero_is_defined(self):
        pool = select_population([(0,), (1,)], [0, 0], random.Random(1))
        self.assertEqual(len(pool), 2)
        self.assertTrue(all(p in [(0,), (1,)] for p in pool))

    def test_lethal_retry_from_original_child(self):
        ga = GeneticAlgorithm(TinyGrid(), 3, GAConfig(mutation_attempts=3))
        child = (0, 1, 2)
        with patch("genetic_alg.core.mutate", side_effect=[(0, 0, 2), (2, 1, 0)]) as m:
            result = ga._mutate_nonlethal(child, (child, child))
        self.assertEqual(result, (2, 1, 0))
        self.assertEqual([call.args[0] for call in m.call_args_list], [child, child])
        self.assertEqual(ga._mutation_trials, 2)
        self.assertEqual(ga._lethal_mutations, 1)
        self.assertEqual(ga._cache[(0, 0, 2)].fitness, 0)

    def test_retry_limit_falls_back_to_valid_original(self):
        ga = GeneticAlgorithm(TinyGrid(), 3, GAConfig(mutation_attempts=2))
        child = (0, 1, 2)
        with patch("genetic_alg.core.mutate", return_value=(0, 0, 2)) as m:
            result = ga._mutate_nonlethal(child, (child, child))
        self.assertEqual(m.call_count, 2)
        self.assertEqual(result, child)
        self.assertEqual(ga._mutation_fallbacks, 1)

    def test_invalid_crossover_child_fallback_uses_valid_parent(self):
        ga = GeneticAlgorithm(TinyGrid(), 3, GAConfig(mutation_attempts=1))
        with patch("genetic_alg.core.mutate", return_value=(0, 0, 2)):
            result = ga._mutate_nonlethal((0, 0, 2), ((0, 1, 2), (1, 1, 2)))
        self.assertEqual(result, (0, 1, 2))

    def test_odd_population_and_modes(self):
        for mode in ("classroom", "legacy"):
            cfg = GAConfig(population_size=11, chromosome_length=8, generations=8,
                           seed=9, evolution_mode=mode, mutation_rate=1)
            r = GeneticAlgorithm(TinyGrid(), 3, cfg).run()
            self.assertTrue(r.found)
            self.assertTrue(all(h["valid_count"] + h["invalid_count"] == 11 for h in r.history))
            self.assertTrue(evaluate_sequence(TinyGrid(), 3, r.actions).solved)
            self.assertEqual(r.history[-1]["mutation_trials"] > 0, mode == "classroom")

    def test_classroom_does_not_require_fitness_improvement(self):
        ga = GeneticAlgorithm(TinyGrid(), 3, GAConfig(mutation_attempts=1))
        child = (0, 1, 2)
        worse = (2, 0, 1)
        with patch("genetic_alg.core.mutate", return_value=worse):
            self.assertEqual(ga._mutate_nonlethal(child, (child, child)), worse)


if __name__ == "__main__":
    unittest.main()
