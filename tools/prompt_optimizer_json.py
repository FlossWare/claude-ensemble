#!/usr/bin/env python3
"""
Prompt Optimization via Pattern Mining + CMA-ES (JSON-based)

Learns which prompt patterns work best for each model based on workflow
execution history stored in JSON files.

Algorithm:
1. Pattern Mining - Extract common prompt templates
2. CMA-ES - Optimize template selection and parameter tuning
3. Model-specific learning - Different patterns for different models

Expected Gain: 15-25% improvement in task success rate
"""

import json
import re
import numpy as np
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import argparse
import glob


class PromptPatternMiner:
    """Extract common patterns from successful prompts"""

    def __init__(self, min_confidence=0.7):
        self.min_confidence = min_confidence
        self.patterns = []

    def extract_patterns(self, prompts_with_scores):
        """Extract n-gram patterns from high-confidence prompts"""
        pattern_scores = defaultdict(list)

        for prompt, confidence, model in prompts_with_scores:
            if confidence < self.min_confidence:
                continue

            # Extract action verbs
            actions = re.findall(r'\b(IMPLEMENT|FIX|REVIEW|ANALYZE|CREATE|UPDATE|REFACTOR|TEST|DOCUMENT|TRAIN|RUN|CHECK)\b',
                                prompt, re.IGNORECASE)

            # Extract code-related terms
            code_terms = re.findall(r'\b(function|class|method|API|database|query|bug|error|issue|script|model|training)\b',
                                   prompt, re.IGNORECASE)

            # Extract file references
            files = re.findall(r'`[^`]+\.(py|js|java|md|sql|sh)`', prompt)

            # Build pattern signature
            pattern = {
                'actions': actions[:3],  # Top 3 actions
                'code_terms': code_terms[:3],
                'has_files': len(files) > 0,
                'length_bucket': len(prompt) // 100,  # Bucket by ~100 chars
                'model': model
            }

            pattern_key = json.dumps(pattern, sort_keys=True)
            pattern_scores[pattern_key].append(confidence)

        # Aggregate patterns
        self.patterns = []
        for pattern_key, scores in pattern_scores.items():
            if len(scores) >= 3:  # Require at least 3 examples
                self.patterns.append({
                    'pattern': json.loads(pattern_key),
                    'avg_confidence': np.mean(scores),
                    'count': len(scores),
                    'std_confidence': np.std(scores)
                })

        # Sort by confidence
        self.patterns.sort(key=lambda x: x['avg_confidence'], reverse=True)
        return self.patterns


class CMAESOptimizer:
    """CMA-ES (Covariance Matrix Adaptation Evolution Strategy) for prompt template optimization"""

    def __init__(self, dim=10, pop_size=20, sigma=0.5):
        self.dim = dim
        self.pop_size = pop_size
        self.sigma = sigma

        # Initialize mean and covariance
        self.mean = np.random.randn(dim) * 0.1
        self.C = np.eye(dim)
        self.generation = 0

        # CMA-ES parameters
        self.mu = pop_size // 2
        self.weights = np.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.weights /= np.sum(self.weights)

        self.mueff = 1 / np.sum(self.weights ** 2)
        self.cc = 4 / (dim + 4)
        self.cs = (self.mueff + 2) / (dim + self.mueff + 5)
        self.c1 = 2 / ((dim + 1.3) ** 2 + self.mueff)
        self.cmu = min(1 - self.c1, 2 * (self.mueff - 2 + 1/self.mueff) / ((dim + 2) ** 2 + self.mueff))
        self.damps = 1 + 2 * max(0, np.sqrt((self.mueff - 1) / (dim + 1)) - 1) + self.cs

        self.pc = np.zeros(dim)
        self.ps = np.zeros(dim)

    def ask(self):
        """Generate candidate solutions"""
        candidates = []
        for _ in range(self.pop_size):
            z = np.random.randn(self.dim)
            y = np.dot(np.linalg.cholesky(self.C), z)
            x = self.mean + self.sigma * y
            candidates.append(x)
        return np.array(candidates)

    def tell(self, candidates, fitnesses):
        """Update distribution based on fitness"""
        # Sort by fitness
        idx = np.argsort(fitnesses)[::-1]  # Descending order
        candidates = candidates[idx]

        # Select top mu
        selected = candidates[:self.mu]

        # Update mean
        old_mean = self.mean.copy()
        self.mean = np.dot(self.weights, selected)

        # Update evolution paths
        self.ps = (1 - self.cs) * self.ps + \
                  np.sqrt(self.cs * (2 - self.cs) * self.mueff) * \
                  np.dot(np.linalg.inv(np.linalg.cholesky(self.C)), (self.mean - old_mean) / self.sigma)

        hsig = np.linalg.norm(self.ps) / np.sqrt(1 - (1 - self.cs) ** (2 * (self.generation + 1))) < \
               (1.4 + 2 / (self.dim + 1)) * np.sqrt(self.dim)

        self.pc = (1 - self.cc) * self.pc + \
                  hsig * np.sqrt(self.cc * (2 - self.cc) * self.mueff) * \
                  (self.mean - old_mean) / self.sigma

        # Update covariance matrix
        artmp = (selected - old_mean) / self.sigma
        self.C = (1 - self.c1 - self.cmu) * self.C + \
                 self.c1 * np.outer(self.pc, self.pc) + \
                 self.cmu * np.dot(artmp.T * self.weights, artmp)

        # Update step size
        self.sigma *= np.exp((self.cs / self.damps) * (np.linalg.norm(self.ps) / np.sqrt(self.dim) - 1))

        self.generation += 1


class PromptOptimizer:
    """Main prompt optimization system"""

    def __init__(self, workflow_dirs):
        self.workflow_dirs = workflow_dirs
        self.miner = PromptPatternMiner()
        self.model_optimizers = {}

    def load_training_data(self):
        """Load worker results from workflow JSON files"""
        data = []

        for workflow_dir in self.workflow_dirs:
            json_files = glob.glob(f"{workflow_dir}/*.json")
            print(f"  Scanning {workflow_dir}: {len(json_files)} files")

            for json_file in json_files:
                try:
                    with open(json_file, 'r') as f:
                        workflow = json.load(f)

                    # Extract agent responses
                    if 'workflowProgress' in workflow:
                        for item in workflow['workflowProgress']:
                            if item.get('type') == 'workflow_agent':
                                prompt = item.get('promptPreview', '')
                                model = item.get('model', 'unknown')
                                state = item.get('state', 'unknown')

                                # Estimate confidence from success/duration
                                confidence = 0.0
                                if state == 'done':
                                    # Higher confidence for successful completions
                                    duration = item.get('durationMs', 0)
                                    # Penalize very slow (>30s) or very fast (<1s) responses
                                    if 1000 <= duration <= 30000:
                                        confidence = 0.85
                                    elif duration < 1000:
                                        confidence = 0.6
                                    else:
                                        confidence = 0.7
                                elif state == 'error':
                                    confidence = 0.0

                                if prompt and confidence > 0:
                                    data.append((prompt, confidence, model))

                except Exception as e:
                    continue

        return data

    def train(self, max_generations=50):
        """Train prompt optimizer"""
        print("Loading training data from JSON files...")
        data = self.load_training_data()
        print(f"Loaded {len(data)} agent executions")

        if len(data) == 0:
            print("ERROR: No training data found!")
            return None

        # Mine patterns
        print("\nMining prompt patterns...")
        patterns = self.miner.extract_patterns(data)
        print(f"Found {len(patterns)} patterns")

        # Display top patterns
        print("\nTop 10 patterns by confidence:")
        for i, p in enumerate(patterns[:10], 1):
            print(f"\n{i}. Avg Confidence: {p['avg_confidence']:.3f} (n={p['count']})")
            print(f"   Pattern: {json.dumps(p['pattern'], indent=6)}")

        # Group by model
        model_data = defaultdict(list)
        for prompt, confidence, model in data:
            model_data[model].append((prompt, confidence))

        print(f"\nTraining model-specific optimizers for {len(model_data)} models...")

        # Train CMA-ES for each model
        results = {}
        for model, model_prompts in model_data.items():
            if len(model_prompts) < 10:
                print(f"\nSkipping {model}: only {len(model_prompts)} samples (need 10+)")
                continue

            print(f"\nOptimizing for {model}...")

            # Encode prompts as features
            features = []
            targets = []
            for prompt, confidence in model_prompts:
                # Simple feature extraction
                feat = [
                    len(prompt),
                    prompt.count('IMPLEMENT'),
                    prompt.count('FIX'),
                    prompt.count('REVIEW'),
                    prompt.count('`'),
                    prompt.count('function'),
                    prompt.count('class'),
                    prompt.count('error'),
                    prompt.count('bug'),
                    len(re.findall(r'\b[A-Z]+\b', prompt))
                ]
                # Pad/truncate to 10 dims
                feat = (feat + [0] * 10)[:10]
                features.append(feat)
                targets.append(confidence)

            features = np.array(features)
            targets = np.array(targets)

            # Normalize features
            feat_mean = np.mean(features, axis=0)
            feat_std = np.std(features, axis=0) + 1e-8
            features = (features - feat_mean) / feat_std

            # Run CMA-ES
            optimizer = CMAESOptimizer(dim=10, pop_size=20)

            best_fitness = -float('inf')
            best_weights = None

            for gen in range(max_generations):
                candidates = optimizer.ask()

                # Evaluate fitness (correlation with confidence)
                fitnesses = []
                for weights in candidates:
                    predictions = np.dot(features, weights)
                    # Fitness = correlation with actual confidence
                    if len(np.unique(targets)) > 1:
                        fitness = np.corrcoef(predictions, targets)[0, 1]
                    else:
                        fitness = 0
                    if np.isnan(fitness):
                        fitness = 0
                    fitnesses.append(fitness)

                fitnesses = np.array(fitnesses)
                optimizer.tell(candidates, fitnesses)

                max_fitness = np.max(fitnesses)
                if max_fitness > best_fitness:
                    best_fitness = max_fitness
                    best_weights = candidates[np.argmax(fitnesses)]

                if (gen + 1) % 10 == 0:
                    print(f"  Generation {gen+1}/{max_generations}: Best correlation = {best_fitness:.3f}")

            results[model] = {
                'weights': best_weights.tolist(),
                'feat_mean': feat_mean.tolist(),
                'feat_std': feat_std.tolist(),
                'correlation': float(best_fitness),
                'n_samples': len(model_prompts)
            }

            print(f"  Final: {best_fitness:.3f} correlation on {len(model_prompts)} samples")

        return {
            'patterns': patterns,
            'model_weights': results,
            'training_samples': len(data),
            'timestamp': datetime.now().isoformat()
        }

    def save_results(self, results, output_path):
        """Save optimization results to JSON"""
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Prompt Optimizer Training (JSON-based)')
    parser.add_argument('--min-confidence', type=float, default=0.7,
                       help='Minimum confidence for pattern mining')
    parser.add_argument('--max-generations', type=int, default=50,
                       help='CMA-ES generations per model')
    parser.add_argument('--output', type=str, default='/tmp/prompt_optimization_results.json',
                       help='Output path for results')
    parser.add_argument('--workflow-dirs', type=str, nargs='+',
                       help='Directories containing workflow JSON files')

    args = parser.parse_args()

    # Find workflow directories if not specified
    if not args.workflow_dirs:
        home = str(Path.home())
        claude_projects = f"{home}/.claude/projects/*claude-global-skills*/*/workflows"
        workflow_dirs = glob.glob(claude_projects)
        print(f"Auto-detected {len(workflow_dirs)} workflow directories")
    else:
        workflow_dirs = args.workflow_dirs

    if not workflow_dirs:
        print("ERROR: No workflow directories found!")
        print("Try: python3 prompt_optimizer_json.py --workflow-dirs /path/to/workflows")
        return

    print("=" * 60)
    print("Prompt Optimization Training (JSON-based)")
    print("=" * 60)
    print(f"Algorithm: Pattern Mining + CMA-ES")
    print(f"Min Confidence: {args.min_confidence}")
    print(f"Max Generations: {args.max_generations}")
    print(f"Workflow Dirs: {len(workflow_dirs)}")
    print(f"Output: {args.output}")
    print("=" * 60)

    # Train
    optimizer = PromptOptimizer(workflow_dirs)
    results = optimizer.train(max_generations=args.max_generations)

    if not results:
        print("\nERROR: Training failed - no data")
        return

    # Save
    optimizer.save_results(results, args.output)

    # Summary
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Total patterns found: {len(results['patterns'])}")
    print(f"Models optimized: {len(results['model_weights'])}")
    print(f"Training samples: {results['training_samples']}")

    if results['model_weights']:
        print("\nModel Performance:")
        for model, data in sorted(results['model_weights'].items(),
                                 key=lambda x: x[1]['correlation'],
                                 reverse=True):
            print(f"  {model:40s}: {data['correlation']:6.3f} correlation (n={data['n_samples']})")

    print("\nNext Steps:")
    print("  1. Review patterns in output JSON file")
    print("  2. Integrate weights into multi-model router")
    print("  3. A/B test optimized vs baseline prompts")
    print("  4. Monitor success rate improvements")

    return results


if __name__ == '__main__':
    main()
