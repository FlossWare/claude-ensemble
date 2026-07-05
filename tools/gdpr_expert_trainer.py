#!/usr/bin/env python3
"""
GDPR Expert Trainer

Trains a Random Forest classifier to:
1. Identify data privacy issues and GDPR violations
2. Classify data processing activities by lawful basis
3. Detect consent management problems
4. Recommend right to deletion implementation strategies
5. Flag cross-border data transfer risks
6. Suggest data minimization improvements

Training data sources:
- Historical workflow executions (PostgreSQL)
- GDPR regulation patterns (Articles 6, 7, 17, 44-50)
- Common compliance errors
- Data protection impact assessment patterns
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

# GDPR knowledge base
GDPR_PATTERNS = {
    'lawful_basis': {
        'categories': [
            'consent', 'contract', 'legal_obligation', 'vital_interests',
            'public_task', 'legitimate_interests'
        ],
        'consent_requirements': [
            'freely_given', 'specific', 'informed', 'unambiguous',
            'clear_affirmative_action', 'granular', 'withdrawable', 'documented'
        ],
        'legitimate_interests': [
            'balancing_test', 'necessity_test', 'less_intrusive_means',
            'impact_assessment', 'transparency_notice'
        ]
    },
    'data_subject_rights': {
        'rights': [
            'right_to_access', 'right_to_rectification', 'right_to_erasure',
            'right_to_restriction', 'right_to_portability', 'right_to_object',
            'automated_decision_making_rights'
        ],
        'erasure_conditions': [
            'purpose_fulfilled', 'consent_withdrawn', 'unlawful_processing',
            'legal_obligation', 'child_consent', 'public_interest'
        ],
        'erasure_exceptions': [
            'freedom_of_expression', 'legal_compliance', 'public_health',
            'archiving_public_interest', 'legal_claims'
        ]
    },
    'data_protection_principles': {
        'principles': [
            'lawfulness_fairness_transparency', 'purpose_limitation',
            'data_minimization', 'accuracy', 'storage_limitation',
            'integrity_confidentiality', 'accountability'
        ],
        'data_minimization': [
            'adequate', 'relevant', 'limited_to_necessary', 'purpose_specific',
            'retention_policy', 'automated_deletion'
        ]
    },
    'cross_border_transfers': {
        'mechanisms': [
            'adequacy_decision', 'standard_contractual_clauses', 'binding_corporate_rules',
            'certification', 'code_of_conduct', 'derogations'
        ],
        'schrems_ii_requirements': [
            'transfer_impact_assessment', 'supplementary_measures',
            'encryption_in_transit', 'encryption_at_rest', 'access_controls',
            'government_access_assessment'
        ]
    },
    'technical_measures': {
        'security': [
            'pseudonymization', 'encryption', 'access_control', 'audit_logging',
            'data_breach_detection', 'incident_response', 'privacy_by_design',
            'privacy_by_default'
        ],
        'consent_management': [
            'consent_record', 'consent_withdrawal', 'consent_versioning',
            'granular_consent', 'consent_ui', 'cookie_consent'
        ],
        'deletion_mechanisms': [
            'soft_delete', 'hard_delete', 'anonymization', 'pseudonymization_reversal',
            'backup_deletion', 'third_party_deletion', 'deletion_verification',
            'retention_schedule_automation'
        ]
    }
}

# Issue categories and severities
ISSUE_CATEGORIES = {
    'critical': [
        'unlawful_processing', 'missing_consent', 'invalid_consent',
        'unauthorized_cross_border_transfer', 'inadequate_security',
        'child_data_without_parental_consent', 'data_breach_unreported'
    ],
    'high': [
        'no_lawful_basis_documented', 'consent_not_withdrawable',
        'deletion_request_ignored', 'no_dpia_for_high_risk',
        'processor_contract_missing', 'no_data_breach_procedures',
        'inadequate_sccs', 'missing_encryption'
    ],
    'medium': [
        'unclear_privacy_notice', 'excessive_data_collection',
        'retention_too_long', 'legitimate_interests_not_balanced',
        'portability_not_implemented', 'cookie_consent_issues',
        'access_request_delayed', 'no_consent_records'
    ],
    'low': [
        'privacy_policy_outdated', 'dpo_not_designated',
        'staff_training_needed', 'documentation_incomplete',
        'third_party_audit_overdue', 'consent_ui_unclear'
    ]
}

# Feature keywords for classification
FEATURE_KEYWORDS = {
    'consent': ['consent', 'opt-in', 'opt-out', 'agree', 'accept', 'permission', 'authorization'],
    'deletion': ['delete', 'erase', 'remove', 'right to be forgotten', 'erasure', 'purge', 'anonymize'],
    'data_collection': ['collect', 'gather', 'store', 'process', 'personal data', 'pii', 'sensitive data'],
    'lawful_basis': ['legal basis', 'lawful', 'legitimate interest', 'contract', 'legal obligation'],
    'security': ['encrypt', 'secure', 'protect', 'pseudonymize', 'anonymize', 'access control'],
    'cross_border': ['transfer', 'third country', 'international', 'scc', 'adequacy', 'schrems'],
    'rights': ['access', 'rectification', 'portability', 'object', 'restrict', 'data subject'],
    'compliance': ['gdpr', 'compliance', 'regulation', 'dpa', 'dpia', 'privacy', 'data protection'],
    'breach': ['breach', 'incident', 'unauthorized', 'disclosure', 'leak', 'compromise'],
    'retention': ['retention', 'storage limit', 'keep', 'archive', 'backup', 'dispose']
}

# Common GDPR violations and their patterns
VIOLATION_PATTERNS = {
    'invalid_consent': [
        'pre-ticked checkbox', 'bundled consent', 'consent not granular',
        'no consent withdrawal', 'unclear consent purpose', 'implicit consent',
        'consent for child without parental', 'consent not documented'
    ],
    'unlawful_processing': [
        'no lawful basis', 'purpose creep', 'excessive processing',
        'unnecessary data collection', 'processing without legal ground'
    ],
    'deletion_failures': [
        'erasure request ignored', 'deletion deadline missed', 'incomplete deletion',
        'backup not deleted', 'third party not notified', 'no deletion verification'
    ],
    'transfer_violations': [
        'no adequacy decision', 'no scc', 'no tia', 'insufficient supplementary measures',
        'government access risk', 'unsafe third country'
    ],
    'security_failures': [
        'no encryption', 'weak access control', 'no breach detection',
        'delayed breach notification', 'inadequate pseudonymization'
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
    """Extract GDPR-specific features from text"""
    if not text:
        return {}

    text_lower = text.lower()
    features = {}

    # Feature category detection
    for category, keywords in FEATURE_KEYWORDS.items():
        features[f'has_{category}'] = any(kw in text_lower for kw in keywords)

    # Lawful basis detection
    for basis in GDPR_PATTERNS['lawful_basis']['categories']:
        features[f'basis_{basis}'] = basis.replace('_', ' ') in text_lower

    # Data subject rights detection
    for right in GDPR_PATTERNS['data_subject_rights']['rights']:
        features[f'right_{right}'] = right.replace('_', ' ') in text_lower

    # Violation pattern detection
    for violation_type, patterns in VIOLATION_PATTERNS.items():
        features[f'violation_{violation_type}'] = any(
            pattern in text_lower for pattern in patterns
        )

    # Technical measure detection
    for measure in GDPR_PATTERNS['technical_measures']['security']:
        features[f'tech_{measure}'] = measure.replace('_', ' ') in text_lower

    # Severity indicators
    features['mentions_child_data'] = any(kw in text_lower for kw in ['child', 'minor', 'parental'])
    features['mentions_sensitive_data'] = any(kw in text_lower for kw in
        ['health', 'medical', 'biometric', 'genetic', 'racial', 'religious', 'sexual orientation'])
    features['mentions_automated_decision'] = any(kw in text_lower for kw in
        ['automated', 'profiling', 'algorithm', 'ai decision', 'machine learning'])
    features['mentions_large_scale'] = any(kw in text_lower for kw in
        ['large scale', 'millions', 'mass', 'widespread'])

    return features

def generate_synthetic_training_data():
    """Generate synthetic GDPR training examples"""
    examples = []

    # Critical violations
    examples.extend([
        {
            'text': 'System processes personal data without documented lawful basis. No consent records found.',
            'category': 'unlawful_processing',
            'severity': 'critical',
            'recommendation': 'Immediately halt processing. Document lawful basis per GDPR Article 6. Implement consent management if using consent as basis.'
        },
        {
            'text': 'Child data collected without verifiable parental consent. Age verification missing.',
            'category': 'invalid_consent',
            'severity': 'critical',
            'recommendation': 'Suspend child data processing. Implement age verification (GDPR Article 8). Obtain verifiable parental consent.'
        },
        {
            'text': 'Personal data transferred to USA without SCC or TIA. Schrems II requirements not met.',
            'category': 'transfer_violations',
            'severity': 'critical',
            'recommendation': 'Halt international transfers. Conduct Transfer Impact Assessment. Implement SCCs with supplementary measures per EDPB recommendations.'
        },
        {
            'text': 'Data breach occurred 10 days ago. DPA not notified. No data subject notification.',
            'category': 'security_failures',
            'severity': 'critical',
            'recommendation': 'Immediately notify DPA (72-hour deadline already missed - document reason). Notify affected data subjects. Document breach in register.'
        }
    ])

    # High severity issues
    examples.extend([
        {
            'text': 'User requested data deletion 45 days ago. Request not fulfilled. No response sent.',
            'category': 'deletion_failures',
            'severity': 'high',
            'recommendation': 'Fulfill erasure request immediately (1-month deadline exceeded). Send confirmation to user. Review deletion procedures per Article 17.'
        },
        {
            'text': 'Consent obtained via pre-ticked checkbox. No granular consent options. Cannot withdraw.',
            'category': 'invalid_consent',
            'severity': 'high',
            'recommendation': 'Invalidate current consent. Redesign consent UI (clear affirmative action required). Implement withdrawal mechanism. Re-obtain valid consent.'
        },
        {
            'text': 'High-risk processing activity identified. No Data Protection Impact Assessment conducted.',
            'category': 'unlawful_processing',
            'severity': 'high',
            'recommendation': 'Conduct DPIA per Article 35. Consult DPA if high residual risk. Implement risk mitigation measures before continuing processing.'
        },
        {
            'text': 'Personal data stored in plaintext. No encryption. Access logs disabled.',
            'category': 'security_failures',
            'severity': 'high',
            'recommendation': 'Implement encryption at rest and in transit. Enable comprehensive audit logging. Conduct security audit per Article 32.'
        }
    ])

    # Medium severity issues
    examples.extend([
        {
            'text': 'Collecting phone number, address, and browsing history for newsletter signup.',
            'category': 'unlawful_processing',
            'severity': 'medium',
            'recommendation': 'Apply data minimization principle (Article 5(1)(c)). Email address sufficient for newsletter. Remove excessive data collection.'
        },
        {
            'text': 'User data retained for 10 years. No documented retention policy. Purpose achieved after 2 years.',
            'category': 'unlawful_processing',
            'severity': 'medium',
            'recommendation': 'Implement retention schedule aligned with purpose. Delete data after purpose fulfilled (Article 5(1)(e)). Document retention policy.'
        },
        {
            'text': 'Privacy notice uses vague language. Lawful basis unclear. No information on data retention.',
            'category': 'invalid_consent',
            'severity': 'medium',
            'recommendation': 'Rewrite privacy notice with specific, clear language (Article 12). State lawful basis. Specify retention periods. Use plain language.'
        },
        {
            'text': 'Third-party processor used. No Data Processing Agreement in place.',
            'category': 'unlawful_processing',
            'severity': 'medium',
            'recommendation': 'Suspend data sharing until DPA signed (Article 28). Ensure processor provides sufficient guarantees. Include mandatory clauses.'
        }
    ])

    # Low severity issues
    examples.extend([
        {
            'text': 'Privacy policy last updated 2018. No mention of recent processing activities.',
            'category': 'unlawful_processing',
            'severity': 'low',
            'recommendation': 'Update privacy policy to reflect current processing. Review annually. Communicate changes to users if material.'
        },
        {
            'text': 'Data Protection Officer not designated. Organization processes large scale sensitive data.',
            'category': 'unlawful_processing',
            'severity': 'low',
            'recommendation': 'Assess DPO designation requirement (Article 37). If required, appoint DPO and publish contact details.'
        },
        {
            'text': 'Staff not trained on GDPR. No documented training records.',
            'category': 'security_failures',
            'severity': 'low',
            'recommendation': 'Implement GDPR awareness training for all staff. Document training completion. Review annually.'
        }
    ])

    # Best practice examples (compliant)
    examples.extend([
        {
            'text': 'Consent obtained via clear checkbox. Granular options provided. Withdrawal link in every email. Consent records maintained.',
            'category': 'valid_consent',
            'severity': 'compliant',
            'recommendation': 'Continue current practice. Review consent UI annually. Monitor withdrawal rate.'
        },
        {
            'text': 'Deletion request received. All systems purged within 14 days. Third parties notified. User confirmation sent.',
            'category': 'proper_deletion',
            'severity': 'compliant',
            'recommendation': 'Continue current deletion process. Document procedure. Review third-party deletion quarterly.'
        },
        {
            'text': 'Data encrypted at rest (AES-256) and in transit (TLS 1.3). Access controls via RBAC. Comprehensive audit logs retained.',
            'category': 'proper_security',
            'severity': 'compliant',
            'recommendation': 'Continue current security measures. Regular security audits. Monitor encryption key rotation.'
        }
    ])

    return examples

def load_historical_data():
    """Load GDPR-related patterns from workflow history"""
    db = get_db()
    cursor = db.cursor()

    # Query workflow executions related to privacy, compliance, data protection
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
            LOWER(we.task_description) LIKE '%gdpr%'
            OR LOWER(we.task_description) LIKE '%privacy%'
            OR LOWER(we.task_description) LIKE '%consent%'
            OR LOWER(we.task_description) LIKE '%data protection%'
            OR LOWER(we.task_description) LIKE '%deletion%'
            OR LOWER(we.task_description) LIKE '%erasure%'
            OR LOWER(wr.task_assigned) LIKE '%compliance%'
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

        # Heuristic categorization based on keywords
        category = 'general_compliance'
        severity = 'medium'

        if any(kw in combined_text.lower() for kw in ['consent', 'opt-in', 'permission']):
            category = 'consent_management'
        elif any(kw in combined_text.lower() for kw in ['delete', 'erase', 'removal', 'right to be forgotten']):
            category = 'deletion_request'
        elif any(kw in combined_text.lower() for kw in ['transfer', 'cross-border', 'international']):
            category = 'data_transfer'
        elif any(kw in combined_text.lower() for kw in ['breach', 'incident', 'unauthorized']):
            category = 'security_incident'
            severity = 'high'

        historical.append({
            'text': combined_text,
            'category': category,
            'severity': severity,
            'confidence': float(confidence) if confidence else 0.7
        })

    cursor.close()
    db.close()

    return historical

def train_gdpr_expert():
    """Train Random Forest classifier for GDPR compliance"""
    print("=== GDPR Expert Trainer ===\n")

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

    # Add custom GDPR features
    print("Extracting GDPR-specific features...")
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
    min_class_count = min(np.bincount([categories.index(c) if c in categories else 0 for c in y_category]))
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

    model_path_cat = output_dir / 'gdpr_expert_category.pkl'
    model_path_sev = output_dir / 'gdpr_expert_severity.pkl'
    vectorizer_path = output_dir / 'gdpr_expert_vectorizer.pkl'

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
        'gdpr_expert',
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
with open('/home/sfloess/.claude/learning/gdpr_expert_category.pkl', 'rb') as f:
    clf_category = pickle.load(f)
with open('/home/sfloess/.claude/learning/gdpr_expert_severity.pkl', 'rb') as f:
    clf_severity = pickle.load(f)
with open('/home/sfloess/.claude/learning/gdpr_expert_vectorizer.pkl', 'rb') as f:
    vectorizer = pickle.load(f)

# Analyze text
text = "User requested data deletion but no response after 60 days"
X = vectorizer.transform([text])

# Add custom features
from gdpr_expert_trainer import extract_features
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

    print("\n✅ GDPR Expert training complete!")

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
    results = train_gdpr_expert()
    print(f"\n=== Training Summary ===")
    print(f"Category Accuracy: {results['category_accuracy']:.1%}")
    print(f"Category F1: {results['category_f1']:.3f}")
    print(f"Severity Accuracy: {results['severity_accuracy']:.1%}")
    print(f"Severity F1: {results['severity_f1']:.3f}")
    print(f"Training Samples: {results['training_samples']}")
    print(f"Unique Categories: {results['unique_categories']}")
