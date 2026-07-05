# Formal Verification Expert

**Trained:** 2026-07-03  
**Model Type:** Random Forest (3 classifiers)  
**Training Examples:** 106 (34 synthetic + 72 historical)  
**Feature Dimension:** 115 (100 TF-IDF + 15 manual features)

## Overview

The Formal Verification Expert is a trained machine learning model that analyzes program correctness verification tasks and provides recommendations for:

1. **Pattern Detection** - Identifies the verification pattern (array_bounds, null_safety, sorting_correctness, etc.)
2. **Tool Selection** - Recommends the best formal verification tool (Dafny, Coq, Z3, TLA+, etc.)
3. **Technique Selection** - Suggests the proof technique (induction, SMT solving, separation logic, etc.)

## Model Performance

| Classifier | Accuracy | F1 Score | Classes |
|------------|----------|----------|---------|
| **Pattern** | 77.3% | 78.5% | 6 |
| **Tool** | 63.6% | 67.9% | 14 |
| **Technique** | 72.7% | 78.5% | 7 |

## Knowledge Base

The expert includes comprehensive knowledge about:

### Proof Techniques (8 total)
- **Induction** - Mathematical induction for recursive/iterative proofs
- **SMT Solving** - Satisfiability Modulo Theories for decidable logics
- **Symbolic Execution** - Path-based exploration with symbolic inputs
- **Deductive Verification** - Hoare logic and weakest precondition
- **Model Checking** - Exhaustive state space exploration
- **Refinement** - Prove implementation refines abstract spec
- **Separation Logic** - Heap reasoning with local reasoning
- **Abstract Interpretation** - Sound overapproximation

### Verification Tools (8 primary)
- **Dafny** - Auto-active verification with SMT backend
- **Coq** - Expressive type theory for deep properties
- **Z3** - Fast SMT solving for constraints
- **TLA+** - Concurrency modeling and model checking
- **Isabelle** - Powerful automation with HOL + ZF
- **KLEE** - Automatic symbolic execution for LLVM
- **Frama-C** - C verification with ACSL annotations
- **VeriFast** - Separation logic for concurrent programs

### Common Patterns (6 total)
- `array_bounds` - Index bounds checking
- `null_safety` - Null pointer safety
- `sorting_correctness` - Sorting algorithm verification
- `binary_search` - Binary search invariants
- `linked_list_traversal` - List memory safety
- `lock_protocol` - Concurrency safety

### Specification Patterns (5 total)
- **Precondition** - `requires P`
- **Postcondition** - `ensures Q`
- **Loop Invariant** - `invariant I`
- **Termination** - `decreases expr`
- **Class Invariant** - Object-level invariants

### Verification Goals (5 categories)
- **Memory Safety** - No null deref, buffer overflow, use-after-free
- **Functional Correctness** - Meets specification, all paths correct
- **Termination** - All recursion/loops terminate
- **Concurrency Safety** - No data races, deadlocks
- **Security Properties** - Information flow, access control

## Files

### Model Files
```
~/.claude/learning/formal_verification_expert.pkl        (992 KB)
~/.claude/learning/formal_verification_expert_report.json (1.1 KB)
```

### Training Script
```
tools/formal_verification_expert_trainer.py              (executable)
```

### Usage Script
```
tools/use_formal_verification_expert.py                  (executable)
```

### Database Entry
```sql
SELECT * FROM learning.specialist_models 
WHERE model_name = 'formal_verification_expert';
```

## Usage

### Python API

```python
import pickle
import numpy as np
from pathlib import Path

# Load model
model_path = Path.home() / '.claude' / 'learning' / 'formal_verification_expert.pkl'
with open(model_path, 'rb') as f:
    model = pickle.load(f)

# Analyze task
task = "Prove binary search correctness with loop invariants"

# Vectorize
X_tfidf = model['vectorizer'].transform([task]).toarray()
X_manual = extract_features_from_task(task)  # See trainer code
X = np.hstack([X_tfidf, [X_manual]])

# Predict
pattern = model['pattern_classifier'].predict(X)[0]
tool = model['tool_classifier'].predict(X)[0]
technique = model['technique_classifier'].predict(X)[0]

# Get probabilities
pattern_probs = model['pattern_classifier'].predict_proba(X)[0]
tool_probs = model['tool_classifier'].predict_proba(X)[0]
technique_probs = model['technique_classifier'].predict_proba(X)[0]

# Access knowledge base
kb = model['knowledge_base']
print(f"Tool info: {kb['tool_selection'][tool]}")
print(f"Technique info: {kb['proof_techniques'][technique]}")
print(f"Pattern guidance: {kb['common_patterns'][pattern]}")
```

### Command Line

```bash
# Run interactive demo
python3 tools/use_formal_verification_expert.py

# Analyze specific task
python3 -c "
from use_formal_verification_expert import analyze_verification_task, print_analysis

result = analyze_verification_task('Verify sorting algorithm correctness')
print_analysis(result)
"
```

## Example Analysis

**Input:**
```
"Verify no null pointer dereferences in linked list traversal"
```

**Output:**
```
PRIMARY RECOMMENDATIONS:
  Pattern: null_safety
  Tool:    VeriFast
  Technique: separation_logic

TOP PATTERNS (by confidence):
  null_safety                    29.9%
  lock_protocol                  27.7%
  array_bounds                   20.7%

DETAILED GUIDANCE:

Pattern Guidance (null_safety):
  precondition: requires ptr != null
  proof_hint: Track nullable types in type system
  common_tools: ['Dafny', 'Viper', 'Kotlin', 'Rust']

Technique Guidance (separation_logic):
  description: Heap reasoning with local reasoning
  use_cases: ['Pointers', 'Memory safety', 'Data structures']
  tools: ['VeriFast', 'Viper', 'Iris', 'Infer']
  difficulty: high
  automation: partial
```

## Training Data

### Synthetic Examples (34)
- Array algorithms (binary search, sorting, bounds checking)
- Memory safety (null pointers, buffer overflows, use-after-free)
- Concurrency (locks, data races, deadlocks, protocols)
- Termination (recursive functions, loops)
- SMT-based verification (constraints, symbolic execution)
- Functional correctness (specifications, compilers)
- Security properties (cryptography, information flow)
- Real-world examples (seL4, CompCert, AWS S3, Rust)

### Historical Data (72)
Extracted from `workflow.executions` and `workflow.worker_results` tables:
- Tasks containing keywords: verify, proof, formal, correct
- Successful executions with confidence > 0.5
- Automatically labeled using keyword matching

## Feature Engineering

### TF-IDF Features (100)
- Extracted from task descriptions
- English stop words removed
- Top 100 features by importance

### Manual Features (15)
1. `has_verify` - Contains verification keywords
2. `has_correctness` - Contains correctness keywords
3. `has_safety` - Contains safety keywords
4. `has_termination` - Contains termination keywords
5. `has_concurrency` - Contains concurrency keywords
6. `has_array` - References arrays/lists
7. `has_pointer` - References pointers
8. `has_sorting` - References sorting/searching
9. `has_tree` - References trees/graphs
10. `mentions_dafny` - Tool-specific keyword
11. `mentions_coq` - Tool-specific keyword
12. `mentions_z3` - Tool-specific keyword
13. `mentions_tla` - Tool-specific keyword
14. `task_length` - Normalized text length
15. `has_code` - Contains code blocks

## Retraining

To retrain with new data:

```bash
# Add examples to TRAINING_EXAMPLES in trainer script
# Or wait for more workflow executions to accumulate
python3 tools/formal_verification_expert_trainer.py
```

The trainer automatically:
1. Loads historical workflow data from PostgreSQL
2. Combines with synthetic examples
3. Trains 3 Random Forest classifiers
4. Saves models to `~/.claude/learning/`
5. Stores metadata in `learning.specialist_models` table

## Integration

### Workflow Integration

```javascript
const { execSync } = require('child_process');

// Analyze verification task
const result = JSON.parse(execSync(
  `python3 -c "
from use_formal_verification_expert import analyze_verification_task
import json
result = analyze_verification_task('${task}')
print(json.dumps(result))
"`
).toString());

console.log(`Recommended tool: ${result.recommendations.tool}`);
console.log(`Recommended technique: ${result.recommendations.technique}`);
```

### PostgreSQL Query

```sql
-- Get specialist model metadata
SELECT 
  model_name,
  accuracy,
  f1_score,
  training_samples,
  categories,
  trained_at
FROM learning.specialist_models
WHERE model_name = 'formal_verification_expert';
```

## Limitations

1. **Tool classifier accuracy (63.6%)** - Some tools have very few training examples
   - Best predictions: Dafny (93% F1), most others have insufficient data
   - Consider: More synthetic examples for rare tools

2. **Class imbalance** - Historical data skewed toward certain patterns
   - `linked_list_traversal`: 12 test samples
   - `null_safety`, `sorting_correctness`: 1 sample each
   - Solution: Active learning to collect more diverse examples

3. **No code analysis** - Only analyzes task descriptions, not actual code
   - Future: Extract features from code structure

4. **Static knowledge base** - Tool capabilities/best practices may evolve
   - Solution: Regular knowledge base updates

## Future Improvements

1. **Expand training data**
   - Add examples for rare tools (CBMC, EasyCrypt, F*, ProVerif)
   - Balance pattern classes
   - Include failed verification attempts (negative examples)

2. **Code-level features**
   - AST analysis
   - Control flow patterns
   - Complexity metrics

3. **Multi-label classification**
   - Some tasks need multiple techniques
   - Combine tools (e.g., Z3 + Dafny)

4. **Confidence thresholds**
   - Flag low-confidence predictions
   - Request human expert for ambiguous cases

5. **Active learning**
   - Identify uncertain predictions
   - Request labels from users
   - Incremental retraining

## References

### Academic Papers
- Integrated Information Theory (IIT) - Φ measurement
- Higher-Order Thought (HOT) Theory - Meta-representation
- Global Neuronal Workspace (GNW) - Attention competition
- Free Energy Principle (FEP) - Bayesian inference

### Formal Methods
- Dafny: https://dafny.org/
- Coq: https://coq.inria.fr/
- Z3: https://github.com/Z3Prover/z3
- TLA+: https://lamport.azurewebsites.net/tla/tla.html
- Isabelle: https://isabelle.in.tum.de/

### Learning Resources
- Software Foundations (Coq): https://softwarefoundations.cis.upenn.edu/
- Program Proofs (Dafny): https://mitpress.mit.edu/books/program-proofs
- Separation Logic: https://www.cs.cmu.edu/~jcr/seplogic.pdf
- Model Checking: https://spinroot.com/spin/whatispin.html

## License

Part of the claude-global-skills distributed learning framework.
See main project documentation for details.
