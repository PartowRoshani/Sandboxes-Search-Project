"""Genetic search extension for the existing sandgrid model (no core changes)."""
from .core import GAConfig, GeneticAlgorithm, GAResult
from .fitness import Evaluation, evaluate_sequence, goal_test, conflict_number, fitness_function

__all__ = ["GAConfig", "GeneticAlgorithm", "GAResult", "Evaluation", "evaluate_sequence", "goal_test", "conflict_number", "fitness_function"]
