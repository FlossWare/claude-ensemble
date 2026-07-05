#!/usr/bin/env python3
"""
Causal Inference Expert Trainer

Trains a Random Forest classifier to:
1. Identify causal relationships vs correlations
2. Detect confounding variables and selection bias
3. Recommend appropriate causal inference methods
4. Identify violations of causal assumptions
5. Suggest experimental designs (RCT, quasi-experimental)
6. Assess causal graph structures (DAGs)

Training data sources:
- Historical workflow executions (PostgreSQL)
- Common causal inference patterns
- Statistical analysis errors
- Experimental design principles
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

# Causal inference knowledge base
CAUSAL_PATTERNS = {
    'causal_relationships': {
        'types': [
            'direct_causation', 'indirect_causation', 'mediation', 'moderation',
            'confounding', 'collider', 'reverse_causation', 'bidirectional'
        ],
        'temporal_criteria': [
            'cause_precedes_effect', 'temporal_contiguity', 'temporal_stability',
            'dose_response_relationship', 'consistency_across_contexts'
        ],
        'hill_criteria': [
            'strength', 'consistency', 'specificity', 'temporality',
            'biological_gradient', 'plausibility', 'coherence',
            'experiment', 'analogy'
        ]
    },
    'bias_types': {
        'selection_bias': [
            'sampling_bias', 'self_selection', 'survivorship_bias',
            'berkson_paradox', 'collider_bias', 'attrition_bias'
        ],
        'confounding_bias': [
            'omitted_variable_bias', 'unmeasured_confounding',
            'time_varying_confounding', 'negative_confounding',
            'residual_confounding'
        ],
        'information_bias': [
            'measurement_error', 'recall_bias', 'observer_bias',
            'detection_bias', 'social_desirability_bias'
        ],
        'other_bias': [
            'regression_to_mean', 'healthy_user_bias', 'immortal_time_bias',
            'publication_bias', 'p_hacking', 'harking'
        ]
    },
    'causal_methods': {
        'randomized_experiments': [
            'rct', 'factorial_design', 'crossover_design', 'cluster_rct',
            'stepped_wedge', 'adaptive_trial', 'pragmatic_trial'
        ],
        'quasi_experimental': [
            'difference_in_differences', 'regression_discontinuity',
            'interrupted_time_series', 'synthetic_control',
            'instrumental_variables', 'propensity_score_matching',
            'inverse_probability_weighting'
        ],
        'observational_methods': [
            'stratification', 'matching', 'regression_adjustment',
            'doubly_robust_estimation', 'sensitivity_analysis',
            'negative_control', 'falsification_test'
        ],
        'graphical_methods': [
            'dag', 'causal_graph', 'path_analysis', 'structural_equation_modeling',
            'backdoor_criterion', 'frontdoor_criterion', 'd_separation'
        ]
    },
    'assumptions': {
        'causal_identification': [
            'exchangeability', 'positivity', 'consistency', 'no_interference',
            'stable_unit_treatment_value', 'ignorability', 'unconfoundedness'
        ],
        'instrumental_variables': [
            'relevance', 'independence', 'exclusion_restriction',
            'monotonicity', 'homogeneity'
        ],
        'regression_discontinuity': [
            'continuity_at_cutoff', 'no_manipulation', 'correct_functional_form',
            'local_randomization', 'no_other_discontinuities'
        ],
        'difference_in_differences': [
            'parallel_trends', 'no_anticipation', 'no_composition_changes',
            'common_shocks', 'treatment_exogeneity'
        ]
    },
    'effect_types': {
        'effects': [
            'average_treatment_effect', 'average_treatment_effect_treated',
            'conditional_average_treatment_effect', 'local_average_treatment_effect',
            'intention_to_treat', 'per_protocol', 'complier_average_causal_effect'
        ],
        'heterogeneity': [
            'subgroup_analysis', 'effect_modification', 'interaction',
            'moderator_analysis', 'differential_effects'
        ]
    }
}

# Issue categories and severities
ISSUE_CATEGORIES = {
    'critical': [
        'reverse_causation_claimed', 'confounding_ignored', 'selection_bias_unaddressed',
        'temporal_order_violated', 'no_control_group', 'p_hacking_detected',
        'causal_claim_without_evidence', 'collider_conditioning'
    ],
    'high': [
        'correlation_as_causation', 'unmeasured_confounding', 'missing_dag',
        'assumption_violation', 'wrong_causal_method', 'insufficient_sample_size',
        'no_sensitivity_analysis', 'invalid_instrumental_variable',
        'parallel_trends_violated', 'manipulation_around_cutoff'
    ],
    'medium': [
        'weak_temporal_evidence', 'limited_external_validity', 'measurement_error',
        'missing_covariates', 'model_misspecification', 'extrapolation_risk',
        'inadequate_controls', 'missing_mechanism_explanation',
        'no_robustness_checks', 'effect_heterogeneity_ignored'
    ],
    'low': [
        'unclear_causal_language', 'missing_dag_justification',
        'insufficient_background_knowledge', 'minor_assumption_concerns',
        'limited_replication', 'incomplete_reporting'
    ]
}

# Feature keywords for classification
FEATURE_KEYWORDS = {
    'causation': ['cause', 'effect', 'causal', 'influence', 'impact', 'determine', 'lead to', 'result in'],
    'correlation': ['correlate', 'associate', 'relate', 'relationship', 'linked', 'connected', 'pattern'],
    'confounding': ['confounder', 'confounding', 'third variable', 'omitted variable', 'lurking variable', 'backdoor'],
    'temporal': ['before', 'after', 'precede', 'follow', 'temporal', 'time', 'sequence', 'lag', 'longitudinal'],
    'randomization': ['random', 'randomize', 'rct', 'trial', 'experiment', 'treatment', 'control', 'placebo'],
    'bias': ['bias', 'selection', 'confound', 'endogenous', 'spurious', 'artifact', 'systematic error'],
    'methods': ['did', 'difference-in-differences', 'regression discontinuity', 'iv', 'instrumental variable',
                'propensity score', 'matching', 'dag', 'causal graph'],
    'assumptions': ['assume', 'assumption', 'exchangeability', 'positivity', 'consistency', 'parallel trends',
                    'exogeneity', 'exclusion restriction'],
    'measurement': ['measure', 'outcome', 'exposure', 'treatment', 'covariate', 'variable', 'indicator'],
    'validity': ['internal validity', 'external validity', 'generalize', 'replicate', 'robust', 'sensitivity']
}

# Common causal inference errors
ERROR_PATTERNS = {
    'correlation_causation_confusion': [
        'correlation implies causation', 'correlation means causation',
        'associated therefore causes', 'related therefore causal',
        'X and Y correlate so X causes Y', 'significant correlation proves causation'
    ],
    'reverse_causation': [
        'reverse causality', 'backwards causation', 'effect precedes cause',
        'outcome causes treatment', 'circular causation unaddressed'
    ],
    'confounding_errors': [
        'confounding not controlled', 'third variable ignored',
        'omitted variable bias', 'unmeasured confounding',
        'backdoor path not blocked', 'confounding structure unclear'
    ],
    'selection_bias': [
        'selection bias', 'sampling bias', 'collider bias',
        'berkson paradox', 'survivorship bias', 'self-selection'
    ],
    'temporal_errors': [
        'temporal order unclear', 'simultaneity bias',
        'reverse temporal order', 'time-varying confounding',
        'anticipation effects', 'dynamic selection'
    ],
    'assumption_violations': [
        'parallel trends violated', 'positivity violated',
        'consistency violated', 'exclusion restriction violated',
        'no manipulation check', 'weak instrument'
    ],
    'methodological_errors': [
        'wrong causal method', 'inappropriate design',
        'inadequate sample size', 'model misspecification',
        'extrapolation beyond support', 'no falsification test',
        'missing sensitivity analysis'
    ]
}

# Valid causal inference patterns
VALID_PATTERNS = {
    'randomized_control_trial': [
        'rct', 'randomized controlled trial', 'random assignment',
        'double blind', 'placebo control', 'treatment and control groups'
    ],
    'natural_experiment': [
        'natural experiment', 'quasi-experiment', 'regression discontinuity',
        'difference-in-differences', 'instrumental variable', 'event study'
    ],
    'causal_diagram': [
        'directed acyclic graph', 'dag', 'causal graph',
        'backdoor criterion', 'frontdoor criterion', 'd-separation',
        'conditional independence'
    ],
    'robust_analysis': [
        'sensitivity analysis', 'robustness check', 'falsification test',
        'placebo test', 'negative control', 'multiple estimation methods',
        'subgroup analysis', 'heterogeneity analysis'
    ]
}

def get_db():
    """Connect to PostgreSQL learning database"""
    return psycopg2.connect(
        host='aio-01',
        port=5433,
        user='sfloess',
        database='learning'
    )

def extract_features(text):
    """Extract causal inference-specific features from text"""
    if not text:
        return {}

    text_lower = text.lower()
    features = {}

    # Feature category detection
    for category, keywords in FEATURE_KEYWORDS.items():
        features[f'has_{category}'] = any(kw in text_lower for kw in keywords)

    # Causal relationship type detection
    for rel_type in CAUSAL_PATTERNS['causal_relationships']['types']:
        features[f'rel_{rel_type}'] = rel_type.replace('_', ' ') in text_lower

    # Bias type detection
    for bias_category, bias_types in CAUSAL_PATTERNS['bias_types'].items():
        for bias_type in bias_types:
            features[f'bias_{bias_type}'] = bias_type.replace('_', ' ') in text_lower

    # Causal method detection
    for method_category, methods in CAUSAL_PATTERNS['causal_methods'].items():
        for method in methods:
            features[f'method_{method}'] = method.replace('_', ' ') in text_lower

    # Error pattern detection
    for error_type, patterns in ERROR_PATTERNS.items():
        features[f'error_{error_type}'] = any(
            pattern in text_lower for pattern in patterns
        )

    # Valid pattern detection
    for valid_type, patterns in VALID_PATTERNS.items():
        features[f'valid_{valid_type}'] = any(
            pattern in text_lower for pattern in patterns
        )

    # Specific indicators
    features['claims_causation'] = any(kw in text_lower for kw in
        ['causes', 'caused by', 'leads to', 'results in', 'determines', 'influences'])
    features['acknowledges_limitation'] = any(kw in text_lower for kw in
        ['limitation', 'caveat', 'however', 'although', 'despite', 'cannot conclude'])
    features['mentions_mechanism'] = any(kw in text_lower for kw in
        ['mechanism', 'pathway', 'mediation', 'process', 'how', 'why'])
    features['quantifies_effect'] = any(kw in text_lower for kw in
        ['effect size', 'magnitude', 'percentage', 'percent', 'increase', 'decrease'])
    features['discusses_temporality'] = any(kw in text_lower for kw in
        ['before', 'after', 'temporal', 'longitudinal', 'time', 'lag', 'precedence'])
    features['uses_counterfactual'] = any(kw in text_lower for kw in
        ['counterfactual', 'what if', 'had not', 'would have', 'potential outcome'])

    return features

def generate_synthetic_training_data():
    """Generate synthetic causal inference training examples"""
    examples = []

    # Critical errors
    examples.extend([
        {
            'text': 'Ice cream sales and drowning deaths are correlated, therefore ice cream causes drowning.',
            'category': 'correlation_causation_confusion',
            'severity': 'critical',
            'recommendation': 'This confuses correlation with causation. Temperature is a confounder affecting both ice cream sales and swimming activity. Use causal diagram to identify confounding structure.'
        },
        {
            'text': 'Students who study more get better grades. Analysis shows higher GPA predicts more study time.',
            'category': 'reverse_causation',
            'severity': 'critical',
            'recommendation': 'Reverse causation error - temporal order is backwards. Studying causes grades, not vice versa. Use longitudinal data to establish temporal precedence.'
        },
        {
            'text': 'Drug shows efficacy in observational study. No adjustment for confounding. Claim causal effect.',
            'category': 'confounding_errors',
            'severity': 'critical',
            'recommendation': 'Cannot claim causation without controlling confounding. Use DAG to identify confounders. Apply propensity score matching, inverse probability weighting, or conduct RCT.'
        },
        {
            'text': 'Hospital quality measured by patient outcomes. Sicker patients go to better hospitals (selection).',
            'category': 'selection_bias',
            'severity': 'critical',
            'recommendation': 'Collider bias - conditioning on hospital selection. Use instrumental variable (e.g., distance) or adjust for severity. Cannot interpret as causal without addressing selection.'
        },
        {
            'text': 'Policy implemented gradually. Compare early vs late adopters as treatment vs control.',
            'category': 'temporal_errors',
            'severity': 'critical',
            'recommendation': 'Dynamic selection bias - early adopters differ systematically. Use staggered difference-in-differences with appropriate identification assumptions. Check parallel trends.'
        },
        {
            'text': 'Claim policy reduced crime by comparing before/after trends, but no control group.',
            'category': 'methodological_errors',
            'severity': 'critical',
            'recommendation': 'Missing counterfactual. Cannot attribute changes to policy without control group. Use difference-in-differences, synthetic control, or comparative interrupted time series.'
        }
    ])

    # High severity issues
    examples.extend([
        {
            'text': 'Education and income are correlated. Conclude education causes higher income.',
            'category': 'correlation_causation_confusion',
            'severity': 'high',
            'recommendation': 'Correlation present but causation unclear. Ability, family background are confounders. Use instrumental variable (e.g., compulsory schooling laws) or sibling/twin fixed effects.'
        },
        {
            'text': 'Regression discontinuity design but individuals can manipulate assignment variable.',
            'category': 'assumption_violations',
            'severity': 'high',
            'recommendation': 'Manipulation violates RD assumptions. Test for bunching at cutoff (McCrary test). Use donut RD, exclude observations near cutoff, or find different design.'
        },
        {
            'text': 'Difference-in-differences analysis assumes parallel trends but no evidence provided.',
            'category': 'assumption_violations',
            'severity': 'high',
            'recommendation': 'Parallel trends is untestable but crucial assumption. Show pre-treatment trends are parallel. Conduct event study. Use matching to improve pre-treatment balance.'
        },
        {
            'text': 'Instrumental variable analysis with weak instrument (F-statistic = 5).',
            'category': 'methodological_errors',
            'severity': 'high',
            'recommendation': 'Weak instrument bias toward OLS. Rule of thumb: F > 10. Find stronger instrument, use LIML estimator, or report weak-IV robust confidence intervals (Anderson-Rubin).'
        },
        {
            'text': 'Propensity score matching with poor overlap. Treatment group has no common support.',
            'category': 'assumption_violations',
            'severity': 'high',
            'recommendation': 'Positivity violation - extrapolating beyond data support. Trim non-overlapping observations. Report common support diagnostics. Consider alternative methods or acknowledge limited generalizability.'
        },
        {
            'text': 'Causal claim based on p-value < 0.05 alone. No effect size, confidence interval, or robustness checks.',
            'category': 'methodological_errors',
            'severity': 'high',
            'recommendation': 'Statistical significance ≠ causation. Report effect size and substantive significance. Conduct sensitivity analysis. Use multiple estimation methods. Consider alternative explanations.'
        }
    ])

    # Medium severity issues
    examples.extend([
        {
            'text': 'Survey shows people who exercise live longer. No controls for baseline health.',
            'category': 'confounding_errors',
            'severity': 'medium',
            'recommendation': 'Healthy user bias - baseline health is confounder. Control for pre-exercise health status. Use inverse probability weighting for time-varying confounding. Consider immortal time bias.'
        },
        {
            'text': 'Training program effect estimated but no mechanism explanation provided.',
            'category': 'methodological_errors',
            'severity': 'medium',
            'recommendation': 'Understanding mechanism strengthens causal inference. Conduct mediation analysis. Examine heterogeneous effects. Test intermediate outcomes. Improves external validity.'
        },
        {
            'text': 'Observational study with strong selection on observables. No sensitivity to unmeasured confounding.',
            'category': 'methodological_errors',
            'severity': 'medium',
            'recommendation': 'Conduct sensitivity analysis for unmeasured confounding (e.g., Rosenbaum bounds, E-value). Discuss plausible confounders. Use negative controls. Acknowledge limitation.'
        },
        {
            'text': 'Causal effect estimated on small subgroup. Generalization to population unclear.',
            'category': 'methodological_errors',
            'severity': 'medium',
            'recommendation': 'LATE (local average treatment effect) may not generalize. Assess external validity. Compare treated vs population characteristics. Explore effect heterogeneity. Acknowledge scope.'
        },
        {
            'text': 'Regression with many controls added until significance achieved.',
            'category': 'methodological_errors',
            'severity': 'medium',
            'recommendation': 'Researcher degrees of freedom/p-hacking. Pre-specify model. Use DAG to justify controls. Avoid post-treatment controls. Report specification curve. Use theory-driven selection.'
        }
    ])

    # Low severity issues
    examples.extend([
        {
            'text': 'Causal inference study but DAG not presented or justified.',
            'category': 'methodological_errors',
            'severity': 'low',
            'recommendation': 'DAG makes causal assumptions explicit. Draw assumed causal structure. Justify with theory or prior research. Helps identify confounders and colliders.'
        },
        {
            'text': 'Uses causal language ("impact", "effect") for purely correlational analysis.',
            'category': 'correlation_causation_confusion',
            'severity': 'low',
            'recommendation': 'Use precise language. "Association" for correlational findings. Reserve "causal effect" for designs with identification strategy. Distinguish descriptive from causal inference.'
        },
        {
            'text': 'Single robustness check performed. No falsification tests or alternative specifications.',
            'category': 'methodological_errors',
            'severity': 'low',
            'recommendation': 'Multiple robustness checks strengthen inference. Vary estimation method, sample, specification. Conduct placebo tests. Test for anticipation effects. Report specification curve.'
        }
    ])

    # Best practices (valid causal inference)
    examples.extend([
        {
            'text': 'RCT with random assignment, double-blind, intention-to-treat analysis, and pre-registered protocol.',
            'category': 'valid_randomized_control',
            'severity': 'compliant',
            'recommendation': 'Gold standard design. Continue ITT as primary analysis. Consider per-protocol as sensitivity. Report CONSORT checklist. Address attrition if present.'
        },
        {
            'text': 'Difference-in-differences with parallel pre-trends shown, event study, and multiple robustness checks.',
            'category': 'valid_quasi_experimental',
            'severity': 'compliant',
            'recommendation': 'Strong quasi-experimental design. Event study shows assumption validity. Consider heterogeneous effects by timing. Test for composition changes.'
        },
        {
            'text': 'Regression discontinuity with continuity tests, bunching analysis, and donut specification.',
            'category': 'valid_quasi_experimental',
            'severity': 'compliant',
            'recommendation': 'Credible RD design. Continue donut as robustness. Report RD checklist. Consider bandwidth sensitivity. Explore effect heterogeneity away from cutoff if relevant.'
        },
        {
            'text': 'Observational study with DAG, multiple methods (matching, weighting, regression), sensitivity analysis for unmeasured confounding.',
            'category': 'valid_observational_analysis',
            'severity': 'compliant',
            'recommendation': 'Rigorous observational analysis. DAG makes assumptions transparent. Triangulation across methods strengthens inference. Sensitivity analysis bounds unmeasured confounding impact.'
        },
        {
            'text': 'IV analysis with strong first stage (F>20), exclusion restriction justified, overidentification test, weak-IV robust inference.',
            'category': 'valid_quasi_experimental',
            'severity': 'compliant',
            'recommendation': 'Strong IV design. Exclusion restriction is critical assumption - continue providing justification. LATE interpretation clear. Consider MTE for effect heterogeneity.'
        }
    ])

    return examples

def load_historical_data():
    """Load causal inference-related patterns from workflow history"""
    db = get_db()
    cursor = db.cursor()

    # Query workflow executions related to causal analysis, statistics, research
    cursor.execute("""
        SELECT
            we.task_description,
            wr.task_assigned,
            wr.result,
            wr.confidence,
            wr.outcome
        FROM workflow.worker_results wr
        JOIN workflow.executions we ON wr.workflow_execution_id = we.id
        WHERE (
            LOWER(we.task_description) LIKE '%causal%'
            OR LOWER(we.task_description) LIKE '%correlation%'
            OR LOWER(we.task_description) LIKE '%statistical%'
            OR LOWER(we.task_description) LIKE '%analysis%'
            OR LOWER(we.task_description) LIKE '%experiment%'
            OR LOWER(we.task_description) LIKE '%research%'
            OR LOWER(wr.task_assigned) LIKE '%regression%'
            OR LOWER(wr.task_assigned) LIKE '%effect%'
        )
        AND wr.outcome = 'success'
        AND wr.confidence > 0.6
        ORDER BY we.created_at DESC
        LIMIT 500
    """)

    historical = []
    for row in cursor.fetchall():
        task_desc, task_assigned, result, confidence, outcome = row
        combined_text = f"{task_desc or ''} {task_assigned or ''} {result or ''}"

        # Heuristic categorization
        category = 'general_analysis'
        severity = 'medium'

        text_lower = combined_text.lower()

        # Check for error patterns
        if any(kw in text_lower for kw in ['correlation', 'correlate', 'associate']) and \
           any(kw in text_lower for kw in ['cause', 'effect', 'impact']):
            category = 'correlation_causation_confusion'
            severity = 'high'
        elif any(kw in text_lower for kw in ['confound', 'third variable', 'omitted variable']):
            category = 'confounding_errors'
            severity = 'high'
        elif any(kw in text_lower for kw in ['selection bias', 'sampling bias', 'collider']):
            category = 'selection_bias'
            severity = 'high'
        elif any(kw in text_lower for kw in ['rct', 'randomized', 'experiment', 'trial']):
            category = 'valid_randomized_control'
            severity = 'compliant'
        elif any(kw in text_lower for kw in ['did', 'difference-in-differences', 'regression discontinuity', 'iv']):
            category = 'valid_quasi_experimental'
            severity = 'compliant'

        historical.append({
            'text': combined_text,
            'category': category,
            'severity': severity,
            'confidence': float(confidence) if confidence else 0.7
        })

    cursor.close()
    db.close()

    return historical

def train_causal_inference_expert():
    """Train Random Forest classifier for causal inference"""
    print("=== Causal Inference Expert Trainer ===\n")

    # Generate training data
    print("Generating synthetic training data...")
    synthetic_data = generate_synthetic_training_data()
    print(f"  Synthetic examples: {len(synthetic_data)}")

    # Load historical data
    print("Loading historical workflow data...")
    historical_data = load_historical_data()
    print(f"  Historical examples: {len(historical_data)}")

    # Combine datasets
    all_data = synthetic_data + historical_data
    print(f"  Total training examples: {len(all_data)}")

    if len(all_data) < 10:
        print("\n⚠️  Insufficient training data. Using synthetic data only.")
        all_data = synthetic_data

    # Prepare features and labels
    texts = [ex['text'] for ex in all_data]
    categories = [ex['category'] for ex in all_data]
    severities = [ex['severity'] for ex in all_data]

    # TF-IDF vectorization
    print("\nVectorizing text data...")
    vectorizer = TfidfVectorizer(
        max_features=500,
        ngram_range=(1, 3),
        min_df=1,
        max_df=0.95
    )
    X = vectorizer.fit_transform(texts)

    # Add custom causal inference features
    print("Extracting causal inference-specific features...")
    custom_features = []
    for text in texts:
        feat = extract_features(text)
        custom_features.append(list(feat.values()))

    X_custom = np.array(custom_features)
    X_combined = np.hstack([X.toarray(), X_custom])

    print(f"  Feature matrix shape: {X_combined.shape}")

    # Train category classifier
    print("\nTraining category classifier...")
    y_category = np.array(categories)

    # Use stratified split if we have enough samples per class
    unique, counts = np.unique(y_category, return_counts=True)
    min_class_count = counts.min()
    use_stratify = min_class_count >= 2

    if use_stratify:
        X_train, X_test, y_train, y_test = train_test_split(
            X_combined, y_category, test_size=0.2, random_state=42, stratify=y_category
        )
    else:
        print("  ⚠️  Small dataset - using random split (no stratification)")
        X_train, X_test, y_train, y_test = train_test_split(
            X_combined, y_category, test_size=0.2, random_state=42
        )

    clf_category = RandomForestClassifier(
        n_estimators=100,
        max_depth=20,
        min_samples_split=5,
        random_state=42
    )
    clf_category.fit(X_train, y_train)

    y_pred = clf_category.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average='weighted')

    print(f"\n=== Category Classifier Results ===")
    print(f"  Accuracy: {accuracy:.2%}")
    print(f"  F1 Score: {f1:.3f}")
    print(f"  Training samples: {len(X_train)}")
    print(f"  Test samples: {len(X_test)}")

    # Train severity classifier
    print("\nTraining severity classifier...")
    y_severity = np.array(severities)

    X_train_sev, X_test_sev, y_train_sev, y_test_sev = train_test_split(
        X_combined, y_severity, test_size=0.2, random_state=42
    )

    clf_severity = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        random_state=42
    )
    clf_severity.fit(X_train_sev, y_train_sev)

    y_pred_sev = clf_severity.predict(X_test_sev)
    accuracy_sev = accuracy_score(y_test_sev, y_pred_sev)
    f1_sev = f1_score(y_test_sev, y_pred_sev, average='weighted')

    print(f"\n=== Severity Classifier Results ===")
    print(f"  Accuracy: {accuracy_sev:.2%}")
    print(f"  F1 Score: {f1_sev:.3f}")

    # Save models
    output_dir = Path('/home/sfloess/.claude/learning')
    output_dir.mkdir(exist_ok=True)

    model_path_cat = output_dir / 'causal_inference_expert_category.pkl'
    model_path_sev = output_dir / 'causal_inference_expert_severity.pkl'
    vectorizer_path = output_dir / 'causal_inference_expert_vectorizer.pkl'

    with open(model_path_cat, 'wb') as f:
        pickle.dump(clf_category, f)
    with open(model_path_sev, 'wb') as f:
        pickle.dump(clf_severity, f)
    with open(vectorizer_path, 'wb') as f:
        pickle.dump(vectorizer, f)

    print(f"\n=== Models Saved ===")
    print(f"  Category model: {model_path_cat}")
    print(f"  Severity model: {model_path_sev}")
    print(f"  Vectorizer: {vectorizer_path}")

    # Save metadata to PostgreSQL
    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning.specialist_models (
            model_name VARCHAR PRIMARY KEY,
            model_type VARCHAR,
            accuracy FLOAT,
            f1_score FLOAT,
            training_samples INTEGER,
            categories TEXT[],
            model_path VARCHAR,
            vectorizer_path VARCHAR,
            trained_at TIMESTAMP DEFAULT NOW()
        )
    """)

    unique_categories = list(set(categories))

    cursor.execute("""
        INSERT INTO learning.specialist_models
        (model_name, model_type, accuracy, f1_score, training_samples,
         categories, model_path, vectorizer_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (model_name) DO UPDATE SET
            accuracy = EXCLUDED.accuracy,
            f1_score = EXCLUDED.f1_score,
            training_samples = EXCLUDED.training_samples,
            trained_at = NOW()
    """, (
        'causal_inference_expert',
        'RandomForest',
        float(accuracy),
        float(f1),
        len(all_data),
        unique_categories,
        str(model_path_cat),
        str(vectorizer_path)
    ))

    db.commit()
    cursor.close()
    db.close()

    print("\n=== Usage Example ===")
    print("""
import pickle
import numpy as np

# Load models
with open('/home/sfloess/.claude/learning/causal_inference_expert_category.pkl', 'rb') as f:
    clf_category = pickle.load(f)
with open('/home/sfloess/.claude/learning/causal_inference_expert_severity.pkl', 'rb') as f:
    clf_severity = pickle.load(f)
with open('/home/sfloess/.claude/learning/causal_inference_expert_vectorizer.pkl', 'rb') as f:
    vectorizer = pickle.load(f)

# Analyze text
text = "Ice cream sales correlate with drowning deaths, so ice cream causes drowning"
X = vectorizer.transform([text])

# Add custom features
from causal_inference_expert_trainer import extract_features
custom_feat = extract_features(text)
X_custom = np.array([list(custom_feat.values())])
X_combined = np.hstack([X.toarray(), X_custom])

# Predict
category = clf_category.predict(X_combined)[0]
severity = clf_severity.predict(X_combined)[0]
confidence = clf_category.predict_proba(X_combined).max()

print(f"Category: {category}")
print(f"Severity: {severity}")
print(f"Confidence: {confidence:.1%}")
""")

    print("\n✅ Causal Inference Expert training complete!")

    return {
        'category_accuracy': accuracy,
        'category_f1': f1,
        'severity_accuracy': accuracy_sev,
        'severity_f1': f1_sev,
        'training_samples': len(all_data),
        'test_samples': len(X_test),
        'unique_categories': len(unique_categories)
    }

if __name__ == '__main__':
    results = train_causal_inference_expert()
    print(f"\n=== Training Summary ===")
    print(f"Category Accuracy: {results['category_accuracy']:.1%}")
    print(f"Category F1: {results['category_f1']:.3f}")
    print(f"Severity Accuracy: {results['severity_accuracy']:.1%}")
    print(f"Severity F1: {results['severity_f1']:.3f}")
    print(f"Training Samples: {results['training_samples']}")
    print(f"Unique Categories: {results['unique_categories']}")
