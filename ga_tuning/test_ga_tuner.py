import copy

from ga_tuner import GAConfig, GeneticAlgorithm, Individual


class FakeEvaluator:
    def evaluate(self, parameters):
        return parameters["x"]


def make_ga(tmp_path, population):
    config = GAConfig(
        population_size=len(population),
        generations=1,
        crossover_rate=0.0,
        mutation_rate=1.0,
        tournament_k=2,
        seed=42,
        output_dir=str(tmp_path),
    )
    ga = GeneticAlgorithm(config)
    ga.evaluators = {"alpha": FakeEvaluator()}
    ga.get_parameter_bounds = lambda system: {"x": (0.0, 10.0)}
    ga.population = population
    return ga


def test_tournament_selection_is_system_scoped(tmp_path):
    ga = make_ga(
        tmp_path,
        [
            Individual("alpha", {"x": 1.0}, fitness=0.1),
            Individual("alpha", {"x": 2.0}, fitness=0.2),
            Individual("beta", {"x": 10.0}, fitness=100.0),
        ],
    )

    selected = ga.tournament_selection("alpha", k=2)

    assert selected.system_name == "alpha"


def test_crossover_without_crossover_clones_parents(tmp_path):
    ga = make_ga(
        tmp_path,
        [
            Individual("alpha", {"x": 2.0}, fitness=2.0),
            Individual("alpha", {"x": 1.0}, fitness=1.0),
        ],
    )
    parent1, parent2 = ga.population
    child1, child2 = ga.crossover(parent1, parent2)

    assert child1 is not parent1
    assert child2 is not parent2
    assert child1.parameters == parent1.parameters
    assert child2.parameters == parent2.parameters


def test_elite_is_preserved_unchanged(tmp_path):
    population = [
        Individual("alpha", {"x": 9.0}, fitness=9.0),
        Individual("alpha", {"x": 5.0}, fitness=5.0),
        Individual("alpha", {"x": 1.0}, fitness=1.0),
    ]
    ga = make_ga(tmp_path, population)
    elite_before = copy.deepcopy(population[0])

    ga.evolve(0)

    elite_after = next(ind for ind in ga.population if ind.parameters == {"x": 9.0})

    assert elite_after is not population[0]
    assert elite_after.parameters == elite_before.parameters
    assert elite_after.fitness == elite_before.fitness
    assert elite_after.generation == 1


def test_generation_preserves_system_population_sizes(tmp_path):
    population = [
        Individual("alpha", {"x": 1.0}, fitness=1.0),
        Individual("alpha", {"x": 2.0}, fitness=2.0),
        Individual("beta", {"x": 3.0}, fitness=3.0),
        Individual("beta", {"x": 4.0}, fitness=4.0),
    ]
    ga = make_ga(tmp_path, population)
    ga.evaluators["beta"] = FakeEvaluator()

    ga.evolve(0)

    assert sum(ind.system_name == "alpha" for ind in ga.population) == 2
    assert sum(ind.system_name == "beta" for ind in ga.population) == 2
