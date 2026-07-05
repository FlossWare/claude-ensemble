#!/usr/bin/env python3
"""
Analogical Reasoning Usage Example

Demonstrates how to use the trained analogical reasoning model.
"""

import sys
from pathlib import Path

# Add tools path
tools_path = Path(__file__).parent
sys.path.insert(0, str(tools_path))

from analogical_reasoning_trainer import AnalogicalReasoning, AnalogicalPattern


def main():
    print("=== Analogical Reasoning Demo ===\n")

    # Load trained model
    model_path = '/home/sfloess/.claude/learning/analogical_reasoning.pkl'
    model = AnalogicalReasoning.load(model_path)

    print(f"Loaded model with {len(model.patterns)} patterns")
    print(f"Domains: {', '.join(set([p.domain for p in model.patterns.values()]))}\n")

    # Example 1: Find analogies for a software problem
    print("Example 1: Find analogies for database bottleneck")
    print("-" * 60)

    db_problem = AnalogicalPattern(
        domain='database',
        entities=['app_server', 'connection_pool', 'database'],
        relations=[
            ('app_server', 'queries', 'database'),
            ('database', 'limited_by', 'connection_pool'),
            ('connection_pool', 'throttles', 'throughput')
        ],
        context='Database connection pool too small, causing slow queries'
    )

    analogies = model.find_analogous_patterns(db_problem, k=3)

    for i, (pattern_id, score) in enumerate(analogies, 1):
        pattern = model.patterns[pattern_id]
        print(f"\n{i}. {pattern.domain.upper()} (similarity: {score:.3f})")
        print(f"   Solution: {pattern.solution}")

    # Example 2: Transfer solution
    print("\n\nExample 2: Transfer solution from best analogy")
    print("-" * 60)

    if analogies:
        best_id = analogies[0][0]
        transfer = model.transfer_solution(best_id, db_problem)

        print(f"\nSource domain: {transfer['source_domain']}")
        print(f"Target domain: {transfer['target_domain']}")
        print(f"\nOriginal solution:")
        print(f"  {transfer['original_solution']}")
        print(f"\nTransferred solution:")
        print(f"  {transfer['transferred_solution']}")
        print(f"\nConfidence: {transfer['confidence']:.3f}")

    # Example 3: Generate metaphor
    print("\n\nExample 3: Generate metaphors")
    print("-" * 60)

    concepts = [
        'learning',
        'debugging',
        'refactoring',
        'optimization'
    ]

    for concept in concepts:
        metaphor = model.generate_metaphor(concept, 'any')
        print(f"\n{concept.capitalize()}: {metaphor}")

    # Example 4: Evaluate analogy quality
    print("\n\nExample 4: Evaluate analogy quality")
    print("-" * 60)

    if len(model.patterns) >= 2:
        pattern_ids = list(model.patterns.keys())

        # Evaluate circuit <-> water (should be high)
        if 'circuit_1' in pattern_ids and 'water_1' in pattern_ids:
            eval1 = model.evaluate_analogy('circuit_1', 'water_1')
            print(f"\nCircuit <-> Water Flow:")
            print(f"  Quality: {eval1['quality_score']:.3f}")
            print(f"  {eval1['interpretation']}")

        # Evaluate circuit <-> software (should be lower)
        if 'circuit_1' in pattern_ids and 'software_1' in pattern_ids:
            eval2 = model.evaluate_analogy('circuit_1', 'software_1')
            print(f"\nCircuit <-> Software:")
            print(f"  Quality: {eval2['quality_score']:.3f}")
            print(f"  {eval2['interpretation']}")

    # Example 5: Add new pattern and find analogies
    print("\n\nExample 5: Add new pattern and find matches")
    print("-" * 60)

    traffic_pattern = AnalogicalPattern(
        domain='traffic_control',
        entities=['traffic_light', 'road_capacity', 'vehicles'],
        relations=[
            ('traffic_light', 'regulates', 'vehicles'),
            ('vehicles', 'limited_by', 'road_capacity'),
            ('road_capacity', 'throttles', 'flow_rate')
        ],
        solution='Add more lanes or optimize light timing',
        context='Traffic congestion due to insufficient road capacity'
    )

    model.add_pattern('traffic_1', traffic_pattern)
    print(f"Added traffic control pattern")

    # Find what it's similar to
    analogies = model.find_analogous_patterns(traffic_pattern, k=3)
    print(f"\nMost similar patterns:")
    for i, (pattern_id, score) in enumerate(analogies, 1):
        pattern = model.patterns[pattern_id]
        print(f"  {i}. {pattern.domain} ({score:.3f})")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("\nModel path: " + model_path)
    print("To use in your code:")
    print("  from analogical_reasoning_trainer import AnalogicalReasoning")
    print("  model = AnalogicalReasoning.load(model_path)")


if __name__ == '__main__':
    main()
