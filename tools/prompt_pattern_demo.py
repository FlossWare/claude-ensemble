#!/usr/bin/env python3
"""
Prompt Pattern Learning Integration Demo
Shows enhancement before/after for different task types
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.prompt_enhancer import PromptEnhancer

def demo():
    """Run enhancement demo across task types"""
    enhancer = PromptEnhancer()

    test_cases = [
        {
            'task': 'I want to fix the authentication bug in login.py',
            'task_type': 'debugging',
            'workflow': ''
        },
        {
            'task': 'implement a Java parser for Salesforce SOAP API',
            'task_type': 'code_generation',
            'workflow': 'code-generation-workflow'
        },
        {
            'task': 'review the security issues in the authentication module',
            'task_type': 'code_review',
            'workflow': 'security-review'
        },
        {
            'task': 'train Thompson Sampling bandit on execution logs',
            'task_type': 'ml_training',
            'workflow': 'fleet-training'
        },
        {
            'task': 'research firmware reverse engineering methods for RAX-75',
            'task_type': 'research',
            'workflow': 'deep-research'
        },
        {
            'task': 'setup PostgreSQL with pgvector extension',
            'task_type': 'system_config',
            'workflow': ''
        }
    ]

    print(f"\n{'='*80}")
    print(f"PROMPT PATTERN LEARNING DEMO")
    print(f"{'='*80}")
    print(f"Loaded {len(enhancer.stats_by_type)} task types with "
          f"{sum(v.get('count', 0) for v in enhancer.stats_by_type.values())} examples")
    print()

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'-'*80}")
        print(f"TEST {i}: {test['task_type'].upper()}")
        print(f"{'-'*80}")
        print(f"Original: {test['task']}")
        print()

        enhanced = enhancer.enhance_prompt(
            test['task'],
            task_type=test['task_type'],
            workflow_name=test['workflow']
        )

        if enhanced != test['task']:
            print(f"Enhanced:\n{enhanced}")
        else:
            print("Enhanced: [No changes - pattern thresholds not met]")

        # Show learned patterns for this type
        stats = enhancer.get_pattern_stats(test['task_type'])
        if stats:
            print()
            print(f"Learned patterns ({stats.get('count', 0)} examples):")
            for pattern in ['imperative', 'constraints', 'examples', 'task_label']:
                pct = stats.get(f'{pattern}_pct', 0)
                if pct > 0.1:
                    print(f"  {pattern}: {pct*100:.0f}%")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    demo()
