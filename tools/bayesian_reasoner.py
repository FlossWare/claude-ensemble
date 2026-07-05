#!/usr/bin/env python3
"""
Bayesian Reasoning System with Uncertainty Quantification

Implements probabilistic reasoning through:
- Bayesian inference (prior → likelihood → posterior)
- Uncertainty propagation
- Belief updating
- Hypothesis testing with credible intervals
- Multi-hypothesis comparison
- Evidence accumulation
"""

import numpy as np
import pickle
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from scipy import stats
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')


@dataclass
class BayesianHypothesis:
    """A hypothesis with prior, likelihood, and posterior beliefs."""
    name: str
    prior: float  # P(H)
    likelihood: float  # P(E|H)
    posterior: float  # P(H|E)
    evidence_count: int
    confidence_interval: Tuple[float, float]
    uncertainty: float  # entropy or variance


@dataclass
class Evidence:
    """A piece of evidence with associated uncertainty."""
    description: str
    observation: Any
    likelihood_given_h1: float  # P(E|H1)
    likelihood_given_h0: float  # P(E|H0)
    reliability: float  # [0,1] how reliable is this evidence
    timestamp: str


class BayesianReasoner:
    """
    Bayesian inference engine for probabilistic reasoning under uncertainty.

    Features:
    - Prior belief specification
    - Likelihood computation from evidence
    - Posterior updating via Bayes' rule
    - Multi-hypothesis comparison
    - Uncertainty quantification (credible intervals, entropy)
    - Evidence accumulation over time
    """

    def __init__(self, base_prior: float = 0.5):
        """
        Initialize Bayesian reasoner.

        Args:
            base_prior: Default prior probability for new hypotheses
        """
        self.base_prior = base_prior
        self.hypotheses: Dict[str, BayesianHypothesis] = {}
        self.evidence_history: List[Evidence] = []
        self.belief_history: List[Dict[str, float]] = []

        # Beta distribution parameters for modeling uncertainty
        self.alpha_beta: Dict[str, Tuple[float, float]] = {}

        # Performance tracking
        self.stats = {
            'total_updates': 0,
            'evidence_count': 0,
            'hypothesis_count': 0,
            'avg_uncertainty': 0.0,
            'calibration_score': 0.0
        }

    def add_hypothesis(
        self,
        name: str,
        prior: Optional[float] = None,
        alpha: float = 1.0,
        beta: float = 1.0
    ) -> None:
        """
        Add a new hypothesis with prior belief.

        Args:
            name: Hypothesis identifier
            prior: Prior probability P(H). If None, uses base_prior
            alpha, beta: Beta distribution parameters for uncertainty modeling
        """
        if prior is None:
            prior = self.base_prior

        self.hypotheses[name] = BayesianHypothesis(
            name=name,
            prior=prior,
            likelihood=1.0,
            posterior=prior,
            evidence_count=0,
            confidence_interval=(0.0, 1.0),
            uncertainty=self._compute_entropy(prior)
        )

        self.alpha_beta[name] = (alpha, beta)
        self.stats['hypothesis_count'] += 1

    def update_belief(
        self,
        hypothesis: str,
        evidence: Evidence,
        normalize: bool = True
    ) -> BayesianHypothesis:
        """
        Update belief in hypothesis given new evidence using Bayes' rule.

        P(H|E) = P(E|H) * P(H) / P(E)

        Args:
            hypothesis: Name of hypothesis to update
            evidence: New evidence observation
            normalize: Whether to normalize across all hypotheses

        Returns:
            Updated hypothesis with posterior belief
        """
        if hypothesis not in self.hypotheses:
            raise ValueError(f"Unknown hypothesis: {hypothesis}")

        h = self.hypotheses[hypothesis]

        # Apply evidence reliability as weight
        weighted_likelihood = (
            evidence.likelihood_given_h1 * evidence.reliability +
            0.5 * (1 - evidence.reliability)  # uncertain evidence → 50/50
        )

        # Bayes' rule: posterior ∝ likelihood × prior
        unnormalized_posterior = weighted_likelihood * h.posterior

        # Store evidence
        self.evidence_history.append(evidence)
        h.evidence_count += 1

        # Update Beta distribution parameters (for uncertainty modeling)
        alpha, beta = self.alpha_beta[hypothesis]
        if evidence.likelihood_given_h1 > 0.5:
            alpha += evidence.reliability
        else:
            beta += evidence.reliability
        self.alpha_beta[hypothesis] = (alpha, beta)

        if normalize:
            # Compute normalization constant P(E)
            total_prob = sum(
                self.hypotheses[h_name].posterior *
                (evidence.likelihood_given_h1 if h_name == hypothesis else evidence.likelihood_given_h0)
                for h_name in self.hypotheses
            )
            h.posterior = unnormalized_posterior / (total_prob + 1e-10)
        else:
            h.posterior = unnormalized_posterior

        # Update uncertainty measures
        h.confidence_interval = self._compute_credible_interval(alpha, beta)
        h.uncertainty = self._compute_entropy(h.posterior)

        # Track belief evolution
        self.belief_history.append({
            h_name: self.hypotheses[h_name].posterior
            for h_name in self.hypotheses
        })

        self.stats['total_updates'] += 1
        self.stats['evidence_count'] += 1
        self.stats['avg_uncertainty'] = np.mean([
            h.uncertainty for h in self.hypotheses.values()
        ])

        return h

    def update_all_hypotheses(
        self,
        evidence: Evidence
    ) -> Dict[str, BayesianHypothesis]:
        """
        Update all hypotheses given new evidence (normalized).

        Args:
            evidence: New evidence to incorporate

        Returns:
            Dict of all updated hypotheses
        """
        # Compute unnormalized posteriors for all hypotheses
        unnormalized = {}
        for h_name in self.hypotheses:
            h = self.hypotheses[h_name]
            likelihood = evidence.likelihood_given_h1 if h_name == list(self.hypotheses.keys())[0] else evidence.likelihood_given_h0
            unnormalized[h_name] = likelihood * h.posterior

        # Normalize
        total = sum(unnormalized.values()) + 1e-10
        for h_name in self.hypotheses:
            self.hypotheses[h_name].posterior = unnormalized[h_name] / total
            self.hypotheses[h_name].evidence_count += 1
            self.hypotheses[h_name].uncertainty = self._compute_entropy(
                self.hypotheses[h_name].posterior
            )

        self.evidence_history.append(evidence)
        self.stats['total_updates'] += len(self.hypotheses)
        self.stats['evidence_count'] += 1

        return self.hypotheses

    def compare_hypotheses(
        self,
        threshold: float = 0.8
    ) -> Dict[str, Any]:
        """
        Compare all hypotheses and determine which are credible.

        Args:
            threshold: Minimum posterior probability to be considered credible

        Returns:
            Comparison report with rankings and decisions
        """
        ranked = sorted(
            self.hypotheses.items(),
            key=lambda x: x[1].posterior,
            reverse=True
        )

        # Bayes factor: odds ratio of top two hypotheses
        bayes_factor = None
        if len(ranked) >= 2:
            p1 = ranked[0][1].posterior
            p2 = ranked[1][1].posterior
            bayes_factor = (p1 / (1 - p1)) / (p2 / (1 - p2) + 1e-10)

        # Interpretation of Bayes factor (Kass & Raftery, 1995)
        bf_interpretation = self._interpret_bayes_factor(bayes_factor)

        return {
            'ranked_hypotheses': [
                {
                    'name': name,
                    'posterior': h.posterior,
                    'prior': h.prior,
                    'evidence_count': h.evidence_count,
                    'uncertainty': h.uncertainty,
                    'credible_interval': h.confidence_interval,
                    'is_credible': h.posterior >= threshold
                }
                for name, h in ranked
            ],
            'winner': ranked[0][0] if ranked else None,
            'winner_probability': ranked[0][1].posterior if ranked else 0.0,
            'bayes_factor': bayes_factor,
            'bayes_factor_interpretation': bf_interpretation,
            'total_uncertainty': np.mean([h.uncertainty for _, h in ranked]),
            'decision': 'accept' if (ranked and ranked[0][1].posterior >= threshold) else 'uncertain'
        }

    def propagate_uncertainty(
        self,
        hypothesis: str,
        n_samples: int = 10000
    ) -> Dict[str, Any]:
        """
        Propagate uncertainty through the model using Monte Carlo sampling.

        Args:
            hypothesis: Hypothesis to analyze
            n_samples: Number of Monte Carlo samples

        Returns:
            Uncertainty quantification results
        """
        if hypothesis not in self.alpha_beta:
            raise ValueError(f"Unknown hypothesis: {hypothesis}")

        alpha, beta = self.alpha_beta[hypothesis]

        # Sample from Beta distribution
        samples = np.random.beta(alpha, beta, n_samples)

        return {
            'mean': np.mean(samples),
            'median': np.median(samples),
            'std': np.std(samples),
            'credible_interval_95': (
                np.percentile(samples, 2.5),
                np.percentile(samples, 97.5)
            ),
            'credible_interval_90': (
                np.percentile(samples, 5),
                np.percentile(samples, 95)
            ),
            'samples': samples.tolist()[:100]  # Return first 100 for inspection
        }

    def compute_mutual_information(
        self,
        hypothesis: str,
        potential_evidence: List[Evidence]
    ) -> List[Tuple[Evidence, float]]:
        """
        Compute mutual information between hypotheses and potential evidence.
        Useful for active learning: which evidence would be most informative?

        Args:
            hypothesis: Hypothesis to analyze
            potential_evidence: List of evidence we could collect

        Returns:
            List of (evidence, mutual_information) sorted by informativeness
        """
        results = []

        for ev in potential_evidence:
            # Current entropy
            h_current = self._compute_entropy(self.hypotheses[hypothesis].posterior)

            # Expected entropy after observing evidence
            # E[H(P|E)] = P(E|H1) * H(P|E=e1) + P(E|H0) * H(P|E=e0)

            # Simulate update with evidence
            h_copy = BayesianHypothesis(**asdict(self.hypotheses[hypothesis]))

            # Posterior if evidence supports hypothesis
            p_after_support = (ev.likelihood_given_h1 * h_copy.posterior) / (
                ev.likelihood_given_h1 * h_copy.posterior +
                ev.likelihood_given_h0 * (1 - h_copy.posterior) + 1e-10
            )

            # Posterior if evidence contradicts hypothesis
            p_after_contradict = (ev.likelihood_given_h0 * h_copy.posterior) / (
                ev.likelihood_given_h0 * h_copy.posterior +
                ev.likelihood_given_h1 * (1 - h_copy.posterior) + 1e-10
            )

            # Expected entropy
            h_after = (
                ev.likelihood_given_h1 * self._compute_entropy(p_after_support) +
                ev.likelihood_given_h0 * self._compute_entropy(p_after_contradict)
            )

            # Mutual information = current entropy - expected entropy
            mi = h_current - h_after
            results.append((ev, mi))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def _compute_entropy(self, p: float) -> float:
        """Compute Shannon entropy of binary distribution."""
        if p <= 0 or p >= 1:
            return 0.0
        return -p * np.log2(p) - (1 - p) * np.log2(1 - p)

    def _compute_credible_interval(
        self,
        alpha: float,
        beta: float,
        credibility: float = 0.95
    ) -> Tuple[float, float]:
        """Compute credible interval from Beta distribution."""
        lower = stats.beta.ppf((1 - credibility) / 2, alpha, beta)
        upper = stats.beta.ppf(1 - (1 - credibility) / 2, alpha, beta)
        return (lower, upper)

    def _interpret_bayes_factor(self, bf: Optional[float]) -> str:
        """Interpret Bayes factor using Kass & Raftery (1995) scale."""
        if bf is None:
            return "insufficient hypotheses"
        if bf < 1:
            return "negative (favors alternative)"
        elif bf < 3:
            return "barely worth mentioning"
        elif bf < 10:
            return "substantial evidence"
        elif bf < 30:
            return "strong evidence"
        elif bf < 100:
            return "very strong evidence"
        else:
            return "decisive evidence"

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of the reasoning system."""
        return {
            'statistics': self.stats,
            'hypotheses': {
                name: {
                    'posterior': h.posterior,
                    'uncertainty': h.uncertainty,
                    'evidence_count': h.evidence_count,
                    'credible_interval': h.confidence_interval
                }
                for name, h in self.hypotheses.items()
            },
            'total_evidence': len(self.evidence_history),
            'belief_trajectory_length': len(self.belief_history)
        }

    def save(self, path: str) -> None:
        """Save model state to disk."""
        # Convert dataclasses to dicts for pickling
        hypotheses_dict = {
            name: asdict(h) for name, h in self.hypotheses.items()
        }
        evidence_dict = [asdict(e) for e in self.evidence_history]

        with open(path, 'wb') as f:
            pickle.dump({
                'hypotheses': hypotheses_dict,
                'alpha_beta': self.alpha_beta,
                'evidence_history': evidence_dict,
                'belief_history': self.belief_history,
                'stats': self.stats,
                'base_prior': self.base_prior
            }, f)

    def load(self, path: str) -> None:
        """Load model state from disk."""
        with open(path, 'rb') as f:
            data = pickle.load(f)

            # Reconstruct dataclasses from dicts
            self.hypotheses = {
                name: BayesianHypothesis(**h_dict)
                for name, h_dict in data['hypotheses'].items()
            }
            self.evidence_history = [
                Evidence(**e_dict) for e_dict in data['evidence_history']
            ]

            self.alpha_beta = data['alpha_beta']
            self.belief_history = data['belief_history']
            self.stats = data['stats']
            self.base_prior = data['base_prior']


def train_bayesian_reasoner_demo():
    """
    Demonstration: Training a Bayesian reasoner on a medical diagnosis scenario.

    Scenario: Patient has symptoms. What's the diagnosis?
    - Hypothesis 1: Common cold (prior: 0.7)
    - Hypothesis 2: Flu (prior: 0.2)
    - Hypothesis 3: COVID-19 (prior: 0.1)
    """
    print("=" * 80)
    print("BAYESIAN REASONING SYSTEM - TRAINING DEMONSTRATION")
    print("=" * 80)
    print()

    reasoner = BayesianReasoner(base_prior=0.33)

    # Add hypotheses with priors based on base rates
    reasoner.add_hypothesis('common_cold', prior=0.7, alpha=7, beta=3)
    reasoner.add_hypothesis('flu', prior=0.2, alpha=2, beta=8)
    reasoner.add_hypothesis('covid19', prior=0.1, alpha=1, beta=9)

    print("Initial Hypotheses:")
    comparison = reasoner.compare_hypotheses()
    for h in comparison['ranked_hypotheses']:
        print(f"  {h['name']:15s}: P={h['posterior']:.3f}, Uncertainty={h['uncertainty']:.3f}")
    print()

    # Evidence 1: Fever (common in flu and COVID, less in cold)
    evidence1 = Evidence(
        description="Patient has fever (38.5°C)",
        observation="fever",
        likelihood_given_h1=0.3,  # P(fever|cold)
        likelihood_given_h0=0.8,  # P(fever|not_cold)
        reliability=0.95,
        timestamp="2026-07-03T10:00:00"
    )

    print("Evidence 1: Patient has fever (38.5°C)")
    reasoner.update_all_hypotheses(evidence1)
    comparison = reasoner.compare_hypotheses()
    for h in comparison['ranked_hypotheses']:
        print(f"  {h['name']:15s}: P={h['posterior']:.3f}, Uncertainty={h['uncertainty']:.3f}")
    print()

    # Evidence 2: Loss of smell (strong indicator of COVID)
    evidence2 = Evidence(
        description="Patient reports loss of smell",
        observation="anosmia",
        likelihood_given_h1=0.05,  # P(anosmia|cold)
        likelihood_given_h0=0.6,   # P(anosmia|covid)
        reliability=0.9,
        timestamp="2026-07-03T10:15:00"
    )

    print("Evidence 2: Patient reports loss of smell")
    reasoner.update_all_hypotheses(evidence2)
    comparison = reasoner.compare_hypotheses()
    for h in comparison['ranked_hypotheses']:
        print(f"  {h['name']:15s}: P={h['posterior']:.3f}, Uncertainty={h['uncertainty']:.3f}")
    print()

    # Evidence 3: Rapid antigen test positive
    evidence3 = Evidence(
        description="Rapid antigen test positive",
        observation="positive_test",
        likelihood_given_h1=0.01,  # P(positive|cold)
        likelihood_given_h0=0.85,  # P(positive|covid)
        reliability=0.88,  # Test has 12% false positive rate
        timestamp="2026-07-03T10:30:00"
    )

    print("Evidence 3: Rapid antigen test positive")
    reasoner.update_all_hypotheses(evidence3)
    comparison = reasoner.compare_hypotheses()
    for h in comparison['ranked_hypotheses']:
        print(f"  {h['name']:15s}: P={h['posterior']:.3f}, Uncertainty={h['uncertainty']:.3f}")
    print()

    # Final comparison
    print("=" * 80)
    print("FINAL DIAGNOSIS")
    print("=" * 80)
    print(f"Winner: {comparison['winner']}")
    print(f"Probability: {comparison['winner_probability']:.3f}")
    print(f"Bayes Factor: {comparison['bayes_factor']:.2f} ({comparison['bayes_factor_interpretation']})")
    print(f"Decision: {comparison['decision'].upper()}")
    print()

    # Uncertainty quantification
    print("Uncertainty Analysis (COVID-19 hypothesis):")
    uncertainty = reasoner.propagate_uncertainty('covid19', n_samples=10000)
    print(f"  Mean probability: {uncertainty['mean']:.3f}")
    print(f"  Std deviation: {uncertainty['std']:.3f}")
    print(f"  95% Credible Interval: [{uncertainty['credible_interval_95'][0]:.3f}, {uncertainty['credible_interval_95'][1]:.3f}]")
    print()

    # Active learning: What evidence would be most informative?
    print("Most Informative Next Tests:")
    potential_tests = [
        Evidence("PCR test", "pcr", 0.01, 0.98, 0.99, "future"),
        Evidence("Chest X-ray", "xray", 0.1, 0.4, 0.85, "future"),
        Evidence("Blood test", "blood", 0.2, 0.5, 0.8, "future")
    ]

    mi_results = reasoner.compute_mutual_information('covid19', potential_tests)
    for ev, mi in mi_results:
        print(f"  {ev.description:20s}: MI={mi:.4f} bits")
    print()

    # Save model
    output_path = Path.home() / 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/learning/bayesian_reasoner.pkl'
    reasoner.save(str(output_path))

    print(f"Model saved to: {output_path}")
    print()

    # Summary statistics
    summary = reasoner.get_summary()
    print("System Statistics:")
    print(json.dumps(summary['statistics'], indent=2))

    return reasoner


if __name__ == '__main__':
    reasoner = train_bayesian_reasoner_demo()

    print("\n" + "=" * 80)
    print("USAGE EXAMPLE")
    print("=" * 80)
    print("""
    from bayesian_reasoner import BayesianReasoner, Evidence

    # Create reasoner
    reasoner = BayesianReasoner(base_prior=0.5)

    # Add competing hypotheses
    reasoner.add_hypothesis('bug_in_auth', prior=0.6)
    reasoner.add_hypothesis('bug_in_database', prior=0.3)
    reasoner.add_hypothesis('network_issue', prior=0.1)

    # Collect evidence
    evidence1 = Evidence(
        description="Error only happens for certain users",
        observation="user_specific",
        likelihood_given_h1=0.8,  # likely if auth bug
        likelihood_given_h0=0.2,  # unlikely otherwise
        reliability=0.9,
        timestamp="2026-07-03T12:00:00"
    )

    # Update beliefs
    reasoner.update_all_hypotheses(evidence1)

    # Compare hypotheses
    result = reasoner.compare_hypotheses(threshold=0.7)
    print(f"Most likely: {result['winner']} (P={result['winner_probability']:.2f})")

    # Quantify uncertainty
    uncertainty = reasoner.propagate_uncertainty('bug_in_auth')
    print(f"95% CI: {uncertainty['credible_interval_95']}")
    """)
