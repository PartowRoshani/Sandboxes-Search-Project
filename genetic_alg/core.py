"""A reproducible, generational genetic algorithm for the SandGrid problem."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from random import Random
from statistics import fmean, median
from time import perf_counter
from typing import Any
from .fitness import Evaluation, evaluate_sequence
from .operators import Chromosome, crossover, mutate, roulette_select, scale_fitnesses


@dataclass(frozen=True)
class GAConfig:
    population_size: int = 50
    chromosome_length: int = 50
    generations: int = 1000
    crossover_rate: float = 0.85
    mutation_rate: float = 0.30
    elitism: int = 2
    immigrant_fraction: float = 0.10
    crossover_method: str = "one_point"
    mutation_method: str = "replace"
    cost_transform: str = "log"
    conflict_mode: str = "occupied"
    seed: int = 42
    max_seconds: float | None = None
    target_cost: int | None = None

    def __post_init__(self):
        if self.population_size < 2:
            raise ValueError("population size must be >= 2")
        if self.chromosome_length < 1 or self.generations < 1:
            raise ValueError("chromosome length and generations must be positive")
        if not 0 <= self.elitism < self.population_size:
            raise ValueError("elitism must be in [0, population_size)")
        for name in ("crossover_rate", "mutation_rate", "immigrant_fraction"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be within [0,1]")
        if self.max_seconds is not None and self.max_seconds <= 0:
            raise ValueError("max_seconds must be positive")
        if self.target_cost is not None and self.target_cost < 0:
            raise ValueError("target_cost must be nonnegative")
        if self.crossover_method not in ("one_point", "two_point"):
            raise ValueError("invalid crossover method")
        if self.mutation_method not in ("replace", "swap"):
            raise ValueError("invalid mutation method")
        if self.cost_transform not in ("log", "linear", "sqrt", "none"):
            raise ValueError("invalid cost transform")
        if self.conflict_mode not in ("occupied", "half_units"):
            raise ValueError("invalid conflict mode")


@dataclass
class GAResult:
    found: bool
    status: str
    cost: int | None
    actions: list[int]
    fitness: float
    best_min_conflict: int
    best_cost_at_min_conflict: int
    generations_completed: int
    evaluations: int  # includes reused evaluations
    unique_evaluations: int
    elapsed_sec: float
    history: list[dict[str, Any]]
    config: GAConfig
    initial_code: int
    chromosome: Chromosome

    @property
    def action_count(self) -> int:
        return len(self.actions)

    def summary(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("history")
        return data


class GeneticAlgorithm:
    def __init__(self, model, initial_state: int, config: GAConfig | None = None):
        self.model = model
        self.initial_state = initial_state
        self.config = config or GAConfig()
        self.rng = Random(self.config.seed)
        self._cache: dict[Chromosome, Evaluation] = {}
        self._evaluations = 0
        if not model.actions:
            raise ValueError("model must have actions")

    def _evaluate(self, genome: Chromosome) -> Evaluation:
        self._evaluations += 1
        if genome not in self._cache:
            cfg = self.config
            self._cache[genome] = evaluate_sequence(
                self.model, self.initial_state, genome,
                conflict_mode=cfg.conflict_mode, cost_transform=cfg.cost_transform)
        return self._cache[genome]

    def random_genome(self) -> Chromosome:
        """Legal random rollout; unused genes after goal are random padding.

        Note: initial validity is built by random sampling of legal successors.
        Offspring are NOT repaired or learned (Darwinian GA). Their illegal
        sequences receive fitness zero during evaluation.
        """
        state = self.initial_state
        alleles: list[int] = []
        while len(alleles) < self.config.chromosome_length and not self.model.is_goal(state):
            options = list(self.model.successors(state))
            if not options:
                break
            next_state, action_id, _cost = self.rng.choice(options)
            alleles.append(action_id)
            state = next_state
        action_count = len(self.model.actions)
        while len(alleles) < self.config.chromosome_length:
            alleles.append(self.rng.randrange(action_count))
        return tuple(alleles)

    def run(self) -> GAResult:
        cfg = self.config
        start = perf_counter()
        population = [self.random_genome() for _ in range(cfg.population_size)]
        history: list[dict[str, Any]] = []
        incumbent_genome: Chromosome | None = None
        incumbent_eval: Evaluation | None = None
        completed = 0
        stopped_for_time = False
        stopped_for_target = False

        for generation in range(cfg.generations + 1):
            if generation > 0 and cfg.max_seconds is not None and perf_counter() - start >= cfg.max_seconds:
                stopped_for_time = True
                break
            evaluations = [self._evaluate(genome) for genome in population]
            fitnesses = [ev.fitness for ev in evaluations]
            ranked = sorted(range(len(population)),
                            key=lambda i: (evaluations[i].fitness, -evaluations[i].cost_at_min_conflict),
                            reverse=True)
            idx = ranked[0]
            best_eval = evaluations[idx]
            if incumbent_eval is None or best_eval.fitness > incumbent_eval.fitness:
                incumbent_eval = best_eval
                incumbent_genome = population[idx]
            solved = [ev for ev in evaluations if ev.solved]
            row = dict(generation=generation, best_fitness=best_eval.fitness,
                       mean_fitness=fmean(fitnesses), median_fitness=median(fitnesses),
                       best_cost=best_eval.path_cost if best_eval.solved else None,
                       best_min_conflict=best_eval.min_conflict,
                       best_cost_at_min_conflict=best_eval.cost_at_min_conflict,
                       solved_count=len(solved), valid_count=sum(e.valid for e in evaluations),
                       invalid_count=sum(not e.valid for e in evaluations),
                       unique_genomes=len(set(population)), elapsed_sec=perf_counter() - start)
            history.append(row)
            completed = generation
            if incumbent_eval.solved and cfg.target_cost is not None and incumbent_eval.path_cost <= cfg.target_cost:
                stopped_for_target = True
                break
            if generation == cfg.generations:
                break
            selection_weights = scale_fitnesses(fitnesses)
            next_population: list[Chromosome] = [population[i] for i in ranked[:cfg.elitism]]
            immigrants = min(cfg.population_size - len(next_population),
                             round(cfg.population_size * cfg.immigrant_fraction))
            # Select parents WITH replacement; two children per crossover.
            while len(next_population) < cfg.population_size - immigrants:
                parent_a = roulette_select(population, selection_weights, self.rng)
                parent_b = roulette_select(population, selection_weights, self.rng)
                if self.rng.random() < cfg.crossover_rate:
                    children = crossover(parent_a, parent_b, self.rng, cfg.crossover_method)
                else:
                    children = parent_a, parent_b
                for child in children:
                    if len(next_population) >= cfg.population_size - immigrants:
                        break
                    if self.rng.random() < cfg.mutation_rate:
                        child = mutate(child, len(self.model.actions), self.rng, cfg.mutation_method)
                    next_population.append(child)
            next_population.extend(self.random_genome() for _ in range(immigrants))
            population = next_population

        assert incumbent_eval is not None and incumbent_genome is not None
        # If goal was not found, the reported actions are only the prefix that
        # attained minimum conflict, not a claimed completed route.
        if incumbent_eval.solved:
            status = "found"
        elif stopped_for_time:
            status = "timeout"
        else:
            status = "not_found"
        return GAResult(
            found=incumbent_eval.solved, status=status,
            cost=incumbent_eval.path_cost if incumbent_eval.solved else None,
            actions=list(incumbent_eval.actions), fitness=incumbent_eval.fitness,
            best_min_conflict=incumbent_eval.min_conflict,
            best_cost_at_min_conflict=incumbent_eval.cost_at_min_conflict,
            generations_completed=completed, evaluations=self._evaluations,
            unique_evaluations=len(self._cache), elapsed_sec=perf_counter()-start,
            history=history, config=cfg, initial_code=self.initial_state,
            chromosome=incumbent_genome)
