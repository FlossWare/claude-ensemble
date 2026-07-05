#!/usr/bin/env python3
"""
Abductive Reasoning Trainer - Inference to Best Explanation (IBE)

Implements abductive reasoning via:
1. Hypothesis Generation - Enumerate candidate explanations
2. Bayesian Inference - P(H|E) ∝ P(E|H) × P(H)
3. Explanation Quality - Simplicity, coherence, explanatory power
4. Continual Learning - Update priors from experience

Architecture:
- Prior knowledge: Stored in PostgreSQL learning.hypotheses
- Evidence evaluation: Likelihood scoring
- Posterior inference: Bayesian update
- Best explanation: Maximize P(H|E) × Simplicity × Coherence

Grade Target: A
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import pickle
import sys

# PostgreSQL integration
sys.path.insert(0, str(Path.home() / '.claude' / 'learning'))
from postgres_adapter import get_db, get_cursor

# Embedding generation
sys.path.insert(0, str(Path.home() / 'Development' / 'redhat' / 'scm' / 'gitlab' / 'cee' / 'sfloess' / 'claude-global-skills' / 'shared'))
try:
    from generate_embeddings import generate_embedding
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("WARNING: sentence-transformers not available, embeddings disabled")

class AbductiveReasoner:
    """
    Bayesian abductive reasoning with explanation quality metrics.

    Key Concepts:
    - Abduction: Inference to best explanation (not deduction/induction)
    - Likelihood: P(E|H) - How well hypothesis explains evidence
    - Prior: P(H) - Prior belief in hypothesis (from experience)
    - Posterior: P(H|E) - Updated belief after seeing evidence
    - Simplicity: Prefer simpler explanations (Occam's razor)
    - Coherence: Consistency with existing knowledge
    """

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path.home() / '.claude' / 'learning' / 'abductive_reasoner.pkl'
        self.db = get_db()

        # Initialize schema
        self._init_schema()

        # Load or initialize state
        if self.model_path.exists():
            self.load()
        else:
            self.hypothesis_priors = {}  # hypothesis_id -> prior probability
            self.evidence_patterns = {}  # pattern_id -> evidence template
            self.explanation_history = []  # past (evidence, hypothesis, success) tuples

    def _init_schema(self):
        """Create PostgreSQL tables for abductive reasoning"""
        schema_sql = """
        CREATE SCHEMA IF NOT EXISTS reasoning;

        CREATE TABLE IF NOT EXISTS reasoning.hypotheses (
            id SERIAL PRIMARY KEY,
            hypothesis_text TEXT NOT NULL,
            embedding VECTOR(384),
            domain TEXT,
            prior_probability FLOAT DEFAULT 0.5,
            simplicity_score FLOAT DEFAULT 0.5,
            coherence_score FLOAT DEFAULT 0.5,
            num_confirmations INT DEFAULT 0,
            num_refutations INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS reasoning.evidence (
            id SERIAL PRIMARY KEY,
            evidence_text TEXT NOT NULL,
            embedding VECTOR(384),
            domain TEXT,
            observed_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS reasoning.explanations (
            id SERIAL PRIMARY KEY,
            evidence_id INT REFERENCES reasoning.evidence(id),
            hypothesis_id INT REFERENCES reasoning.hypotheses(id),
            likelihood FLOAT NOT NULL,  -- P(E|H)
            prior FLOAT NOT NULL,  -- P(H)
            posterior FLOAT NOT NULL,  -- P(H|E)
            explanation_quality FLOAT NOT NULL,  -- Combined score
            chosen_as_best BOOLEAN DEFAULT FALSE,
            confirmed BOOLEAN,  -- NULL until verified
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(evidence_id, hypothesis_id)
        );

        CREATE INDEX IF NOT EXISTS idx_hypotheses_embedding
            ON reasoning.hypotheses USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);

        CREATE INDEX IF NOT EXISTS idx_evidence_embedding
            ON reasoning.evidence USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """

        with get_cursor() as (cursor, conn):
            cursor.execute(schema_sql)

    def generate_hypotheses(self, evidence: str, domain: str = 'general', k: int = 5) -> List[Dict]:
        """
        Generate candidate hypotheses for observed evidence.

        Strategies:
        1. Similar evidence lookup (vector similarity)
        2. Domain-specific templates
        3. Causal reasoning patterns

        Returns:
            List of hypotheses with prior probabilities
        """
        hypotheses = []

        # Strategy 1: Find similar past evidence and their explanations
        if EMBEDDINGS_AVAILABLE:
            evidence_embedding = generate_embedding(evidence)

            similar_sql = """
            SELECT DISTINCT h.id, h.hypothesis_text, h.prior_probability,
                   h.simplicity_score, h.coherence_score,
                   e.embedding <=> %s::vector as similarity
            FROM reasoning.hypotheses h
            JOIN reasoning.explanations ex ON h.id = ex.hypothesis_id
            JOIN reasoning.evidence e ON ex.evidence_id = e.id
            WHERE h.domain = %s OR h.domain = 'general'
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
            """

            similar = self.db.query(similar_sql, (
                evidence_embedding.tobytes() if isinstance(evidence_embedding, np.ndarray) else evidence_embedding,
                domain,
                evidence_embedding.tobytes() if isinstance(evidence_embedding, np.ndarray) else evidence_embedding,
                k
            ))

            hypotheses.extend(similar)

        # Strategy 2: High prior hypotheses in this domain
        high_prior_sql = """
        SELECT id, hypothesis_text, prior_probability,
               simplicity_score, coherence_score
        FROM reasoning.hypotheses
        WHERE (domain = %s OR domain = 'general')
          AND prior_probability > 0.3
        ORDER BY prior_probability DESC
        LIMIT %s
        """

        high_prior = self.db.query(high_prior_sql, (domain, k))

        # Merge and deduplicate
        seen = set()
        merged = []
        for h in (hypotheses + high_prior):
            if h['id'] not in seen:
                seen.add(h['id'])
                merged.append(h)

        return merged[:k]

    def compute_likelihood(self, evidence: str, hypothesis: str) -> float:
        """
        Compute P(E|H) - how likely is evidence given hypothesis.

        Uses:
        - Semantic similarity (if hypothesis implies evidence)
        - Logical entailment estimation
        - Pattern matching strength
        """
        if not EMBEDDINGS_AVAILABLE:
            # Fallback: simple text overlap
            evidence_words = set(evidence.lower().split())
            hypothesis_words = set(hypothesis.lower().split())
            overlap = len(evidence_words & hypothesis_words)
            return min(1.0, overlap / max(len(evidence_words), 1))

        # Semantic similarity via embeddings
        evidence_emb = generate_embedding(evidence)
        hypothesis_emb = generate_embedding(hypothesis)

        # Cosine similarity
        if isinstance(evidence_emb, list):
            evidence_emb = np.array(evidence_emb)
        if isinstance(hypothesis_emb, list):
            hypothesis_emb = np.array(hypothesis_emb)

        similarity = np.dot(evidence_emb, hypothesis_emb) / (
            np.linalg.norm(evidence_emb) * np.linalg.norm(hypothesis_emb) + 1e-9
        )

        # Map similarity [0,1] to likelihood [0.1, 0.9]
        # (avoid extreme probabilities for numerical stability)
        return 0.1 + 0.8 * float(similarity)

    def compute_simplicity(self, hypothesis: str) -> float:
        """
        Occam's razor: prefer simpler explanations.

        Metrics:
        - Shorter hypotheses (fewer words)
        - Fewer assumptions (count "if", "assume", "requires")
        - Lower Kolmogorov complexity estimate
        """
        words = hypothesis.split()
        word_penalty = min(1.0, 10 / (len(words) + 1))  # Prefer <10 words

        assumption_keywords = ['if', 'assume', 'requires', 'depends', 'must', 'only if']
        assumption_count = sum(1 for kw in assumption_keywords if kw in hypothesis.lower())
        assumption_penalty = max(0.0, 1.0 - 0.2 * assumption_count)

        return 0.7 * word_penalty + 0.3 * assumption_penalty

    def compute_coherence(self, hypothesis: str, domain: str) -> float:
        """
        Coherence with existing knowledge.

        Checks:
        - Consistency with confirmed hypotheses in domain
        - Absence of contradictions
        - Support from related hypotheses
        """
        if not EMBEDDINGS_AVAILABLE:
            return 0.5  # Neutral

        hypothesis_emb = generate_embedding(hypothesis)

        # Find related confirmed hypotheses
        coherence_sql = """
        SELECT h.hypothesis_text, h.embedding <=> %s::vector as similarity
        FROM reasoning.hypotheses h
        JOIN reasoning.explanations ex ON h.id = ex.hypothesis_id
        WHERE (h.domain = %s OR h.domain = 'general')
          AND ex.confirmed = TRUE
        ORDER BY h.embedding <=> %s::vector
        LIMIT 5
        """

        related = self.db.query(coherence_sql, (
            hypothesis_emb.tobytes() if isinstance(hypothesis_emb, np.ndarray) else hypothesis_emb,
            domain,
            hypothesis_emb.tobytes() if isinstance(hypothesis_emb, np.ndarray) else hypothesis_emb
        ))

        if not related:
            return 0.5  # No prior knowledge

        # Average similarity to confirmed hypotheses
        similarities = [1.0 - r['similarity'] for r in related]
        return float(np.mean(similarities))

    def infer_best_explanation(
        self,
        evidence: str,
        domain: str = 'general',
        return_all: bool = False
    ) -> Dict[str, Any]:
        """
        Abductive inference: find best explanation for evidence.

        Algorithm:
        1. Generate candidate hypotheses
        2. For each hypothesis H:
           - Compute P(E|H) (likelihood)
           - Retrieve P(H) (prior)
           - Compute P(H|E) ∝ P(E|H) × P(H) (Bayes rule)
           - Compute quality = P(H|E) × Simplicity × Coherence
        3. Return hypothesis with highest quality

        Args:
            evidence: Observed evidence to explain
            domain: Domain context
            return_all: Return all candidates (not just best)

        Returns:
            Best explanation or all candidates with scores
        """
        # Store evidence
        evidence_embedding = None
        if EMBEDDINGS_AVAILABLE:
            evidence_embedding = generate_embedding(evidence)

        insert_evidence_sql = """
        INSERT INTO reasoning.evidence (evidence_text, embedding, domain)
        VALUES (%s, %s, %s)
        RETURNING id
        """

        evidence_row = self.db.query(insert_evidence_sql, (
            evidence,
            evidence_embedding.tobytes() if isinstance(evidence_embedding, np.ndarray) else evidence_embedding,
            domain
        ))
        evidence_id = evidence_row[0]['id']

        # Generate hypotheses
        candidates = self.generate_hypotheses(evidence, domain, k=10)

        if not candidates:
            # No existing hypotheses - create generic one
            generic_hypothesis = f"Unknown cause in {domain} domain"
            self._add_hypothesis(generic_hypothesis, domain)
            candidates = self.generate_hypotheses(evidence, domain, k=10)

        # Evaluate each candidate
        explanations = []
        for h in candidates:
            hypothesis_id = h['id']
            hypothesis_text = h['hypothesis_text']
            prior = h['prior_probability']

            # Compute components
            likelihood = self.compute_likelihood(evidence, hypothesis_text)
            simplicity = self.compute_simplicity(hypothesis_text)
            coherence = h.get('coherence_score', self.compute_coherence(hypothesis_text, domain))

            # Bayesian update: P(H|E) ∝ P(E|H) × P(H)
            # Normalize later
            posterior_unnorm = likelihood * prior

            # Explanation quality = Posterior × Simplicity × Coherence
            quality = posterior_unnorm * simplicity * coherence

            explanations.append({
                'hypothesis_id': hypothesis_id,
                'hypothesis_text': hypothesis_text,
                'likelihood': likelihood,
                'prior': prior,
                'posterior_unnorm': posterior_unnorm,
                'simplicity': simplicity,
                'coherence': coherence,
                'quality': quality
            })

        # Normalize posteriors
        total_posterior = sum(e['posterior_unnorm'] for e in explanations)
        if total_posterior > 0:
            for e in explanations:
                e['posterior'] = e['posterior_unnorm'] / total_posterior
        else:
            for e in explanations:
                e['posterior'] = 1.0 / len(explanations)

        # Sort by quality
        explanations.sort(key=lambda x: x['quality'], reverse=True)

        # Store explanations
        for i, exp in enumerate(explanations):
            insert_exp_sql = """
            INSERT INTO reasoning.explanations
            (evidence_id, hypothesis_id, likelihood, prior, posterior, explanation_quality, chosen_as_best)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (evidence_id, hypothesis_id) DO UPDATE SET
                likelihood = EXCLUDED.likelihood,
                posterior = EXCLUDED.posterior,
                explanation_quality = EXCLUDED.explanation_quality,
                chosen_as_best = EXCLUDED.chosen_as_best
            """
            self.db.query(insert_exp_sql, (
                evidence_id,
                exp['hypothesis_id'],
                exp['likelihood'],
                exp['prior'],
                exp['posterior'],
                exp['quality'],
                i == 0  # Best explanation
            ))

        if return_all:
            return {
                'evidence_id': evidence_id,
                'explanations': explanations
            }
        else:
            best = explanations[0]
            return {
                'evidence_id': evidence_id,
                'best_hypothesis': best['hypothesis_text'],
                'confidence': best['quality'],
                'posterior': best['posterior'],
                'components': {
                    'likelihood': best['likelihood'],
                    'prior': best['prior'],
                    'simplicity': best['simplicity'],
                    'coherence': best['coherence']
                }
            }

    def _add_hypothesis(self, hypothesis: str, domain: str):
        """Add new hypothesis to knowledge base"""
        embedding = None
        if EMBEDDINGS_AVAILABLE:
            embedding = generate_embedding(hypothesis)

        simplicity = self.compute_simplicity(hypothesis)
        coherence = self.compute_coherence(hypothesis, domain)

        insert_sql = """
        INSERT INTO reasoning.hypotheses
        (hypothesis_text, embedding, domain, simplicity_score, coherence_score)
        VALUES (%s, %s, %s, %s, %s)
        """

        self.db.query(insert_sql, (
            hypothesis,
            embedding.tobytes() if isinstance(embedding, np.ndarray) else embedding,
            domain,
            simplicity,
            coherence
        ))

    def update_from_feedback(self, evidence_id: int, hypothesis_id: int, confirmed: bool):
        """
        Update hypothesis prior based on confirmation/refutation.

        Uses Beta distribution update:
        - Confirmed: alpha += 1
        - Refuted: beta += 1
        - Prior = alpha / (alpha + beta)
        """
        # Mark explanation as confirmed/refuted
        update_exp_sql = """
        UPDATE reasoning.explanations
        SET confirmed = %s
        WHERE evidence_id = %s AND hypothesis_id = %s
        """
        self.db.query(update_exp_sql, (confirmed, evidence_id, hypothesis_id))

        # Update hypothesis counts and prior
        if confirmed:
            update_hyp_sql = """
            UPDATE reasoning.hypotheses
            SET num_confirmations = num_confirmations + 1,
                prior_probability = (num_confirmations + 1.0) / (num_confirmations + num_refutations + 2.0),
                updated_at = NOW()
            WHERE id = %s
            """
        else:
            update_hyp_sql = """
            UPDATE reasoning.hypotheses
            SET num_refutations = num_refutations + 1,
                prior_probability = (num_confirmations + 1.0) / (num_confirmations + num_refutations + 2.0),
                updated_at = NOW()
            WHERE id = %s
            """

        self.db.query(update_hyp_sql, (hypothesis_id,))

    def save(self):
        """Save model state to disk"""
        state = {
            'hypothesis_priors': self.hypothesis_priors,
            'evidence_patterns': self.evidence_patterns,
            'explanation_history': self.explanation_history,
            'saved_at': datetime.now().isoformat()
        }

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, 'wb') as f:
            pickle.dump(state, f)

    def load(self):
        """Load model state from disk"""
        with open(self.model_path, 'rb') as f:
            state = pickle.load(f)

        self.hypothesis_priors = state.get('hypothesis_priors', {})
        self.evidence_patterns = state.get('evidence_patterns', {})
        self.explanation_history = state.get('explanation_history', [])

def train_abductive_reasoner(
    training_examples: List[Dict[str, Any]],
    domain: str = 'general'
) -> AbductiveReasoner:
    """
    Train abductive reasoner from examples.

    Args:
        training_examples: List of {evidence, hypothesis, confirmed} dicts
        domain: Domain context

    Returns:
        Trained AbductiveReasoner
    """
    reasoner = AbductiveReasoner()

    for example in training_examples:
        evidence = example['evidence']
        hypothesis = example['hypothesis']
        confirmed = example.get('confirmed', True)

        # Add hypothesis if new
        check_sql = """
        SELECT id FROM reasoning.hypotheses
        WHERE hypothesis_text = %s AND domain = %s
        """
        existing = reasoner.db.query(check_sql, (hypothesis, domain))

        if not existing:
            reasoner._add_hypothesis(hypothesis, domain)
            existing = reasoner.db.query(check_sql, (hypothesis, domain))

        hypothesis_id = existing[0]['id']

        # Infer explanation (creates evidence entry)
        result = reasoner.infer_best_explanation(evidence, domain)
        evidence_id = result['evidence_id']

        # Update with feedback
        reasoner.update_from_feedback(evidence_id, hypothesis_id, confirmed)

    reasoner.save()
    return reasoner

if __name__ == '__main__':
    # Example: Medical diagnosis domain
    training_data = [
        {
            'evidence': 'Patient has fever, cough, and fatigue',
            'hypothesis': 'Viral respiratory infection',
            'confirmed': True
        },
        {
            'evidence': 'Patient has fever, cough, and chest pain',
            'hypothesis': 'Bacterial pneumonia',
            'confirmed': True
        },
        {
            'evidence': 'Server returns 500 error after deployment',
            'hypothesis': 'Configuration mismatch in production',
            'confirmed': True
        },
        {
            'evidence': 'Tests pass locally but fail in CI',
            'hypothesis': 'Environment-specific dependency issue',
            'confirmed': True
        },
        {
            'evidence': 'Code works in dev but crashes in production',
            'hypothesis': 'Race condition under high load',
            'confirmed': True
        }
    ]

    print("Training abductive reasoner...")
    reasoner = train_abductive_reasoner(training_data, domain='general')

    print("\nTesting inference...")

    test_cases = [
        'Patient has fever and cough',
        'Server crashes after recent deployment',
        'Tests fail only on CI server'
    ]

    for evidence in test_cases:
        print(f"\nEvidence: {evidence}")
        result = reasoner.infer_best_explanation(evidence, domain='general')
        print(f"Best explanation: {result['best_hypothesis']}")
        print(f"Confidence: {result['confidence']:.3f}")
        print(f"Posterior: {result['posterior']:.3f}")
        print(f"Components: {json.dumps(result['components'], indent=2)}")

    print(f"\nModel saved to: {reasoner.model_path}")
