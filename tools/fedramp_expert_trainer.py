#!/usr/bin/env python3
"""
FedRAMP Expert Trainer

Trains a Random Forest classifier to:
1. Identify FedRAMP compliance requirements (Low/Moderate/High baselines)
2. Map NIST 800-53 controls to implementation guidance
3. Detect common compliance gaps in cloud architectures
4. Recommend remediation steps for authorization packages
5. Guide ATO (Authority to Operate) process steps

Training data sources:
- Historical workflow executions (PostgreSQL)
- FedRAMP control patterns
- Common compliance issues
- NIST 800-53 Rev 5 control families
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

# FedRAMP knowledge base
FEDRAMP_KNOWLEDGE = {
    'baselines': {
        'Low': {
            'controls': 125,
            'use_cases': ['Public websites', 'Low-impact SaaS', 'Non-sensitive data'],
            'processing_time': '3-6 months',
            'cost_estimate': '$100k-250k'
        },
        'Moderate': {
            'controls': 325,
            'use_cases': ['PII', 'Financial data', 'Healthcare (non-PHI)', 'CUI'],
            'processing_time': '6-12 months',
            'cost_estimate': '$250k-750k'
        },
        'High': {
            'controls': 421,
            'use_cases': ['Law enforcement', 'Emergency services', 'National security', 'PHI'],
            'processing_time': '12-24 months',
            'cost_estimate': '$1M-3M+'
        },
        'LI-SaaS': {
            'controls': 146,
            'use_cases': ['Leveraging FedRAMP authorized IaaS/PaaS'],
            'processing_time': '3-6 months',
            'cost_estimate': '$150k-400k'
        }
    },
    'control_families': {
        'AC': {'name': 'Access Control', 'priority': 'critical'},
        'AU': {'name': 'Audit and Accountability', 'priority': 'high'},
        'AT': {'name': 'Awareness and Training', 'priority': 'medium'},
        'CM': {'name': 'Configuration Management', 'priority': 'critical'},
        'CP': {'name': 'Contingency Planning', 'priority': 'high'},
        'IA': {'name': 'Identification and Authentication', 'priority': 'critical'},
        'IR': {'name': 'Incident Response', 'priority': 'high'},
        'MA': {'name': 'Maintenance', 'priority': 'medium'},
        'MP': {'name': 'Media Protection', 'priority': 'medium'},
        'PE': {'name': 'Physical and Environmental Protection', 'priority': 'high'},
        'PL': {'name': 'Planning', 'priority': 'medium'},
        'PS': {'name': 'Personnel Security', 'priority': 'medium'},
        'RA': {'name': 'Risk Assessment', 'priority': 'high'},
        'CA': {'name': 'Security Assessment and Authorization', 'priority': 'critical'},
        'SC': {'name': 'System and Communications Protection', 'priority': 'critical'},
        'SI': {'name': 'System and Information Integrity', 'priority': 'critical'},
        'SA': {'name': 'System and Services Acquisition', 'priority': 'medium'},
        'PM': {'name': 'Program Management', 'priority': 'low'}
    },
    'common_gaps': {
        'encryption_at_rest': {
            'controls': ['SC-28', 'SC-28(1)'],
            'severity': 'critical',
            'remediation': 'Enable FIPS 140-2 validated encryption for all data at rest'
        },
        'encryption_in_transit': {
            'controls': ['SC-8', 'SC-8(1)', 'SC-13'],
            'severity': 'critical',
            'remediation': 'Enforce TLS 1.2+ for all network communications'
        },
        'mfa_missing': {
            'controls': ['IA-2(1)', 'IA-2(2)', 'IA-2(11)'],
            'severity': 'critical',
            'remediation': 'Implement PIV/CAC or FIPS 140-2 Level 1+ MFA for all privileged users'
        },
        'logging_insufficient': {
            'controls': ['AU-2', 'AU-3', 'AU-6', 'AU-12'],
            'severity': 'high',
            'remediation': 'Enable comprehensive audit logging with minimum 90-day retention'
        },
        'incident_response_plan': {
            'controls': ['IR-1', 'IR-4', 'IR-5', 'IR-6', 'IR-8'],
            'severity': 'high',
            'remediation': 'Develop and test IR plan with 1-hour reporting requirement'
        },
        'vulnerability_scanning': {
            'controls': ['RA-5', 'RA-5(5)'],
            'severity': 'high',
            'remediation': 'Monthly authenticated scans + annual penetration test'
        },
        'continuous_monitoring': {
            'controls': ['CA-7', 'SI-4'],
            'severity': 'high',
            'remediation': 'Implement ConMon with monthly POA&M updates'
        },
        'boundary_protection': {
            'controls': ['SC-7', 'SC-7(3)', 'SC-7(5)'],
            'severity': 'critical',
            'remediation': 'Deploy deny-by-default firewalls and boundary controls'
        },
        'separation_of_duties': {
            'controls': ['AC-5', 'AC-6'],
            'severity': 'medium',
            'remediation': 'Implement RBAC with separation between admin/security/audit roles'
        },
        'configuration_baselines': {
            'controls': ['CM-2', 'CM-6', 'CM-7'],
            'severity': 'high',
            'remediation': 'Establish CIS/DISA STIG baselines with automated compliance checks'
        }
    },
    'ato_phases': [
        'Pre-Authorization (Readiness Assessment)',
        'Full Security Assessment (3PAO)',
        'Authorization (Agency ATO)',
        'Continuous Monitoring (ConMon)',
        'Annual Assessment',
        'Significant Change Request'
    ],
    'required_artifacts': [
        'System Security Plan (SSP)',
        'Security Assessment Plan (SAP)',
        'Security Assessment Report (SAR)',
        'Plan of Action & Milestones (POA&M)',
        'Continuous Monitoring Strategy',
        'Incident Response Plan',
        'Configuration Management Plan',
        'Control Implementation Summary (CIS)',
        'FIPS 199 Categorization',
        'E-Authentication Risk Assessment',
        'Privacy Impact Assessment (PIA)',
        'Laws and Regulations Tracking'
    ]
}

# Feature keywords for classification
FEATURE_KEYWORDS = {
    'baseline_level': ['low impact', 'moderate impact', 'high impact', 'li-saas', 'fedramp'],
    'control_families': ['access control', 'audit', 'configuration', 'encryption', 'incident', 'authentication'],
    'encryption': ['fips', 'aes', 'tls', 'ssl', 'encryption', 'cryptographic', 'kms'],
    'authentication': ['mfa', 'piv', 'cac', 'multi-factor', 'two-factor', 'sso', 'saml', 'oauth'],
    'logging': ['audit log', 'siem', 'cloudtrail', 'splunk', 'log retention', 'audit trail'],
    'monitoring': ['continuous monitoring', 'conmon', 'vulnerability scan', 'intrusion detection'],
    'compliance': ['nist 800-53', 'control', 'baseline', 'ssp', 'ato', 'authorization'],
    'incident_response': ['incident', 'breach', 'notification', 'us-cert', 'incident response plan'],
    'network_security': ['firewall', 'boundary', 'vpc', 'network segmentation', 'dmz', 'waf'],
    'data_protection': ['cui', 'pii', 'phi', 'data classification', 'data loss prevention'],
    'assessment': ['3pao', 'penetration test', 'vulnerability assessment', 'security assessment'],
    'infrastructure': ['aws', 'azure', 'gcp', 'cloud', 'iaas', 'paas', 'saas']
}

# Issue categories and their severities
ISSUE_CATEGORIES = {
    'authorization_blocker': ['mfa_missing', 'encryption_at_rest', 'encryption_in_transit', 'boundary_protection'],
    'high_risk_gap': ['logging_insufficient', 'incident_response_plan', 'vulnerability_scanning', 'continuous_monitoring'],
    'compliance_required': ['configuration_baselines', 'separation_of_duties'],
    'documentation_needed': ['ssp', 'sar', 'poam', 'conmon_strategy']
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
    """Extract features from FedRAMP/compliance-related text"""
    if not text:
        return {}

    text_lower = text.lower()
    features = {}

    # Baseline detection
    features['is_low'] = 1.0 if 'low impact' in text_lower or 'fedramp low' in text_lower else 0.0
    features['is_moderate'] = 1.0 if 'moderate impact' in text_lower or 'fedramp moderate' in text_lower else 0.0
    features['is_high'] = 1.0 if 'high impact' in text_lower or 'fedramp high' in text_lower else 0.0
    features['is_li_saas'] = 1.0 if 'li-saas' in text_lower or 'li saas' in text_lower else 0.0

    # Category features
    for category, keywords in FEATURE_KEYWORDS.items():
        features[f'has_{category}'] = 1.0 if any(kw in text_lower for kw in keywords) else 0.0

    # Control family detection
    for family_code, family_data in FEDRAMP_KNOWLEDGE['control_families'].items():
        family_name_lower = family_data['name'].lower()
        features[f'family_{family_code}'] = 1.0 if family_name_lower in text_lower or family_code.lower() in text_lower else 0.0

    # Complexity indicators
    features['has_control_number'] = 1.0 if any(f'{family}-' in text for family in FEDRAMP_KNOWLEDGE['control_families'].keys()) else 0.0
    features['mentions_nist'] = 1.0 if 'nist' in text_lower or '800-53' in text_lower else 0.0
    features['text_length'] = min(len(text) / 1000.0, 10.0)  # Normalize to 0-10
    features['mentions_gap'] = 1.0 if any(w in text_lower for w in ['gap', 'missing', 'non-compliant', 'deficiency']) else 0.0

    # Common gap indicators
    for gap_key, gap_data in FEDRAMP_KNOWLEDGE['common_gaps'].items():
        features[f'gap_{gap_key}'] = 1.0 if gap_key.replace('_', ' ') in text_lower else 0.0

    # ATO phase detection
    for phase in FEDRAMP_KNOWLEDGE['ato_phases']:
        phase_key = phase.lower().replace(' ', '_').replace('(', '').replace(')', '')
        features[f'phase_{phase_key}'] = 1.0 if phase.lower() in text_lower else 0.0

    return features

def create_synthetic_training_data():
    """
    Create synthetic training data for FedRAMP scenarios.
    In production, this would come from actual ATO packages, assessments, and compliance reviews.
    """
    training_examples = []

    # Baseline selection examples
    baseline_examples = [
        {
            'text': 'Public-facing website with no PII or sensitive data. What FedRAMP baseline applies?',
            'category': 'baseline_selection',
            'baseline': 'Low',
            'action': 'fedramp_low_authorization'
        },
        {
            'text': 'Cloud service processing Controlled Unclassified Information (CUI) for federal contracts',
            'category': 'baseline_selection',
            'baseline': 'Moderate',
            'action': 'fedramp_moderate_authorization'
        },
        {
            'text': 'Law enforcement system handling criminal justice information and biometric data',
            'category': 'baseline_selection',
            'baseline': 'High',
            'action': 'fedramp_high_authorization'
        },
        {
            'text': 'SaaS application deployed on AWS GovCloud leveraging FedRAMP authorized infrastructure',
            'category': 'baseline_selection',
            'baseline': 'LI-SaaS',
            'action': 'fedramp_li_saas_authorization'
        },
    ]

    # Control implementation examples
    control_examples = [
        {
            'text': 'How do I implement AC-2 Account Management for cloud users in AWS GovCloud?',
            'category': 'control_implementation',
            'control_family': 'AC',
            'severity': 'critical',
            'action': 'configure_iam_account_management'
        },
        {
            'text': 'Need to satisfy AU-2 Audit Events for FedRAMP Moderate baseline',
            'category': 'control_implementation',
            'control_family': 'AU',
            'severity': 'high',
            'action': 'enable_cloudtrail_comprehensive_logging'
        },
        {
            'text': 'Implement IA-2(1) MFA for privileged users accessing federal systems',
            'category': 'control_implementation',
            'control_family': 'IA',
            'severity': 'critical',
            'action': 'enforce_piv_or_hardware_mfa'
        },
        {
            'text': 'SC-28 Protection of Information at Rest requires FIPS 140-2 validated encryption',
            'category': 'control_implementation',
            'control_family': 'SC',
            'severity': 'critical',
            'action': 'enable_fips_encryption_at_rest'
        },
        {
            'text': 'IR-4 Incident Handling requires 1-hour reporting to US-CERT for federal incidents',
            'category': 'control_implementation',
            'control_family': 'IR',
            'severity': 'high',
            'action': 'configure_incident_notification_automation'
        },
        {
            'text': 'CA-7 Continuous Monitoring with monthly POA&M updates to FedRAMP PMO',
            'category': 'control_implementation',
            'control_family': 'CA',
            'severity': 'high',
            'action': 'setup_conmon_automation'
        },
    ]

    # Gap detection examples
    gap_examples = [
        {
            'text': 'RDS database encryption is disabled. Violates SC-28.',
            'category': 'gap_detection',
            'gap': 'encryption_at_rest',
            'severity': 'critical',
            'action': 'enable_rds_encryption_fips_140_2'
        },
        {
            'text': 'CloudTrail logs only retained for 30 days. FedRAMP requires 90 days minimum.',
            'category': 'gap_detection',
            'gap': 'logging_insufficient',
            'severity': 'high',
            'action': 'extend_cloudtrail_retention_90_days'
        },
        {
            'text': 'No MFA configured for IAM users with admin privileges',
            'category': 'gap_detection',
            'gap': 'mfa_missing',
            'severity': 'critical',
            'action': 'enforce_mfa_for_privileged_users'
        },
        {
            'text': 'Security groups allow 0.0.0.0/0 inbound on port 22. Violates SC-7 boundary protection.',
            'category': 'gap_detection',
            'gap': 'boundary_protection',
            'severity': 'critical',
            'action': 'restrict_security_group_to_approved_cidrs'
        },
        {
            'text': 'No vulnerability scanning performed in last 30 days. RA-5 non-compliant.',
            'category': 'gap_detection',
            'gap': 'vulnerability_scanning',
            'severity': 'high',
            'action': 'schedule_monthly_authenticated_scans'
        },
        {
            'text': 'Incident Response Plan not tested in last 12 months. IR-3 annual requirement.',
            'category': 'gap_detection',
            'gap': 'incident_response_plan',
            'severity': 'high',
            'action': 'conduct_tabletop_exercise'
        },
    ]

    # ATO process guidance
    ato_examples = [
        {
            'text': 'What are the steps to achieve FedRAMP ATO for a new SaaS product?',
            'category': 'ato_guidance',
            'phase': 'Pre-Authorization',
            'action': 'provide_ato_roadmap'
        },
        {
            'text': 'How do I select a FedRAMP 3PAO for security assessment?',
            'category': 'ato_guidance',
            'phase': 'Full Security Assessment',
            'action': 'recommend_3pao_selection_criteria'
        },
        {
            'text': 'What deliverables are required for FedRAMP authorization package?',
            'category': 'ato_guidance',
            'phase': 'Authorization',
            'action': 'list_required_artifacts'
        },
        {
            'text': 'How often must I update POA&M for continuous monitoring?',
            'category': 'ato_guidance',
            'phase': 'Continuous Monitoring',
            'action': 'explain_conmon_monthly_poam_updates'
        },
    ]

    # Documentation examples
    doc_examples = [
        {
            'text': 'How do I complete the System Security Plan (SSP) for FedRAMP?',
            'category': 'documentation',
            'artifact': 'SSP',
            'action': 'provide_ssp_template_guidance'
        },
        {
            'text': 'What goes in the Control Implementation Summary (CIS) worksheet?',
            'category': 'documentation',
            'artifact': 'CIS',
            'action': 'explain_cis_completion'
        },
        {
            'text': 'How to document inherited controls from AWS GovCloud in SSP?',
            'category': 'documentation',
            'artifact': 'SSP',
            'action': 'guide_inherited_control_documentation'
        },
    ]

    # Cloud-specific implementation examples
    cloud_examples = [
        {
            'text': 'Configure AWS Security Hub for FedRAMP Moderate continuous monitoring',
            'category': 'cloud_implementation',
            'platform': 'AWS',
            'baseline': 'Moderate',
            'action': 'setup_security_hub_fedramp_moderate'
        },
        {
            'text': 'Enable Azure Defender for FedRAMP High authorization',
            'category': 'cloud_implementation',
            'platform': 'Azure',
            'baseline': 'High',
            'action': 'configure_azure_defender_fedramp_high'
        },
        {
            'text': 'Implement GCP VPC Service Controls for boundary protection SC-7',
            'category': 'cloud_implementation',
            'platform': 'GCP',
            'control_family': 'SC',
            'action': 'configure_vpc_service_controls'
        },
    ]

    # Combine all examples
    training_examples.extend(baseline_examples)
    training_examples.extend(control_examples)
    training_examples.extend(gap_examples)
    training_examples.extend(ato_examples)
    training_examples.extend(doc_examples)
    training_examples.extend(cloud_examples)

    return training_examples

def fetch_workflow_data():
    """Fetch FedRAMP/compliance-related workflow executions from PostgreSQL"""
    db = get_db()
    cursor = db.cursor()

    # Query workflows mentioning FedRAMP, NIST, compliance, controls
    cursor.execute("""
        SELECT
            e.workflow_name,
            e.task_description,
            wr.task_assigned,
            wr.result,
            wr.outcome,
            wr.confidence,
            wr.model
        FROM workflow.executions e
        JOIN workflow.worker_results wr ON e.id = wr.workflow_execution_id
        WHERE
            LOWER(e.task_description) LIKE '%fedramp%'
            OR LOWER(e.task_description) LIKE '%nist%'
            OR LOWER(e.task_description) LIKE '%compliance%'
            OR LOWER(e.task_description) LIKE '%authorization%'
            OR LOWER(e.task_description) LIKE '%control%'
            OR LOWER(wr.task_assigned) LIKE '%fedramp%'
            OR LOWER(wr.task_assigned) LIKE '%nist%'
        ORDER BY e.created_at DESC
        LIMIT 500
    """)

    rows = cursor.fetchall()
    cursor.close()
    db.close()

    workflow_examples = []
    for row in rows:
        workflow_name, task_desc, task_assigned, result, outcome, confidence, model = row

        combined_text = f"{task_desc or ''} {task_assigned or ''} {result or ''}"

        # Infer category from workflow outcome and confidence
        category = 'compliance_review' if outcome == 'success' and confidence > 0.8 else 'gap_detection'

        workflow_examples.append({
            'text': combined_text,
            'category': category,
            'outcome': outcome,
            'confidence': confidence,
            'model': model
        })

    return workflow_examples

def prepare_training_data():
    """Combine synthetic and workflow data"""
    print("Creating synthetic training data...")
    synthetic_data = create_synthetic_training_data()
    print(f"  Generated {len(synthetic_data)} synthetic examples")

    print("Fetching workflow history...")
    workflow_data = fetch_workflow_data()
    print(f"  Retrieved {len(workflow_data)} workflow examples")

    all_data = synthetic_data + workflow_data
    print(f"Total training examples: {len(all_data)}")

    return all_data, len(synthetic_data), len(workflow_data)

def train_classifier():
    """Train Random Forest classifier for FedRAMP expertise"""
    print("\n" + "="*80)
    print("FedRAMP EXPERT TRAINER")
    print("="*80)

    # Prepare data
    data, num_synthetic, num_workflow = prepare_training_data()

    # Extract texts and labels
    texts = [example['text'] for example in data]
    labels = [example['category'] for example in data]

    print(f"\nLabel distribution:")
    label_counts = defaultdict(int)
    for label in labels:
        label_counts[label] += 1
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")

    # TF-IDF vectorization
    print("\nVectorizing text with TF-IDF...")
    vectorizer = TfidfVectorizer(
        max_features=500,
        ngram_range=(1, 3),
        stop_words='english',
        min_df=2
    )
    X_tfidf = vectorizer.fit_transform(texts)

    # Extract manual features
    print("Extracting domain-specific features...")
    feature_vectors = [extract_features(text) for text in texts]

    # Convert to numpy array
    feature_keys = sorted(feature_vectors[0].keys())
    X_manual = np.array([[fv.get(k, 0.0) for k in feature_keys] for fv in feature_vectors])

    # Combine TF-IDF and manual features
    X_combined = np.hstack([X_tfidf.toarray(), X_manual])
    y = np.array(labels)

    print(f"Feature matrix shape: {X_combined.shape}")
    print(f"  TF-IDF features: {X_tfidf.shape[1]}")
    print(f"  Manual features: {X_manual.shape[1]}")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_combined, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\nTraining set: {len(X_train)} examples")
    print(f"Test set: {len(X_test)} examples")

    # Train Random Forest
    print("\nTraining Random Forest classifier...")
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    clf.fit(X_train, y_train)

    # Evaluate
    print("\nEvaluating model...")
    y_pred = clf.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average='weighted')

    print(f"\nAccuracy: {accuracy:.3f}")
    print(f"F1 Score (weighted): {f1:.3f}")

    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Feature importance
    print("\nTop 20 Most Important Features:")
    feature_names = vectorizer.get_feature_names_out().tolist() + feature_keys
    importances = clf.feature_importances_
    indices = np.argsort(importances)[::-1][:20]

    for i, idx in enumerate(indices):
        print(f"  {i+1}. {feature_names[idx]}: {importances[idx]:.4f}")

    # Save model
    model_dir = Path.home() / '.claude' / 'learning'
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / 'fedramp_expert.pkl'
    vectorizer_path = model_dir / 'fedramp_expert_vectorizer.pkl'
    feature_keys_path = model_dir / 'fedramp_expert_feature_keys.json'
    stats_path = model_dir / 'fedramp_expert_stats.json'

    print(f"\nSaving model to {model_path}...")
    with open(model_path, 'wb') as f:
        pickle.dump(clf, f)

    print(f"Saving vectorizer to {vectorizer_path}...")
    with open(vectorizer_path, 'wb') as f:
        pickle.dump(vectorizer, f)

    print(f"Saving feature keys to {feature_keys_path}...")
    with open(feature_keys_path, 'w') as f:
        json.dump(feature_keys, f)

    # Save statistics
    stats = {
        'trained_at': datetime.now().isoformat(),
        'training_examples': len(data),
        'synthetic_examples': num_synthetic,
        'workflow_examples': num_workflow,
        'accuracy': float(accuracy),
        'f1_score': float(f1),
        'num_features': X_combined.shape[1],
        'tfidf_features': X_tfidf.shape[1],
        'manual_features': X_manual.shape[1],
        'label_distribution': dict(label_counts),
        'top_features': [
            {'name': feature_names[idx], 'importance': float(importances[idx])}
            for idx in indices[:20]
        ]
    }

    print(f"Saving statistics to {stats_path}...")
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)

    print("\n" + "="*80)
    print("TRAINING COMPLETE")
    print("="*80)
    print(f"\nModel saved to: {model_path}")
    print(f"Accuracy: {accuracy:.1%}")
    print(f"F1 Score: {f1:.1%}")

    # Save model reference to model_mapping.json
    mapping_path = Path('/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/model_mapping.json')
    if mapping_path.exists():
        with open(mapping_path, 'r') as f:
            mapping = json.load(f)
    else:
        mapping = {'models': [], 'model_to_id': {}, 'context_features': []}

    if 'fedramp-expert' not in mapping['models']:
        mapping['models'].append('fedramp-expert')
        mapping['model_to_id']['fedramp-expert'] = len(mapping['models']) - 1

        with open(mapping_path, 'w') as f:
            json.dump(mapping, f, indent=2)

        print(f"\nRegistered 'fedramp-expert' in {mapping_path}")

    return clf, vectorizer, feature_keys, stats

if __name__ == '__main__':
    train_classifier()
