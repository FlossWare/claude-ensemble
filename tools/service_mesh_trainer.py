#!/usr/bin/env python3
"""
Service Mesh Expert Trainer

Trains a Random Forest classifier to:
1. Identify service mesh configuration issues (Linkerd, Consul)
2. Recommend traffic policies (load balancing, retries, timeouts)
3. Detect common misconfigurations
4. Suggest best practices

Training data sources:
- Historical workflow executions (PostgreSQL)
- Service mesh documentation patterns
- Common configuration errors
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

# Service mesh knowledge base
SERVICE_MESH_PATTERNS = {
    'linkerd': {
        'traffic_policies': [
            'retry_budget', 'timeout_policy', 'circuit_breaker', 'load_balancing',
            'rate_limiting', 'failover', 'traffic_split', 'canary_deployment'
        ],
        'common_issues': [
            'missing_proxy_injection', 'tls_misconfiguration', 'mtls_disabled',
            'policy_not_applied', 'service_profile_missing', 'tap_unavailable'
        ],
        'configurations': [
            'ServiceProfile', 'TrafficSplit', 'HTTPRoute', 'TCPRoute',
            'Server', 'ServerAuthorization', 'ProxyConfiguration'
        ]
    },
    'consul': {
        'traffic_policies': [
            'service_resolver', 'service_router', 'service_splitter',
            'load_balancer', 'failover', 'retry_join', 'intentions'
        ],
        'common_issues': [
            'sidecar_registration_failed', 'acl_misconfiguration',
            'connect_disabled', 'health_check_failing', 'dns_resolution_error',
            'encryption_not_enabled'
        ],
        'configurations': [
            'service_defaults', 'proxy_defaults', 'service_intentions',
            'service_resolver', 'service_router', 'service_splitter',
            'ingress_gateway', 'terminating_gateway'
        ]
    }
}

# Feature keywords for classification
FEATURE_KEYWORDS = {
    'mesh_type': ['linkerd', 'consul', 'istio', 'service mesh'],
    'traffic_management': ['retry', 'timeout', 'circuit breaker', 'load balance', 'failover'],
    'security': ['mtls', 'tls', 'encryption', 'certificate', 'acl', 'authorization', 'intentions'],
    'observability': ['metrics', 'tracing', 'tap', 'prometheus', 'grafana', 'jaeger'],
    'deployment': ['canary', 'blue-green', 'traffic split', 'progressive rollout'],
    'configuration': ['yaml', 'config', 'crd', 'custom resource', 'policy'],
    'troubleshooting': ['debug', 'error', 'failing', 'issue', 'problem', 'fix'],
    'performance': ['latency', 'throughput', 'bandwidth', 'resource', 'cpu', 'memory']
}

# Issue categories and their severities
ISSUE_CATEGORIES = {
    'security_critical': ['mtls_disabled', 'encryption_not_enabled', 'acl_misconfiguration'],
    'availability_high': ['missing_proxy_injection', 'circuit_breaker', 'health_check_failing'],
    'performance_medium': ['load_balancing', 'timeout_policy', 'retry_budget'],
    'observability_low': ['tap_unavailable', 'metrics', 'service_profile_missing']
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
    """Extract features from service mesh-related text"""
    if not text:
        return {}

    text_lower = text.lower()
    features = {}

    # Mesh type detection
    features['is_linkerd'] = 1.0 if 'linkerd' in text_lower else 0.0
    features['is_consul'] = 1.0 if 'consul' in text_lower else 0.0
    features['is_istio'] = 1.0 if 'istio' in text_lower else 0.0

    # Category features
    for category, keywords in FEATURE_KEYWORDS.items():
        features[f'has_{category}'] = 1.0 if any(kw in text_lower for kw in keywords) else 0.0

    # Complexity indicators
    features['has_code'] = 1.0 if '```' in text else 0.0
    features['has_yaml'] = 1.0 if 'apiversion:' in text_lower or 'kind:' in text_lower else 0.0
    features['text_length'] = min(len(text) / 1000.0, 5.0)  # Normalize to 0-5
    features['mentions_error'] = 1.0 if any(w in text_lower for w in ['error', 'fail', 'issue']) else 0.0

    # Traffic policy indicators
    for mesh, policies in SERVICE_MESH_PATTERNS.items():
        for policy in policies['traffic_policies']:
            policy_key = policy.replace(' ', '_')
            features[f'{mesh}_{policy_key}'] = 1.0 if policy.replace('_', ' ') in text_lower else 0.0

    return features

def create_synthetic_training_data():
    """
    Create synthetic training data for service mesh scenarios.
    In production, this would come from actual support tickets, documentation, and user queries.
    """
    training_examples = []

    # Linkerd examples (expanded with more variations)
    linkerd_examples = [
        # Traffic policy configurations (5 examples)
        {
            'text': 'Configure Linkerd retry policy with exponential backoff for gRPC services',
            'category': 'traffic_policy_configuration',
            'mesh': 'linkerd',
            'severity': 'medium',
            'action': 'create_service_profile_with_retry_budget'
        },
        {
            'text': 'Configure Linkerd timeout policy for slow backend services',
            'category': 'traffic_policy_configuration',
            'mesh': 'linkerd',
            'severity': 'medium',
            'action': 'set_timeout_in_service_profile'
        },
        {
            'text': 'Set up Linkerd load balancing policy for HTTP services',
            'category': 'traffic_policy_configuration',
            'mesh': 'linkerd',
            'severity': 'medium',
            'action': 'configure_load_balancing_in_service_profile'
        },
        {
            'text': 'Configure Linkerd rate limiting for API endpoints',
            'category': 'traffic_policy_configuration',
            'mesh': 'linkerd',
            'severity': 'medium',
            'action': 'implement_rate_limiting_policy'
        },
        {
            'text': 'Set request timeout and retry budget for Linkerd microservices',
            'category': 'traffic_policy_configuration',
            'mesh': 'linkerd',
            'severity': 'medium',
            'action': 'create_comprehensive_service_profile'
        },
        # Configuration issues (5 examples)
        {
            'text': 'Linkerd proxy not injecting into pods, deployment annotation missing',
            'category': 'configuration_issue',
            'mesh': 'linkerd',
            'severity': 'high',
            'action': 'add_proxy_injection_annotation'
        },
        {
            'text': 'Linkerd ServiceProfile not applying to routes',
            'category': 'configuration_issue',
            'mesh': 'linkerd',
            'severity': 'high',
            'action': 'verify_service_profile_namespace_and_selectors'
        },
        {
            'text': 'Linkerd proxy init container failing to start',
            'category': 'configuration_issue',
            'mesh': 'linkerd',
            'severity': 'high',
            'action': 'check_network_policy_and_rbac_permissions'
        },
        {
            'text': 'Linkerd trust anchor certificate expired',
            'category': 'configuration_issue',
            'mesh': 'linkerd',
            'severity': 'critical',
            'action': 'rotate_linkerd_trust_anchor_and_issuer'
        },
        {
            'text': 'Linkerd policy controller not enforcing Server resources',
            'category': 'configuration_issue',
            'mesh': 'linkerd',
            'severity': 'high',
            'action': 'validate_policy_controller_config'
        },
        # Security configurations (5 examples)
        {
            'text': 'Set up mTLS for service-to-service communication in Linkerd',
            'category': 'security_configuration',
            'mesh': 'linkerd',
            'severity': 'critical',
            'action': 'enable_automatic_mtls'
        },
        {
            'text': 'Configure Linkerd authorization policies for zero-trust security',
            'category': 'security_configuration',
            'mesh': 'linkerd',
            'severity': 'critical',
            'action': 'create_server_authorization_resources'
        },
        {
            'text': 'Implement external certificate management for Linkerd',
            'category': 'security_configuration',
            'mesh': 'linkerd',
            'severity': 'critical',
            'action': 'configure_cert_manager_integration'
        },
        {
            'text': 'Restrict service mesh access using Linkerd Server and ServerAuthorization',
            'category': 'security_configuration',
            'mesh': 'linkerd',
            'severity': 'critical',
            'action': 'define_fine_grained_authorization_policies'
        },
        {
            'text': 'Enable Linkerd audit logging for security compliance',
            'category': 'security_configuration',
            'mesh': 'linkerd',
            'severity': 'critical',
            'action': 'configure_proxy_log_level_and_audit_trails'
        },
        # Deployment strategies (3 examples)
        {
            'text': 'Implement canary deployment using Linkerd TrafficSplit',
            'category': 'deployment_strategy',
            'mesh': 'linkerd',
            'severity': 'medium',
            'action': 'create_traffic_split_resource'
        },
        {
            'text': 'Progressive rollout with Linkerd and Flagger',
            'category': 'deployment_strategy',
            'mesh': 'linkerd',
            'severity': 'medium',
            'action': 'deploy_flagger_for_automated_canary'
        },
        {
            'text': 'Blue-green deployment strategy using Linkerd traffic shifting',
            'category': 'deployment_strategy',
            'mesh': 'linkerd',
            'severity': 'medium',
            'action': 'configure_traffic_split_100_percent_cutover'
        },
        # Troubleshooting (3 examples)
        {
            'text': 'Debug Linkerd tap not showing any traffic',
            'category': 'troubleshooting',
            'mesh': 'linkerd',
            'severity': 'low',
            'action': 'check_tap_rbac_and_proxy_config'
        },
        {
            'text': 'Linkerd proxy connection failures between services',
            'category': 'troubleshooting',
            'mesh': 'linkerd',
            'severity': 'high',
            'action': 'check_mtls_certificates_and_identity'
        },
        {
            'text': 'Investigate high latency in Linkerd service mesh',
            'category': 'troubleshooting',
            'mesh': 'linkerd',
            'severity': 'high',
            'action': 'analyze_linkerd_stat_and_tap_output'
        }
    ]

    # Consul examples (expanded)
    consul_examples = [
        # Security configurations (5 examples)
        {
            'text': 'Configure Consul service mesh intentions for microservice authorization',
            'category': 'security_configuration',
            'mesh': 'consul',
            'severity': 'critical',
            'action': 'create_service_intentions_allow_rules'
        },
        {
            'text': 'Consul ACL token permissions for service mesh operations',
            'category': 'security_configuration',
            'mesh': 'consul',
            'severity': 'critical',
            'action': 'create_acl_policy_with_service_write'
        },
        {
            'text': 'Enable Consul service mesh encryption for gossip and RPC',
            'category': 'security_configuration',
            'mesh': 'consul',
            'severity': 'critical',
            'action': 'generate_gossip_key_and_enable_tls'
        },
        {
            'text': 'Configure mTLS for Consul Connect sidecar proxies',
            'category': 'security_configuration',
            'mesh': 'consul',
            'severity': 'critical',
            'action': 'enable_connect_ca_and_certificate_rotation'
        },
        {
            'text': 'Implement Consul namespace isolation for multi-tenancy',
            'category': 'security_configuration',
            'mesh': 'consul',
            'severity': 'critical',
            'action': 'create_namespaces_and_acl_policies'
        },
        # Traffic policy configurations (5 examples)
        {
            'text': 'Set up Consul service resolver for failover between datacenters',
            'category': 'traffic_policy_configuration',
            'mesh': 'consul',
            'severity': 'high',
            'action': 'create_service_resolver_with_failover'
        },
        {
            'text': 'Configure Consul service router for path-based routing',
            'category': 'traffic_policy_configuration',
            'mesh': 'consul',
            'severity': 'medium',
            'action': 'create_service_router_with_http_path_prefix'
        },
        {
            'text': 'Set up Consul retry and timeout policies for resilience',
            'category': 'traffic_policy_configuration',
            'mesh': 'consul',
            'severity': 'medium',
            'action': 'configure_service_defaults_with_upstream_config'
        },
        {
            'text': 'Configure Consul load balancing strategy for service mesh',
            'category': 'traffic_policy_configuration',
            'mesh': 'consul',
            'severity': 'medium',
            'action': 'set_load_balancer_policy_in_service_defaults'
        },
        {
            'text': 'Implement request header manipulation in Consul service router',
            'category': 'traffic_policy_configuration',
            'mesh': 'consul',
            'severity': 'medium',
            'action': 'configure_router_header_modification'
        },
        # Configuration issues (5 examples)
        {
            'text': 'Consul Connect sidecar proxy registration failing',
            'category': 'configuration_issue',
            'mesh': 'consul',
            'severity': 'high',
            'action': 'check_connect_enabled_and_sidecar_definition'
        },
        {
            'text': 'Consul service discovery not finding mesh services',
            'category': 'configuration_issue',
            'mesh': 'consul',
            'severity': 'high',
            'action': 'verify_service_registration_and_health_checks'
        },
        {
            'text': 'Consul ingress gateway listener not accepting traffic',
            'category': 'configuration_issue',
            'mesh': 'consul',
            'severity': 'high',
            'action': 'check_gateway_service_and_port_configuration'
        },
        {
            'text': 'Consul proxy configuration not applying to sidecars',
            'category': 'configuration_issue',
            'mesh': 'consul',
            'severity': 'high',
            'action': 'validate_proxy_defaults_and_service_defaults'
        },
        {
            'text': 'Consul CA certificate rotation failing',
            'category': 'configuration_issue',
            'mesh': 'consul',
            'severity': 'critical',
            'action': 'check_ca_provider_config_and_logs'
        },
        # Deployment strategies (3 examples)
        {
            'text': 'Implement blue-green deployment using Consul service splitter',
            'category': 'deployment_strategy',
            'mesh': 'consul',
            'severity': 'medium',
            'action': 'configure_service_splitter_weights'
        },
        {
            'text': 'Canary deployment with Consul service splitter and resolver',
            'category': 'deployment_strategy',
            'mesh': 'consul',
            'severity': 'medium',
            'action': 'create_gradual_traffic_shift_configuration'
        },
        {
            'text': 'A/B testing using Consul service router rules',
            'category': 'deployment_strategy',
            'mesh': 'consul',
            'severity': 'medium',
            'action': 'configure_router_with_header_matching'
        },
        # Troubleshooting (3 examples)
        {
            'text': 'Consul health checks failing, service marked unhealthy',
            'category': 'troubleshooting',
            'mesh': 'consul',
            'severity': 'high',
            'action': 'adjust_health_check_interval_and_timeout'
        },
        {
            'text': 'Debug Consul Connect proxy connectivity issues',
            'category': 'troubleshooting',
            'mesh': 'consul',
            'severity': 'high',
            'action': 'check_upstream_config_and_intentions'
        },
        {
            'text': 'Investigate Consul service mesh high CPU usage',
            'category': 'troubleshooting',
            'mesh': 'consul',
            'severity': 'high',
            'action': 'analyze_proxy_metrics_and_connection_count'
        }
    ]

    return linkerd_examples + consul_examples

def load_historical_data(db):
    """Load historical workflow data related to service mesh topics"""
    cursor = db.cursor()

    cursor.execute("""
        SELECT
            wr.task_assigned,
            wr.result,
            wr.outcome,
            wr.confidence,
            we.workflow_name
        FROM workflow.worker_results wr
        JOIN workflow.executions we ON wr.workflow_execution_id = we.id
        WHERE (
            LOWER(wr.task_assigned) LIKE '%linkerd%' OR
            LOWER(wr.task_assigned) LIKE '%consul%' OR
            LOWER(wr.task_assigned) LIKE '%service mesh%' OR
            LOWER(wr.task_assigned) LIKE '%traffic polic%' OR
            LOWER(wr.result) LIKE '%linkerd%' OR
            LOWER(wr.result) LIKE '%consul%'
        )
        AND wr.outcome = 'success'
        AND wr.confidence > 0.7
        ORDER BY we.created_at DESC
        LIMIT 100
    """)

    historical = []
    for row in cursor.fetchall():
        task, result, outcome, confidence, workflow = row
        if task and result:
            # Infer category from task and result
            combined_text = f"{task} {result}".lower()

            if any(word in combined_text for word in ['security', 'mtls', 'tls', 'acl', 'authorization']):
                category = 'security_configuration'
                severity = 'critical'
            elif any(word in combined_text for word in ['error', 'fail', 'issue', 'problem']):
                category = 'troubleshooting'
                severity = 'high'
            elif any(word in combined_text for word in ['retry', 'timeout', 'circuit breaker']):
                category = 'traffic_policy_configuration'
                severity = 'medium'
            elif any(word in combined_text for word in ['canary', 'blue-green', 'deployment']):
                category = 'deployment_strategy'
                severity = 'medium'
            else:
                category = 'general_configuration'
                severity = 'low'

            mesh = 'linkerd' if 'linkerd' in combined_text else 'consul' if 'consul' in combined_text else 'generic'

            historical.append({
                'text': task,
                'category': category,
                'mesh': mesh,
                'severity': severity,
                'action': 'see_historical_result',
                'confidence': float(confidence) if confidence else 0.8
            })

    cursor.close()
    return historical

def train_service_mesh_expert():
    """Train service mesh expert classifier"""
    print("=== Service Mesh Expert Trainer ===\n")

    db = get_db()

    # Load training data
    print("Loading training data...")
    synthetic_data = create_synthetic_training_data()
    historical_data = load_historical_data(db)

    all_data = synthetic_data + historical_data
    print(f"  Synthetic examples: {len(synthetic_data)}")
    print(f"  Historical examples: {len(historical_data)}")
    print(f"  Total training examples: {len(all_data)}\n")

    # Extract features and labels
    texts = [ex['text'] for ex in all_data]
    categories = [ex['category'] for ex in all_data]
    meshes = [ex['mesh'] for ex in all_data]

    # Create TF-IDF vectorizer
    print("Creating TF-IDF features...")
    vectorizer = TfidfVectorizer(
        max_features=500,
        ngram_range=(1, 3),
        stop_words='english',
        min_df=1
    )

    tfidf_features = vectorizer.fit_transform(texts).toarray()

    # Add custom features
    custom_features = []
    for text in texts:
        feat = extract_features(text)
        custom_features.append(list(feat.values()))

    custom_features = np.array(custom_features)

    # Combine features
    X = np.hstack([tfidf_features, custom_features])
    y_category = np.array(categories)
    y_mesh = np.array(meshes)

    print(f"  Feature dimensions: {X.shape}")
    print(f"  Unique categories: {len(set(categories))}")
    print(f"  Unique meshes: {len(set(meshes))}\n")

    # Split data (no stratify due to small dataset)
    X_train, X_test, y_cat_train, y_cat_test, y_mesh_train, y_mesh_test = train_test_split(
        X, y_category, y_mesh, test_size=0.2, random_state=42
    )

    # Train category classifier
    print("Training category classifier...")
    category_clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=20,
        min_samples_split=2,
        random_state=42,
        n_jobs=-1
    )
    category_clf.fit(X_train, y_cat_train)

    y_cat_pred = category_clf.predict(X_test)
    cat_accuracy = accuracy_score(y_cat_test, y_cat_pred)
    cat_f1 = f1_score(y_cat_test, y_cat_pred, average='weighted')

    print(f"  Category accuracy: {cat_accuracy:.2%}")
    print(f"  Category F1 score: {cat_f1:.3f}\n")

    # Train mesh type classifier
    print("Training mesh type classifier...")
    mesh_clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_split=2,
        random_state=42,
        n_jobs=-1
    )
    mesh_clf.fit(X_train, y_mesh_train)

    y_mesh_pred = mesh_clf.predict(X_test)
    mesh_accuracy = accuracy_score(y_mesh_test, y_mesh_pred)
    mesh_f1 = f1_score(y_mesh_test, y_mesh_pred, average='weighted')

    print(f"  Mesh type accuracy: {mesh_accuracy:.2%}")
    print(f"  Mesh type F1 score: {mesh_f1:.3f}\n")

    # Feature importance
    feature_names = vectorizer.get_feature_names_out().tolist() + list(extract_features("sample").keys())
    cat_importances = category_clf.feature_importances_
    top_features_idx = np.argsort(cat_importances)[-10:]

    print("Top 10 features for category classification:")
    for idx in reversed(top_features_idx):
        if idx < len(feature_names):
            print(f"  {feature_names[idx]}: {cat_importances[idx]:.4f}")

    # Save models
    model_dir = Path.home() / '.claude' / 'learning'
    model_dir.mkdir(parents=True, exist_ok=True)

    category_model_path = model_dir / 'service_mesh_category_clf.pkl'
    mesh_model_path = model_dir / 'service_mesh_type_clf.pkl'
    vectorizer_path = model_dir / 'service_mesh_vectorizer.pkl'
    metadata_path = model_dir / 'service_mesh_metadata.json'

    print(f"\nSaving models...")
    with open(category_model_path, 'wb') as f:
        pickle.dump(category_clf, f)

    with open(mesh_model_path, 'wb') as f:
        pickle.dump(mesh_clf, f)

    with open(vectorizer_path, 'wb') as f:
        pickle.dump(vectorizer, f)

    metadata = {
        'training_date': datetime.now().isoformat(),
        'num_examples': len(all_data),
        'synthetic_examples': len(synthetic_data),
        'historical_examples': len(historical_data),
        'category_accuracy': float(cat_accuracy),
        'category_f1': float(cat_f1),
        'mesh_accuracy': float(mesh_accuracy),
        'mesh_f1': float(mesh_f1),
        'categories': sorted(list(set(categories))),
        'meshes': sorted(list(set(meshes))),
        'feature_count': X.shape[1],
        'service_mesh_patterns': SERVICE_MESH_PATTERNS,
        'issue_categories': ISSUE_CATEGORIES
    }

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"  Category model: {category_model_path}")
    print(f"  Mesh type model: {mesh_model_path}")
    print(f"  Vectorizer: {vectorizer_path}")
    print(f"  Metadata: {metadata_path}")

    # Store in PostgreSQL
    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning.service_mesh_models (
            model_name VARCHAR PRIMARY KEY,
            category_accuracy FLOAT,
            category_f1 FLOAT,
            mesh_accuracy FLOAT,
            mesh_f1 FLOAT,
            training_examples INTEGER,
            feature_count INTEGER,
            model_path VARCHAR,
            metadata JSONB,
            trained_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("""
        INSERT INTO learning.service_mesh_models
        (model_name, category_accuracy, category_f1, mesh_accuracy, mesh_f1,
         training_examples, feature_count, model_path, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (model_name) DO UPDATE SET
            category_accuracy = EXCLUDED.category_accuracy,
            category_f1 = EXCLUDED.category_f1,
            mesh_accuracy = EXCLUDED.mesh_accuracy,
            mesh_f1 = EXCLUDED.mesh_f1,
            training_examples = EXCLUDED.training_examples,
            trained_at = NOW()
    """, (
        'service_mesh_expert_v1',
        float(cat_accuracy),
        float(cat_f1),
        float(mesh_accuracy),
        float(mesh_f1),
        len(all_data),
        X.shape[1],
        str(category_model_path),
        json.dumps(metadata)
    ))

    db.commit()
    cursor.close()
    db.close()

    print("\n✅ Service Mesh expert models trained and saved!")
    print(f"\nUsage example:")
    print(f"""
import pickle
import numpy as np

# Load models
with open('{category_model_path}', 'rb') as f:
    category_clf = pickle.load(f)

with open('{mesh_model_path}', 'rb') as f:
    mesh_clf = pickle.load(f)

with open('{vectorizer_path}', 'rb') as f:
    vectorizer = pickle.load(f)

# Predict
query = "Configure Linkerd circuit breaker for failing service"
tfidf = vectorizer.transform([query]).toarray()
custom_feat = np.array([list(extract_features(query).values())])
X = np.hstack([tfidf, custom_feat])

category = category_clf.predict(X)[0]
mesh_type = mesh_clf.predict(X)[0]
category_proba = category_clf.predict_proba(X)[0].max()

print(f"Category: {{category}} (confidence: {{category_proba:.2%}})")
print(f"Mesh: {{mesh_type}}")
    """)

    return {
        'category_accuracy': cat_accuracy,
        'category_f1': cat_f1,
        'mesh_accuracy': mesh_accuracy,
        'mesh_f1': mesh_f1,
        'training_examples': len(all_data),
        'models_saved': True
    }

if __name__ == '__main__':
    results = train_service_mesh_expert()

    print(f"\n=== Training Summary ===")
    print(f"Category Classification: {results['category_accuracy']:.1%} accuracy, {results['category_f1']:.3f} F1")
    print(f"Mesh Type Classification: {results['mesh_accuracy']:.1%} accuracy, {results['mesh_f1']:.3f} F1")
    print(f"Training Examples: {results['training_examples']}")
    print(f"Models Saved: {results['models_saved']}")
