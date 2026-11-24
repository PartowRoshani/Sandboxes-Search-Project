"""Checks that timing and optional memory profiling use separate executions."""
import tracemalloc
import unittest

from genetic_alg.experiments import _memory_call, ga_run
from genetic_alg.core import GAConfig
from genetic_alg.tests.test_genetic import TinyGrid


class TestTimingSeparation(unittest.TestCase):
    def test_default_executes_once_without_tracing(self):
        observed = []

        def task():
            observed.append(tracemalloc.is_tracing())
            return len(observed)

        result, peak = _memory_call(task)
        self.assertEqual(result, 1)
        self.assertEqual(peak, "")
        self.assertEqual(observed, [False])

    def test_memory_run_is_separate_and_does_not_replace_timed_result(self):
        observed = []

        def task():
            observed.append(tracemalloc.is_tracing())
            holder = bytearray(1024 * 32)
            self.assertEqual(len(holder), 1024 * 32)
            return len(observed)

        result, peak = _memory_call(task, measure_memory=True)
        self.assertEqual(result, 1)  # First / untraced run is the result.
        self.assertEqual(observed, [False, True])
        self.assertGreaterEqual(peak, 1024 * 32)
        self.assertFalse(tracemalloc.is_tracing())

    def test_ga_run_records_untraced_time_and_missing_memory_as_blank(self):
        cfg = GAConfig(population_size=12, chromosome_length=12,
                       generations=3, seed=42)
        row, history, result = ga_run(TinyGrid(), 3, cfg)
        self.assertEqual(row["peak_python_bytes"], "")
        self.assertEqual(row["elapsed_sec"], round(result.elapsed_sec, 6))
        self.assertTrue(history)


if __name__ == "__main__":
    unittest.main()
