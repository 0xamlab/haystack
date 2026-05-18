"""
genetic.mojo — Genetic algorithm optimizer. Zero Python imports.

Replaces DEAP with pure Mojo implementations for population-based
evolutionary optimization with tournament selection, crossover,
Gaussian mutation, and elitism.

Public API:
  Individual               — Genes + fitness
  GAConfig                 — GA hyperparameters
  initialize_population    — Random population within bounds
  tournament_select        — Tournament selection
  crossover_uniform        — Uniform crossover
  crossover_single_point   — Single-point crossover
  mutate_gaussian          — Gaussian mutation with clamping
  evolve_one_generation    — One generation step
  run_ga                   — Full GA run
  best_individual          — Return fittest individual
"""
from std.math import sqrt, abs as fabs, log
from std.random import random_float64


# ── Constants ─────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793


# ── Box-Muller normal RNG ────────────────────────────────────────────────────


fn _randn() -> Float64:
    """Standard normal variate via Box-Muller."""
    var u1 = random_float64()
    var u2 = random_float64()
    if u1 < 1e-15:
        u1 = 1e-15
    var r = sqrt(-2.0 * log(u1))
    var theta = 2.0 * PI * u2
    # cos via Taylor
    var v = theta
    while v > PI:
        v -= 2.0 * PI
    while v < -PI:
        v += 2.0 * PI
    var x2 = v * v
    var x4 = x2 * x2
    var x6 = x4 * x2
    var x8 = x6 * x2
    var x10 = x8 * x2
    var cosv = 1.0 - x2 / 2.0 + x4 / 24.0 - x6 / 720.0 + x8 / 40320.0 - x10 / 3628800.0
    return r * cosv


# ── Individual struct ────────────────────────────────────────────────────────


struct Individual(Copyable, Movable):
    """An individual with genes and fitness."""

    var genes: List[Float64]
    var fitness: Float64

    fn __init__(out self, genes: List[Float64], fitness: Float64):
        self.genes = genes.copy()
        self.fitness = fitness


# ── GAConfig struct ──────────────────────────────────────────────────────────


struct GAConfig(Copyable, Movable):
    """Configuration for the genetic algorithm."""

    var population_size: Int
    var n_genes: Int
    var mutation_rate: Float64
    var crossover_rate: Float64
    var elitism: Int
    var gene_min: Float64
    var gene_max: Float64

    fn __init__(out self, population_size: Int, n_genes: Int,
                mutation_rate: Float64, crossover_rate: Float64,
                elitism: Int, gene_min: Float64, gene_max: Float64):
        self.population_size = population_size
        self.n_genes = n_genes
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism = elitism
        self.gene_min = gene_min
        self.gene_max = gene_max


# ── Evaluation functions ─────────────────────────────────────────────────────


fn _evaluate(ind: Individual, eval_fn_id: Int) -> Float64:
    """Built-in evaluation. id==0: fitness = -sum((gene_i - i)^2)."""
    if eval_fn_id == 0:
        var s: Float64 = 0.0
        for i in range(len(ind.genes)):
            var diff = ind.genes[i] - Float64(i)
            s += diff * diff
        return -s
    return 0.0


# ── initialize_population ───────────────────────────────────────────────────


fn initialize_population(config: GAConfig) -> List[Individual]:
    """Create random population within [gene_min, gene_max]."""
    var pop = List[Individual]()
    var rng = config.gene_max - config.gene_min
    for _ in range(config.population_size):
        var genes = List[Float64]()
        for _ in range(config.n_genes):
            genes.append(config.gene_min + random_float64() * rng)
        pop.append(Individual(genes^, 0.0))
    return pop^


# ── tournament_select ────────────────────────────────────────────────────────


fn tournament_select(population: List[Individual], tournament_size: Int) -> Individual:
    """Tournament selection: pick best from random subset."""
    var n = len(population)
    var best_idx = Int(random_float64() * Float64(n))
    if best_idx >= n:
        best_idx = n - 1
    var best_fit = population[best_idx].fitness
    for _ in range(1, tournament_size):
        var idx = Int(random_float64() * Float64(n))
        if idx >= n:
            idx = n - 1
        if population[idx].fitness > best_fit:
            best_idx = idx
            best_fit = population[idx].fitness
    var g = List[Float64]()
    for i in range(len(population[best_idx].genes)):
        g.append(population[best_idx].genes[i])
    return Individual(g^, population[best_idx].fitness)


# ── crossover_uniform ────────────────────────────────────────────────────────


fn crossover_uniform(parent1: Individual, parent2: Individual, rate: Float64) -> Individual:
    """Uniform crossover: each gene randomly from either parent."""
    var genes = List[Float64]()
    for i in range(len(parent1.genes)):
        if random_float64() < rate:
            genes.append(parent2.genes[i])
        else:
            genes.append(parent1.genes[i])
    return Individual(genes^, 0.0)


# ── crossover_single_point ──────────────────────────────────────────────────


fn crossover_single_point(parent1: Individual, parent2: Individual) -> Individual:
    """Single-point crossover at random split."""
    var n = len(parent1.genes)
    var point = Int(random_float64() * Float64(n))
    if point >= n:
        point = n - 1
    if point < 1:
        point = 1
    var genes = List[Float64]()
    for i in range(point):
        genes.append(parent1.genes[i])
    for i in range(point, n):
        genes.append(parent2.genes[i])
    return Individual(genes^, 0.0)


# ── mutate_gaussian ──────────────────────────────────────────────────────────


fn mutate_gaussian(mut ind: Individual, rate: Float64, sigma: Float64,
                   gene_min: Float64, gene_max: Float64):
    """Gaussian mutation: each gene has `rate` probability of adding N(0, sigma)."""
    for i in range(len(ind.genes)):
        if random_float64() < rate:
            var v = ind.genes[i] + _randn() * sigma
            if v < gene_min:
                v = gene_min
            if v > gene_max:
                v = gene_max
            ind.genes[i] = v


# ── best_individual ──────────────────────────────────────────────────────────


fn best_individual(population: List[Individual]) -> Individual:
    """Return individual with highest fitness."""
    var best_idx = 0
    var best_fit = population[0].fitness
    for i in range(1, len(population)):
        if population[i].fitness > best_fit:
            best_fit = population[i].fitness
            best_idx = i
    var g = List[Float64]()
    for i in range(len(population[best_idx].genes)):
        g.append(population[best_idx].genes[i])
    return Individual(g^, population[best_idx].fitness)


# ── _sort_by_fitness (descending) ────────────────────────────────────────────


fn _sort_by_fitness(mut pop: List[Individual]):
    """Insertion sort population by fitness descending."""
    var n = len(pop)
    for i in range(1, n):
        var key_fit = pop[i].fitness
        var key_genes = List[Float64]()
        for g in range(len(pop[i].genes)):
            key_genes.append(pop[i].genes[g])
        var j = i - 1
        while j >= 0 and pop[j].fitness < key_fit:
            # shift
            var sg = List[Float64]()
            for g in range(len(pop[j].genes)):
                sg.append(pop[j].genes[g])
            pop[j + 1] = Individual(sg^, pop[j].fitness)
            j -= 1
        pop[j + 1] = Individual(key_genes^, key_fit)


# ── evolve_one_generation ────────────────────────────────────────────────────


fn evolve_one_generation(population: List[Individual], config: GAConfig,
                         eval_fn_id: Int) -> List[Individual]:
    """One generation: evaluate, sort, elitism, fill via selection+crossover+mutation."""
    # Evaluate all
    var pop = List[Individual]()
    for i in range(len(population)):
        var g = List[Float64]()
        for j in range(len(population[i].genes)):
            g.append(population[i].genes[j])
        var ind = Individual(g^, 0.0)
        ind.fitness = _evaluate(ind, eval_fn_id)
        pop.append(ind^)

    _sort_by_fitness(pop)

    var new_pop = List[Individual]()
    # Keep elites
    var elite_count = config.elitism
    if elite_count > len(pop):
        elite_count = len(pop)
    for i in range(elite_count):
        var g = List[Float64]()
        for j in range(len(pop[i].genes)):
            g.append(pop[i].genes[j])
        new_pop.append(Individual(g^, pop[i].fitness))

    # Fill rest
    while len(new_pop) < config.population_size:
        var p1 = tournament_select(pop, 3)
        var p2 = tournament_select(pop, 3)
        var child: Individual
        if random_float64() < config.crossover_rate:
            child = crossover_uniform(p1, p2, 0.5)
        else:
            var cg = List[Float64]()
            for j in range(len(p1.genes)):
                cg.append(p1.genes[j])
            child = Individual(cg^, 0.0)
        mutate_gaussian(child, config.mutation_rate, 0.5, config.gene_min, config.gene_max)
        child.fitness = _evaluate(child, eval_fn_id)
        new_pop.append(child^)

    return new_pop^


# ── run_ga ───────────────────────────────────────────────────────────────────


fn run_ga(config: GAConfig, n_generations: Int, eval_fn_id: Int = 0) -> Individual:
    """Run full GA for n_generations, return best individual."""
    var pop = initialize_population(config)
    # Initial evaluation
    for i in range(len(pop)):
        pop[i].fitness = _evaluate(pop[i], eval_fn_id)

    for _ in range(n_generations):
        pop = evolve_one_generation(pop, config, eval_fn_id)

    return best_individual(pop)
