"""Darwinian operators: fitness-proportionate selection and random variations."""
from __future__ import annotations
import random
from typing import Sequence

Chromosome = tuple[int, ...]


def scale_fitnesses(fitnesses: Sequence[float]) -> list[float]:
    """Fitness scaling for roulette selection (preserves ordering).

    A large goal bonus is essential for feasibility ranking, but if all solved
    values are near 100000, raw ratios would be nearly uniform even when route
    costs differ. Affine min-max scaling restores useful selection pressure.
    Invalid individuals keep weight zero; valid low-fitness individuals retain
    a small nonzero chance of reproduction.
    """
    if any(f < 0 for f in fitnesses):
        raise ValueError("fitness must be nonnegative")
    positives = [f for f in fitnesses if f > 0]
    if not positives:
        return [0.0] * len(fitnesses)
    lo, hi = min(positives), max(positives)
    if hi == lo:
        return [1.0 if f > 0 else 0.0 for f in fitnesses]
    return [(0.05 + (f - lo) / (hi - lo)) if f > 0 else 0.0
            for f in fitnesses]


def roulette_select(population: Sequence[Chromosome], fitnesses: Sequence[float],
                    rng: random.Random) -> Chromosome:
    """Select with replacement; larger fitness means larger selection probability."""
    if not population or len(population) != len(fitnesses):
        raise ValueError("population and fitnesses must be nonempty and equally sized")
    if any(f < 0 for f in fitnesses):
        raise ValueError("roulette selection requires non-negative fitness")
    total = sum(fitnesses)
    if total <= 0:
        return rng.choice(population)  # No division by zero when all are invalid.
    threshold = rng.random() * total
    cumulative = 0.0
    for genome, fitness in zip(population, fitnesses):
        cumulative += fitness
        if cumulative >= threshold:
            return genome
    return population[-1]


def crossover(a: Chromosome, b: Chromosome, rng: random.Random,
              method: str = "one_point") -> tuple[Chromosome, Chromosome]:
    """One-point (default) or two-point crossover; genome length is preserved."""
    if len(a) != len(b):
        raise ValueError("parents must have equal genome lengths")
    n = len(a)
    if n < 2:
        return a, b
    if method == "one_point":
        k = rng.randrange(1, n)
        return a[:k] + b[k:], b[:k] + a[k:]
    if method == "two_point":
        if n < 3:
            return crossover(a, b, rng, "one_point")
        i, j = sorted(rng.sample(range(1, n), 2))
        return (a[:i] + b[i:j] + a[j:],
                b[:i] + a[i:j] + b[j:])
    raise ValueError(f"unknown crossover method: {method}")


def mutate(genome: Chromosome, action_count: int, rng: random.Random,
           method: str = "replace") -> Chromosome:
    """Change one allele or swap two positions; never use a learned local policy."""
    if not genome:
        return genome
    if action_count < 1:
        raise ValueError("the model has no action IDs")
    values = list(genome)
    if method == "replace":
        i = rng.randrange(len(values))
        old = values[i]
        if action_count > 1 and 0 <= old < action_count:
            value = rng.randrange(action_count - 1)
            if value >= old:
                value += 1
        else:
            value = rng.randrange(action_count)
        values[i] = value
    elif method == "swap":
        if len(values) < 2:
            return genome
        i, j = rng.sample(range(len(values)), 2)
        values[i], values[j] = values[j], values[i]
    else:
        raise ValueError(f"unknown mutation method: {method}")
    return tuple(values)
