#!/usr/bin/env python3
"""
Formal Verification Expert Trainer

Trains a Random Forest classifier to:
1. Identify verification opportunities (preconditions, postconditions, invariants)
2. Select appropriate proof techniques (induction, SMT, symbolic execution)
3. Detect common proof patterns (loop invariants, termination arguments)
4. Map code patterns to formal specifications
5. Recommend verification tools (Dafny, Coq, Z3, TLA+, Isabelle)

Training data sources:
- Historical workflow executions (PostgreSQL)
- Formal verification patterns
- Common proof strategies
- Tool-specific idioms
"""

import psycopg2
import numpy as np
import json
import pickle
from datetime import datetime
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score
from collections import defaultdict

# Formal verification knowledge base
VERIFICATION_KNOWLEDGE = {
    'proof_techniques': {
        'induction': {
            'description': 'Mathematical induction for recursive/iterative proofs',
            'use_cases': ['Loop correctness', 'Recursive functions', 'List/tree properties'],
            'tools': ['Dafny', 'Coq', 'Isabelle/HOL', 'Lean'],
            'difficulty': 'medium',
            'automation': 'partial'
        },
        'smt_solving': {
            'description': 'Satisfiability Modulo Theories for decidable logics',
            'use_cases': ['Integer arithmetic', 'Bit-vectors', 'Arrays', 'Constraints'],
            'tools': ['Z3', 'CVC5', 'Yices', 'Boolector'],
            'difficulty': 'low',
            'automation': 'full'
        },
        'symbolic_execution': {
            'description': 'Path-based exploration with symbolic inputs',
            'use_cases': ['Test generation', 'Bug finding', 'Reachability'],
            'tools': ['KLEE', 'Symbolic PathFinder', 'angr', 'S2E'],
            'difficulty': 'medium',
            'automation': 'full'
        },
        'deductive_verification': {
            'description': 'Hoare logic and weakest precondition calculus',
            'use_cases': ['Full functional correctness', 'Complex invariants'],
            'tools': ['Dafny', 'Why3', 'Frama-C', 'KeY'],
            'difficulty': 'high',
            'automation': 'interactive'
        },
        'model_checking': {
            'description': 'Exhaustive state space exploration',
            'use_cases': ['Finite-state systems', 'Concurrency', 'Protocols'],
            'tools': ['TLA+', 'SPIN', 'NuSMV', 'CBMC'],
            'difficulty': 'medium',
            'automation': 'full'
        },
        'refinement': {
            'description': 'Prove implementation refines abstract spec',
            'use_cases': ['Stepwise development', 'Compiler correctness'],
            'tools': ['Event-B', 'Alloy', 'TLA+', 'Isabelle'],
            'difficulty': 'high',
            'automation': 'interactive'
        },
        'separation_logic': {
            'description': 'Heap reasoning with local reasoning',
            'use_cases': ['Pointers', 'Memory safety', 'Data structures'],
            'tools': ['VeriFast', 'Viper', 'Iris', 'Infer'],
            'difficulty': 'high',
            'automation': 'partial'
        },
        'abstract_interpretation': {
            'description': 'Sound overapproximation of program behaviors',
            'use_cases': ['Static analysis', 'Range analysis', 'Interval domains'],
            'tools': ['Astrée', 'Polyspace', 'CodeSonar', 'Infer'],
            'difficulty': 'medium',
            'automation': 'full'
        }
    },
    'specification_patterns': {
        'precondition': {
            'description': 'Conditions that must hold before execution',
            'examples': ['requires x >= 0', 'requires len(arr) > 0', 'requires ptr != null'],
            'syntax': {
                'dafny': 'requires P',
                'jml': '@requires P;',
                'spark': 'Pre => P',
                'eiffel': 'require P'
            }
        },
        'postcondition': {
            'description': 'Conditions guaranteed after execution',
            'examples': ['ensures result >= 0', 'ensures sorted(result)', 'ensures old(x) <= x'],
            'syntax': {
                'dafny': 'ensures Q',
                'jml': '@ensures Q;',
                'spark': 'Post => Q',
                'eiffel': 'ensure Q'
            }
        },
        'loop_invariant': {
            'description': 'Condition preserved by each loop iteration',
            'examples': ['invariant i <= len(arr)', 'invariant forall j :: 0 <= j < i ==> sorted(arr[..j])'],
            'syntax': {
                'dafny': 'invariant I',
                'jml': '@loop_invariant I;',
                'why3': 'invariant { I }',
                'frama_c': '/*@ loop invariant I; */'
            }
        },
        'termination': {
            'description': 'Proof that recursion/loop terminates',
            'examples': ['decreases n', 'decreases len(list)', 'variant { n }'],
            'syntax': {
                'dafny': 'decreases expr',
                'coq': 'Measure expr',
                'why3': 'variant { expr }',
                'isabelle': 'using [[termination_simp]]'
            }
        },
        'class_invariant': {
            'description': 'Condition maintained by all class methods',
            'examples': ['invariant size >= 0', 'invariant data.Length == capacity'],
            'syntax': {
                'dafny': 'class C { ... } invariant I',
                'jml': '//@ invariant I;',
                'eiffel': 'invariant I'
            }
        }
    },
    'common_patterns': {
        'array_bounds': {
            'precondition': 'requires 0 <= i < arr.Length',
            'proof_hint': 'Use index bounds in loop invariant',
            'common_tools': ['Dafny', 'Frama-C', 'SPARK']
        },
        'null_safety': {
            'precondition': 'requires ptr != null',
            'proof_hint': 'Track nullable types in type system',
            'common_tools': ['Dafny', 'Viper', 'Kotlin', 'Rust']
        },
        'sorting_correctness': {
            'postcondition': 'ensures sorted(result) && multiset(result) == multiset(input)',
            'proof_hint': 'Prove permutation + sortedness separately',
            'common_tools': ['Dafny', 'Why3', 'Isabelle']
        },
        'binary_search': {
            'loop_invariant': 'invariant forall k :: 0 <= k < low ==> arr[k] < target',
            'proof_hint': 'Maintain search space partitioning invariant',
            'common_tools': ['Dafny', 'KeY', 'Frama-C']
        },
        'linked_list_traversal': {
            'termination': 'decreases reachable(current)',
            'proof_hint': 'Use acyclicity or reachability measure',
            'common_tools': ['Dafny', 'VeriFast', 'Viper']
        },
        'lock_protocol': {
            'invariant': 'invariant locked ==> holds(this, lock)',
            'proof_hint': 'Model lock ownership in separation logic',
            'common_tools': ['Viper', 'Iris', 'VeriFast']
        }
    },
    'tool_selection': {
        'Dafny': {
            'strengths': ['Auto-active verification', 'SMT backend', 'Good for imperative code'],
            'weaknesses': ['Limited concurrency', 'No floating point'],
            'best_for': ['Algorithms', 'Data structures', 'Education'],
            'language': 'Dafny (C#-like)',
            'automation': 0.7
        },
        'Coq': {
            'strengths': ['Expressive type theory', 'Large library', 'Mature ecosystem'],
            'weaknesses': ['Steep learning curve', 'Manual proofs'],
            'best_for': ['Mathematics', 'Compilers', 'Deep properties'],
            'language': 'Gallina (ML-like)',
            'automation': 0.3
        },
        'Z3': {
            'strengths': ['Fast SMT solving', 'Many theories', 'API support'],
            'weaknesses': ['No loops/recursion', 'Incomplete for quantifiers'],
            'best_for': ['Constraints', 'Bounded verification', 'Test generation'],
            'language': 'SMT-LIB2',
            'automation': 1.0
        },
        'TLA+': {
            'strengths': ['Concurrency modeling', 'Model checking', 'Industry proven'],
            'weaknesses': ['Not for code verification', 'State explosion'],
            'best_for': ['Distributed systems', 'Protocols', 'Design'],
            'language': 'TLA+ (temporal logic)',
            'automation': 0.8
        },
        'Isabelle': {
            'strengths': ['Powerful automation', 'HOL + ZF', 'Large formalization'],
            'weaknesses': ['Learning curve', 'Setup complexity'],
            'best_for': ['Mathematics', 'Operating systems', 'Cryptography'],
            'language': 'Isabelle/HOL',
            'automation': 0.5
        },
        'KLEE': {
            'strengths': ['Automatic path exploration', 'Test generation', 'Bug finding'],
            'weaknesses': ['Path explosion', 'Limited to LLVM'],
            'best_for': ['C/C++ bug finding', 'Test generation', 'Reachability'],
            'language': 'LLVM bitcode',
            'automation': 1.0
        },
        'Frama-C': {
            'strengths': ['C verification', 'ACSL annotations', 'Industrial use'],
            'weaknesses': ['C-specific', 'Complex setup'],
            'best_for': ['Safety-critical C', 'MISRA compliance', 'Aerospace'],
            'language': 'C + ACSL',
            'automation': 0.6
        },
        'VeriFast': {
            'strengths': ['Separation logic', 'Concurrent programs', 'Java/C support'],
            'weaknesses': ['Manual annotations', 'Learning curve'],
            'best_for': ['Concurrent data structures', 'Lock protocols', 'Memory safety'],
            'language': 'Java/C + annotations',
            'automation': 0.4
        }
    },
    'verification_goals': {
        'memory_safety': {
            'properties': ['No null dereference', 'No buffer overflow', 'No use-after-free'],
            'recommended_tools': ['Viper', 'VeriFast', 'Infer', 'Rust'],
            'difficulty': 'medium'
        },
        'functional_correctness': {
            'properties': ['Meets specification', 'All paths correct', 'Edge cases handled'],
            'recommended_tools': ['Dafny', 'Why3', 'Coq', 'Isabelle'],
            'difficulty': 'high'
        },
        'termination': {
            'properties': ['All recursion terminates', 'All loops terminate', 'No infinite paths'],
            'recommended_tools': ['Dafny', 'Coq', 'AProVE', 'KITTeL'],
            'difficulty': 'high'
        },
        'concurrency_safety': {
            'properties': ['No data races', 'No deadlocks', 'Protocol adherence'],
            'recommended_tools': ['TLA+', 'Viper', 'Iris', 'CBMC'],
            'difficulty': 'high'
        },
        'security_properties': {
            'properties': ['Information flow', 'Access control', 'Cryptographic correctness'],
            'recommended_tools': ['ProVerif', 'Tamarin', 'EasyCrypt', 'F*'],
            'difficulty': 'very_high'
        }
    }
}

# Synthetic training data (expanded with verification patterns)
TRAINING_EXAMPLES = [
    # Array algorithms
    ('Verify binary search returns correct index', 'binary_search', 'Dafny', 'induction'),
    ('Prove sorting algorithm correctness', 'sorting_correctness', 'Why3', 'induction'),
    ('Check array bounds in loop', 'array_bounds', 'Frama-C', 'smt_solving'),
    ('Verify in-place array reversal', 'array_bounds', 'Dafny', 'induction'),
    ('Prove quicksort partitioning invariant', 'sorting_correctness', 'Dafny', 'induction'),

    # Memory safety
    ('Check null pointer dereference', 'null_safety', 'Viper', 'separation_logic'),
    ('Verify no buffer overflow in strcpy', 'array_bounds', 'Frama-C', 'symbolic_execution'),
    ('Prove linked list memory safety', 'linked_list_traversal', 'VeriFast', 'separation_logic'),
    ('Check use-after-free in destructor', 'null_safety', 'Infer', 'separation_logic'),
    ('Verify smart pointer ownership', 'null_safety', 'Viper', 'separation_logic'),

    # Concurrency
    ('Model distributed consensus protocol', 'lock_protocol', 'TLA+', 'model_checking'),
    ('Verify mutex lock safety', 'lock_protocol', 'Viper', 'separation_logic'),
    ('Check for data races in parallel code', 'lock_protocol', 'CBMC', 'model_checking'),
    ('Prove deadlock freedom in dining philosophers', 'lock_protocol', 'TLA+', 'model_checking'),
    ('Verify thread-safe queue implementation', 'lock_protocol', 'VeriFast', 'separation_logic'),

    # Termination
    ('Prove recursive function terminates', 'linked_list_traversal', 'Dafny', 'induction'),
    ('Verify while loop terminates', 'binary_search', 'Dafny', 'induction'),
    ('Check no infinite recursion in tree traversal', 'linked_list_traversal', 'Coq', 'induction'),
    ('Prove Ackermann function terminates', 'linked_list_traversal', 'Isabelle', 'induction'),

    # SMT-based verification
    ('Find counterexample to assertion', 'array_bounds', 'Z3', 'smt_solving'),
    ('Generate test inputs for branch coverage', 'array_bounds', 'KLEE', 'symbolic_execution'),
    ('Solve constraints for bounded model checking', 'array_bounds', 'Z3', 'smt_solving'),
    ('Verify bit-manipulation correctness', 'array_bounds', 'Z3', 'smt_solving'),

    # Functional correctness
    ('Prove map function preserves length', 'sorting_correctness', 'Coq', 'induction'),
    ('Verify stack push/pop specification', 'array_bounds', 'Dafny', 'deductive_verification'),
    ('Check hash table insert/lookup correctness', 'array_bounds', 'Why3', 'deductive_verification'),
    ('Prove compiler optimization preserves semantics', 'sorting_correctness', 'Isabelle', 'refinement'),

    # Security properties
    ('Verify cryptographic protocol authentication', 'lock_protocol', 'ProVerif', 'model_checking'),
    ('Check information flow in declassification', 'null_safety', 'F*', 'deductive_verification'),
    ('Prove absence of timing side channels', 'array_bounds', 'EasyCrypt', 'deductive_verification'),

    # Real-world examples
    ('Verify seL4 microkernel memory isolation', 'null_safety', 'Isabelle', 'separation_logic'),
    ('Prove CompCert compiler correctness', 'sorting_correctness', 'Coq', 'refinement'),
    ('Check AWS S3 encryption specification', 'lock_protocol', 'TLA+', 'model_checking'),
    ('Verify Rust borrow checker soundness', 'null_safety', 'Coq', 'deductive_verification'),
]

def get_db():
    """Connect to PostgreSQL learning database"""
    return psycopg2.connect(
        host='aio-01',
        port=5433,
        user='sfloess',
        database='learning'
    )

def extract_features_from_task(task_text):
    """Extract verification-specific features from task description"""
    task_lower = task_text.lower() if task_text else ""

    features = {}

    # Verification keywords
    features['has_verify'] = 1.0 if any(kw in task_lower for kw in ['verify', 'prove', 'check', 'formal']) else 0.0
    features['has_correctness'] = 1.0 if any(kw in task_lower for kw in ['correct', 'specification', 'invariant']) else 0.0
    features['has_safety'] = 1.0 if any(kw in task_lower for kw in ['safety', 'memory', 'null', 'bounds']) else 0.0
    features['has_termination'] = 1.0 if any(kw in task_lower for kw in ['terminat', 'halting', 'loop', 'recursive']) else 0.0
    features['has_concurrency'] = 1.0 if any(kw in task_lower for kw in ['concurrent', 'thread', 'lock', 'race', 'deadlock']) else 0.0

    # Code patterns
    features['has_array'] = 1.0 if any(kw in task_lower for kw in ['array', 'list', 'buffer']) else 0.0
    features['has_pointer'] = 1.0 if any(kw in task_lower for kw in ['pointer', 'reference', 'dereference']) else 0.0
    features['has_sorting'] = 1.0 if any(kw in task_lower for kw in ['sort', 'search', 'binary search']) else 0.0
    features['has_tree'] = 1.0 if any(kw in task_lower for kw in ['tree', 'graph', 'linked list']) else 0.0

    # Tools mentioned
    features['mentions_dafny'] = 1.0 if 'dafny' in task_lower else 0.0
    features['mentions_coq'] = 1.0 if 'coq' in task_lower else 0.0
    features['mentions_z3'] = 1.0 if 'z3' in task_lower else 0.0
    features['mentions_tla'] = 1.0 if 'tla' in task_lower else 0.0

    # Complexity indicators
    features['task_length'] = min(len(task_text) / 1000.0, 1.0) if task_text else 0.0
    features['has_code'] = 1.0 if '```' in task_text else 0.0

    return list(features.values())

def load_historical_data():
    """Load verification-related tasks from workflow database"""
    db = get_db()
    cursor = db.cursor()

    # Query workflow executions related to verification
    cursor.execute("""
        SELECT
            we.task_description,
            wr.task_assigned,
            wr.model,
            wr.outcome,
            wr.confidence
        FROM workflow.executions we
        JOIN workflow.worker_results wr ON we.id = wr.workflow_execution_id
        WHERE (
            LOWER(we.task_description) LIKE '%verify%'
            OR LOWER(we.task_description) LIKE '%proof%'
            OR LOWER(we.task_description) LIKE '%formal%'
            OR LOWER(wr.task_assigned) LIKE '%verify%'
            OR LOWER(wr.task_assigned) LIKE '%correct%'
        )
        AND wr.outcome = 'success'
        AND wr.confidence > 0.5
        ORDER BY we.created_at DESC
        LIMIT 1000
    """)

    historical_data = cursor.fetchall()
    cursor.close()
    db.close()

    return historical_data

def train_formal_verification_expert():
    """Train Random Forest classifier for verification expertise"""
    print("=== Formal Verification Expert Trainer ===\n")

    # Combine synthetic and historical data
    historical_data = load_historical_data()
    print(f"Loaded {len(historical_data)} historical verification tasks")

    # Prepare training data
    X_text = []
    y_pattern = []
    y_tool = []
    y_technique = []

    # Add synthetic examples
    for task, pattern, tool, technique in TRAINING_EXAMPLES:
        X_text.append(task)
        y_pattern.append(pattern)
        y_tool.append(tool)
        y_technique.append(technique)

    print(f"Added {len(TRAINING_EXAMPLES)} synthetic training examples")

    # Add historical data (with inferred labels from knowledge base)
    for task_desc, task_assigned, model, outcome, confidence in historical_data:
        task_text = task_assigned if task_assigned else task_desc
        if not task_text:
            continue

        # Infer pattern based on keywords
        task_lower = task_text.lower()
        inferred_pattern = 'array_bounds'  # default
        if 'sort' in task_lower:
            inferred_pattern = 'sorting_correctness'
        elif 'null' in task_lower or 'pointer' in task_lower:
            inferred_pattern = 'null_safety'
        elif 'lock' in task_lower or 'concurrent' in task_lower:
            inferred_pattern = 'lock_protocol'
        elif 'list' in task_lower or 'tree' in task_lower:
            inferred_pattern = 'linked_list_traversal'
        elif 'search' in task_lower:
            inferred_pattern = 'binary_search'

        # Infer tool
        inferred_tool = 'Dafny'  # default
        if 'coq' in task_lower:
            inferred_tool = 'Coq'
        elif 'z3' in task_lower or 'smt' in task_lower:
            inferred_tool = 'Z3'
        elif 'tla' in task_lower:
            inferred_tool = 'TLA+'

        # Infer technique
        inferred_technique = 'induction'  # default
        if 'smt' in task_lower or 'constraint' in task_lower:
            inferred_technique = 'smt_solving'
        elif 'symbolic' in task_lower:
            inferred_technique = 'symbolic_execution'
        elif 'model check' in task_lower:
            inferred_technique = 'model_checking'
        elif 'separation' in task_lower or 'heap' in task_lower:
            inferred_technique = 'separation_logic'

        X_text.append(task_text)
        y_pattern.append(inferred_pattern)
        y_tool.append(inferred_tool)
        y_technique.append(inferred_technique)

    print(f"Total training examples: {len(X_text)}")

    # Convert text to TF-IDF features
    vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
    X_tfidf = vectorizer.fit_transform(X_text).toarray()

    # Add manual features
    X_manual = np.array([extract_features_from_task(text) for text in X_text])
    X = np.hstack([X_tfidf, X_manual])

    print(f"Feature dimension: {X.shape[1]} (TF-IDF: {X_tfidf.shape[1]}, Manual: {X_manual.shape[1]})")

    # Train three classifiers: pattern, tool, technique
    results = {}

    for target_name, y in [('pattern', y_pattern), ('tool', y_tool), ('technique', y_technique)]:
        print(f"\n=== Training {target_name} classifier ===")

        # Check if stratification is possible (all classes need >=2 samples)
        from collections import Counter
        class_counts = Counter(y)
        min_count = min(class_counts.values())
        use_stratify = min_count >= 2

        # Split data
        if use_stratify:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
        else:
            print(f"  Warning: Some classes have <2 samples, disabling stratification")
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

        # Train Random Forest
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            class_weight='balanced'
        )
        clf.fit(X_train, y_train)

        # Evaluate
        y_pred = clf.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='weighted')

        print(f"  Accuracy: {accuracy:.3f}")
        print(f"  F1 Score: {f1:.3f}")
        print(f"  Unique classes: {len(set(y))}")

        # Classification report
        print("\n  Classification Report:")
        print(classification_report(y_test, y_pred, zero_division=0))

        results[target_name] = {
            'classifier': clf,
            'accuracy': accuracy,
            'f1_score': f1,
            'classes': clf.classes_.tolist()
        }

    # Save models
    output_dir = Path.home() / '.claude' / 'learning'
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / 'formal_verification_expert.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump({
            'pattern_classifier': results['pattern']['classifier'],
            'tool_classifier': results['tool']['classifier'],
            'technique_classifier': results['technique']['classifier'],
            'vectorizer': vectorizer,
            'knowledge_base': VERIFICATION_KNOWLEDGE,
            'trained_at': datetime.now().isoformat()
        }, f)

    print(f"\n✅ Model saved: {model_path}")

    # Save metadata report
    report_path = output_dir / 'formal_verification_expert_report.json'
    with open(report_path, 'w') as f:
        json.dump({
            'trained_at': datetime.now().isoformat(),
            'training_examples': len(X_text),
            'synthetic_examples': len(TRAINING_EXAMPLES),
            'historical_examples': len(historical_data),
            'feature_dimension': X.shape[1],
            'pattern_accuracy': results['pattern']['accuracy'],
            'pattern_f1': results['pattern']['f1_score'],
            'pattern_classes': results['pattern']['classes'],
            'tool_accuracy': results['tool']['accuracy'],
            'tool_f1': results['tool']['f1_score'],
            'tool_classes': results['tool']['classes'],
            'technique_accuracy': results['technique']['accuracy'],
            'technique_f1': results['technique']['f1_score'],
            'technique_classes': results['technique']['classes'],
            'knowledge_base_size': {
                'proof_techniques': len(VERIFICATION_KNOWLEDGE['proof_techniques']),
                'specification_patterns': len(VERIFICATION_KNOWLEDGE['specification_patterns']),
                'common_patterns': len(VERIFICATION_KNOWLEDGE['common_patterns']),
                'tools': len(VERIFICATION_KNOWLEDGE['tool_selection']),
                'verification_goals': len(VERIFICATION_KNOWLEDGE['verification_goals'])
            }
        }, f, indent=2)

    print(f"✅ Report saved: {report_path}")

    # Store in PostgreSQL
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO learning.specialist_models
        (model_name, model_type, accuracy, f1_score,
         training_samples, categories, model_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (model_name) DO UPDATE SET
            accuracy = EXCLUDED.accuracy,
            f1_score = EXCLUDED.f1_score,
            training_samples = EXCLUDED.training_samples,
            categories = EXCLUDED.categories,
            trained_at = NOW()
    """, (
        'formal_verification_expert',
        'RandomForest',
        results['pattern']['accuracy'],
        results['pattern']['f1_score'],
        len(X_text),
        results['pattern']['classes'],
        str(model_path)
    ))

    db.commit()
    cursor.close()
    db.close()

    print("\n✅ Metadata stored in PostgreSQL (learning.specialist_models)")

    # Usage example
    print("\n" + "="*70)
    print("USAGE EXAMPLE")
    print("="*70)
    print(f"""
import pickle

# Load model
with open('{model_path}', 'rb') as f:
    model = pickle.load(f)

# Analyze verification task
task = "Prove binary search correctness with loop invariants"

# Vectorize
X_tfidf = model['vectorizer'].transform([task]).toarray()
X_manual = extract_features_from_task(task)
X = np.hstack([X_tfidf, [X_manual]])

# Predict
pattern = model['pattern_classifier'].predict(X)[0]
tool = model['tool_classifier'].predict(X)[0]
technique = model['technique_classifier'].predict(X)[0]

print(f"Pattern: {{pattern}}")
print(f"Tool: {{tool}}")
print(f"Technique: {{technique}}")

# Get knowledge base guidance
kb = model['knowledge_base']
print(f"\\nTool info: {{kb['tool_selection'][tool]}}")
print(f"Technique info: {{kb['proof_techniques'][technique]}}")
print(f"Pattern guidance: {{kb['common_patterns'][pattern]}}")
""")

    return {
        'model_path': str(model_path),
        'report_path': str(report_path),
        'pattern_accuracy': results['pattern']['accuracy'],
        'tool_accuracy': results['tool']['accuracy'],
        'technique_accuracy': results['technique']['accuracy'],
        'training_examples': len(X_text)
    }

if __name__ == '__main__':
    results = train_formal_verification_expert()
    print("\n" + "="*70)
    print("TRAINING COMPLETE")
    print("="*70)
    print(f"Pattern Classification Accuracy: {results['pattern_accuracy']:.1%}")
    print(f"Tool Selection Accuracy: {results['tool_accuracy']:.1%}")
    print(f"Technique Selection Accuracy: {results['technique_accuracy']:.1%}")
    print(f"Total Training Examples: {results['training_examples']}")
    print(f"\nModel: {results['model_path']}")
    print(f"Report: {results['report_path']}")
