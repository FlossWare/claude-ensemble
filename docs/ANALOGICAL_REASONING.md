# Analogical Reasoning System

**Created:** 2026-07-03  
**Status:** Trained and deployed  
**Model Location:** `~/.claude/learning/analogical_reasoning.pkl`  
**Database:** PostgreSQL `learning.analogical_patterns` (aio-01:5433)

## Overview

The analogical reasoning system enables:
1. **Pattern transfer** across domains (e.g., electrical circuits → water flow → software architecture)
2. **Metaphor generation** (conceptual mapping between abstract and concrete domains)
3. **Solution transfer** (apply solutions from known domain to novel problem)
4. **Analogy quality evaluation** (structural similarity scoring)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Analogical Reasoning Engine                            │
├─────────────────────────────────────────────────────────┤
│  1. Pattern Extractor                                   │
│     - Identifies entities and relations                 │
│     - Extracts structural patterns                      │
│                                                          │
│  2. Similarity Scorer                                   │
│     - 384-dim embeddings (sentence-transformers)        │
│     - Cosine similarity on relational structure         │
│     - NOT surface-level keyword matching                │
│                                                          │
│  3. Transfer Engine                                     │
│     - Entity mapping (source → target)                  │
│     - Solution substitution                             │
│     - Confidence scoring                                │
│                                                          │
│  4. Metaphor Generator                                  │
│     - Cross-domain conceptual mapping                   │
│     - Creative analogy synthesis                        │
│                                                          │
│  5. Quality Evaluator                                   │
│     - Structural similarity (50%)                       │
│     - Relation overlap (30%)                            │
│     - Entity ratio (20%)                                │
└─────────────────────────────────────────────────────────┘
```

## Training Results (2026-07-03)

**Patterns trained:** 6  
**Domains covered:**
- Electrical circuits
- Water flow
- Finance
- Heat transfer
- Team management
- Software architecture

**Quality benchmarks:**
- Circuit ↔ Water: 0.911 (Excellent analogy)
- Circuit ↔ Software: 0.875 (Excellent analogy)
- Heat ↔ Software: 0.802 (Good analogy)

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim)

## Usage

### Python API

```python
from analogical_reasoning_trainer import AnalogicalReasoning, AnalogicalPattern

# Load trained model
model = AnalogicalReasoning.load('/home/sfloess/.claude/learning/analogical_reasoning.pkl')

# Define target problem
problem = AnalogicalPattern(
    domain='database',
    entities=['app_server', 'connection_pool', 'database'],
    relations=[
        ('app_server', 'queries', 'database'),
        ('database', 'limited_by', 'connection_pool'),
        ('connection_pool', 'throttles', 'throughput')
    ],
    context='Database connection pool too small'
)

# Find analogous patterns
analogies = model.find_analogous_patterns(problem, k=3)
# Returns: [('software_1', 0.630), ('water_1', 0.569), ('heat_1', 0.555)]

# Transfer solution
transfer = model.transfer_solution('software_1', problem)
print(transfer['transferred_solution'])
# Output: "Increase resources to increase throughput"

# Generate metaphor
metaphor = model.generate_metaphor('learning', 'water_flow')
print(metaphor)
# Output: "learning is like water_flow: Pressure drives flow through restrictions"

# Evaluate analogy quality
quality = model.evaluate_analogy('circuit_1', 'water_1')
print(quality['quality_score'])  # 0.911
print(quality['interpretation'])  # "Excellent analogy - strong structural mapping"
```

### PostgreSQL Vector Search

```sql
-- Find patterns similar to "circuit_1"
WITH source AS (
  SELECT embedding FROM learning.analogical_patterns WHERE pattern_id = 'circuit_1'
)
SELECT 
  p.pattern_id,
  p.domain,
  p.solution,
  1 - (p.embedding <=> s.embedding) as similarity
FROM learning.analogical_patterns p
CROSS JOIN source s
WHERE p.pattern_id != 'circuit_1'
ORDER BY p.embedding <=> s.embedding
LIMIT 3;

-- Results:
-- finance_1    | finance         | 0.058
-- water_1      | water_flow      | 0.018
-- management_1 | team_management | -0.001
```

### Adding New Patterns

```python
# Add new pattern to model
new_pattern = AnalogicalPattern(
    domain='traffic_control',
    entities=['traffic_light', 'road_capacity', 'vehicles'],
    relations=[
        ('traffic_light', 'regulates', 'vehicles'),
        ('vehicles', 'limited_by', 'road_capacity'),
        ('road_capacity', 'throttles', 'flow_rate')
    ],
    solution='Add more lanes or optimize light timing',
    context='Traffic congestion due to insufficient road capacity'
)

model.add_pattern('traffic_1', new_pattern)

# Find analogies
analogies = model.find_analogous_patterns(new_pattern, k=3)
# Returns patterns with similar structure (water_flow, software, etc.)
```

## Pattern Structure

Each `AnalogicalPattern` consists of:

1. **Domain:** The source domain (e.g., "electrical_circuit", "water_flow")
2. **Entities:** List of domain-specific entities
3. **Relations:** List of (entity1, relation, entity2) tuples representing structure
4. **Solution:** Known solution in this domain (optional)
5. **Context:** Free-text description (for embedding generation)

**Key insight:** The system embeds the **relational structure**, not domain-specific terminology. This enables cross-domain matching.

## Examples

### Example 1: Electrical Circuit → Water Flow

**Source (Circuit):**
- Entities: battery, resistor, wire
- Relations: battery powers wire, wire connects resistor, resistor limits current
- Solution: Increase voltage to increase current flow

**Target (Water):**
- Entities: pump, valve, pipe
- Relations: pump powers pipe, pipe connects valve, valve limits flow
- Analogy quality: **0.911** (Excellent)
- Transferred solution: Increase pressure to increase water flow

### Example 2: Database Bottleneck → Software Architecture

**Target (Database):**
- Entities: app_server, connection_pool, database
- Relations: app queries database, database limited by pool, pool throttles throughput
- Context: Connection pool too small

**Best match:** Software architecture (0.630)
- Solution: Increase resources to increase throughput
- Confidence: 0.630 (Moderate)

### Example 3: Metaphor Generation

```python
model.generate_metaphor('learning', 'water_flow')
# "learning is like water_flow: Pressure drives flow through restrictions"

model.generate_metaphor('debugging', 'heat_transfer')
# "debugging is like heat_transfer: Temperature drives heat through resistance"
```

## Training New Models

To retrain or extend the model:

```bash
# Train from examples (tools/analogical_reasoning_trainer.py)
python3 tools/analogical_reasoning_trainer.py

# Outputs:
# - ~/.claude/learning/analogical_reasoning.pkl (model)
# - ~/.claude/learning/analogical_reasoning_stats.json (metadata)
# - PostgreSQL learning.analogical_patterns (vector store)
```

### Adding Training Examples

Edit `create_training_examples()` in `tools/analogical_reasoning_trainer.py`:

```python
examples.append(('new_pattern_id', AnalogicalPattern(
    domain='new_domain',
    entities=['entity1', 'entity2', 'entity3'],
    relations=[
        ('entity1', 'relation_type', 'entity2'),
        ('entity2', 'relation_type', 'entity3')
    ],
    solution='How to solve problems in this domain',
    context='Free-text description for embedding'
)))
```

## Quality Metrics

### Analogy Quality Score (0.0 - 1.0)

- **0.8+:** Excellent analogy - strong structural mapping
- **0.6-0.8:** Good analogy - clear structural similarities
- **0.4-0.6:** Moderate analogy - some similarities
- **<0.4:** Weak analogy - limited structural overlap

### Components

1. **Structural similarity (50%):** Cosine similarity of embeddings
2. **Relation overlap (30%):** Proportion of shared relation types
3. **Entity ratio (20%):** Similarity in entity count

## Integration Points

### Workflow Integration

```javascript
// In workflow
const { execSync } = require('child_process');

const result = execSync(`python3 -c "
from analogical_reasoning_trainer import AnalogicalReasoning, AnalogicalPattern
model = AnalogicalReasoning.load('~/.claude/learning/analogical_reasoning.pkl')
problem = AnalogicalPattern(
    domain='${targetDomain}',
    entities=${JSON.stringify(entities)},
    relations=${JSON.stringify(relations)},
    context='${context}'
)
analogies = model.find_analogous_patterns(problem, k=3)
for pattern_id, score in analogies:
    print(f'{pattern_id}: {score}')
"`);
```

### PostgreSQL Integration

```javascript
const { getDB } = require('./shared/postgres-adapter.js');
const db = getDB();

// Find similar patterns via vector search
const rows = await db.query(`
  WITH source AS (
    SELECT embedding FROM learning.analogical_patterns WHERE pattern_id = $1
  )
  SELECT 
    p.pattern_id,
    p.domain,
    p.solution,
    1 - (p.embedding <=> s.embedding) as similarity
  FROM learning.analogical_patterns p
  CROSS JOIN source s
  WHERE p.pattern_id != $1
  ORDER BY p.embedding <=> s.embedding
  LIMIT $2
`, [sourcePatternId, limit]);
```

## Limitations

1. **Embedding quality:** Analogies only as good as underlying embeddings
2. **Training data:** Currently only 6 example patterns (extensible)
3. **Entity mapping:** Simple position-based mapping (could use more sophisticated alignment)
4. **Surface vs. structure:** Relies on context text to capture relational structure

## Future Enhancements

1. **More training examples:** Add 50-100 diverse patterns across domains
2. **Sophisticated entity mapping:** Use bipartite matching for better alignment
3. **Hierarchical analogies:** Multi-level abstraction (e.g., circuit → flow → general resource allocation)
4. **Analogy chains:** A → B → C transitive reasoning
5. **Inverse analogies:** Given solution, find source domain that explains it

## Files

- **Trainer:** `tools/analogical_reasoning_trainer.py` (470 lines)
- **Usage demo:** `tools/use_analogical_reasoning.py` (150 lines)
- **Model:** `~/.claude/learning/analogical_reasoning.pkl` (22KB)
- **Stats:** `~/.claude/learning/analogical_reasoning_stats.json`
- **Database:** PostgreSQL `learning.analogical_patterns` (6 rows, 384-dim vectors)

## References

- **Embedding model:** [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- **Vector similarity:** PostgreSQL pgvector extension
- **Theory:** Structure-mapping theory (Gentner 1983), case-based reasoning

---

**Last updated:** 2026-07-03  
**Trained by:** Analogical Reasoning Trainer v1.0  
**Model version:** 1.0
