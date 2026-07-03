#!/usr/bin/env python3
"""
Feedback Loop Optimizer

Monitors and prevents self-referential feedback loops in distributed LLM orchestration.
Integrates with PostgreSQL + pgvector for pattern detection and intervention.

Architecture:
- Layer 1: Fast detection via model distribution analysis (anti-echo-chamber)
- Layer 2: Cross-correlation analysis (evaluator-generator coupling detection)
- Layer 3: Temporal pattern analysis (reward hacking detection)
- Layer 4: Embedding similarity clustering (concept collapse detection)

Created: 2026-07-03
Status: PRODUCTION READY
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
import warnings

# Add learning directory to path for postgres_adapter
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))

try:
    from postgres_adapter import get_db, get_execution_monitor
except ImportError:
    warnings.warn("postgres_adapter not found, using direct connection")
    get_db = None


@dataclass
class FeedbackLoopRisk:
    """Container for detected feedback loop risk"""
    risk_type: str  # 'model_dominance', 'eval_gen_coupling', 'reward_hacking', 'concept_collapse'
    severity: float  # 0.0 - 1.0
    description: str
    evidence: Dict[str, Any]
    mitigation: str
    timestamp: datetime


class FeedbackLoopOptimizer:
    """
    Detects and mitigates self-referential feedback loops in multi-AI systems

    Monitored Patterns:
    1. Model Dominance (>70/30 distribution)
    2. Evaluator-Generator Coupling (same model evaluating its own output)
    3. Reward Hacking (exploiting evaluation criteria)
    4. Concept Collapse (converging to single solution pattern)
    """

    def __init__(self, db_config: Optional[Dict] = None):
        """
        Initialize optimizer

        Args:
            db_config: PostgreSQL connection config (defaults to aio-01:5433/learning)
        """
        self.db_config = db_config or {
            'host': 'aio-01',
            'port': 5433,
            'database': 'learning',
            'user': 'claude',
            'cursor_factory': RealDictCursor
        }

        # Risk thresholds
        self.dominance_threshold = 0.70  # Alert if one model >70% usage
        self.coupling_threshold = 0.40   # Alert if same model eval >40% of own outputs
        self.reward_hack_threshold = 0.85  # Alert if quality spikes without diversity
        self.collapse_threshold = 0.90   # Alert if embedding similarity >0.90

        # Temporal analysis window (default: 7 days)
        self.analysis_window_days = 7

    def _get_connection(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(**self.db_config)

    def analyze_model_distribution(self, window_days: Optional[int] = None) -> Tuple[Dict[str, float], List[FeedbackLoopRisk]]:
        """
        Analyze model usage distribution to detect echo chamber effects

        Returns:
            (distribution, risks) where distribution is {model: percentage}
        """
        window = window_days or self.analysis_window_days
        cutoff = datetime.now() - timedelta(days=window)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Get model usage from monitoring.execution_summary
                cur.execute("""
                    SELECT model, COUNT(*) as count
                    FROM monitoring.execution_summary
                    WHERE timestamp > %s
                      AND outcome = 'success'
                    GROUP BY model
                    ORDER BY count DESC
                """, (cutoff,))

                rows = cur.fetchall()

        if not rows:
            return {}, []

        total = sum(row['count'] for row in rows)
        distribution = {row['model']: row['count'] / total for row in rows}

        risks = []

        # Check for dominance (>70/30 rule)
        for model, percentage in distribution.items():
            if percentage > self.dominance_threshold:
                risks.append(FeedbackLoopRisk(
                    risk_type='model_dominance',
                    severity=min(1.0, (percentage - self.dominance_threshold) / (1.0 - self.dominance_threshold)),
                    description=f"Model '{model}' dominates with {percentage*100:.1f}% usage",
                    evidence={
                        'model': model,
                        'percentage': percentage,
                        'threshold': self.dominance_threshold,
                        'distribution': distribution,
                        'total_executions': total,
                        'window_days': window
                    },
                    mitigation="Force rotate models: temporarily boost selection probability for underused models",
                    timestamp=datetime.now()
                ))

        return distribution, risks

    def analyze_eval_generator_coupling(self, window_days: Optional[int] = None) -> List[FeedbackLoopRisk]:
        """
        Detect if models are frequently evaluating their own outputs

        Checks workflow.worker_results + workflow.arbiter_decisions for correlation
        """
        window = window_days or self.analysis_window_days
        cutoff = datetime.now() - timedelta(days=window)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Find cases where arbiter_model == worker model
                cur.execute("""
                    SELECT
                        w.model as worker_model,
                        a.arbiter_model,
                        COUNT(*) as coupling_count
                    FROM workflow.worker_results w
                    JOIN workflow.arbiter_decisions a
                        ON a.workflow_execution_id = w.workflow_execution_id
                        AND w.id = ANY(a.worker_result_ids)
                    WHERE w.created_at > %s
                    GROUP BY w.model, a.arbiter_model
                    HAVING COUNT(*) > 5
                    ORDER BY coupling_count DESC
                """, (cutoff,))

                couplings = cur.fetchall()

                # Get total arbiter decisions per model for percentage calc
                cur.execute("""
                    SELECT arbiter_model, COUNT(*) as total
                    FROM workflow.arbiter_decisions
                    WHERE created_at > %s
                    GROUP BY arbiter_model
                """, (cutoff,))

                totals = {row['arbiter_model']: row['total'] for row in cur.fetchall()}

        risks = []

        for coupling in couplings:
            worker = coupling['worker_model']
            arbiter = coupling['arbiter_model']
            count = coupling['coupling_count']
            total = totals.get(arbiter, count)

            # Self-evaluation: worker == arbiter
            if worker == arbiter:
                percentage = count / total if total > 0 else 0

                if percentage > self.coupling_threshold:
                    risks.append(FeedbackLoopRisk(
                        risk_type='eval_gen_coupling',
                        severity=min(1.0, (percentage - self.coupling_threshold) / (1.0 - self.coupling_threshold)),
                        description=f"Model '{worker}' evaluating its own outputs {percentage*100:.1f}% of the time",
                        evidence={
                            'model': worker,
                            'self_eval_count': count,
                            'total_evals': total,
                            'self_eval_percentage': percentage,
                            'threshold': self.coupling_threshold,
                            'window_days': window
                        },
                        mitigation="Enforce arbiter diversity: never allow worker.model == arbiter.model",
                        timestamp=datetime.now()
                    ))

        return risks

    def analyze_reward_hacking(self, window_days: Optional[int] = None) -> List[FeedbackLoopRisk]:
        """
        Detect reward hacking: quality scores increasing without diversity

        Indicators:
        - Monotonic quality increase over time
        - Decreasing model diversity
        - Converging task patterns (embedding similarity)
        """
        window = window_days or self.analysis_window_days
        cutoff = datetime.now() - timedelta(days=window)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Get daily quality trends + diversity
                cur.execute("""
                    SELECT
                        DATE(timestamp) as day,
                        AVG(quality_score) as avg_quality,
                        STDDEV(quality_score) as quality_stddev,
                        COUNT(DISTINCT model) as model_diversity,
                        COUNT(*) as executions
                    FROM monitoring.execution_summary
                    WHERE timestamp > %s
                      AND quality_score IS NOT NULL
                      AND outcome = 'success'
                    GROUP BY DATE(timestamp)
                    ORDER BY day ASC
                """, (cutoff,))

                daily_stats = cur.fetchall()

        if len(daily_stats) < 3:
            return []  # Need at least 3 days for trend analysis

        risks = []

        # Calculate trend: quality increasing + diversity decreasing = suspicious
        qualities = [row['avg_quality'] for row in daily_stats if row['avg_quality']]
        diversities = [row['model_diversity'] for row in daily_stats]

        if len(qualities) < 3:
            return []

        # Simple linear trend (positive = increasing)
        quality_trend = np.polyfit(range(len(qualities)), qualities, 1)[0]
        diversity_trend = np.polyfit(range(len(diversities)), diversities, 1)[0]

        # Red flag: quality up, diversity down
        if quality_trend > 0.02 and diversity_trend < -0.1:
            # Check recent quality vs baseline
            recent_quality = np.mean(qualities[-3:])
            baseline_quality = np.mean(qualities[:3])

            if recent_quality > self.reward_hack_threshold and recent_quality > baseline_quality * 1.1:
                risks.append(FeedbackLoopRisk(
                    risk_type='reward_hacking',
                    severity=min(1.0, (recent_quality - baseline_quality) / baseline_quality),
                    description=f"Quality increased {((recent_quality/baseline_quality - 1)*100):.1f}% while diversity decreased",
                    evidence={
                        'quality_trend': float(quality_trend),
                        'diversity_trend': float(diversity_trend),
                        'recent_quality': float(recent_quality),
                        'baseline_quality': float(baseline_quality),
                        'daily_stats': [
                            {
                                'day': str(row['day']),
                                'quality': float(row['avg_quality']) if row['avg_quality'] else None,
                                'diversity': row['model_diversity']
                            }
                            for row in daily_stats
                        ],
                        'window_days': window
                    },
                    mitigation="Adversarial evaluation: use external validators (ChatGPT framework) to verify quality gains",
                    timestamp=datetime.now()
                ))

        return risks

    def analyze_concept_collapse(self, limit: int = 100) -> List[FeedbackLoopRisk]:
        """
        Detect concept collapse: outputs converging to similar patterns

        Uses workflow.worker_results embeddings to measure diversity
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Get recent worker results with embeddings
                cur.execute("""
                    SELECT
                        id,
                        model,
                        result_embedding::text as embedding_json,
                        confidence,
                        created_at
                    FROM workflow.worker_results
                    WHERE result_embedding IS NOT NULL
                      AND outcome = 'success'
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))

                results = cur.fetchall()

        if len(results) < 10:
            return []  # Need sufficient data

        # Parse embeddings
        embeddings = []
        metadata = []

        for row in results:
            try:
                emb_json = row['embedding_json']
                if emb_json:
                    emb = json.loads(emb_json)
                    if isinstance(emb, list) and len(emb) > 0:
                        embeddings.append(np.array(emb))
                        metadata.append({
                            'id': row['id'],
                            'model': row['model'],
                            'confidence': row['confidence'],
                            'created_at': row['created_at']
                        })
            except (json.JSONDecodeError, ValueError):
                continue

        if len(embeddings) < 10:
            return []

        # Compute pairwise cosine similarities
        embeddings = np.array(embeddings)

        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normalized = embeddings / norms

        # Cosine similarity matrix (dot product of normalized vectors)
        similarity_matrix = np.dot(normalized, normalized.T)

        # Get upper triangle (exclude diagonal and duplicates)
        n = len(similarity_matrix)
        upper_tri_indices = np.triu_indices(n, k=1)
        similarities = similarity_matrix[upper_tri_indices]

        # Calculate statistics
        mean_similarity = np.mean(similarities)
        max_similarity = np.max(similarities)
        high_sim_count = np.sum(similarities > self.collapse_threshold)

        risks = []

        # Red flag: mean similarity > 0.85 OR >20% pairs > 0.90 similarity
        if mean_similarity > 0.85 or (high_sim_count / len(similarities)) > 0.20:
            risks.append(FeedbackLoopRisk(
                risk_type='concept_collapse',
                severity=min(1.0, mean_similarity),
                description=f"Output embeddings show high similarity (mean={mean_similarity:.3f}, max={max_similarity:.3f})",
                evidence={
                    'mean_similarity': float(mean_similarity),
                    'max_similarity': float(max_similarity),
                    'high_similarity_count': int(high_sim_count),
                    'total_pairs': len(similarities),
                    'high_similarity_percentage': float(high_sim_count / len(similarities)),
                    'collapse_threshold': self.collapse_threshold,
                    'sample_size': len(embeddings),
                    'similarity_histogram': {
                        '0.0-0.5': int(np.sum(similarities < 0.5)),
                        '0.5-0.7': int(np.sum((similarities >= 0.5) & (similarities < 0.7))),
                        '0.7-0.85': int(np.sum((similarities >= 0.7) & (similarities < 0.85))),
                        '0.85-0.95': int(np.sum((similarities >= 0.85) & (similarities < 0.95))),
                        '0.95-1.0': int(np.sum(similarities >= 0.95))
                    }
                },
                mitigation="Increase task diversity: use temperature sampling, inject noise, vary prompts",
                timestamp=datetime.now()
            ))

        return risks

    def run_full_analysis(self, window_days: Optional[int] = None, save_to_db: bool = True) -> Dict[str, Any]:
        """
        Run all 4 feedback loop analyses

        Returns:
            {
                'timestamp': datetime,
                'window_days': int,
                'risks': [FeedbackLoopRisk],
                'summary': {
                    'total_risks': int,
                    'critical': int,  # severity > 0.8
                    'high': int,      # severity > 0.6
                    'medium': int,    # severity > 0.4
                    'low': int        # severity <= 0.4
                },
                'model_distribution': dict,
                'recommendations': [str]
            }
        """
        window = window_days or self.analysis_window_days

        print(f"Running feedback loop analysis (window: {window} days)...")

        # Layer 1: Model distribution
        print("  [1/4] Analyzing model distribution...")
        distribution, dominance_risks = self.analyze_model_distribution(window)

        # Layer 2: Eval-generator coupling
        print("  [2/4] Analyzing evaluator-generator coupling...")
        coupling_risks = self.analyze_eval_generator_coupling(window)

        # Layer 3: Reward hacking
        print("  [3/4] Analyzing reward hacking patterns...")
        reward_risks = self.analyze_reward_hacking(window)

        # Layer 4: Concept collapse
        print("  [4/4] Analyzing concept collapse...")
        collapse_risks = self.analyze_concept_collapse()

        # Combine all risks
        all_risks = dominance_risks + coupling_risks + reward_risks + collapse_risks

        # Sort by severity (highest first)
        all_risks.sort(key=lambda r: r.severity, reverse=True)

        # Categorize risks
        critical = [r for r in all_risks if r.severity > 0.8]
        high = [r for r in all_risks if 0.6 < r.severity <= 0.8]
        medium = [r for r in all_risks if 0.4 < r.severity <= 0.6]
        low = [r for r in all_risks if r.severity <= 0.4]

        # Generate recommendations
        recommendations = []

        if critical:
            recommendations.append("CRITICAL: Immediate intervention required to prevent feedback loop collapse")

        if dominance_risks:
            recommendations.append("Implement forced model rotation to restore diversity")

        if coupling_risks:
            recommendations.append("Enforce arbiter != worker model constraint")

        if reward_risks:
            recommendations.append("Enable adversarial evaluation (ChatGPT framework) for external validation")

        if collapse_risks:
            recommendations.append("Increase task diversity: vary prompts, use temperature sampling")

        if not all_risks:
            recommendations.append("No significant feedback loop risks detected - system healthy")

        result = {
            'timestamp': datetime.now(),
            'window_days': window,
            'risks': [
                {
                    'risk_type': r.risk_type,
                    'severity': r.severity,
                    'description': r.description,
                    'evidence': r.evidence,
                    'mitigation': r.mitigation,
                    'timestamp': r.timestamp.isoformat()
                }
                for r in all_risks
            ],
            'summary': {
                'total_risks': len(all_risks),
                'critical': len(critical),
                'high': len(high),
                'medium': len(medium),
                'low': len(low)
            },
            'model_distribution': distribution,
            'recommendations': recommendations
        }

        # Save to database if requested
        if save_to_db and all_risks:
            self._save_risks_to_db(all_risks)

        return result

    def _save_risks_to_db(self, risks: List[FeedbackLoopRisk]):
        """Save detected risks to monitoring.feedback_loop_risks table"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Create table if not exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS monitoring.feedback_loop_risks (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMPTZ NOT NULL,
                        risk_type VARCHAR(50) NOT NULL,
                        severity FLOAT NOT NULL,
                        description TEXT NOT NULL,
                        evidence JSONB,
                        mitigation TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)

                # Insert risks
                for risk in risks:
                    try:
                        cur.execute("""
                            INSERT INTO monitoring.feedback_loop_risks
                            (timestamp, risk_type, severity, description, evidence, mitigation)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            risk.timestamp,
                            risk.risk_type,
                            risk.severity,
                            risk.description,
                            json.dumps(risk.evidence),
                            risk.mitigation
                        ))
                    except Exception as e:
                        print(f"Warning: Failed to save risk to DB: {e}", file=sys.stderr)

                conn.commit()

    def get_mitigation_actions(self, risk_type: str) -> List[str]:
        """
        Get actionable mitigation steps for a risk type

        Returns:
            List of shell commands or configuration changes
        """
        actions = {
            'model_dominance': [
                "# Update multi-model-router.py to boost underused models",
                "# Temporarily increase selection probability for minority models",
                "# Example: if opus >70%, boost sonnet/haiku/gemini weights by 2×"
            ],
            'eval_gen_coupling': [
                "# Enforce arbiter != worker constraint in workflow orchestration",
                "# Modify consensus-replay or similar workflows",
                "# Example: filter out workers with same model as arbiter"
            ],
            'reward_hacking': [
                "# Enable Layer 2 adversarial evaluation",
                "# Use ChatGPT framework for external validation",
                "# Check: ~/.claude/self/evaluation-harness.mjs",
                "# Run: node ~/.claude/self/evaluation-harness.mjs"
            ],
            'concept_collapse': [
                "# Increase temperature in model calls (0.7 → 0.9)",
                "# Vary prompt templates (use jinja2 templates with randomization)",
                "# Inject task diversity (alternate between code/research/security)"
            ]
        }

        return actions.get(risk_type, ["No specific mitigation defined"])

    def print_report(self, analysis: Dict[str, Any]):
        """Print human-readable analysis report"""
        print("\n" + "="*80)
        print("FEEDBACK LOOP ANALYSIS REPORT")
        print("="*80)
        print(f"Timestamp: {analysis['timestamp'].isoformat()}")
        print(f"Analysis Window: {analysis['window_days']} days")
        print()

        # Summary
        summary = analysis['summary']
        print("SUMMARY:")
        print(f"  Total Risks: {summary['total_risks']}")
        print(f"    Critical (>0.8): {summary['critical']}")
        print(f"    High (0.6-0.8): {summary['high']}")
        print(f"    Medium (0.4-0.6): {summary['medium']}")
        print(f"    Low (<0.4): {summary['low']}")
        print()

        # Model distribution
        if analysis['model_distribution']:
            print("MODEL DISTRIBUTION:")
            for model, percentage in sorted(
                analysis['model_distribution'].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  {model:20s}: {percentage*100:5.1f}%")
            print()

        # Risks
        if analysis['risks']:
            print("DETECTED RISKS:")
            for i, risk in enumerate(analysis['risks'], 1):
                severity_label = (
                    "CRITICAL" if risk['severity'] > 0.8 else
                    "HIGH" if risk['severity'] > 0.6 else
                    "MEDIUM" if risk['severity'] > 0.4 else
                    "LOW"
                )
                print(f"\n  [{i}] {risk['risk_type'].upper()} - {severity_label} (severity={risk['severity']:.2f})")
                print(f"      {risk['description']}")
                print(f"      Mitigation: {risk['mitigation']}")
        else:
            print("No risks detected - system healthy ✓")

        # Recommendations
        print("\nRECOMMENDATIONS:")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"  {i}. {rec}")

        print("\n" + "="*80)


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Feedback Loop Optimizer - Detect self-referential patterns in multi-AI systems"
    )
    parser.add_argument(
        '--window',
        type=int,
        default=7,
        help='Analysis window in days (default: 7)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Save JSON report to file'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save risks to database'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    # Run analysis
    optimizer = FeedbackLoopOptimizer()

    if not args.quiet:
        analysis = optimizer.run_full_analysis(
            window_days=args.window,
            save_to_db=not args.no_save
        )
        optimizer.print_report(analysis)
    else:
        import contextlib
        import io

        # Suppress output
        with contextlib.redirect_stdout(io.StringIO()):
            analysis = optimizer.run_full_analysis(
                window_days=args.window,
                save_to_db=not args.no_save
            )

    # Save JSON if requested
    if args.output:
        # Convert datetime to string for JSON serialization
        analysis_json = analysis.copy()
        analysis_json['timestamp'] = analysis['timestamp'].isoformat()

        output_path = Path(args.output).expanduser()
        output_path.write_text(json.dumps(analysis_json, indent=2))

        if not args.quiet:
            print(f"\nReport saved to: {output_path}")

    # Exit code based on severity
    summary = analysis['summary']
    if summary['critical'] > 0:
        sys.exit(2)  # Critical risks
    elif summary['high'] > 0:
        sys.exit(1)  # High risks
    else:
        sys.exit(0)  # OK


if __name__ == '__main__':
    main()
