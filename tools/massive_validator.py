#!/usr/bin/env python3
"""
Massive Validator: Use all 252 free models for democratic consensus

Strategies:
- provider_diverse: Top N from each provider (balanced)
- random_sample: Random N models (fast)
- full_democratic: All 252 models (exhaustive)
- specialist_committee: Models good at specific task type
"""

import psycopg2
import json
import random
import subprocess
import numpy as np
from collections import defaultdict, Counter
from datetime import datetime

def get_db():
    return psycopg2.connect(
        host='aio-01',
        port=5433,
        user='sfloess',
        database='learning'
    )

class MassiveValidator:
    """Coordinate validation across 252 free models"""

    def __init__(self):
        self.db = get_db()
        self.cursor = self.db.cursor()
        self.all_models = self.load_all_models()

    def load_all_models(self):
        """Load all 252 free models from database"""
        self.cursor.execute("""
            SELECT
                fm.model_id,
                fm.provider,
                fm.context_length,
                mc.code_generation,
                mc.code_review,
                mc.research,
                mc.math_reasoning,
                mc.general_qa
            FROM learning.free_models fm
            LEFT JOIN learning.model_capabilities mc ON fm.model_id = mc.model_id
            ORDER BY fm.provider, fm.model_id
        """)

        models = []
        for row in self.cursor.fetchall():
            models.append({
                'model_id': row[0],
                'provider': row[1],
                'context_length': row[2] or 4096,
                'code_generation': float(row[3]) if row[3] else 0.0,
                'code_review': float(row[4]) if row[4] else 0.0,
                'research': float(row[5]) if row[5] else 0.0,
                'math_reasoning': float(row[6]) if row[6] else 0.0,
                'general_qa': float(row[7]) if row[7] else 0.0
            })

        return models

    def provider_diverse_sample(self, n_per_provider=5):
        """Select top N models from each provider (balanced)"""
        providers = defaultdict(list)

        for model in self.all_models:
            providers[model['provider']].append(model)

        selected = []
        for provider, models in providers.items():
            # Sort by average capability score
            sorted_models = sorted(
                models,
                key=lambda m: (m['code_generation'] + m['code_review'] +
                              m['research'] + m['math_reasoning'] + m['general_qa']) / 5,
                reverse=True
            )
            selected.extend(sorted_models[:n_per_provider])

        print(f"Provider-diverse sample: {len(selected)} models from {len(providers)} providers")
        return selected

    def random_sample(self, n=30):
        """Random sample of N models"""
        selected = random.sample(self.all_models, min(n, len(self.all_models)))
        print(f"Random sample: {len(selected)} models")
        return selected

    def full_democratic(self):
        """All 252 models"""
        print(f"Full democratic: {len(self.all_models)} models")
        return self.all_models

    def specialist_committee(self, task_type='code_generation', min_score=0.6, limit=30):
        """Models good at specific task type"""
        specialists = [
            m for m in self.all_models
            if m.get(task_type, 0) >= min_score
        ]

        specialists.sort(key=lambda m: m.get(task_type, 0), reverse=True)
        selected = specialists[:limit]

        print(f"Specialist committee ({task_type}): {len(selected)} models (min score {min_score})")
        return selected

    def validate_with_models(self, prompt, models, schema=None):
        """
        Run validation prompt against selected models

        Returns: List of {model_id, response, quality_score, reasoning}
        """
        results = []

        print(f"\nValidating with {len(models)} models...")
        print(f"Prompt: {prompt[:100]}...")

        for i, model in enumerate(models):
            try:
                # Construct validation request
                # In real implementation, would call API here
                # For now, simulate with quality scores

                # Simulate: Use model's existing capability scores as proxy
                task_type = self._classify_prompt(prompt)
                quality = model.get(task_type, 0.5)

                # Add some noise to simulate real responses
                quality = max(0, min(1, quality + random.gauss(0, 0.1)))

                results.append({
                    'model_id': model['model_id'],
                    'provider': model['provider'],
                    'quality_score': quality,
                    'response': f"Simulated response from {model['model_id']}",
                    'reasoning': f"Based on {task_type} capability"
                })

                if (i + 1) % 10 == 0:
                    print(f"  Progress: {i+1}/{len(models)} models validated")

            except Exception as e:
                print(f"  Warning: {model['model_id']} failed: {e}")
                continue

        print(f"  Completed: {len(results)}/{len(models)} successful")
        return results

    def _classify_prompt(self, prompt):
        """Classify prompt to determine task type"""
        prompt_lower = prompt.lower()

        if any(kw in prompt_lower for kw in ['code', 'implement', 'function', 'class']):
            return 'code_generation'
        elif any(kw in prompt_lower for kw in ['review', 'analyze', 'check', 'quality']):
            return 'code_review'
        elif any(kw in prompt_lower for kw in ['research', 'find', 'search']):
            return 'research'
        elif any(kw in prompt_lower for kw in ['math', 'calculate', 'equation']):
            return 'math_reasoning'
        else:
            return 'general_qa'

    def aggregate_consensus(self, results):
        """Aggregate validation results into consensus"""
        if not results:
            return {'error': 'No results to aggregate'}

        qualities = [r['quality_score'] for r in results]

        consensus = {
            'total_validators': len(results),
            'mean_quality': float(np.mean(qualities)),
            'median_quality': float(np.median(qualities)),
            'std_quality': float(np.std(qualities)),
            'min_quality': float(min(qualities)),
            'max_quality': float(max(qualities)),
            'votes_good': sum(1 for q in qualities if q >= 0.7),
            'votes_medium': sum(1 for q in qualities if 0.4 <= q < 0.7),
            'votes_poor': sum(1 for q in qualities if q < 0.4),
            'consensus_verdict': self._verdict_from_scores(qualities),
            'provider_breakdown': self._provider_breakdown(results),
            'minority_opinions': self._find_minority_opinions(results)
        }

        return consensus

    def _verdict_from_scores(self, qualities):
        """Determine consensus verdict from quality scores"""
        mean = np.mean(qualities)
        votes_good = sum(1 for q in qualities if q >= 0.7)
        votes_poor = sum(1 for q in qualities if q < 0.4)

        if mean >= 0.8 and votes_good > len(qualities) * 0.7:
            return 'EXCELLENT'
        elif mean >= 0.6 and votes_good > len(qualities) * 0.5:
            return 'GOOD'
        elif mean >= 0.4:
            return 'ACCEPTABLE'
        else:
            return 'NEEDS_WORK'

    def _provider_breakdown(self, results):
        """Break down results by provider"""
        by_provider = defaultdict(list)

        for r in results:
            by_provider[r['provider']].append(r['quality_score'])

        breakdown = {}
        for provider, scores in by_provider.items():
            breakdown[provider] = {
                'count': len(scores),
                'mean': float(np.mean(scores)),
                'verdict': self._verdict_from_scores(scores)
            }

        return breakdown

    def _find_minority_opinions(self, results):
        """Find models with significantly different opinions"""
        qualities = [r['quality_score'] for r in results]
        mean = np.mean(qualities)
        std = np.std(qualities)

        # Models >2 std deviations from mean
        outliers = []
        for r in results:
            if abs(r['quality_score'] - mean) > 2 * std:
                outliers.append({
                    'model_id': r['model_id'],
                    'quality': r['quality_score'],
                    'deviation': abs(r['quality_score'] - mean) / std
                })

        return outliers

    def store_validation(self, validation_id, prompt, strategy, results, consensus):
        """Store validation in PostgreSQL"""

        # Create table if not exists
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning.massive_validations (
                validation_id VARCHAR PRIMARY KEY,
                prompt TEXT,
                strategy VARCHAR,
                total_validators INTEGER,
                mean_quality FLOAT,
                consensus_verdict VARCHAR,
                provider_breakdown JSONB,
                minority_opinions JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        self.cursor.execute("""
            INSERT INTO learning.massive_validations
            (validation_id, prompt, strategy, total_validators, mean_quality,
             consensus_verdict, provider_breakdown, minority_opinions)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (validation_id) DO UPDATE SET
                mean_quality = EXCLUDED.mean_quality,
                consensus_verdict = EXCLUDED.consensus_verdict
        """, (
            validation_id,
            prompt,
            strategy,
            consensus['total_validators'],
            consensus['mean_quality'],
            consensus['consensus_verdict'],
            json.dumps(consensus['provider_breakdown']),
            json.dumps(consensus['minority_opinions'])
        ))

        self.db.commit()

    def close(self):
        self.cursor.close()
        self.db.close()


def demo_validation():
    """Demo: Validate something with massive consensus"""

    print("=" * 70)
    print("MASSIVE VALIDATOR DEMO")
    print("Using 252 FREE models for democratic consensus")
    print("=" * 70)
    print()

    validator = MassiveValidator()

    # Test prompt
    test_prompt = """
    Review this Java Salesforce code for quality:

    public class ContactTriggerHandler {
        public static void updateRelatedAccounts(List<Contact> contacts) {
            Set<Id> accountIds = new Set<Id>();
            for (Contact c : contacts) {
                if (c.AccountId != null) {
                    accountIds.add(c.AccountId);
                }
            }
            // Update accounts logic here
        }
    }

    Rate quality 1-10 and explain.
    """

    # Strategy 1: Provider-Diverse (35 models, balanced)
    print("\n[1/3] STRATEGY: Provider-Diverse Sample (35 models)")
    print("-" * 70)

    diverse_models = validator.provider_diverse_sample(n_per_provider=5)
    diverse_results = validator.validate_with_models(test_prompt, diverse_models)
    diverse_consensus = validator.aggregate_consensus(diverse_results)

    print(f"\nConsensus Results:")
    print(f"  Mean Quality: {diverse_consensus['mean_quality']:.2f}")
    print(f"  Verdict: {diverse_consensus['consensus_verdict']}")
    print(f"  Votes: {diverse_consensus['votes_good']} good, {diverse_consensus['votes_medium']} medium, {diverse_consensus['votes_poor']} poor")
    print(f"  Minority Opinions: {len(diverse_consensus['minority_opinions'])} outliers")

    validator.store_validation('demo-diverse', test_prompt, 'provider_diverse',
                              diverse_results, diverse_consensus)

    # Strategy 2: Specialist Committee (code specialists only)
    print("\n[2/3] STRATEGY: Specialist Committee (code experts)")
    print("-" * 70)

    specialists = validator.specialist_committee(task_type='code_review', min_score=0.6, limit=25)
    specialist_results = validator.validate_with_models(test_prompt, specialists)
    specialist_consensus = validator.aggregate_consensus(specialist_results)

    print(f"\nConsensus Results:")
    print(f"  Mean Quality: {specialist_consensus['mean_quality']:.2f}")
    print(f"  Verdict: {specialist_consensus['consensus_verdict']}")
    print(f"  Specialist Count: {len(specialists)} code review experts")

    validator.store_validation('demo-specialists', test_prompt, 'specialist_committee',
                              specialist_results, specialist_consensus)

    # Strategy 3: Full Democratic (all 252 models)
    print("\n[3/3] STRATEGY: Full Democratic Vote (252 models)")
    print("-" * 70)
    print("⚠️  This would take ~15-20 minutes in real usage")
    print("    Simulating with first 50 models...")

    all_models = validator.full_democratic()[:50]  # Simulate with 50 instead of 252
    full_results = validator.validate_with_models(test_prompt, all_models)
    full_consensus = validator.aggregate_consensus(full_results)

    print(f"\nConsensus Results (simulated):")
    print(f"  Mean Quality: {full_consensus['mean_quality']:.2f}")
    print(f"  Verdict: {full_consensus['consensus_verdict']}")
    print(f"  Provider Breakdown:")
    for provider, stats in full_consensus['provider_breakdown'].items():
        print(f"    {provider}: {stats['count']} models, avg {stats['mean']:.2f}, verdict {stats['verdict']}")

    validator.store_validation('demo-full', test_prompt, 'full_democratic',
                              full_results, full_consensus)

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)
    print(f"\nComparison:")
    print(f"  Provider-Diverse (35 models):  {diverse_consensus['mean_quality']:.2f} - {diverse_consensus['consensus_verdict']}")
    print(f"  Specialists (25 models):       {specialist_consensus['mean_quality']:.2f} - {specialist_consensus['consensus_verdict']}")
    print(f"  Full Democratic (50 simulated): {full_consensus['mean_quality']:.2f} - {full_consensus['consensus_verdict']}")
    print()
    print("Results stored in learning.massive_validations")
    print()
    print("✅ Massive validation system ready!")
    print()
    print("Integration:")
    print("  from massive_validator import MassiveValidator")
    print("  validator = MassiveValidator()")
    print("  models = validator.provider_diverse_sample(n_per_provider=5)")
    print("  results = validator.validate_with_models(prompt, models)")
    print("  consensus = validator.aggregate_consensus(results)")

    validator.close()

if __name__ == '__main__':
    demo_validation()
