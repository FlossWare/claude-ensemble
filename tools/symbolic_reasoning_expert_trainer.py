#!/usr/bin/env python3
"""
Symbolic Reasoning Expert Trainer

Trains a Random Forest classifier to:
1. Identify logical reasoning patterns (deduction, induction, abduction)
2. Detect logical fallacies and invalid inference chains
3. Recommend proof strategies (direct, contradiction, contrapositive, induction)
4. Classify reasoning complexity (propositional, first-order, modal, temporal)
5. Suggest symbolic representation improvements
6. Identify opportunities for formal verification

Training data sources:
- Historical workflow executions (PostgreSQL)
- Logical reasoning patterns
- Common fallacies and invalid arguments
- Proof strategies and tactics
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

# Symbolic reasoning knowledge base
REASONING_KNOWLEDGE = {
    'reasoning_types': {
        'deductive': {
            'description': 'Conclusion necessarily follows from premises',
            'patterns': ['modus_ponens', 'modus_tollens', 'hypothetical_syllogism',
                        'disjunctive_syllogism', 'constructive_dilemma'],
            'validity': 'sound if premises true',
            'examples': ['All A are B, x is A, therefore x is B']
        },
        'inductive': {
            'description': 'Conclusion probable given premises',
            'patterns': ['generalization', 'statistical_syllogism', 'argument_from_analogy',
                        'causal_inference', 'prediction'],
            'validity': 'strength varies with evidence',
            'examples': ['Most A are B, x is A, therefore x is probably B']
        },
        'abductive': {
            'description': 'Inference to best explanation',
            'patterns': ['hypothesis_formation', 'diagnostic_reasoning', 'explanation_selection'],
            'validity': 'plausibility-based',
            'examples': ['The grass is wet, best explanation is rain']
        }
    },

    'logical_systems': {
        'propositional': {
            'operators': ['AND', 'OR', 'NOT', 'IMPLIES', 'IFF'],
            'complexity': 'NP-complete',
            'use_cases': ['Boolean circuits', 'SAT solving', 'Basic proofs']
        },
        'first_order': {
            'operators': ['FORALL', 'EXISTS', 'AND', 'OR', 'NOT', 'IMPLIES'],
            'complexity': 'semi-decidable',
            'use_cases': ['Mathematics', 'Program verification', 'Databases']
        },
        'modal': {
            'operators': ['NECESSARY', 'POSSIBLE', 'KNOWS', 'BELIEVES'],
            'complexity': 'varies by system',
            'use_cases': ['Knowledge representation', 'Epistemology', 'Security protocols']
        },
        'temporal': {
            'operators': ['ALWAYS', 'EVENTUALLY', 'UNTIL', 'NEXT'],
            'complexity': 'PSPACE-complete',
            'use_cases': ['System verification', 'Planning', 'Reactive systems']
        },
        'description_logic': {
            'operators': ['SUBCLASS', 'INTERSECTION', 'UNION', 'COMPLEMENT', 'RESTRICTION'],
            'complexity': 'varies by expressiveness',
            'use_cases': ['Ontologies', 'Semantic web', 'Knowledge graphs']
        }
    },

    'proof_strategies': {
        'direct_proof': {
            'description': 'Prove P → Q by assuming P and deriving Q',
            'difficulty': 'medium',
            'when_to_use': 'Clear forward path from premises to conclusion'
        },
        'proof_by_contradiction': {
            'description': 'Assume ¬Q and derive contradiction',
            'difficulty': 'medium',
            'when_to_use': 'Direct proof unclear, negation easier to work with'
        },
        'proof_by_contrapositive': {
            'description': 'Prove ¬Q → ¬P instead of P → Q',
            'difficulty': 'easy',
            'when_to_use': 'Contrapositive easier to prove'
        },
        'proof_by_induction': {
            'description': 'Base case + inductive step',
            'difficulty': 'hard',
            'when_to_use': 'Natural numbers, recursive structures'
        },
        'proof_by_cases': {
            'description': 'Exhaust all possible cases',
            'difficulty': 'medium',
            'when_to_use': 'Natural disjunction in problem'
        },
        'constructive_proof': {
            'description': 'Explicitly construct witness/example',
            'difficulty': 'hard',
            'when_to_use': 'Existence claim needs concrete example'
        },
        'proof_by_counterexample': {
            'description': 'Find single counterexample to universal claim',
            'difficulty': 'easy',
            'when_to_use': 'Disproving universal statements'
        }
    },

    'logical_fallacies': {
        'formal': {
            'affirming_consequent': {
                'pattern': 'P → Q, Q, therefore P',
                'invalid_because': 'Q can be true for other reasons',
                'severity': 'critical'
            },
            'denying_antecedent': {
                'pattern': 'P → Q, ¬P, therefore ¬Q',
                'invalid_because': 'Q can be true even if P is false',
                'severity': 'critical'
            },
            'undistributed_middle': {
                'pattern': 'All A are B, All C are B, therefore All A are C',
                'invalid_because': 'Middle term not distributed',
                'severity': 'high'
            },
            'illicit_major': {
                'pattern': 'Conclusion distributes term not distributed in major premise',
                'invalid_because': 'Overgeneralization',
                'severity': 'high'
            },
            'illicit_minor': {
                'pattern': 'Conclusion distributes term not distributed in minor premise',
                'invalid_because': 'Overgeneralization',
                'severity': 'high'
            }
        },
        'informal': {
            'circular_reasoning': {
                'pattern': 'Conclusion assumed in premise',
                'severity': 'critical',
                'example': 'Bible is true because it says so'
            },
            'false_dichotomy': {
                'pattern': 'Only two options when more exist',
                'severity': 'high',
                'example': 'Either you are with us or against us'
            },
            'hasty_generalization': {
                'pattern': 'Insufficient sample for conclusion',
                'severity': 'medium',
                'example': 'Met two rude Parisians, all Parisians are rude'
            },
            'slippery_slope': {
                'pattern': 'Chain reaction without justification',
                'severity': 'medium',
                'example': 'Allow A, then B will happen, then C, then disaster'
            },
            'ad_hominem': {
                'pattern': 'Attack person instead of argument',
                'severity': 'low',
                'example': 'Reject argument because source is biased'
            }
        }
    },

    'inference_rules': {
        'propositional': [
            'modus_ponens', 'modus_tollens', 'disjunctive_syllogism',
            'hypothetical_syllogism', 'constructive_dilemma', 'destructive_dilemma',
            'conjunction', 'simplification', 'addition', 'resolution'
        ],
        'first_order': [
            'universal_instantiation', 'universal_generalization',
            'existential_instantiation', 'existential_generalization',
            'skolemization', 'unification'
        ],
        'derived': [
            'contrapositive', 'de_morgan', 'double_negation',
            'distributivity', 'commutativity', 'associativity'
        ]
    }
}

# Issue categories and severities
ISSUE_CATEGORIES = {
    'critical': [
        'formal_fallacy', 'circular_reasoning', 'invalid_inference',
        'contradictory_premises', 'unsound_argument', 'type_error'
    ],
    'high': [
        'informal_fallacy', 'weak_induction', 'ambiguous_terms',
        'equivocation', 'missing_premise', 'scope_confusion'
    ],
    'medium': [
        'hasty_generalization', 'false_analogy', 'ad_hoc_reasoning',
        'confirmation_bias', 'overfitting_to_examples', 'incomplete_proof'
    ],
    'low': [
        'verbose_proof', 'unclear_notation', 'redundant_steps',
        'missing_explanation', 'notation_inconsistency'
    ]
}

# Feature keywords for classification
FEATURE_KEYWORDS = {
    'deductive': ['therefore', 'hence', 'thus', 'consequently', 'implies', 'if then', 'all', 'every', 'necessarily'],
    'inductive': ['probably', 'likely', 'most', 'generally', 'typically', 'usually', 'often', 'tends to'],
    'abductive': ['best explanation', 'hypothesis', 'suggests', 'indicates', 'plausible', 'diagnostic'],

    'propositional': ['and', 'or', 'not', 'if', 'iff', 'boolean', 'true', 'false'],
    'first_order': ['forall', 'exists', 'all', 'some', 'every', 'there exists', 'for all'],
    'modal': ['necessary', 'possible', 'must', 'might', 'could', 'knows', 'believes'],
    'temporal': ['always', 'eventually', 'until', 'next', 'after', 'before', 'future'],

    'proof': ['proof', 'theorem', 'lemma', 'corollary', 'qed', 'suppose', 'assume', 'given', 'let'],
    'contradiction': ['contradiction', 'absurd', 'impossible', 'contrary', 'assume not'],
    'induction': ['base case', 'inductive step', 'inductive hypothesis', 'n+1', 'recursive'],

    'fallacy': ['fallacy', 'invalid', 'unsound', 'error', 'mistake', 'wrong', 'incorrect'],
    'verification': ['verify', 'validate', 'check', 'test', 'ensure', 'guarantee', 'certify']
}

# Common reasoning issues and their patterns
REASONING_ISSUES = {
    'affirming_consequent': [
        'if A then B', 'B is true', 'therefore A',
        'implies', 'consequence is true', 'conclude antecedent'
    ],
    'denying_antecedent': [
        'if A then B', 'A is false', 'therefore B is false',
        'antecedent not true', 'conclude consequent false'
    ],
    'hasty_generalization': [
        'few examples', 'small sample', 'generalize', 'all',
        'insufficient evidence', 'extrapolate'
    ],
    'circular_reasoning': [
        'assume conclusion', 'beg the question', 'premise equals conclusion',
        'circular', 'proves itself'
    ],
    'missing_premise': [
        'gap in logic', 'unstated assumption', 'implicit premise',
        'leap', 'not justified'
    ],
    'scope_confusion': [
        'quantifier scope', 'all', 'some', 'exists', 'forall',
        'order of quantifiers', 'binding'
    ],
    'type_error': [
        'category mistake', 'type mismatch', 'comparing incomparable',
        'invalid operation', 'domain error'
    ]
}

class SymbolicReasoningExpertTrainer:
    """Train Random Forest to identify reasoning patterns and issues"""

    def __init__(self, db_host='aio-01', db_port=5433, db_user='sfloess', db_name='learning'):
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_name = db_name

        self.db = None
        self.cursor = None

        # ML components
        self.vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 3))
        self.classifier = RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_split=5,
            class_weight='balanced',
            random_state=42
        )

        # Training stats
        self.stats = {
            'training_samples': 0,
            'reasoning_types': defaultdict(int),
            'logical_systems': defaultdict(int),
            'fallacies_detected': defaultdict(int),
            'proof_strategies': defaultdict(int),
            'accuracy': 0.0,
            'f1_score': 0.0,
            'trained_at': None
        }

    def connect(self):
        """Connect to PostgreSQL"""
        self.db = psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            user=self.db_user,
            database=self.db_name
        )
        self.cursor = self.db.cursor()
        print(f"✓ Connected to {self.db_name} on {self.db_host}:{self.db_port}")

    def create_synthetic_training_data(self):
        """Generate synthetic training data from knowledge base"""
        X_text = []
        y_labels = []

        print("Generating synthetic training data...")

        # 1. Reasoning type examples
        reasoning_examples = {
            'deductive_valid': [
                'All humans are mortal. Socrates is human. Therefore Socrates is mortal.',
                'If it rains, the ground gets wet. It is raining. Therefore the ground is wet.',
                'Every prime number greater than 2 is odd. 17 is prime and greater than 2. Therefore 17 is odd.',
                'All squares are rectangles. All rectangles have four sides. Therefore all squares have four sides.',
                'All metals conduct electricity. Copper is a metal. Therefore copper conducts electricity.',
                'If a number is divisible by 10, it is divisible by 5. 30 is divisible by 10. Therefore 30 is divisible by 5.',
                'All mammals breathe air. Whales are mammals. Therefore whales breathe air.',
                'Every even number greater than 2 is composite. 8 is even and greater than 2. Therefore 8 is composite.',
                'If angle sum is 180, then triangle. Angle sum is 180. Therefore triangle.',
                'All birds have feathers. Penguins are birds. Therefore penguins have feathers.'
            ],
            'deductive_invalid': [
                'If it rains, the ground gets wet. The ground is wet. Therefore it rained.',  # affirming consequent
                'If P then Q. Not P. Therefore not Q.',  # denying antecedent
                'All cats are mammals. All dogs are mammals. Therefore all cats are dogs.',  # undistributed middle
                'If you study, you pass. You did not study. Therefore you failed.',
                'All politicians are liars. All liars are untrustworthy. Some politicians are trustworthy.',
                'If it is a dog, it barks. It barks. Therefore it is a dog.',
                'All As are Bs. All Cs are Bs. Therefore all As are Cs.',
                'If elected, taxes increase. Not elected. Therefore taxes do not increase.',
                'All fish swim. All swimmers are athletic. Therefore all fish are athletic.',
                'If you run fast, you win. You did not run fast. Therefore you did not win.'
            ],
            'inductive_strong': [
                'The sun has risen every day for billions of years. Therefore the sun will rise tomorrow.',
                '99% of surveyed voters support policy X. Therefore policy X has majority support.',
                'In 1000 coin flips, 503 were heads. Therefore the coin is fair.',
                'Every observed swan has been white. The next swan will probably be white.',
                '95% of customers rated product 5 stars. Most customers are satisfied.',
                'Metal expands when heated in 10000 experiments. Metal generally expands when heated.',
                'All 50 samples tested positive. Most of the population likely tests positive.',
                'Team won 45 of last 50 games. Team will probably win next game.',
                'Drug cured 90% of 1000 patients. Drug is probably effective.',
                'Price increased every quarter for 10 years. Price will likely increase next quarter.'
            ],
            'inductive_weak': [
                'I met two rude people from Paris. Therefore all Parisians are rude.',  # hasty generalization
                'My car is reliable. Therefore all cars of this brand are reliable.',
                'It rained on my birthday last year. It will rain on my birthday this year.',
                'I ate at that restaurant once and got sick. The restaurant always serves bad food.',
                'Two politicians were corrupt. All politicians are corrupt.',
                'One student cheated. All students in the class are cheaters.',
                'My neighbor has a loud dog. All dogs in the neighborhood are loud.',
                'One experiment failed. This approach never works.',
                'I saw a black cat and had bad luck. Black cats cause bad luck.',
                'Two flights were delayed. This airline is always late.'
            ],
            'abductive': [
                'The grass is wet. The best explanation is that it rained.',
                'Patient has fever, cough, fatigue. Most likely explanation is flu.',
                'Server is down. Most probable cause is network connectivity issue.',
                'Car will not start. Battery is probably dead.',
                'Dog is barking at door. Probably someone is approaching.',
                'Code crashed with null pointer. Likely missing null check.',
                'Stock price dropped 20%. Probably bad earnings report.',
                'Plant leaves are yellow. Most likely nitrogen deficiency.',
                'Computer is slow. Probably low memory or malware.',
                'Test scores improved. Best explanation is better teaching methods.'
            ]
        }

        for category, examples in reasoning_examples.items():
            for example in examples:
                X_text.append(example)
                y_labels.append(category)
                self.stats['reasoning_types'][category] += 1

        # 2. Logical system examples
        logic_examples = {
            'propositional': [
                'P AND Q implies P',
                'P OR NOT P is always true',
                'If (P implies Q) and (Q implies R) then (P implies R)',
                '(P AND Q) OR (P AND R) equals P AND (Q OR R)',
                'NOT (P AND Q) equals (NOT P) OR (NOT Q)',
                'P implies Q is equivalent to NOT P OR Q',
                'P IFF Q means (P implies Q) AND (Q implies P)',
                'If P then Q. If Q then R. Therefore if P then R.',
                '(P OR Q) AND NOT P implies Q',
                'P AND (Q OR R) equals (P AND Q) OR (P AND R)',
                'NOT (P OR Q) equals (NOT P) AND (NOT Q)',
                'P OR Q. NOT Q. Therefore P.',
                'Boolean satisfiability: find assignment making formula true.',
                'Conjunction normal form: AND of OR clauses.',
                'Modus ponens: P implies Q, P, therefore Q.'
            ],
            'first_order': [
                'For all x, if P(x) then Q(x). P(a). Therefore Q(a).',
                'There exists an x such that P(x) and Q(x).',
                'For all x, there exists y such that x < y.',
                'If for all x P(x) then there exists x such that P(x).',
                'For all x for all y, if x < y then not y < x.',
                'There exists x such that for all y, P(x,y).',
                'For all x (P(x) implies Q(x)). For all x P(x). Therefore for all x Q(x).',
                'Skolemization: replace existential with function.',
                'Universal instantiation: from for all x P(x) derive P(a).',
                'Existential generalization: from P(a) derive there exists x P(x).',
                'For all x there exists y such that loves(x,y).',
                'There exists x such that for all y, if human(y) then mortal(y).',
                'Unification: find substitution making terms identical.',
                'Resolution: combine clauses to derive new clause.',
                'Herbrand universe: domain of ground terms.'
            ],
            'modal': [
                'It is necessary that all bachelors are unmarried.',
                'It is possible that aliens exist.',
                'If necessarily P then possibly P.',
                'Agent A knows that P implies Q.',
                'It is necessary that 2+2=4.',
                'Possibly it will rain tomorrow.',
                'If necessarily P and possibly not Q, then possibly (P and not Q).',
                'Knowledge is closed under implication: K(P) and K(P implies Q) implies K(Q).',
                'Belief does not imply truth: B(P) does not imply P.',
                'S5 axiom: if possibly P then necessarily possibly P.',
                'Agent knows that agent knows P implies agent knows P.',
                'It must be true that triangles have three sides.',
                'It might be the case that faster-than-light travel is possible.',
                'Necessarily if P then possibly P.',
                'Common knowledge: everyone knows, everyone knows everyone knows, etc.'
            ],
            'temporal': [
                'Eventually the program terminates.',
                'The system always responds within 1 second.',
                'Request R is handled until completion.',
                'After event A, eventually event B occurs.',
                'Always if request then eventually response.',
                'Safety property: bad state never reached.',
                'Liveness property: good state eventually reached.',
                'Until operator: P holds until Q becomes true.',
                'Next operator: P holds in next state.',
                'Globally operator: P holds in all future states.',
                'Finally operator: P holds in some future state.',
                'Weak until: P until Q, or P forever if Q never holds.',
                'Release operator: Q holds until and including when P holds.',
                'Linear temporal logic: model checker for reactive systems.',
                'Computation tree logic: branching time logic.'
            ]
        }

        for category, examples in logic_examples.items():
            for example in examples:
                X_text.append(example)
                y_labels.append(category)
                self.stats['logical_systems'][category] += 1

        # 3. Fallacy examples
        fallacy_examples = {
            'affirming_consequent': [
                'If Jones is elected, taxes will increase. Taxes increased. Therefore Jones was elected.',
                'If you study hard, you will pass. You passed. Therefore you studied hard.',
                'If it is raining, the streets are wet. The streets are wet. Therefore it is raining.',
                'If program has bug, tests fail. Tests failed. Therefore program has bug.',
                'If you exercise, you lose weight. You lost weight. Therefore you exercised.',
                'If it is hot, ice cream melts. Ice cream melted. Therefore it was hot.',
                'If market crashes, stocks fall. Stocks fell. Therefore market crashed.',
                'If server is down, users complain. Users complained. Therefore server is down.',
                'If medicine works, symptoms improve. Symptoms improved. Therefore medicine worked.',
                'If soil is fertile, plants grow. Plants grew. Therefore soil is fertile.'
            ],
            'denying_antecedent': [
                'If you are a student, you get a discount. You are not a student. Therefore you do not get a discount.',
                'If it is sunny, we will go to the beach. It is not sunny. Therefore we will not go to the beach.',
                'If P is true, Q is true. P is false. Therefore Q is false.',
                'If you are rich, you are happy. You are not rich. Therefore you are not happy.',
                'If code compiles, it runs. Code does not compile. Therefore it does not run.',
                'If alarm sounds, there is fire. Alarm did not sound. Therefore no fire.',
                'If temperature drops, pipes freeze. Temperature did not drop. Therefore pipes did not freeze.',
                'If password is correct, login succeeds. Password incorrect. Therefore login fails.',
                'If hypothesis is true, experiment succeeds. Hypothesis false. Therefore experiment fails.',
                'If you study, you pass. You did not study. Therefore you did not pass.'
            ],
            'circular_reasoning': [
                'The Bible is true because it says so in the Bible.',
                'I am trustworthy because I say I am trustworthy.',
                'This policy is good because it is beneficial, and it is beneficial because it is good.',
                'God exists because the Bible says so, and the Bible is true because God wrote it.',
                'I am right because I am never wrong, and I am never wrong because I am right.',
                'This is the best approach because it is superior, and it is superior because it is the best.',
                'The law is just because it is fair, and it is fair because it is just.',
                'My argument is sound because it is valid, and it is valid because it is sound.',
                'This theory is correct because it explains the data, and it explains the data because it is correct.',
                'Democracy is best because majority rules, and majority rules because democracy is best.'
            ],
            'hasty_generalization': [
                'I met two rude people from city X. Everyone from city X is rude.',
                'My friend got food poisoning at that restaurant. That restaurant always serves bad food.',
                'Two experiments failed. This approach never works.',
                'One politician lied. All politicians are liars.',
                'My car broke down. This brand makes terrible cars.',
                'Two students cheated. The whole class is dishonest.',
                'I saw one bad movie this year. All movies this year are bad.',
                'Three tests failed. The entire codebase is broken.',
                'Two flights were delayed. This airline is always late.',
                'One doctor was incompetent. All doctors are incompetent.'
            ],
            'false_dichotomy': [
                'You are either with us or against us.',
                'Either we cut spending or the economy collapses.',
                'Either you believe in science or you believe in religion.',
                'Either you support the policy or you hate progress.',
                'Either we ban it completely or allow it without restrictions.',
                'Either you trust me completely or you do not trust me at all.',
                'Either we invest everything or we invest nothing.',
                'Either you agree with me or you are ignorant.',
                'Either we go to war or we show weakness.',
                'Either accept this solution or face disaster.'
            ]
        }

        for category, examples in fallacy_examples.items():
            for example in examples:
                X_text.append(example)
                y_labels.append(f'fallacy_{category}')
                self.stats['fallacies_detected'][category] += 1

        # 4. Proof strategy examples
        proof_examples = {
            'direct_proof': [
                'Prove: If n is even, then n^2 is even. Proof: Let n = 2k. Then n^2 = 4k^2 = 2(2k^2), which is even.',
                'Prove: The sum of two odd numbers is even. Let a = 2k+1 and b = 2m+1. Then a+b = 2k+2m+2 = 2(k+m+1).',
                'Prove: If x > 0 and y > 0, then x+y > 0. Since x > 0 and y > 0, x+y > 0+0 = 0.',
                'Prove: If a divides b and b divides c, then a divides c. Let b = ka and c = mb. Then c = m(ka) = (mk)a.',
                'Prove: Sum of two even numbers is even. Let a = 2k, b = 2m. Then a+b = 2k+2m = 2(k+m).',
                'Prove: Product of two odd numbers is odd. Let a = 2k+1, b = 2m+1. Then ab = 4km+2k+2m+1 = 2(2km+k+m)+1.',
                'Prove: If n is divisible by 6, then n is divisible by 3. Since n = 6k and 6 = 2*3, n = (2k)*3.',
                'Prove: Transitivity of equality: if a = b and b = c, then a = c. Substitute b for a in b = c.',
                'Prove: If a < b and c < d, then a+c < b+d. Add inequalities: a+c < b+c < b+d.',
                'Prove: If n^2 is odd then n is odd. Direct: Let n be odd, n = 2k+1. Then n^2 = 4k^2+4k+1 which is odd.'
            ],
            'proof_by_contradiction': [
                'Prove: sqrt(2) is irrational. Assume sqrt(2) = a/b in lowest terms. Then 2b^2 = a^2. Contradiction.',
                'Prove: There are infinitely many primes. Assume finitely many primes p1...pn. Consider N = p1*...*pn + 1. Contradiction.',
                'Prove: There is no largest integer. Assume n is largest. Then n+1 > n. Contradiction.',
                'Prove: sqrt(3) is irrational. Assume sqrt(3) = a/b in lowest terms. Then 3b^2 = a^2. Leads to contradiction.',
                'Prove: There is no rational r with r^2 = 3. Assume r = a/b. Then 3b^2 = a^2. Contradiction.',
                'Prove: log_2(3) is irrational. Assume log_2(3) = a/b. Then 2^(a/b) = 3, so 2^a = 3^b. Contradiction.',
                'Prove: No integer x satisfies 2x = 3. Assume x exists. Then x = 3/2 which is not an integer. Contradiction.',
                'Prove: Set of real numbers is uncountable. Assume countable list. Cantor diagonalization gives contradiction.',
                'Prove: sqrt(p) is irrational for prime p. Assume sqrt(p) = a/b. Then pb^2 = a^2. Contradiction.',
                'Prove: There exist irrational a,b with a^b rational. Assume not. Consider sqrt(2)^sqrt(2). Contradiction.'
            ],
            'proof_by_induction': [
                'Prove: 1+2+...+n = n(n+1)/2. Base: n=1 gives 1. Step: Assume true for n, prove for n+1.',
                'Prove: 2^n > n for all n >= 1. Base: 2^1 = 2 > 1. Step: Assume 2^n > n, then 2^(n+1) = 2*2^n > 2n > n+1.',
                'Prove: n! > 2^n for n >= 4. Base: 4! = 24 > 16 = 2^4. Step: Assume true for n, show for n+1.',
                'Prove: 1^2 + 2^2 + ... + n^2 = n(n+1)(2n+1)/6. Base: n=1 gives 1. Inductive step expands (n+1)^2.',
                'Prove: Fibonacci recurrence F(n+1) = F(n) + F(n-1). Base: F(1)=1, F(2)=1. Step follows definition.',
                'Prove: n^3 - n is divisible by 3 for all n. Base: 0. Step: (n+1)^3 - (n+1) = n^3 + 3n^2 + 3n.',
                'Prove: Sum of first n odd numbers is n^2. Base: 1 = 1^2. Step: add (2n+1) to both sides.',
                'Prove: 2^n >= n+1 for all n >= 0. Base: n=0 gives 1 >= 1. Step: 2^(n+1) = 2*2^n >= 2(n+1).',
                'Prove: Every n >= 2 is product of primes. Base: 2 is prime. Step: n+1 is prime or composite.',
                'Prove: Geometric sum 1 + r + r^2 + ... + r^n = (r^(n+1)-1)/(r-1). Base + inductive step.'
            ],
            'proof_by_contrapositive': [
                'Prove: If n^2 is even, then n is even. Contrapositive: If n is odd, then n^2 is odd. Let n = 2k+1...',
                'Prove: If xy is irrational, then x or y is irrational. Contrapositive: If x and y are rational, xy is rational.',
                'Prove: If n^3 is odd, then n is odd. Contrapositive: If n is even, then n^3 is even.',
                'Prove: If a divides bc and gcd(a,b)=1, then a divides c. Contrapositive approach via Bezout identity.',
                'Prove: If n^2 is divisible by 3, then n is divisible by 3. Contrapositive: if n not divisible by 3, n^2 not divisible by 3.',
                'Prove: If x^2 < y^2 and x,y > 0, then x < y. Contrapositive: if x >= y then x^2 >= y^2.',
                'Prove: If f is not continuous, then f is not differentiable. Contrapositive of: differentiable implies continuous.',
                'Prove: If n is not divisible by 4, then n^2 is not divisible by 16. Contrapositive: divisibility argument.',
                'Prove: If sum of digits not divisible by 9, number not divisible by 9. Contrapositive of divisibility rule.',
                'Prove: If a+b is irrational, then a or b is irrational. Contrapositive: both rational implies sum rational.'
            ]
        }

        for category, examples in proof_examples.items():
            for example in examples:
                X_text.append(example)
                y_labels.append(category)
                self.stats['proof_strategies'][category] += 1

        self.stats['training_samples'] = len(X_text)
        print(f"✓ Generated {len(X_text)} synthetic training examples")

        return X_text, y_labels

    def train(self):
        """Train the classifier"""
        print("\n=== Training Symbolic Reasoning Expert ===\n")

        # Generate training data
        X_text, y_labels = self.create_synthetic_training_data()

        # Vectorize text
        print("Vectorizing text features...")
        X_features = self.vectorizer.fit_transform(X_text)
        print(f"✓ Created feature matrix: {X_features.shape}")

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_features, y_labels, test_size=0.2, random_state=42, stratify=y_labels
        )
        print(f"✓ Split: {X_train.shape[0]} train, {X_test.shape[0]} test")

        # Train classifier
        print("\nTraining Random Forest classifier...")
        self.classifier.fit(X_train, y_train)
        print("✓ Training complete")

        # Evaluate
        y_pred = self.classifier.predict(X_test)
        self.stats['accuracy'] = accuracy_score(y_test, y_pred)
        self.stats['f1_score'] = f1_score(y_test, y_pred, average='weighted')
        self.stats['trained_at'] = datetime.now().isoformat()

        print(f"\n=== Model Performance ===")
        print(f"Accuracy: {self.stats['accuracy']:.3f}")
        print(f"F1 Score: {self.stats['f1_score']:.3f}")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, zero_division=0))

        # Feature importance
        feature_names = self.vectorizer.get_feature_names_out()
        importances = self.classifier.feature_importances_
        top_features = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:20]

        print("\n=== Top 20 Important Features ===")
        for feature, importance in top_features:
            print(f"{feature:20s} {importance:.4f}")

    def save_model(self, output_dir='/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning'):
        """Save trained model and stats"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save classifier
        model_file = output_path / 'symbolic_reasoning_expert.pkl'
        with open(model_file, 'wb') as f:
            pickle.dump({
                'classifier': self.classifier,
                'vectorizer': self.vectorizer,
                'knowledge_base': REASONING_KNOWLEDGE,
                'trained_at': self.stats['trained_at']
            }, f)
        print(f"\n✓ Saved model: {model_file}")

        # Save stats
        stats_file = output_path / 'symbolic_reasoning_expert_stats.json'
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        print(f"✓ Saved stats: {stats_file}")

        return model_file

    def predict(self, text):
        """Predict reasoning category for text"""
        X = self.vectorizer.transform([text])
        prediction = self.classifier.predict(X)[0]
        probabilities = self.classifier.predict_proba(X)[0]
        confidence = max(probabilities)

        return {
            'category': prediction,
            'confidence': float(confidence),
            'all_probabilities': {
                cls: float(prob)
                for cls, prob in zip(self.classifier.classes_, probabilities)
            }
        }

    def analyze_reasoning(self, text):
        """Full reasoning analysis with recommendations"""
        prediction = self.predict(text)
        category = prediction['category']

        analysis = {
            'input': text,
            'category': category,
            'confidence': prediction['confidence'],
            'recommendations': []
        }

        # Add category-specific recommendations
        if category.startswith('fallacy_'):
            fallacy_type = category.replace('fallacy_', '')
            analysis['issue_type'] = 'logical_fallacy'
            analysis['severity'] = 'high'
            analysis['recommendations'].append(f"Detected {fallacy_type} fallacy")

            if fallacy_type == 'affirming_consequent':
                analysis['recommendations'].append("Invalid inference. Q being true doesn't prove P.")
                analysis['recommendations'].append("Consider: Could Q be true for other reasons?")
            elif fallacy_type == 'denying_antecedent':
                analysis['recommendations'].append("Invalid inference. P being false doesn't prove Q is false.")
                analysis['recommendations'].append("Consider: Could Q be true even if P is false?")
            elif fallacy_type == 'circular_reasoning':
                analysis['recommendations'].append("Argument assumes its own conclusion")
                analysis['recommendations'].append("Provide independent justification for premises")
            elif fallacy_type == 'hasty_generalization':
                analysis['recommendations'].append("Insufficient evidence for generalization")
                analysis['recommendations'].append("Increase sample size or qualify conclusion with 'some' instead of 'all'")

        elif category in ['deductive_valid', 'deductive_invalid']:
            analysis['issue_type'] = 'deductive_reasoning'
            analysis['valid'] = (category == 'deductive_valid')
            if category == 'deductive_invalid':
                analysis['severity'] = 'high'
                analysis['recommendations'].append("Check inference rules")
                analysis['recommendations'].append("Verify each step follows from previous")

        elif category in ['inductive_strong', 'inductive_weak']:
            analysis['issue_type'] = 'inductive_reasoning'
            analysis['strength'] = 'strong' if category == 'inductive_strong' else 'weak'
            if category == 'inductive_weak':
                analysis['severity'] = 'medium'
                analysis['recommendations'].append("Consider larger sample size")
                analysis['recommendations'].append("Look for confounding variables")

        elif category.startswith('proof_'):
            proof_strategy = category.replace('proof_', '')
            analysis['issue_type'] = 'proof_strategy'
            analysis['strategy'] = proof_strategy
            analysis['recommendations'].append(f"Using {proof_strategy} approach")

            if proof_strategy == 'by_induction':
                analysis['recommendations'].append("Verify base case")
                analysis['recommendations'].append("Clearly state inductive hypothesis")
                analysis['recommendations'].append("Show inductive step holds")

        return analysis


def main():
    """Main training script"""
    trainer = SymbolicReasoningExpertTrainer()

    try:
        trainer.connect()
        trainer.train()
        model_file = trainer.save_model()

        # Test predictions
        print("\n=== Testing Model ===\n")

        test_cases = [
            "If it rains, the ground gets wet. The ground is wet. Therefore it rained.",
            "All humans are mortal. Socrates is human. Therefore Socrates is mortal.",
            "Prove by induction: sum of first n integers equals n(n+1)/2",
            "I met two rude people from Paris. All Parisians are rude.",
            "For all x there exists y such that x < y"
        ]

        for test_case in test_cases:
            result = trainer.analyze_reasoning(test_case)
            print(f"Input: {test_case[:60]}...")
            print(f"Category: {result['category']} (confidence: {result['confidence']:.2f})")
            if result.get('recommendations'):
                print("Recommendations:")
                for rec in result['recommendations']:
                    print(f"  - {rec}")
            print()

        print("✓ Symbolic Reasoning Expert training complete!")
        print(f"✓ Model saved to: {model_file}")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if trainer.db:
            trainer.db.close()

    return True


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
