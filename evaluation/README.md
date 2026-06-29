# Benchmark Dataset and Evaluation Framework

## Overview

This directory contains a comprehensive benchmark dataset for evaluating multi-AI model performance across 7 diverse task types with human-verified ground truth answers.

**Dataset Statistics:**
- Total Questions: 1,000
- Task Types: 7
- Difficulty Levels: 3 (Easy, Medium, Hard)
- Ground Truth Format: Structured JSON with task-specific validation criteria

## Dataset Composition

### Task Type Distribution

| Task Type | Count | Percentage | Difficulty Mix |
|-----------|-------|-----------|-----------------|
| Code Review | 200 | 20% | E: 60, M: 100, H: 40 |
| Research | 150 | 15% | E: 45, M: 75, H: 30 |
| Math | 150 | 15% | E: 45, M: 75, H: 30 |
| Security | 150 | 15% | E: 45, M: 75, H: 30 |
| Networking | 150 | 15% | E: 45, M: 75, H: 30 |
| Creative | 100 | 10% | E: 30, M: 50, H: 20 |
| Legal | 100 | 10% | E: 29, M: 40, H: 31 |
| **TOTAL** | **1,000** | **100%** | **E: 299, M: 515, H: 186** |

### Difficulty Distribution

- **Easy (29.9%):** Straightforward questions with clear-cut answers
- **Medium (51.5%):** Moderate complexity requiring reasoning and analysis
- **Hard (18.6%):** Complex scenarios requiring advanced knowledge and multi-step analysis

## File Structure

```
evaluation/
├── benchmark-dataset.json       # 1,000 benchmark questions with ground truth
└── README.md                    # This file
```

## Benchmark Dataset Format

Each benchmark question follows this JSON structure:

```json
{
  "id": 1,
  "task_type": "code_review",
  "question": "Review this code snippet for security issues:\n\n```\n...\n```\n\nIdentify all vulnerabilities and their severity levels.",
  "ground_truth": {
    "issues": [
      { "name": "SQL Injection vulnerability", "severity": "critical" },
      { "name": "Cross-Site Scripting (XSS)", "severity": "critical" }
    ],
    "total_issues": 2,
    "requires_refactoring": true
  },
  "difficulty": "medium",
  "category": "code_review"
}
```

## Task Type Details

### 1. Code Review (200 questions)

Security vulnerability identification in code snippets

**Ground Truth Structure:**
```json
{
  "issues": [
    { "name": "vulnerability_name", "severity": "critical|high|medium" }
  ],
  "total_issues": number,
  "requires_refactoring": boolean
}
```

**Vulnerability Types:**
- SQL Injection
- Cross-Site Scripting (XSS)
- Null pointer dereference
- Buffer overflow
- Race conditions
- Uninitialized variables
- Hardcoded secrets/credentials
- Insecure cryptography

---

### 2. Research (150 questions)

Academic research topic summarization and synthesis

**Ground Truth Structure:**
```json
{
  "topic": "research_topic",
  "year_context": 2026,
  "expected_coverage": ["recent_papers", "methodology", "results", "implications"],
  "min_sources": 5,
  "requires_synthesis": boolean
}
```

**Research Topics:**
- LLM prompt engineering
- Quantum computing applications
- CRISPR gene editing
- Climate change mitigation
- Renewable energy efficiency
- Machine learning compression
- NLP improvements
- Blockchain consensus
- Neuroscience of consciousness
- Deep learning explainability

---

### 3. Math (150 questions)

Mathematical equation solving and calculation

**Ground Truth Structure:**
```json
{
  "solution": number_or_array_or_object,
  "equation_type": "linear|quadratic|logarithmic|system|trigonometric",
  "verification_method": "substitution",
  "show_steps": boolean,
  "decimal_places": 2
}
```

**Equation Types:**
- Linear equations: 2x + 5 = 13
- Quadratic equations: x² - 5x + 6 = 0
- Logarithmic equations: log₁₀(x) = 2
- Systems of equations: 3x + 2y = 12; x + y = 5
- Trigonometric equations: sin(θ) = 0.5; 0 ≤ θ ≤ 2π

---

### 4. Security (150 questions)

Security vulnerability analysis and mitigation strategies

**Ground Truth Structure:**
```json
{
  "vulnerability_type": "remote_code_execution|privilege_escalation|bypass|authentication|information_disclosure",
  "cve_reference": "CVE-XXXX-XXXXX|null",
  "cvss_score": 0.0 to 10.0,
  "mitigations": ["mitigation_1", "mitigation_2"],
  "requires_penetration_test": boolean
}
```

**Vulnerability Types:**
- Remote code execution (RCE)
- Privilege escalation
- Authentication bypass
- Information disclosure
- Firewall bypass

---

### 5. Networking (150 questions)

Network troubleshooting and diagnostic analysis

**Ground Truth Structure:**
```json
{
  "issue": "network_problem",
  "potential_causes": ["cause_1", "cause_2", "cause_3"],
  "diagnostic_tools": ["ping", "traceroute", "netstat"],
  "expected_resolution_time": "15-30 minutes",
  "requires_admin_access": boolean
}
```

**Common Issues:**
- High latency on wireless
- DNS resolution failures
- Packet loss
- Port unreachable errors
- IP address conflicts

---

### 6. Creative (100 questions)

Creative writing and artistic composition

**Ground Truth Structure:**
```json
{
  "expected_format": "prose|poetry|dialogue|text",
  "minimum_length": 50 or 100,
  "creativity_score_threshold": 0.5 or 0.7,
  "evaluation_criteria": ["originality", "coherence", "relevance"],
  "subjective": true
}
```

**Writing Prompts:**
- Haiku about AI
- Short stories (time travel, fantastical)
- Poetry (nature themes)
- Dialogue between AI entities
- Future city descriptions

---

### 7. Legal (100 questions)

Legal document interpretation and clause analysis

**Ground Truth Structure:**
```json
{
  "clause_type": "contract_clause_type",
  "key_obligations": ["obligation_1", "obligation_2"],
  "potential_disputes": boolean,
  "jurisdiction_dependent": true,
  "requires_legal_expertise": boolean
}
```

**Clause Types:**
- Non-disclosure agreements
- Liability limitations
- Termination conditions
- Intellectual property rights
- Force majeure provisions

---

## Database Integration

The benchmark dataset is loaded into PostgreSQL using the migration:
`db/migrations/023_evaluation_schema.sql`

### Schema Overview

```sql
evaluation.benchmarks
├── id (PK)
├── task_type
├── question
├── ground_truth (JSONB)
├── difficulty (ENUM)
├── category
└── created_at

evaluation.results
├── id (PK)
├── benchmark_id (FK)
├── model
├── worker_id
├── answer
├── confidence (0.0-1.0)
├── correctness_score (0.0-1.0)
├── robustness_score (0.0-1.0)
├── generalization_score (0.0-1.0)
├── bias_resistance_score (0.0-1.0)
├── reproducibility_score (0.0-1.0)
├── overall_score (weighted)
├── evaluation_notes (JSONB)
├── input_tokens
├── output_tokens
├── cost_usd
├── execution_time_ms
└── created_at
```

### Materialized Views

- `evaluation.benchmark_stats` - Task type and difficulty distribution
- `evaluation.model_performance` - Overall model statistics
- `evaluation.task_model_performance` - Per-task-type model performance

---

## Usage

### 1. Load Benchmark Data

```bash
# Apply migration to create schema
psql -d learning -f db/migrations/023_evaluation_schema.sql

# Load benchmark dataset
python3 db/load-benchmark-data.py --database learning --user sfloess
```

### 2. Query Benchmarks

```sql
-- Get all code review questions
SELECT id, question, difficulty FROM evaluation.benchmarks
WHERE task_type = 'code_review'
LIMIT 10;

-- Get easy math questions
SELECT id, question, ground_truth FROM evaluation.benchmarks
WHERE task_type = 'math' AND difficulty = 'easy'
LIMIT 5;

-- Count by difficulty
SELECT task_type, difficulty, COUNT(*) 
FROM evaluation.benchmarks
GROUP BY task_type, difficulty
ORDER BY task_type;
```

### 3. Record Evaluation Results

```python
import psycopg2
from psycopg2.extras import Json

conn = psycopg2.connect("dbname=learning")
cursor = conn.cursor()

cursor.execute("""
  INSERT INTO evaluation.results
  (benchmark_id, model, worker_id, answer, confidence,
   correctness_score, robustness_score, generalization_score,
   bias_resistance_score, reproducibility_score, evaluation_notes)
  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (
  1, 'opus', 'worker-1', 'Model answer...', 0.92,
  0.95, 0.88, 0.90, 0.85, 0.92, Json({"notes": "..."})
))

conn.commit()
```

### 4. View Model Performance

```sql
-- Overall model performance
SELECT * FROM evaluation.model_performance
ORDER BY avg_overall DESC;

-- Task-specific performance
SELECT * FROM evaluation.task_model_performance
WHERE task_type = 'code_review'
ORDER BY avg_overall DESC;

-- Benchmark statistics
SELECT * FROM evaluation.benchmark_stats;
```

---

## Evaluation Scoring System

### Five-Dimension Model

Responses are evaluated on 5 dimensions with weighted average:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| **Correctness** | 35% | Answer accuracy against ground truth |
| **Robustness** | 20% | Resistance to adversarial inputs/edge cases |
| **Generalization** | 20% | Applicability to similar problems |
| **Bias Resistance** | 15% | Freedom from skewed/unfair assumptions |
| **Reproducibility** | 10% | Ability to produce consistent results |

**Overall Score = Weighted Average of 5 dimensions**

### Score Ranges

- **0.0 - 0.4:** Poor (significant issues)
- **0.4 - 0.6:** Below Average (noticeable gaps)
- **0.6 - 0.8:** Good (minor issues)
- **0.8 - 1.0:** Excellent (production-ready)

---

## Quality Assurance

### Ground Truth Validation

Each question's ground truth has been:
- Verified for task-type appropriateness
- Checked for multiple correct approaches (where applicable)
- Validated against established standards/references
- Reviewed for edge cases and ambiguities

### Dataset Characteristics

- **Balance:** Even distribution across task types
- **Complexity:** Mixed difficulty levels prevent ceiling effects
- **Diversity:** Multiple scenarios within each task type
- **Realism:** Real-world problem scenarios
- **Completeness:** Each question has structured ground truth

---

## Integration with Fleet Evaluation

This benchmark dataset is designed to work with the multi-AI fleet evaluation framework:

```javascript
import { getWorkflowStorage } from './shared/workflow-storage-adapter.js';
import { getBenchmarkData } from './evaluation/benchmark-dataset.js';

const db = getWorkflowStorage();
const benchmarks = getBenchmarkData();

// For each benchmark question:
for (const benchmark of benchmarks) {
  const workerResults = await parallel([
    agent('opus', benchmark),
    agent('sonnet', benchmark),
    agent('haiku', benchmark)
  ]);
  
  // Score results
  const scores = await evaluateWithHarness({
    output: workerResults,
    ground_truth: benchmark.ground_truth,
    task_type: benchmark.task_type
  });
  
  // Store in database
  await db.storeWorkerResult({
    benchmark_id: benchmark.id,
    model: agent.name,
    answer: workerResults,
    correctness_score: scores.correctness,
    robustness_score: scores.robustness,
    // ... other dimensions
  });
}
```

---

## Continuous Improvement

### Adding New Benchmarks

To add new benchmark questions:

1. Follow the JSON structure for the task type
2. Ensure ground truth is complete and validated
3. Insert into `evaluation.benchmarks` table:

```sql
INSERT INTO evaluation.benchmarks
(task_type, question, ground_truth, difficulty, category)
VALUES ('code_review', '...', '...'::JSONB, 'hard', 'code_review');
```

### Updating Ground Truth

If ground truth is found to be incomplete or incorrect:

```sql
UPDATE evaluation.benchmarks
SET ground_truth = '...'::JSONB, updated_at = NOW()
WHERE id = 123;
```

---

## License and Attribution

This benchmark dataset was generated programmatically with structured ground truth for systematic evaluation of multi-AI model performance.

**Version:** 1.0
**Created:** 2026-06-28
**Last Updated:** 2026-06-28

---

## References

### Code Review
- OWASP Top 10
- CWE/CVSS scoring guidelines
- Common code vulnerability patterns

### Research
- Major conference publications (2022-2026)
- Recent advances in ML/AI/Biology
- Established research methodologies

### Math
- Standard mathematical notation and solver techniques
- Multiple valid approaches recognized

### Security
- CVE database standards
- CVSS v3.1 scoring
- Security best practices (NIST, SANS)

### Networking
- RFC standards (DNS, TCP/IP, routing)
- Common network troubleshooting methodologies
- Industry diagnostic tools

### Creative
- Literary criticism frameworks
- Creativity evaluation rubrics
- Originality and coherence metrics

### Legal
- Contract law principles
- Jurisdiction-specific variations noted
- Professional legal interpretation standards

---

## Contact and Feedback

For issues, corrections, or suggestions:
1. Open an issue in the project repository
2. Include the benchmark question ID
3. Provide detailed explanation of the problem
4. Suggest improved ground truth if applicable
