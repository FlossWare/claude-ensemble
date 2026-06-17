# GA Testing Strategy for Fleet Orchestration

## Phase 1: Unit Tests (Validate Components)

### Test 1: Chromosome Creation & Serialization
```python
# ~/.claude/learning/tests/test_chromosome.py

def test_chromosome_creation():
    """Verify chromosome creates valid routing strategies"""
    
    chrome = FleetChromosome()
    
    # Check all genes present
    assert chrome.workers is not None
    assert chrome.arbiter is not None
    assert chrome.consensus in ['single', 'weighted', 'majority', 'rotating']
    assert 15000 <= chrome.timeout_ms <= 90000
    assert 2 <= chrome.num_workers <= 8
    assert len(chrome.host_preference) == 4
    
    # Check serialization
    data = chrome.to_dict()
    assert 'workers' in data
    assert 'arbiter' in data
    
    print("✅ Chromosome creation test passed")

def test_chromosome_validation():
    """Verify invalid chromosomes are rejected"""
    
    chrome = FleetChromosome()
    chrome.timeout_ms = -5000  # Invalid!
    
    # Should be clamped or error
    assert chrome.validate() == False or chrome.timeout_ms > 0
    
    print("✅ Chromosome validation test passed")
```

### Test 2: Crossover Produces Valid Children
```python
def test_crossover():
    """Verify crossover creates valid hybrid strategies"""
    
    parent1 = FleetChromosome()
    parent1.workers = [{"model": "phi3.5", "host": "server-01"}]
    parent1.arbiter = {"model": "qwen2.5", "host": "server-01"}
    parent1.fitness = 0.85
    
    parent2 = FleetChromosome()
    parent2.workers = [{"model": "mistral", "host": "server-03"}]
    parent2.arbiter = {"model": "phi3.5", "host": "server-03"}
    parent2.fitness = 0.72
    
    child = crossover(parent1, parent2)
    
    # Verify child has valid genes
    assert child.workers is not None
    assert child.arbiter is not None
    
    # Verify child inherits from both parents
    # (either phi3.5 or mistral should be present)
    models = [w['model'] for w in child.workers]
    assert 'phi3.5' in models or 'mistral' in models
    
    print("✅ Crossover test passed")

def test_crossover_preserves_better_parent():
    """Verify crossover prefers genes from fitter parent"""
    
    strong_parent = FleetChromosome()
    strong_parent.fitness = 0.92
    strong_parent.arbiter = {"model": "qwen2.5", "host": "server-03"}
    
    weak_parent = FleetChromosome()
    weak_parent.fitness = 0.45
    weak_parent.arbiter = {"model": "gemma3", "host": "aio-01"}
    
    child = crossover(strong_parent, weak_parent)
    
    # Child should favor strong parent's arbiter
    assert child.arbiter == strong_parent.arbiter
    
    print("✅ Crossover fitness preference test passed")
```

### Test 3: Mutation Changes Genes
```python
def test_mutation():
    """Verify mutation actually changes genes"""
    
    parent = FleetChromosome()
    parent.arbiter = {"model": "phi3.5", "host": "server-01"}
    parent.timeout_ms = 45000
    parent_dict = parent.to_dict()
    
    child = mutate(parent, mutation_rate=1.0)  # Force mutation
    child_dict = child.to_dict()
    
    # At least one gene should be different
    assert parent_dict != child_dict
    
    # But child should still be valid
    assert child.validate()
    
    print("✅ Mutation test passed")

def test_mutation_stays_in_bounds():
    """Verify mutations don't create invalid values"""
    
    parent = FleetChromosome()
    parent.timeout_ms = 90000  # Max value
    
    for _ in range(100):  # Try 100 mutations
        child = mutate(parent)
        assert 15000 <= child.timeout_ms <= 90000
        assert 2 <= child.num_workers <= 8
    
    print("✅ Mutation bounds test passed")
```

### Test 4: Fitness Calculation
```python
def test_fitness_calculation():
    """Verify fitness rewards good strategies"""
    
    # Mock execution results
    good_results = {
        'success_rate': 0.95,
        'avg_duration': 2000,  # 2s - fast
        'avg_quality': 0.90,
        'total_cost': 0.01  # cheap
    }
    
    bad_results = {
        'success_rate': 0.45,
        'avg_duration': 10000,  # 10s - slow
        'avg_quality': 0.50,
        'total_cost': 0.10  # expensive
    }
    
    good_fitness = calculate_fitness_from_results(good_results)
    bad_fitness = calculate_fitness_from_results(bad_results)
    
    # Good should be much higher than bad
    assert good_fitness > bad_fitness * 2
    
    print(f"✅ Fitness calculation test passed")
    print(f"   Good strategy: {good_fitness:.2f}")
    print(f"   Bad strategy:  {bad_fitness:.2f}")
```

---

## Phase 2: Integration Tests (Graph + PostgreSQL)

### Test 5: Store/Retrieve from Graph
```python
def test_graph_storage():
    """Verify chromosomes stored in AGE graph"""
    
    chrome = FleetChromosome()
    chrome.id = 'test-strategy-001'
    chrome.fitness = 0.75
    
    # Store in graph
    store_in_graph(chrome)
    
    # Retrieve
    conn = psycopg2.connect(host='aio-01', database='learning', ...)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM cypher('ga_evolution', $$
          MATCH (s:Strategy {id: $id})
          RETURN s.fitness as fitness
        $$) as (fit agtype)
    """, {'id': 'test-strategy-001'})
    
    retrieved_fitness = cur.fetchone()[0]
    
    assert abs(retrieved_fitness - 0.75) < 0.001
    
    print("✅ Graph storage test passed")

def test_parent_relationships():
    """Verify parent-child relationships in graph"""
    
    parent1 = create_test_chromosome('parent1', fitness=0.80)
    parent2 = create_test_chromosome('parent2', fitness=0.75)
    
    child = crossover(parent1, parent2)
    store_child_in_graph(child, parent1, parent2, 'crossover')
    
    # Query graph for parents
    cur.execute("""
        SELECT * FROM cypher('ga_evolution', $$
          MATCH (p1)-[:PARENT_OF {type: 'crossover'}]->(child {id: $id})
          RETURN p1.id as parent_id
        $$) as (pid agtype)
    """, {'id': child.id})
    
    parent_ids = [r[0] for r in cur.fetchall()]
    
    assert 'parent1' in parent_ids
    assert 'parent2' in parent_ids
    
    print("✅ Parent relationships test passed")
```

---

## Phase 3: Evolutionary Tests (GA Algorithm)

### Test 6: Population Evolves Over Generations
```python
def test_evolution_improves_fitness():
    """Verify GA actually improves fitness over time"""
    
    # Create initial population (all random, low fitness)
    ga = FleetGeneticOptimizer()
    ga.create_random_population(size=20)
    
    # Mock fitness evaluations (simulate execution)
    gen0_avg = get_average_fitness(ga.population)
    
    # Evolve for 3 generations
    for gen in range(3):
        ga.evolve_one_generation()
    
    gen3_avg = get_average_fitness(ga.population)
    
    # Gen3 should be better than Gen0
    assert gen3_avg > gen0_avg
    
    print(f"✅ Evolution improvement test passed")
    print(f"   Gen0 avg fitness: {gen0_avg:.2f}")
    print(f"   Gen3 avg fitness: {gen3_avg:.2f}")
    print(f"   Improvement: {((gen3_avg / gen0_avg - 1) * 100):.1f}%")

def test_elitism_preserves_best():
    """Verify elite strategies survive to next gen"""
    
    ga = FleetGeneticOptimizer()
    ga.create_random_population(size=20)
    
    # Set one strategy as very fit
    ga.population[0].fitness = 0.99
    best_id = ga.population[0].id
    
    # Evolve
    ga.evolve_one_generation()
    
    # Best should still exist
    ids = [c.id for c in ga.population]
    assert best_id in ids
    
    print("✅ Elitism test passed")

def test_diversity_maintained():
    """Verify population doesn't converge too quickly"""
    
    ga = FleetGeneticOptimizer()
    ga.create_random_population(size=20)
    
    # Evolve 5 generations
    for _ in range(5):
        ga.evolve_one_generation()
    
    # Check diversity (should have different strategies)
    unique_arbiters = set(c.arbiter['model'] for c in ga.population)
    unique_consensus = set(c.consensus for c in ga.population)
    
    # Should have at least 2 different arbiters and 2 consensus types
    assert len(unique_arbiters) >= 2
    assert len(unique_consensus) >= 2
    
    print(f"✅ Diversity test passed")
    print(f"   Unique arbiters: {len(unique_arbiters)}")
    print(f"   Unique consensus: {len(unique_consensus)}")
```

---

## Phase 4: End-to-End Tests (Real Fleet Execution)

### Test 7: Execute Real Task with Chromosome
```python
def test_real_execution():
    """Execute actual task on fleet with GA chromosome"""
    
    chrome = FleetChromosome()
    chrome.workers = [{"model": "phi3.5", "host": "server-01"}]
    chrome.arbiter = {"model": "qwen2.5-coder", "host": "server-01"}
    chrome.num_workers = 2
    chrome.timeout_ms = 30000
    
    # Simple test task
    task = {
        'type': 'code',
        'prompt': 'Python: print hello world',
        'expected': 'print'
    }
    
    # Execute
    result = execute_with_chromosome(task, chrome)
    
    # Verify result
    assert result is not None
    assert 'outcome' in result
    assert result['outcome'] in ['success', 'failure']
    
    # Verify logged to PostgreSQL
    cur.execute("""
        SELECT COUNT(*) FROM monitoring.execution_summary
        WHERE workflow = 'ga_test'
          AND timestamp > NOW() - INTERVAL '1 minute'
    """)
    
    count = cur.fetchone()[0]
    assert count > 0
    
    print(f"✅ Real execution test passed")
    print(f"   Result: {result['outcome']}")
    print(f"   Duration: {result.get('duration_ms', 0)}ms")
```

### Test 8: Full GA Cycle (Mini Version)
```python
def test_full_ga_mini():
    """Run complete GA with small population on real tasks"""
    
    print("\n=== MINI GA TEST ===")
    print("Population: 5 strategies")
    print("Generations: 2")
    print("Tasks per eval: 3")
    print()
    
    ga = FleetGeneticOptimizer()
    ga.population_size = 5
    
    # Create initial population
    ga.create_random_population(size=5)
    
    # Evolve 2 generations
    best = ga.evolve(generations=2, tasks_per_eval=3)
    
    # Verify we got a result
    assert best is not None
    assert best.fitness > 0
    
    # Verify lineage in graph
    lineage = ga.get_lineage(best.id)
    assert len(lineage) > 0
    
    print(f"✅ Full GA mini test passed")
    print(f"   Best fitness: {best.fitness:.2f}")
    print(f"   Lineage depth: {len(lineage)}")
    
    return best
```

---

## Phase 5: Performance Tests

### Test 9: Thompson Sampling + GA Integration
```python
def test_thompson_ga_integration():
    """Verify GA strategies integrate with Thompson Sampling"""
    
    # Initialize both systems
    thompson = ThompsonSampling()
    ga = FleetGeneticOptimizer()
    
    # Run 20 tasks with Thompson only
    for i in range(20):
        strategy = thompson.select()
        result = mock_execute(strategy)
        thompson.update(strategy, result)
    
    thompson_only_avg = get_average_quality(thompson)
    
    # Evolve GA and inject best
    best_ga = ga.evolve(generations=2, tasks_per_eval=3)
    thompson.add_strategy(best_ga.id, best_ga.to_dict())
    
    # Run 20 more tasks
    for i in range(20):
        strategy = thompson.select()
        result = mock_execute(strategy)
        thompson.update(strategy, result)
    
    thompson_with_ga_avg = get_average_quality(thompson)
    
    # With GA should be equal or better
    assert thompson_with_ga_avg >= thompson_only_avg
    
    print(f"✅ Thompson + GA integration test passed")
    print(f"   Thompson only: {thompson_only_avg:.2f}")
    print(f"   Thompson + GA: {thompson_with_ga_avg:.2f}")
```

### Test 10: Benchmark Performance Over Time
```python
def test_performance_progression():
    """Verify system improves over 100 tasks"""
    
    orchestrator = GAEnhancedOrchestrator()
    
    results_by_bucket = {
        'tasks_1_25': [],
        'tasks_26_50': [],
        'tasks_51_75': [],
        'tasks_76_100': []
    }
    
    # Run 100 tasks
    for task_num in range(1, 101):
        task = generate_test_task()
        result = orchestrator.route(task)
        
        # Bucket results
        if task_num <= 25:
            results_by_bucket['tasks_1_25'].append(result)
        elif task_num <= 50:
            results_by_bucket['tasks_26_50'].append(result)
        elif task_num <= 75:
            results_by_bucket['tasks_51_75'].append(result)
        else:
            results_by_bucket['tasks_76_100'].append(result)
    
    # Calculate averages
    avgs = {}
    for bucket, results in results_by_bucket.items():
        success_rate = sum(1 for r in results if r['success']) / len(results)
        avg_duration = sum(r['duration'] for r in results) / len(results)
        avgs[bucket] = {'success': success_rate, 'duration': avg_duration}
    
    # Verify improvement trend
    assert avgs['tasks_76_100']['success'] >= avgs['tasks_1_25']['success']
    
    print(f"✅ Performance progression test passed")
    print(f"   Tasks 1-25:   {avgs['tasks_1_25']['success']:.0%} success")
    print(f"   Tasks 76-100: {avgs['tasks_76_100']['success']:.0%} success")
```

---

## Test Execution Plan

**Order of execution:**

```bash
# 1. Unit tests (fast, no fleet needed)
pytest ~/.claude/learning/tests/test_chromosome.py
pytest ~/.claude/learning/tests/test_crossover.py
pytest ~/.claude/learning/tests/test_mutation.py
pytest ~/.claude/learning/tests/test_fitness.py

# 2. Integration tests (require PostgreSQL + AGE)
pytest ~/.claude/learning/tests/test_graph.py
pytest ~/.claude/learning/tests/test_relationships.py

# 3. Evolution tests (require graph, mock execution)
pytest ~/.claude/learning/tests/test_evolution.py
pytest ~/.claude/learning/tests/test_elitism.py

# 4. End-to-end tests (require full fleet)
pytest ~/.claude/learning/tests/test_real_execution.py
pytest ~/.claude/learning/tests/test_full_ga.py

# 5. Performance tests (longest, ~30 minutes)
pytest ~/.claude/learning/tests/test_integration.py
pytest ~/.claude/learning/tests/test_performance.py -v
```

**Timeline:**
- Unit tests: ~2 minutes
- Integration tests: ~5 minutes
- Evolution tests: ~10 minutes
- End-to-end tests: ~15 minutes
- Performance tests: ~30 minutes
**Total: ~1 hour**

---

## Success Criteria

**Tests must demonstrate:**

✅ **Correctness:**
- Chromosomes create valid routing strategies
- Crossover produces viable children
- Mutations stay within bounds
- Graph relationships are correct

✅ **Evolution:**
- Fitness improves over generations
- Elite strategies survive
- Diversity is maintained
- Best strategies found in <10 generations

✅ **Integration:**
- GA strategies work with Thompson Sampling
- Real fleet executions succeed
- PostgreSQL logging works
- Graph queries are fast (<100ms)

✅ **Performance:**
- Success rate improves 10%+ after GA
- Speed improves or stays same
- System reaches 80%+ success by task 200

**If all tests pass → Deploy to production!**
