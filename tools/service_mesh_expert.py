#!/usr/bin/env python3
"""
Service Mesh Expert - Inference Script

Load trained models and provide service mesh recommendations for:
- Linkerd traffic policies
- Consul service mesh configurations
- Common troubleshooting scenarios
"""

import pickle
import numpy as np
import json
import sys
from pathlib import Path

# Import feature extraction from trainer
sys.path.insert(0, str(Path(__file__).parent))
from service_mesh_trainer import extract_features, SERVICE_MESH_PATTERNS, ISSUE_CATEGORIES

class ServiceMeshExpert:
    """Service Mesh expert system using trained ML models"""

    def __init__(self):
        learning_dir = Path.home() / '.claude' / 'learning'

        # Load models
        with open(learning_dir / 'service_mesh_category_clf.pkl', 'rb') as f:
            self.category_clf = pickle.load(f)

        with open(learning_dir / 'service_mesh_type_clf.pkl', 'rb') as f:
            self.mesh_clf = pickle.load(f)

        with open(learning_dir / 'service_mesh_vectorizer.pkl', 'rb') as f:
            self.vectorizer = pickle.load(f)

        with open(learning_dir / 'service_mesh_metadata.json', 'r') as f:
            self.metadata = json.load(f)

        print("✅ Service Mesh Expert loaded successfully")
        print(f"   Categories: {', '.join(self.metadata['categories'])}")
        print(f"   Meshes: {', '.join(self.metadata['meshes'])}")
        print(f"   Model accuracy: {self.metadata['mesh_accuracy']:.1%} (mesh), {self.metadata['category_accuracy']:.1%} (category)\n")

    def predict(self, query):
        """Predict category and mesh type for a query"""
        # Extract features
        tfidf = self.vectorizer.transform([query]).toarray()
        custom_feat = np.array([list(extract_features(query).values())])
        X = np.hstack([tfidf, custom_feat])

        # Predict
        category = self.category_clf.predict(X)[0]
        mesh_type = self.mesh_clf.predict(X)[0]

        category_proba = self.category_clf.predict_proba(X)[0]
        mesh_proba = self.mesh_clf.predict_proba(X)[0]

        category_confidence = category_proba.max()
        mesh_confidence = mesh_proba.max()

        # Get top 3 categories
        top_cat_idx = np.argsort(category_proba)[-3:][::-1]
        top_categories = [(self.category_clf.classes_[i], category_proba[i]) for i in top_cat_idx]

        return {
            'category': category,
            'category_confidence': float(category_confidence),
            'top_categories': [(cat, float(conf)) for cat, conf in top_categories],
            'mesh': mesh_type,
            'mesh_confidence': float(mesh_confidence)
        }

    def get_recommendations(self, query):
        """Get actionable recommendations for a service mesh query"""
        prediction = self.predict(query)

        category = prediction['category']
        mesh = prediction['mesh']

        recommendations = {
            'query': query,
            'predicted_mesh': mesh,
            'predicted_category': category,
            'confidence': {
                'mesh': prediction['mesh_confidence'],
                'category': prediction['category_confidence']
            },
            'alternative_categories': prediction['top_categories'][1:],
            'recommendations': []
        }

        # Generate recommendations based on category and mesh
        if mesh in ['linkerd', 'consul']:
            patterns = SERVICE_MESH_PATTERNS.get(mesh, {})

            if 'traffic_policy' in category or 'configuration' in category:
                recommendations['recommendations'].append({
                    'type': 'traffic_policies',
                    'mesh': mesh,
                    'policies': patterns.get('traffic_policies', []),
                    'suggestion': f"Consider these {mesh} traffic policies: {', '.join(patterns.get('traffic_policies', [])[:5])}"
                })

            if 'security' in category:
                recommendations['recommendations'].append({
                    'type': 'security',
                    'mesh': mesh,
                    'suggestion': f"For {mesh} security: Enable mTLS, configure authorization policies, rotate certificates regularly"
                })

            if 'troubleshooting' in category or 'issue' in category:
                recommendations['recommendations'].append({
                    'type': 'common_issues',
                    'mesh': mesh,
                    'issues': patterns.get('common_issues', []),
                    'suggestion': f"Check these common {mesh} issues: {', '.join(patterns.get('common_issues', [])[:3])}"
                })

            if 'deployment' in category:
                recommendations['recommendations'].append({
                    'type': 'deployment_strategy',
                    'mesh': mesh,
                    'suggestion': f"For {mesh} deployments: Use canary/blue-green strategies, configure traffic splits, monitor metrics during rollout"
                })

            # Add configuration resources
            recommendations['recommended_resources'] = patterns.get('configurations', [])[:5]

        # Severity assessment
        severity = 'medium'
        for severity_level, issues in ISSUE_CATEGORIES.items():
            if any(issue in query.lower() for issue in issues):
                severity = severity_level.split('_')[1]
                break

        recommendations['severity'] = severity

        return recommendations

    def interactive_mode(self):
        """Run interactive Q&A mode"""
        print("=== Service Mesh Expert - Interactive Mode ===")
        print("Ask questions about Linkerd or Consul configurations, traffic policies, or troubleshooting.")
        print("Type 'quit' or 'exit' to end.\n")

        while True:
            try:
                query = input("Your question: ").strip()

                if query.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break

                if not query:
                    continue

                print("\nAnalyzing...\n")

                result = self.get_recommendations(query)

                print(f"📊 Prediction:")
                print(f"   Service Mesh: {result['predicted_mesh']} (confidence: {result['confidence']['mesh']:.1%})")
                print(f"   Category: {result['predicted_category']} (confidence: {result['confidence']['category']:.1%})")
                print(f"   Severity: {result['severity']}")

                if result.get('alternative_categories'):
                    print(f"\n   Alternative categories:")
                    for cat, conf in result['alternative_categories']:
                        print(f"      - {cat}: {conf:.1%}")

                print(f"\n💡 Recommendations:")
                for rec in result['recommendations']:
                    print(f"   {rec.get('type', 'general').upper()}: {rec.get('suggestion', 'N/A')}")

                if result.get('recommended_resources'):
                    print(f"\n📚 Relevant {result['predicted_mesh']} resources:")
                    for res in result['recommended_resources']:
                        print(f"      - {res}")

                print("\n" + "="*60 + "\n")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

def main():
    """Main entry point"""
    expert = ServiceMeshExpert()

    # Example queries
    examples = [
        "Configure Linkerd circuit breaker for failing microservices",
        "Set up Consul service mesh intentions for authorization",
        "Debug Linkerd proxy not injecting into pods",
        "Implement canary deployment using Consul service splitter",
        "Consul health checks failing repeatedly"
    ]

    if len(sys.argv) > 1:
        # Command-line mode
        query = ' '.join(sys.argv[1:])
        result = expert.get_recommendations(query)
        print(json.dumps(result, indent=2))
    else:
        # Demo mode
        print("=== Service Mesh Expert - Demo Mode ===\n")

        for query in examples:
            print(f"Query: {query}")
            result = expert.get_recommendations(query)

            print(f"  Mesh: {result['predicted_mesh']} ({result['confidence']['mesh']:.1%})")
            print(f"  Category: {result['predicted_category']} ({result['confidence']['category']:.1%})")
            print(f"  Severity: {result['severity']}")

            if result['recommendations']:
                print(f"  Recommendation: {result['recommendations'][0].get('suggestion', 'N/A')}")

            print()

        print("\nRun with --interactive for Q&A mode")
        print("Or pass a query as arguments: ./service_mesh_expert.py 'your question here'\n")

        if '--interactive' in sys.argv or '-i' in sys.argv:
            expert.interactive_mode()

if __name__ == '__main__':
    main()
