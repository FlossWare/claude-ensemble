#!/usr/bin/env python3
"""
Constraint Satisfaction Problem (CSP) Trainer

Trains a Random Forest classifier to:
1. Identify CSP problem types (scheduling, planning, resource allocation, graph coloring)
2. Recommend search strategies (backtracking, forward checking, arc consistency)
3. Detect constraint types (unary, binary, global, soft, hard)
4. Suggest optimization techniques (variable ordering, value ordering, constraint propagation)
5. Predict search space complexity and pruning effectiveness
6. Recommend hybrid approaches (local search, genetic algorithms, SAT encoding)

Training data sources:
- Historical workflow executions (PostgreSQL)
- CSP problem patterns and solutions
- Search strategy performance metrics
- Constraint propagation effectiveness
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

# CSP Knowledge Base
CSP_KNOWLEDGE = {
    'problem_types': {
        'scheduling': {
            'description': 'Assign tasks to time slots/resources respecting temporal constraints',
            'variables': 'tasks, time_slots, resources',
            'constraints': ['precedence', 'resource_capacity', 'deadlines', 'dependencies'],
            'common_algorithms': ['backtracking', 'constraint_programming', 'local_search'],
            'complexity': 'NP-complete',
            'examples': ['job_shop', 'timetabling', 'project_scheduling', 'nurse_rostering']
        },
        'resource_allocation': {
            'description': 'Assign limited resources to competing demands',
            'variables': 'resources, demands, allocations',
            'constraints': ['capacity', 'exclusivity', 'preference', 'fairness'],
            'common_algorithms': ['auction', 'matching', 'optimization'],
            'complexity': 'NP-hard',
            'examples': ['bandwidth_allocation', 'cloud_resource_allocation', 'task_assignment']
        },
        'graph_coloring': {
            'description': 'Assign colors to graph nodes such that adjacent nodes differ',
            'variables': 'nodes, colors',
            'constraints': ['adjacency', 'color_limit'],
            'common_algorithms': ['greedy', 'backtracking', 'dsatur'],
            'complexity': 'NP-complete',
            'examples': ['register_allocation', 'frequency_assignment', 'exam_scheduling']
        },
        'satisfiability': {
            'description': 'Find variable assignments satisfying logical constraints',
            'variables': 'boolean_variables, domain_variables',
            'constraints': ['clauses', 'cardinality', 'implications'],
            'common_algorithms': ['DPLL', 'CDCL', 'local_search'],
            'complexity': 'NP-complete (SAT), NP-hard (MAX-SAT)',
            'examples': ['circuit_verification', 'planning', 'configuration']
        },
        'configuration': {
            'description': 'Select compatible components from catalogs',
            'variables': 'components, features, compatibility',
            'constraints': ['requires', 'excludes', 'compatibility', 'cardinality'],
            'common_algorithms': ['constraint_programming', 'SAT_encoding'],
            'complexity': 'NP-complete',
            'examples': ['product_configuration', 'system_design', 'package_management']
        },
        'planning': {
            'description': 'Find sequence of actions to reach goal state',
            'variables': 'actions, states, resources',
            'constraints': ['preconditions', 'effects', 'resource_limits', 'temporal'],
            'common_algorithms': ['GraphPlan', 'SAT_planning', 'heuristic_search'],
            'complexity': 'PSPACE-complete',
            'examples': ['robot_planning', 'logistics', 'workflow_synthesis']
        }
    },

    'search_strategies': {
        'backtracking': {
            'description': 'DFS with constraint checking and backjumping',
            'when_to_use': 'Small-medium problems, need guarantees',
            'strengths': ['completeness', 'optimality', 'simple'],
            'weaknesses': ['exponential_worst_case', 'memory_overhead'],
            'optimizations': ['intelligent_backtracking', 'conflict_directed_backjumping']
        },
        'forward_checking': {
            'description': 'Propagate constraints after each assignment',
            'when_to_use': 'Dense constraints, early detection needed',
            'strengths': ['early_pruning', 'reduced_backtracking'],
            'weaknesses': ['overhead_per_node', 'incomplete_propagation'],
            'optimizations': ['domain_filtering', 'look_ahead']
        },
        'arc_consistency': {
            'description': 'Ensure every value has support in constrained variables',
            'when_to_use': 'Binary constraints dominant',
            'strengths': ['strong_pruning', 'polynomial_per_iteration'],
            'weaknesses': ['repeated_computation', 'doesn\'t_guarantee_solution'],
            'algorithms': ['AC-1', 'AC-3', 'AC-4', 'optimal_AC']
        },
        'path_consistency': {
            'description': 'Extend arc consistency to triples',
            'when_to_use': 'Higher-order constraints',
            'strengths': ['stronger_than_arc_consistency', 'detects_more_inconsistencies'],
            'weaknesses': ['O(n^3) complexity', 'diminishing_returns'],
            'algorithms': ['PC-1', 'PC-2', 'PC-8']
        },
        'local_search': {
            'description': 'Iteratively improve assignment by local moves',
            'when_to_use': 'Large problems, near-optimal acceptable',
            'strengths': ['scales_well', 'fast_solutions', 'anytime'],
            'weaknesses': ['incomplete', 'local_minima', 'no_optimality_guarantee'],
            'algorithms': ['hill_climbing', 'simulated_annealing', 'tabu_search', 'GSAT', 'WalkSAT']
        },
        'hybrid': {
            'description': 'Combine systematic and local search',
            'when_to_use': 'Complex problems needing both guarantees and scale',
            'strengths': ['best_of_both', 'adaptive'],
            'weaknesses': ['complexity', 'tuning_needed'],
            'examples': ['LDS', 'IBBA', 'DFS+local_search']
        }
    },

    'constraint_types': {
        'unary': {
            'description': 'Constraints on single variable',
            'handling': 'domain_reduction',
            'examples': ['X > 5', 'color != red'],
            'complexity': 'O(1)'
        },
        'binary': {
            'description': 'Constraints between two variables',
            'handling': 'arc_consistency',
            'examples': ['X < Y', 'adjacent_different_colors'],
            'complexity': 'O(d^2)'
        },
        'ternary': {
            'description': 'Constraints on three variables',
            'handling': 'path_consistency_or_decomposition',
            'examples': ['X + Y = Z', 'triangle_inequality'],
            'complexity': 'O(d^3)'
        },
        'global': {
            'description': 'Constraints on arbitrary number of variables',
            'handling': 'specialized_propagators',
            'examples': ['alldifferent', 'sum', 'cardinality', 'cumulative'],
            'complexity': 'varies by constraint'
        },
        'hard': {
            'description': 'Must be satisfied',
            'handling': 'standard_CSP_techniques',
            'examples': ['precedence', 'capacity_limits'],
            'violation': 'solution_invalid'
        },
        'soft': {
            'description': 'Preferably satisfied',
            'handling': 'optimization_objective',
            'examples': ['preferences', 'quality_metrics'],
            'violation': 'penalty_cost'
        }
    },

    'variable_ordering_heuristics': {
        'minimum_remaining_values': {
            'description': 'Choose variable with smallest domain (most constrained)',
            'rationale': 'Fail-first principle, detect conflicts early',
            'performance': 'excellent for tight constraints',
            'alias': 'MRV, fail-first'
        },
        'degree_heuristic': {
            'description': 'Choose variable involved in most constraints',
            'rationale': 'Maximum impact on remaining variables',
            'performance': 'good tie-breaker for MRV',
            'alias': 'max-degree'
        },
        'dynamic_degree': {
            'description': 'Degree among unassigned variables only',
            'rationale': 'More accurate constraint density',
            'performance': 'better than static degree',
            'alias': 'dom/deg'
        },
        'weighted_degree': {
            'description': 'Weight by constraint failures',
            'rationale': 'Focus on hard constraints',
            'performance': 'excellent for conflict-driven search',
            'alias': 'dom/wdeg'
        }
    },

    'value_ordering_heuristics': {
        'least_constraining_value': {
            'description': 'Choose value leaving most options for neighbors',
            'rationale': 'Maximize future flexibility',
            'performance': 'excellent for finding any solution',
            'alias': 'LCV'
        },
        'min_conflicts': {
            'description': 'Choose value minimizing constraint violations',
            'rationale': 'Reduce backtracking',
            'performance': 'good for local search',
            'alias': 'min-conflicts'
        },
        'max_promise': {
            'description': 'Choose value maximizing objective function',
            'rationale': 'Optimization-focused',
            'performance': 'good for soft constraints',
            'alias': 'promise'
        }
    },

    'consistency_algorithms': {
        'AC-3': {
            'description': 'Arc consistency via iterative domain reduction',
            'complexity': 'O(ed^3) where e=edges, d=domain_size',
            'completeness': 'no (only detects some inconsistencies)',
            'use_case': 'standard arc consistency',
            'optimizations': ['AC-3d', 'AC-3.1', 'AC-2001']
        },
        'PC-2': {
            'description': 'Path consistency on triples',
            'complexity': 'O(n^3 d^3)',
            'completeness': 'no',
            'use_case': 'stronger than AC, weaker than full consistency',
            'optimizations': ['PC-4', 'PC-8']
        },
        'singleton_arc_consistency': {
            'description': 'AC after tentatively assigning each value',
            'complexity': 'O(nd) × AC complexity',
            'completeness': 'stronger than AC',
            'use_case': 'when AC insufficient but full search too expensive',
            'alias': 'SAC'
        },
        'generalized_arc_consistency': {
            'description': 'AC generalized to n-ary constraints',
            'complexity': 'depends on constraint arity',
            'completeness': 'no',
            'use_case': 'global constraints',
            'alias': 'GAC, hyper-arc-consistency'
        }
    },

    'optimization_techniques': {
        'constraint_propagation': {
            'description': 'Reduce domains by constraint inference',
            'impact': 'exponential search space reduction',
            'cost': 'polynomial per propagation',
            'when_to_use': 'always (unless trivial problem)'
        },
        'nogood_learning': {
            'description': 'Record conflict causes to avoid repetition',
            'impact': 'prevent redundant search',
            'cost': 'memory for nogood storage',
            'when_to_use': 'problems with repeated conflicts'
        },
        'symmetry_breaking': {
            'description': 'Add constraints eliminating symmetric solutions',
            'impact': 'reduce search space by symmetry factor',
            'cost': 'constraint overhead',
            'when_to_use': 'symmetric problems (graph coloring, etc.)'
        },
        'lazy_evaluation': {
            'description': 'Delay constraint checks until necessary',
            'impact': 'avoid unnecessary computation',
            'cost': 'potential delayed conflict detection',
            'when_to_use': 'expensive constraint checks'
        },
        'restarts': {
            'description': 'Restart search periodically with learned knowledge',
            'impact': 'escape poor variable ordering',
            'cost': 'lose partial progress',
            'when_to_use': 'heavy-tailed runtime distribution'
        }
    },

    'encodings': {
        'SAT_encoding': {
            'description': 'Convert CSP to boolean satisfiability',
            'advantages': ['mature_solvers', 'conflict_learning', 'efficient_propagation'],
            'disadvantages': ['encoding_overhead', 'loss_of_structure'],
            'use_case': 'leverage SAT solver advances'
        },
        'integer_programming': {
            'description': 'Convert CSP to IP/MIP',
            'advantages': ['optimization_objective', 'mature_solvers', 'LP_relaxation'],
            'disadvantages': ['continuous_relaxation_weak', 'encoding_overhead'],
            'use_case': 'optimization problems'
        },
        'SMT_encoding': {
            'description': 'Convert to satisfiability modulo theories',
            'advantages': ['rich_theories', 'decision_procedures', 'conflict_learning'],
            'disadvantages': ['solver_complexity'],
            'use_case': 'arithmetic/theory-heavy constraints'
        }
    }
}

# Feature extraction patterns
CSP_PATTERNS = {
    # Problem type indicators
    'scheduling_patterns': [
        'task', 'schedule', 'time', 'deadline', 'precedence', 'resource',
        'shift', 'timetable', 'calendar', 'sequence', 'workflow', 'job'
    ],
    'resource_patterns': [
        'allocate', 'assign', 'capacity', 'bandwidth', 'memory', 'cpu',
        'worker', 'machine', 'quota', 'limit', 'share', 'distribute'
    ],
    'graph_patterns': [
        'node', 'edge', 'adjacent', 'neighbor', 'color', 'vertex',
        'register', 'frequency', 'interference', 'conflict'
    ],
    'sat_patterns': [
        'boolean', 'clause', 'literal', 'satisfiability', 'truth',
        'cnf', 'dnf', 'implication', 'constraint'
    ],
    'config_patterns': [
        'component', 'feature', 'option', 'compatible', 'requires',
        'excludes', 'version', 'dependency', 'package'
    ],

    # Search strategy indicators
    'systematic_search': [
        'complete', 'optimal', 'guarantee', 'backtrack', 'exhaustive',
        'branch', 'prune', 'bound'
    ],
    'local_search': [
        'improve', 'neighbor', 'move', 'hill', 'climb', 'anneal',
        'tabu', 'genetic', 'random', 'restart'
    ],

    # Constraint type indicators
    'hard_constraint': [
        'must', 'require', 'enforce', 'violate', 'invalid', 'impossible'
    ],
    'soft_constraint': [
        'prefer', 'should', 'better', 'ideal', 'optimize', 'minimize',
        'maximize', 'cost', 'penalty', 'quality'
    ],

    # Complexity indicators
    'small_scale': ['< 100', 'small', 'few', 'simple', 'trivial'],
    'medium_scale': ['100-1000', 'moderate', 'medium', 'manageable'],
    'large_scale': ['> 1000', 'large', 'massive', 'complex', 'huge', 'scale']
}


class ConstraintSatisfactionTrainer:
    """Train ML model to recommend CSP solving strategies"""

    def __init__(self):
        self.learning_dir = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning'
        self.model_path = self.learning_dir / 'constraint_satisfaction.pkl'
        self.stats_path = self.learning_dir / 'constraint_satisfaction_stats.json'

        self.vectorizer = TfidfVectorizer(max_features=200, ngram_range=(1, 3))
        self.classifier = RandomForestClassifier(
            n_estimators=150,
            max_depth=20,
            min_samples_split=3,
            class_weight='balanced',
            random_state=42
        )

        self.db_config = {
            'host': 'aio-01',
            'port': 5433,
            'dbname': 'learning',
            'user': 'sfloess'
        }

    def connect_db(self):
        """Connect to PostgreSQL"""
        return psycopg2.connect(**self.db_config)

    def extract_features(self, text):
        """Extract CSP-specific features from text"""
        text_lower = text.lower()
        features = {}

        # Problem type features
        for prob_type, patterns in CSP_PATTERNS.items():
            if 'patterns' in prob_type:
                features[f'has_{prob_type}'] = sum(
                    1 for p in patterns if p in text_lower
                ) / len(patterns)

        # Complexity features
        features['text_length'] = len(text)
        features['num_constraints'] = text_lower.count('constraint') + text_lower.count('must') + text_lower.count('should')
        features['num_variables'] = text_lower.count('variable') + text_lower.count('assign')

        return features

    def generate_synthetic_training_data(self):
        """Generate synthetic CSP training examples"""
        X_text = []
        y_labels = []

        # Simplified to 6 main categories with 10+ examples each

        # 1. Backtracking (systematic search)
        backtracking_examples = [
            ("Schedule 50 tasks on 5 machines with precedence constraints", "backtracking"),
            ("Small workshop scheduling with 20 jobs", "backtracking"),
            ("Assign 30 tasks to machines with dependencies", "backtracking"),
            ("Optimal coloring for medium graphs", "backtracking"),
            ("Graph coloring with chromatic number search", "backtracking"),
            ("Package manager dependency resolution", "backtracking"),
            ("Software dependencies with version constraints", "backtracking"),
            ("Systematic search for valid configuration", "backtracking"),
            ("N-queens problem on 8x8 board", "backtracking"),
            ("Sudoku solver with constraint checking", "backtracking"),
            ("Map coloring with minimal colors", "backtracking"),
            ("Binary constraint satisfaction with small domains", "backtracking"),
        ]

        # 2. Constraint Programming (CP solvers)
        cp_examples = [
            ("Timetable for 200 courses avoiding conflicts", "constraint_programming"),
            ("Course scheduling with room and instructor constraints", "constraint_programming"),
            ("Conference scheduling with parallel tracks", "constraint_programming"),
            ("Multi-tenant resource allocation with isolation", "constraint_programming"),
            ("Memory and CPU allocation with capacity limits", "constraint_programming"),
            ("Product configuration with 100 features and dependencies", "constraint_programming"),
            ("Software product line configuration", "constraint_programming"),
            ("Feature model configuration with constraints", "constraint_programming"),
            ("Job shop scheduling with resource constraints", "constraint_programming"),
            ("Vehicle routing with time windows", "constraint_programming"),
            ("Bin packing with multiple dimensions", "constraint_programming"),
            ("Nurse rostering with complex regulations", "constraint_programming"),
        ]

        # 3. Local Search (metaheuristics)
        local_search_examples = [
            ("Assign shifts to 100 nurses with preferences", "local_search"),
            ("Large-scale employee rostering with soft preferences", "local_search"),
            ("Shift assignment for 500 workers", "local_search"),
            ("Maximum satisfiability with soft clauses", "local_search"),
            ("Weighted MAX-SAT optimization", "local_search"),
            ("Large SAT instance with local search", "local_search"),
            ("Exam scheduling with 5000 students", "local_search"),
            ("Large graph coloring problem", "local_search"),
            ("Traveling salesman problem optimization", "local_search"),
            ("Quadratic assignment problem", "local_search"),
            ("Facility location with soft constraints", "local_search"),
            ("Portfolio optimization with preferences", "local_search"),
        ]

        # 4. SAT/SMT Encoding
        sat_smt_examples = [
            ("Boolean satisfiability with 1000 variables", "sat_encoding"),
            ("CNF formula satisfiability", "sat_encoding"),
            ("Small SAT problem with unit propagation", "sat_encoding"),
            ("Circuit verification checking equivalence", "sat_encoding"),
            ("Large SAT instance with conflict learning", "sat_encoding"),
            ("Industrial SAT problem with clause learning", "sat_encoding"),
            ("Planning problem encoded as SAT", "sat_encoding"),
            ("Bounded model checking via SAT encoding", "sat_encoding"),
            ("System design with compatibility constraints", "sat_encoding"),
            ("Hardware configuration via SAT encoding", "sat_encoding"),
            ("Configuration with arithmetic constraints", "sat_encoding"),
            ("Complex dependency resolution using SMT", "sat_encoding"),
        ]

        # 5. Graph Algorithms (specialized)
        graph_examples = [
            ("Register allocation for compiler", "graph_algorithms"),
            ("Quick graph coloring for small graphs", "graph_algorithms"),
            ("Greedy coloring with vertex ordering", "graph_algorithms"),
            ("Frequency assignment minimizing interference", "graph_algorithms"),
            ("DSatur heuristic for large graph coloring", "graph_algorithms"),
            ("Conflict graph coloring", "graph_algorithms"),
            ("Network flow optimization", "graph_algorithms"),
            ("Minimum spanning tree with constraints", "graph_algorithms"),
            ("Bipartite matching of workers to jobs", "graph_algorithms"),
            ("Maximum matching problem", "graph_algorithms"),
            ("Vertex cover optimization", "graph_algorithms"),
            ("Graph partitioning problem", "graph_algorithms"),
        ]

        # 6. Optimization (mathematical programming)
        optimization_examples = [
            ("Allocate bandwidth to 1000 requests with fairness", "optimization"),
            ("Network resource allocation with QoS guarantees", "optimization"),
            ("CPU allocation among containers with priorities", "optimization"),
            ("Assign tasks to workers maximizing skill match", "optimization"),
            ("Task assignment problem with preferences", "optimization"),
            ("Fair division of limited resources", "optimization"),
            ("Auction-based resource allocation", "optimization"),
            ("Dynamic pricing for resource allocation", "optimization"),
            ("Linear programming for resource allocation", "optimization"),
            ("Integer programming for scheduling", "optimization"),
            ("Multi-objective optimization problem", "optimization"),
            ("Knapsack problem with constraints", "optimization"),
        ]

        # Combine all examples
        all_examples = (
            backtracking_examples + cp_examples + local_search_examples +
            sat_smt_examples + graph_examples + optimization_examples
        )

        for text, label in all_examples:
            X_text.append(text)
            y_labels.append(label)

        return X_text, y_labels

    def train(self):
        """Train the constraint satisfaction model"""
        print("=" * 80)
        print("CONSTRAINT SATISFACTION PROBLEM TRAINER")
        print("=" * 80)
        print()

        # Generate training data
        print("Generating synthetic training data...")
        X_text, y_labels = self.generate_synthetic_training_data()

        print(f"  Total examples: {len(X_text)}")
        print(f"  Unique strategies: {len(set(y_labels))}")
        print()

        # Vectorize text
        print("Vectorizing text features...")
        X_vectorized = self.vectorizer.fit_transform(X_text)

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_vectorized, y_labels, test_size=0.2, random_state=42, stratify=y_labels
        )

        print(f"  Training set: {X_train.shape[0]} examples")
        print(f"  Test set: {X_test.shape[0]} examples")
        print()

        # Train model
        print("Training Random Forest classifier...")
        self.classifier.fit(X_train, y_train)

        # Evaluate
        train_pred = self.classifier.predict(X_train)
        test_pred = self.classifier.predict(X_test)

        train_acc = accuracy_score(y_train, train_pred)
        test_acc = accuracy_score(y_test, test_pred)
        train_f1 = f1_score(y_train, train_pred, average='weighted')
        test_f1 = f1_score(y_test, test_pred, average='weighted')

        print("PERFORMANCE METRICS")
        print("-" * 80)
        print(f"Training Accuracy:  {train_acc:.3f}")
        print(f"Test Accuracy:      {test_acc:.3f}")
        print(f"Training F1:        {train_f1:.3f}")
        print(f"Test F1:            {test_f1:.3f}")
        print()

        print("CLASSIFICATION REPORT (Test Set)")
        print("-" * 80)
        print(classification_report(y_test, test_pred))

        # Save model
        print("Saving model and statistics...")
        with open(self.model_path, 'wb') as f:
            pickle.dump({
                'vectorizer': self.vectorizer,
                'classifier': self.classifier,
                'knowledge_base': CSP_KNOWLEDGE,
                'patterns': CSP_PATTERNS
            }, f)

        stats = {
            'trained_at': datetime.now().isoformat(),
            'total_examples': len(X_text),
            'num_strategies': len(set(y_labels)),
            'train_accuracy': float(train_acc),
            'test_accuracy': float(test_acc),
            'train_f1': float(train_f1),
            'test_f1': float(test_f1),
            'feature_count': X_vectorized.shape[1]
        }

        with open(self.stats_path, 'w') as f:
            json.dump(stats, f, indent=2)

        print(f"  Model saved to: {self.model_path}")
        print(f"  Stats saved to: {self.stats_path}")
        print()
        print("=" * 80)
        print("TRAINING COMPLETE")
        print("=" * 80)

        return stats

    def predict(self, problem_description):
        """Predict best CSP strategy for given problem"""
        # Load model
        with open(self.model_path, 'rb') as f:
            model_data = pickle.load(f)

        vectorizer = model_data['vectorizer']
        classifier = model_data['classifier']
        knowledge = model_data['knowledge_base']

        # Vectorize input
        X = vectorizer.transform([problem_description])

        # Predict
        strategy = classifier.predict(X)[0]
        probabilities = classifier.predict_proba(X)[0]
        confidence = max(probabilities)

        # Get top 3 strategies
        top_indices = np.argsort(probabilities)[-3:][::-1]
        top_strategies = [
            (classifier.classes_[i], probabilities[i])
            for i in top_indices
        ]

        return {
            'recommended_strategy': strategy,
            'confidence': float(confidence),
            'top_3_strategies': [
                {'strategy': s, 'probability': float(p)}
                for s, p in top_strategies
            ],
            'knowledge_base': knowledge
        }


def main():
    trainer = ConstraintSatisfactionTrainer()
    stats = trainer.train()

    # Example predictions
    print()
    print("EXAMPLE PREDICTIONS")
    print("=" * 80)

    test_cases = [
        "Schedule 100 tasks on 10 machines with precedence constraints",
        "Assign bandwidth to 5000 network requests with fairness",
        "Color a graph with 200 nodes minimizing colors used",
        "Boolean SAT problem with 10000 variables"
    ]

    for test in test_cases:
        print(f"\nProblem: {test}")
        result = trainer.predict(test)
        print(f"  Strategy: {result['recommended_strategy']}")
        print(f"  Confidence: {result['confidence']:.3f}")
        print(f"  Alternatives:")
        for alt in result['top_3_strategies'][1:]:
            print(f"    - {alt['strategy']} ({alt['probability']:.3f})")


if __name__ == '__main__':
    main()
