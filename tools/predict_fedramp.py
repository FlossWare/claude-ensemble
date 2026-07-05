#!/usr/bin/env python3
"""
FedRAMP Expert Prediction Script

Uses trained Random Forest classifier to:
1. Classify FedRAMP compliance questions
2. Recommend baseline (Low/Moderate/High/LI-SaaS)
3. Identify control gaps
4. Suggest remediation actions
"""

import pickle
import json
import sys
from pathlib import Path

def load_fedramp_expert():
    """Load trained FedRAMP expert model"""
    model_dir = Path.home() / '.claude' / 'learning'

    model_path = model_dir / 'fedramp_expert.pkl'
    vectorizer_path = model_dir / 'fedramp_expert_vectorizer.pkl'
    feature_keys_path = model_dir / 'fedramp_expert_feature_keys.json'

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found at {model_path}. "
            "Run fedramp_expert_trainer.py first."
        )

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)

    with open(feature_keys_path, 'r') as f:
        feature_keys = json.load(f)

    return model, vectorizer, feature_keys

def extract_features(text):
    """Extract domain features (must match trainer)"""
    if not text:
        return {}

    text_lower = text.lower()
    features = {}

    # Import from trainer (simplified version)
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

    CONTROL_FAMILIES = {
        'AC': 'Access Control', 'AU': 'Audit and Accountability', 'AT': 'Awareness and Training',
        'CM': 'Configuration Management', 'CP': 'Contingency Planning',
        'IA': 'Identification and Authentication', 'IR': 'Incident Response',
        'MA': 'Maintenance', 'MP': 'Media Protection',
        'PE': 'Physical and Environmental Protection', 'PL': 'Planning',
        'PS': 'Personnel Security', 'RA': 'Risk Assessment',
        'CA': 'Security Assessment and Authorization',
        'SC': 'System and Communications Protection',
        'SI': 'System and Information Integrity',
        'SA': 'System and Services Acquisition', 'PM': 'Program Management'
    }

    COMMON_GAPS = {
        'encryption_at_rest': None, 'encryption_in_transit': None, 'mfa_missing': None,
        'logging_insufficient': None, 'incident_response_plan': None,
        'vulnerability_scanning': None, 'continuous_monitoring': None,
        'boundary_protection': None, 'separation_of_duties': None,
        'configuration_baselines': None
    }

    ATO_PHASES = [
        'Pre-Authorization (Readiness Assessment)',
        'Full Security Assessment (3PAO)',
        'Authorization (Agency ATO)',
        'Continuous Monitoring (ConMon)',
        'Annual Assessment',
        'Significant Change Request'
    ]

    # Baseline detection
    features['is_low'] = 1.0 if 'low impact' in text_lower or 'fedramp low' in text_lower else 0.0
    features['is_moderate'] = 1.0 if 'moderate impact' in text_lower or 'fedramp moderate' in text_lower else 0.0
    features['is_high'] = 1.0 if 'high impact' in text_lower or 'fedramp high' in text_lower else 0.0
    features['is_li_saas'] = 1.0 if 'li-saas' in text_lower or 'li saas' in text_lower else 0.0

    # Category features
    for category, keywords in FEATURE_KEYWORDS.items():
        features[f'has_{category}'] = 1.0 if any(kw in text_lower for kw in keywords) else 0.0

    # Control family detection
    for family_code, family_name in CONTROL_FAMILIES.items():
        family_name_lower = family_name.lower()
        features[f'family_{family_code}'] = 1.0 if family_name_lower in text_lower or family_code.lower() in text_lower else 0.0

    # Complexity indicators
    features['has_control_number'] = 1.0 if any(f'{family}-' in text for family in CONTROL_FAMILIES.keys()) else 0.0
    features['mentions_nist'] = 1.0 if 'nist' in text_lower or '800-53' in text_lower else 0.0
    features['text_length'] = min(len(text) / 1000.0, 10.0)
    features['mentions_gap'] = 1.0 if any(w in text_lower for w in ['gap', 'missing', 'non-compliant', 'deficiency']) else 0.0

    # Gap detection
    for gap_key in COMMON_GAPS.keys():
        features[f'gap_{gap_key}'] = 1.0 if gap_key.replace('_', ' ') in text_lower else 0.0

    # ATO phase detection
    for phase in ATO_PHASES:
        phase_key = phase.lower().replace(' ', '_').replace('(', '').replace(')', '')
        features[f'phase_{phase_key}'] = 1.0 if phase.lower() in text_lower else 0.0

    return features

def predict(text, verbose=True):
    """Predict category and provide FedRAMP guidance"""
    model, vectorizer, feature_keys = load_fedramp_expert()

    # Vectorize
    X_tfidf = vectorizer.transform([text])

    # Extract features
    features = extract_features(text)
    X_manual = [[features.get(k, 0.0) for k in feature_keys]]

    # Combine
    import numpy as np
    X_combined = np.hstack([X_tfidf.toarray(), X_manual])

    # Predict
    prediction = model.predict(X_combined)[0]
    probabilities = model.predict_proba(X_combined)[0]

    # Get class probabilities
    class_probs = {
        cls: prob
        for cls, prob in zip(model.classes_, probabilities)
    }

    # Sort by probability
    sorted_probs = sorted(class_probs.items(), key=lambda x: -x[1])

    if verbose:
        print("="*80)
        print("FedRAMP EXPERT PREDICTION")
        print("="*80)
        print(f"\nQuery: {text}\n")
        print(f"Category: {prediction}")
        print(f"Confidence: {class_probs[prediction]:.1%}\n")

        print("Top 3 Predictions:")
        for i, (cls, prob) in enumerate(sorted_probs[:3], 1):
            print(f"  {i}. {cls}: {prob:.1%}")

        # Provide guidance based on category
        print("\n" + "="*80)
        print("GUIDANCE")
        print("="*80)

        if prediction == 'baseline_selection':
            print("\nFedRAMP Baseline Selection:")
            print("  - Low Impact: Public websites, no PII (125 controls, 3-6 months)")
            print("  - Moderate Impact: CUI, PII, financial data (325 controls, 6-12 months)")
            print("  - High Impact: Law enforcement, national security (421 controls, 12-24 months)")
            print("  - LI-SaaS: Leveraging FedRAMP IaaS/PaaS (146 controls, 3-6 months)")

        elif prediction == 'control_implementation':
            print("\nControl Implementation Steps:")
            print("  1. Review NIST 800-53 Rev 5 control description")
            print("  2. Map to cloud service capabilities (AWS/Azure/GCP)")
            print("  3. Document implementation in SSP Part 13")
            print("  4. Configure automated compliance checks")
            print("  5. Test and validate control effectiveness")

        elif prediction == 'gap_detection':
            print("\nCommon FedRAMP Gaps:")
            print("  - Encryption at rest (SC-28): Enable FIPS 140-2 validated encryption")
            print("  - MFA for privileged users (IA-2): Implement PIV/CAC or hardware tokens")
            print("  - Log retention (AU-11): Minimum 90 days for FedRAMP")
            print("  - Vulnerability scanning (RA-5): Monthly authenticated scans required")
            print("  - Incident response (IR-4): 1-hour US-CERT notification")

        elif prediction == 'ato_guidance':
            print("\nFedRAMP ATO Process:")
            print("  Phase 1: Readiness Assessment (optional but recommended)")
            print("  Phase 2: 3PAO Security Assessment (SAP → SAR)")
            print("  Phase 3: Agency Authorization (ATO issuance)")
            print("  Phase 4: Continuous Monitoring (monthly POA&M updates)")
            print("  Phase 5: Annual Assessment (required)")

        elif prediction == 'documentation':
            print("\nRequired FedRAMP Artifacts:")
            print("  - System Security Plan (SSP)")
            print("  - Security Assessment Report (SAR)")
            print("  - Plan of Action & Milestones (POA&M)")
            print("  - Continuous Monitoring Strategy")
            print("  - Incident Response Plan")
            print("  - Configuration Management Plan")
            print("  - Control Implementation Summary (CIS)")

        elif prediction == 'cloud_implementation':
            print("\nCloud Platform Guidance:")
            print("  AWS GovCloud: Inherits 161 controls from FedRAMP High baseline")
            print("  Azure Government: Inherits 171 controls from FedRAMP High baseline")
            print("  GCP: Use Assured Workloads for FedRAMP compliance")
            print("\n  Key: Document inherited controls in SSP Part 13 Control Summary")

        print("\n" + "="*80)

    return {
        'prediction': prediction,
        'confidence': class_probs[prediction],
        'all_predictions': sorted_probs
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 predict_fedramp.py 'your FedRAMP question here'")
        print("\nExamples:")
        print("  python3 predict_fedramp.py 'What baseline for CUI data?'")
        print("  python3 predict_fedramp.py 'How to implement SC-28 encryption at rest?'")
        print("  python3 predict_fedramp.py 'RDS encryption disabled - compliance gap?'")
        sys.exit(1)

    query = ' '.join(sys.argv[1:])
    predict(query, verbose=True)

if __name__ == '__main__':
    main()
