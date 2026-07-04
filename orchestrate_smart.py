#!/usr/bin/env python3
"""
Smart Fleet Orchestrator - GA + Thompson Sampling + Complexity + Prompt Patterns Integration
Runs on aio-01 with intelligent model selection

Combines:
1. Auto-Profiler (GA-based exploration for unprofiled models)
2. Contextual Bandit (Thompson Sampling for task-specific model selection)
3. Complexity Estimator (predicts task difficulty before execution)
4. Prompt Enhancer (learned patterns from 692 examples)
5. Fleet Executor (distributed execution)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from shared.fleet_executor import execute_on_fleet_parallel
from shared.error_recovery import ErrorRecoveryClassifier
from shared.prompt_enhancer import PromptEnhancer
from tools.auto_profiler import AutoProfiler
from tools.contextual_bandit_trainer_v2 import ContextualBandit, extract_context
from tools.complexity_estimator import ComplexityEstimator
from pathlib import Path
import json
import time

class SmartOrchestrator:
    """Intelligent orchestrator with GA + Thompson Sampling + Complexity + Prompt Patterns"""

    def __init__(self, exploration_rate=0.15, adaptive=True):
        """
        exploration_rate: Base probability of using unprofiled model (GA exploration)
        adaptive: If True, adjust exploration based on coverage (30% → 15% → 5%)
        """
        self.profiler = AutoProfiler(exploration_rate=exploration_rate, adaptive=adaptive)

        # PostgreSQL connection for worker/model discovery
        import psycopg2
        self.db_conn = psycopg2.connect(
            host='aio-01',
            port=5433,
            dbname='learning',
            user='claude'
        )

        # Load prompt enhancer (learned patterns from 692 task examples)
        try:
            self.prompt_enhancer = PromptEnhancer()
            print("✅ Loaded prompt pattern enhancer")
        except Exception as e:
            print(f"⚠️  Prompt enhancer error: {e}")
            self.prompt_enhancer = None

        # Load Thompson Sampling bandit if available
        try:
            self.bandit = ContextualBandit.load(
                os.path.expanduser('~/.claude/learning/contextual_bandit_v2.json')
            )
            print("✅ Loaded Thompson Sampling bandit")
        except:
            print("⚠️  Thompson Sampling bandit not found - using Auto-Profiler only")
            self.bandit = None

        # Load model mapping if available
        try:
            with open(os.path.expanduser('~/.claude/learning/model_mapping.json'), 'r') as f:
                mapping = json.load(f)
                # Handle nested structure: {"model_to_id": {...}}
                model_to_id = mapping.get('model_to_id', mapping)
                self.id_to_model = {v: k for k, v in model_to_id.items()}
                print(f"✅ Loaded model mapping ({len(self.id_to_model)} models)")
        except Exception as e:
            print(f"⚠️  Model mapping error: {e}")
            self.id_to_model = None

        # Load complexity estimator if available
        try:
            self.complexity_estimator = ComplexityEstimator()
            estimator_path = Path.home() / ".claude" / "learning" / "complexity_estimator.pkl"
            if estimator_path.exists():
                self.complexity_estimator.load(str(estimator_path))
                print("✅ Loaded complexity estimator")
            else:
                print("⚠️  Complexity estimator not trained - run tools/complexity_estimator.py")
                self.complexity_estimator = None
        except Exception as e:
            print(f"⚠️  Complexity estimator error: {e}")
            self.complexity_estimator = None

        # Load error recovery classifier if available
        try:
            self.error_recovery = ErrorRecoveryClassifier()
            if self.error_recovery.loaded:
                metrics = self.error_recovery.get_metrics()
                if metrics:
                    acc = metrics.get('retryable', {}).get('accuracy', 0)
                    print(f"✅ Loaded error recovery classifier ({acc:.1%} accuracy)")
            else:
                print("⚠️  Error recovery classifier not trained")
                self.error_recovery = None
        except Exception as e:
            print(f"⚠️  Error recovery classifier error: {e}")
            self.error_recovery = None

    def predict_complexity(self, task_description):
        """
        Predict task complexity before execution
        
        Returns: dict with predicted_duration_ms, predicted_confidence, complexity_category
                 or None if estimator not available
        """
        if not self.complexity_estimator:
            return None
        
        try:
            prediction = self.complexity_estimator.predict(task_description)
            return prediction
        except Exception as e:
            print(f"⚠️  Complexity prediction failed: {e}")
            return None

    def select_model(self, task_description, task_type='general_qa', workflow_name='',
                     complexity_info=None):
        """
        Select best model for task using GA + Thompson Sampling + Complexity

        Args:
            task_description: The task prompt
            task_type: Task category
            workflow_name: Workflow context
            complexity_info: Optional complexity prediction from predict_complexity()

        Returns: (model_id, selection_method)
        """
        # HARDCODED VERIFIED WORKING MODELS (2026-07-03)
        # These are known to work after testing - fallback if PostgreSQL fails
        VERIFIED_WORKING_MODELS = [
            'llama-3.3-70b-versatile',  # Groq, FREE, FAST (VERIFIED 2026-07-03)
            'llama-3.1-8b-instant',      # Groq, FREE, FAST (VERIFIED 2026-07-03)
        ]

        # Complexity-based routing adjustments
        prefer_strong_model = False
        prefer_cheap_model = False
        force_thompson = False
        
        if complexity_info:
            category = complexity_info['complexity_category']
            confidence = complexity_info['predicted_confidence']
            
            # VERY_COMPLEX tasks → prefer Thompson Sampling (if available)
            if category == 'VERY_COMPLEX':
                force_thompson = True
                prefer_strong_model = True
            
            # Low confidence → prefer stronger models
            elif confidence < 0.5:
                prefer_strong_model = True
            
            # SIMPLE + high confidence → prefer cheaper models
            elif category == 'SIMPLE' and confidence > 0.8:
                prefer_cheap_model = True

        # Strategy 1: Thompson Sampling (forced for VERY_COMPLEX or available)
        if self.bandit and self.id_to_model and (force_thompson or not prefer_cheap_model):
            context = extract_context(task_description, workflow_name)
            model_idx, ucb_scores = self.bandit.select_model(context)

            if model_idx in self.id_to_model:
                model = self.id_to_model[model_idx]
                
                # Override with stronger model if needed
                if prefer_strong_model and model in ['gpt-4o-mini', 'haiku']:
                    # Upgrade to stronger model
                    strong_models = ['opus', 'sonnet', 'gpt-4o']
                    for strong in strong_models:
                        if any(strong in self.id_to_model.values()):
                            model = strong
                            print(f"🎯 Thompson Sampling selected (upgraded for complexity): {model}")
                            return model, 'thompson_sampling_upgraded'
                
                print(f"🎯 Thompson Sampling selected: {model}")
                return model, 'thompson_sampling'

        # Strategy 2: Simple task routing (query PostgreSQL for best API model)
        if prefer_cheap_model:
            # Query PostgreSQL for best models (any quality score)
            cur = self.db_conn.cursor()
            cur.execute("""
                SELECT model_id, general_qa, provider
                FROM learning.model_capabilities
                WHERE general_qa IS NOT NULL
                ORDER BY general_qa DESC
                LIMIT 5
            """)
            api_models = cur.fetchall()

            if api_models:
                # Try top models, but fallback to verified if none in verified list
                for model_id, quality, provider in api_models:
                    if model_id in VERIFIED_WORKING_MODELS:
                        print(f"💰 Best VERIFIED model from PostgreSQL: {model_id} (quality={quality:.3f}, provider={provider})")
                        return model_id, 'postgres_verified'

                # PostgreSQL model not verified, use first verified model
                print(f"⚠️  PostgreSQL best model not verified, using fallback")
                fallback = VERIFIED_WORKING_MODELS[0]
                print(f"💰 Using verified fallback: {fallback}")
                return fallback, 'verified_fallback'

            # No models in PostgreSQL, use verified fallback
            fallback = VERIFIED_WORKING_MODELS[0]
            print(f"💰 No models in PostgreSQL, using verified fallback: {fallback}")
            return fallback, 'verified_fallback'

        # Strategy 3: Fall back to Auto-Profiler (GA-based exploration)
        model, is_exploration = self.profiler.select_model_for_task(task_type)

        # SAFETY: If profiler returns a model not in verified list, override with verified
        if model not in VERIFIED_WORKING_MODELS:
            print(f"⚠️  Auto-Profiler selected unverified model '{model}', using verified fallback")
            model = VERIFIED_WORKING_MODELS[0]
            return model, 'verified_override'

        if is_exploration:
            print(f"🔍 GA Exploration selected: {model}")
            return model, 'ga_exploration'
        else:
            print(f"✓ Auto-Profiler selected: {model}")
            return model, 'auto_profiler'

    def orchestrate_task(self, task_description, workers=None, task_type='general_qa',
                        workflow_name='', max_tokens=4000, max_retries=2):
        """
        Orchestrate task with intelligent model selection + auto-retry on failure

        Args:
            task_description: The question/task to distribute
            workers: List of worker hostnames (default: all 8 workers)
            task_type: Task category for Auto-Profiler
            workflow_name: Workflow name for Thompson Sampling context
            max_tokens: Max tokens per response
            max_retries: Maximum retry attempts (default: 2)

        Returns:
            dict with results and metadata
        """
        if workers is None:
            # Query active workers from PostgreSQL fleet.workers
            cur = self.db_conn.cursor()
            cur.execute("""
                SELECT hostname
                FROM fleet.workers
                WHERE status = 'active'
                  AND last_heartbeat > NOW() - INTERVAL '5 minutes'
                ORDER BY hostname
            """)
            workers = [row[0] for row in cur.fetchall()]

            if not workers:
                # Fallback to hardcoded list if no workers registered
                print("⚠️  No active workers in fleet.workers, using fallback list")
                workers = [
                    "server-01", "server-02", "server-03",
                    "laptop-01", "pi-01", "pi-02",
                    "desktop-ap", "server-ap"
                ]
            else:
                print(f"✅ Found {len(workers)} active workers in fleet registry")

        # STEP 0: Enhance prompt using learned patterns (before model selection)
        original_task = task_description
        if self.prompt_enhancer:
            task_type_classified = self.prompt_enhancer.classify_task_type(task_description, workflow_name)
            task_description = self.prompt_enhancer.enhance_prompt(
                task_description,
                task_type=task_type_classified,
                workflow_name=workflow_name
            )
            if task_description != original_task:
                print(f"🎨 Enhanced prompt using patterns from {task_type_classified} tasks")
                print()

        print(f"\n{'='*60}")
        print(f"SMART ORCHESTRATOR")
        print(f"{'='*60}")
        print(f"Task: {task_description[:80]}...")
        print(f"Workers: {len(workers)}")
        print(f"Task Type: {task_type}")
        print()

        # STEP 1: Predict complexity BEFORE model selection
        complexity_start = time.time()
        complexity_info = self.predict_complexity(task_description)
        complexity_time = time.time() - complexity_start

        if complexity_info:
            print(f"🔮 Complexity Prediction ({complexity_time*1000:.0f}ms):")
            print(f"  Category:   {complexity_info['complexity_category']}")
            print(f"  Duration:   {complexity_info['predicted_duration_ms']:,} ms "
                  f"({complexity_info['predicted_duration_ms']/1000:.1f}s)")
            print(f"  Confidence: {complexity_info['predicted_confidence']:.2f}")
            print()

        # STEP 2: Select model using GA + Thompson Sampling + Complexity
        start_time = time.time()
        model, selection_method = self.select_model(
            task_description,
            task_type=task_type,
            workflow_name=workflow_name,
            complexity_info=complexity_info
        )

        if not model:
            print("❌ No model selected - falling back to gpt-4o-mini")
            model = "gpt-4o-mini"
            selection_method = 'fallback'

        print(f"Model: {model} (via {selection_method})")
        print(f"Selection time: {time.time() - start_time:.2f}s")
        print()

        # Create tasks (same task for all workers for consensus)
        tasks = [task_description] * len(workers)

        # Execute on fleet with retry logic
        print(f"Executing on {len(workers)} workers...")
        exec_start = time.time()
        retry_count = 0
        retry_history = []

        results = execute_on_fleet_parallel(
            workers=workers,
            model=model,
            tasks=tasks,
            max_tokens=max_tokens
        )

        exec_time = time.time() - exec_start

        # Calculate success rate
        successes = sum(1 for r in results if not r.get('error'))
        success_rate = successes / len(results) if results else 0

        # AUTO-RETRY on failure using error recovery classifier
        while retry_count < max_retries and success_rate < 0.5 and self.error_recovery:
            # Analyze first error for retry decision
            first_error = next((r for r in results if r.get('error')), None)
            if not first_error:
                break

            error_msg = first_error.get('error', 'unknown')

            # Predict if retryable
            recovery = self.error_recovery.predict_recovery(
                model=model,
                task_type=task_type,
                error_type=error_msg,
                duration_ms=int(exec_time * 1000)
            )

            if not recovery['is_retryable']:
                print(f"\n⚠️  Error not retryable (confidence: {recovery['retryable_confidence']:.2f})")
                break

            retry_count += 1
            print(f"\n🔄 RETRY {retry_count}/{max_retries}")
            print(f"  Retryable: {recovery['is_retryable']} (confidence: {recovery['retryable_confidence']:.2f})")

            # Use recommended retry model if available
            retry_model = model
            if recovery['best_retry_model']:
                retry_model = recovery['best_retry_model']
                print(f"  Switching model: {model} → {retry_model} "
                      f"(confidence: {recovery['retry_model_confidence']:.2f})")
                print(f"  Success probability: {recovery['retry_success_probability']:.2f}")
            else:
                print(f"  Retrying with same model: {model}")

            # Record retry attempt
            retry_history.append({
                'retry_number': retry_count,
                'original_model': model,
                'retry_model': retry_model,
                'error_type': error_msg,
                'retryable_confidence': recovery['retryable_confidence'],
                'retry_success_probability': recovery['retry_success_probability']
            })

            # Retry execution
            retry_start = time.time()
            results = execute_on_fleet_parallel(
                workers=workers,
                model=retry_model,
                tasks=tasks,
                max_tokens=max_tokens
            )
            retry_time = time.time() - retry_start
            exec_time += retry_time

            # Update model if retry succeeded
            model = retry_model

            # Recalculate success rate
            successes = sum(1 for r in results if not r.get('error'))
            success_rate = successes / len(results) if results else 0

            print(f"  Retry result: {successes}/{len(results)} ({success_rate*100:.1f}% success)")

            # Break if successful
            if success_rate >= 0.5:
                print(f"  ✅ Retry successful!")
                break

        print(f"\n{'='*60}")
        print(f"RESULTS")
        print(f"{'='*60}")
        print(f"Execution time: {exec_time:.2f}s")
        print(f"Success rate: {successes}/{len(results)} ({success_rate*100:.1f}%)")

        if retry_history:
            print(f"Retries: {len(retry_history)}")
            for retry in retry_history:
                print(f"  Retry {retry['retry_number']}: {retry['original_model']} → {retry['retry_model']} "
                      f"(success prob: {retry['retry_success_probability']:.2f})")

        # Compare predicted vs actual duration
        if complexity_info:
            predicted_ms = complexity_info['predicted_duration_ms']
            actual_ms = exec_time * 1000
            error_pct = abs(actual_ms - predicted_ms) / predicted_ms * 100
            print(f"Duration prediction: {predicted_ms:,}ms predicted vs {actual_ms:,.0f}ms actual "
                  f"({error_pct:.1f}% error)")
        print()

        # Record result if using GA exploration
        if selection_method == 'ga_exploration':
            avg_latency = exec_time * 1000 / len(workers)  # ms per worker
            self.profiler.record_result(model, task_type, success_rate, avg_latency)

        # Build return dict with complexity metadata
        result = {
            'model': model,
            'selection_method': selection_method,
            'workers': len(workers),
            'successes': successes,
            'failures': len(results) - successes,
            'success_rate': success_rate,
            'execution_time': exec_time,
            'results': results,
            'retry_count': retry_count,
            'retry_history': retry_history
        }

        # Add complexity metadata if available
        if complexity_info:
            result['complexity'] = {
                'category': complexity_info['complexity_category'],
                'predicted_duration_ms': complexity_info['predicted_duration_ms'],
                'predicted_confidence': complexity_info['predicted_confidence'],
                'actual_duration_ms': int(exec_time * 1000),
                'prediction_error_pct': abs(exec_time * 1000 - complexity_info['predicted_duration_ms'])
                                       / complexity_info['predicted_duration_ms'] * 100
            }

        return result

    def get_status(self):
        """Get orchestrator status"""
        print("\n" + "="*60)
        print("SMART ORCHESTRATOR STATUS")
        print("="*60)

        # Auto-Profiler status
        status = self.profiler.get_status()
        print(f"\n📊 Auto-Profiler (GA):")
        print(f"  Coverage: {status['profiled_models']}/{status['total_models']} ({status['coverage_pct']:.1f}%)")
        print(f"  Avg tests/model: {status['avg_tests_per_model']:.1f}")
        print(f"  By task type:")
        for task, count in status['by_task'].items():
            print(f"    {task}: {count} models")

        # Thompson Sampling status
        if self.bandit and self.id_to_model:
            print(f"\n🎯 Thompson Sampling:")
            print(f"  Models trained: {len(self.id_to_model)}")
            print(f"  Context dimensions: {self.bandit.context_dim}")
            print(f"  Exploration parameter (alpha): {self.bandit.alpha}")
        else:
            print(f"\n🎯 Thompson Sampling: Not loaded")

        # Complexity Estimator status
        if self.complexity_estimator:
            stats = self.complexity_estimator.training_stats
            print(f"\n🔮 Complexity Estimator:")
            print(f"  Duration R²: {stats['duration']['test_r2']:.4f}")
            print(f"  Confidence R²: {stats['confidence']['test_r2']:.4f}")
            print(f"  Training samples: {stats['n_train']}")
            print(f"  Top features (duration):")
            for feat, imp in list(stats['feature_importance']['duration'].items())[:3]:
                print(f"    {feat}: {imp:.4f}")
        else:
            print(f"\n🔮 Complexity Estimator: Not loaded")

        # Prompt Enhancer status
        if self.prompt_enhancer and self.prompt_enhancer.stats_by_type:
            print(f"\n🎨 Prompt Pattern Enhancer:")
            print(f"  Task types: {len(self.prompt_enhancer.stats_by_type)}")
            total_examples = sum(v.get('count', 0) for v in self.prompt_enhancer.stats_by_type.values())
            print(f"  Total examples: {total_examples}")
            print(f"  Top task types:")
            sorted_types = sorted(
                self.prompt_enhancer.stats_by_type.items(),
                key=lambda x: x[1].get('count', 0),
                reverse=True
            )[:5]
            for task_type, stats in sorted_types:
                print(f"    {task_type}: {stats.get('count', 0)} examples")
        else:
            print(f"\n🎨 Prompt Pattern Enhancer: Not loaded")

        # Error Recovery Classifier status
        if self.error_recovery and self.error_recovery.loaded:
            metrics = self.error_recovery.get_metrics()
            print(f"\n🔄 Error Recovery Classifier:")
            print(f"  Retryable accuracy: {metrics['retryable']['accuracy']:.1%}")
            print(f"  Retry model accuracy: {metrics['retry_model']['accuracy']:.1%}")
            print(f"  Retry success accuracy: {metrics['retry_success']['accuracy']:.1%}")
            print(f"  Training samples: {self.error_recovery.clf_dict.get('training_samples', 'N/A')}")
        else:
            print(f"\n🔄 Error Recovery Classifier: Not loaded")

        print()

    def close(self):
        """Cleanup"""
        self.profiler.close()


def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 orchestrate_smart.py '<task>' [task_type] [workflow_name]")
        print()
        print("Examples:")
        print("  orchestrate_smart.py 'Implement Java parser' code_generation")
        print("  orchestrate_smart.py 'Review security issues' code_review")
        print("  orchestrate_smart.py 'Research firmware methods' research")
        print()
        print("Options:")
        print("  --status : Show orchestrator status")
        sys.exit(1)

    if sys.argv[1] == '--status':
        orch = SmartOrchestrator(exploration_rate=0.15)
        orch.get_status()
        orch.close()
        return

    task = sys.argv[1]
    task_type = sys.argv[2] if len(sys.argv) > 2 else 'general_qa'
    workflow_name = sys.argv[3] if len(sys.argv) > 3 else ''

    # Create orchestrator
    orch = SmartOrchestrator(exploration_rate=0.15)

    # Run task
    result = orch.orchestrate_task(
        task_description=task,
        task_type=task_type,
        workflow_name=workflow_name
    )

    # Print individual results
    for i, r in enumerate(result['results']):
        worker = ["server-01", "server-02", "server-03", "laptop-01",
                  "pi-01", "pi-02", "desktop-ap", "server-ap"][i]

        if r.get('error'):
            print(f"❌ {worker}: {r['error']}")
        else:
            response = r.get('response', '')
            print(f"✓ {worker}: {response[:150]}...")

    print(f"\n{'='*60}")
    print(f"Model: {result['model']} (via {result['selection_method']})")
    print(f"Success: {result['successes']}/{result['workers']} workers")
    print(f"Time: {result['execution_time']:.2f}s")
    
    if 'complexity' in result:
        comp = result['complexity']
        print(f"Complexity: {comp['category']} "
              f"(predicted {comp['predicted_duration_ms']}ms, "
              f"actual {comp['actual_duration_ms']}ms, "
              f"error {comp['prediction_error_pct']:.1f}%)")
    
    print(f"{'='*60}\n")

    orch.close()


if __name__ == "__main__":
    main()