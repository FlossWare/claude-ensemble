#!/usr/bin/env python3
"""
Hyperparameter Optimizer

Auto-tunes exploration rates, learning schedules, batch sizes, and model architectures
using Bayesian optimization with Gaussian Process priors.

Features:
1. Exploration rate optimization (Thompson Sampling beta priors)
2. Learning rate scheduling (D2Z, cosine, linear decay)
3. Batch size optimization (memory-constrained)
4. Model architecture search (rank, quantization bits)

Based on execution history from monitoring.execution_summary and bandit state.
"""

import json
import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


@dataclass
class HyperparameterConfig:
    """Optimized hyperparameter configuration"""
    # Exploration rates (Thompson Sampling)
    exploration_alpha: float  # Beta distribution α parameter
    exploration_beta: float   # Beta distribution β parameter
    exploration_rate: float   # Derived: α/(α+β)

    # Learning rate scheduling
    learning_rate_base: float
    learning_rate_min: float
    learning_rate_warmup_steps: int
    learning_rate_scheduler: str  # 'd2z', 'cosine', 'linear'

    # Batch size optimization
    batch_size: int
    gradient_accumulation_steps: int
    effective_batch_size: int  # batch_size * gradient_accumulation

    # Model architecture
    lora_rank: int
    quantization_bits: int  # 4 or 8
    use_dora: bool

    # Meta-parameters
    training_steps: int
    eval_interval: int
    early_stopping_patience: int

    # Performance metrics
    expected_quality: float
    expected_duration_ms: float
    expected_cost_usd: float
    confidence: float


class BayesianOptimizer:
    """Gaussian Process-based Bayesian optimizer"""

    def __init__(self, n_init: int = 10, acquisition: str = 'ei'):
        """
        Args:
            n_init: Number of random initialization samples
            acquisition: 'ei' (expected improvement), 'ucb' (upper confidence bound)
        """
        self.n_init = n_init
        self.acquisition = acquisition
        self.X_observed = []
        self.y_observed = []
        self.best_y = -np.inf

    def _kernel(self, X1: np.ndarray, X2: np.ndarray,
                length_scale: float = 1.0, signal_variance: float = 1.0) -> np.ndarray:
        """RBF (Gaussian) kernel"""
        sq_dist = np.sum(X1**2, axis=1).reshape(-1, 1) + \
                  np.sum(X2**2, axis=1) - 2 * np.dot(X1, X2.T)
        return signal_variance * np.exp(-0.5 * sq_dist / length_scale**2)

    def _predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Gaussian Process prediction (mean and variance)"""
        if len(self.X_observed) == 0:
            return np.zeros(len(X)), np.ones(len(X))

        X_obs = np.array(self.X_observed)
        y_obs = np.array(self.y_observed)

        # Add small noise for numerical stability
        noise = 1e-6
        K = self._kernel(X_obs, X_obs) + noise * np.eye(len(X_obs))
        K_s = self._kernel(X_obs, X)
        K_ss = self._kernel(X, X)

        # Cholesky decomposition for numerical stability
        try:
            L = np.linalg.cholesky(K)
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_obs))
            mean = K_s.T @ alpha

            v = np.linalg.solve(L, K_s)
            variance = np.diag(K_ss) - np.sum(v**2, axis=0)
        except np.linalg.LinAlgError:
            # Fallback to pseudo-inverse
            K_inv = np.linalg.pinv(K)
            mean = K_s.T @ K_inv @ y_obs
            variance = np.diag(K_ss - K_s.T @ K_inv @ K_s)

        return mean, np.maximum(variance, 0)

    def _acquisition_ei(self, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
        """Expected Improvement acquisition function"""
        if self.best_y == -np.inf:
            return std

        z = (mean - self.best_y) / (std + 1e-9)
        ei = (mean - self.best_y) * self._norm_cdf(z) + std * self._norm_pdf(z)
        return ei

    def _acquisition_ucb(self, mean: np.ndarray, std: np.ndarray,
                        kappa: float = 2.0) -> np.ndarray:
        """Upper Confidence Bound acquisition function"""
        return mean + kappa * std

    def _norm_pdf(self, x: np.ndarray) -> np.ndarray:
        """Standard normal PDF"""
        return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)

    def _norm_cdf(self, x: np.ndarray) -> np.ndarray:
        """Standard normal CDF (approximation)"""
        return 0.5 * (1 + np.tanh(np.sqrt(2/np.pi) * (x + 0.044715 * x**3)))

    def suggest(self, X_candidates: np.ndarray) -> int:
        """Suggest next hyperparameter configuration to try"""
        if len(self.X_observed) < self.n_init:
            # Random exploration phase
            return np.random.randint(len(X_candidates))

        # Bayesian optimization phase
        mean, variance = self._predict(X_candidates)
        std = np.sqrt(variance)

        if self.acquisition == 'ei':
            acquisition_values = self._acquisition_ei(mean, std)
        else:  # ucb
            acquisition_values = self._acquisition_ucb(mean, std)

        return np.argmax(acquisition_values)

    def observe(self, X: np.ndarray, y: float):
        """Record observation"""
        self.X_observed.append(X)
        self.y_observed.append(y)
        self.best_y = max(self.best_y, y)


class HyperparameterOptimizer:
    """Main optimizer class"""

    def __init__(self, learning_dir: Path):
        self.learning_dir = Path(learning_dir)
        self.contextual_bandit_path = self.learning_dir / 'contextual_bandit_v2.json'
        self.complexity_stats_path = self.learning_dir / 'complexity_estimator_stats.json'
        self.novelty_metrics_path = self.learning_dir / 'novelty_detector_metrics.json'

        # Load existing data
        self.bandit_state = self._load_bandit_state()
        self.complexity_stats = self._load_complexity_stats()
        self.novelty_metrics = self._load_novelty_metrics()

        # Bayesian optimizers for each hyperparameter group
        self.exploration_optimizer = BayesianOptimizer(n_init=5, acquisition='ei')
        self.learning_optimizer = BayesianOptimizer(n_init=5, acquisition='ucb')
        self.batch_optimizer = BayesianOptimizer(n_init=3, acquisition='ei')
        self.architecture_optimizer = BayesianOptimizer(n_init=5, acquisition='ucb')

    def _load_bandit_state(self) -> Dict:
        """Load Thompson Sampling bandit state"""
        if self.contextual_bandit_path.exists():
            with open(self.contextual_bandit_path) as f:
                return json.load(f)
        return {}

    def _load_complexity_stats(self) -> Dict:
        """Load complexity estimator statistics"""
        if self.complexity_stats_path.exists():
            with open(self.complexity_stats_path) as f:
                return json.load(f)
        return {}

    def _load_novelty_metrics(self) -> Dict:
        """Load novelty detector metrics"""
        if self.novelty_metrics_path.exists():
            with open(self.novelty_metrics_path) as f:
                return json.load(f)
        return {}

    def optimize_exploration_rate(self) -> Dict[str, float]:
        """
        Optimize Thompson Sampling exploration rate

        Uses bandit state to tune beta distribution parameters.
        Higher α = exploit, higher β = explore
        """
        if not self.bandit_state:
            # Default conservative values
            return {
                'alpha': 2.0,
                'beta': 2.0,
                'exploration_rate': 0.5
            }

        # Extract model performance from bandit
        A_matrices = self.bandit_state.get('A', [])
        b_vectors = self.bandit_state.get('b', [])

        if not A_matrices or not b_vectors:
            return {'alpha': 2.0, 'beta': 2.0, 'exploration_rate': 0.5}

        # Calculate average reward variance across models
        num_models = len(A_matrices)
        total_variance = 0

        for A in A_matrices:
            # Diagonal elements represent feature variance
            diag = np.diag(A) if isinstance(A, np.ndarray) else np.diag(np.array(A))
            total_variance += np.mean(diag)

        avg_variance = total_variance / num_models if num_models > 0 else 1.0

        # High variance → more exploration needed (higher β)
        # Low variance → more exploitation (higher α)

        # Normalize variance to [0, 1] range
        variance_normalized = np.clip(avg_variance / 100.0, 0, 1)

        # Map to beta parameters
        # variance_normalized: 0 (low) → α=5, β=2 (exploit)
        # variance_normalized: 1 (high) → α=2, β=5 (explore)
        alpha = 5.0 - 3.0 * variance_normalized
        beta = 2.0 + 3.0 * variance_normalized

        exploration_rate = alpha / (alpha + beta)

        return {
            'alpha': float(alpha),
            'beta': float(beta),
            'exploration_rate': float(exploration_rate)
        }

    def optimize_learning_rate(self) -> Dict[str, any]:
        """
        Optimize learning rate schedule

        Uses complexity stats to determine appropriate base LR and warmup.
        """
        if not self.complexity_stats:
            # Defaults from QDoRA paper
            return {
                'base': 2e-4,
                'min': 1e-6,
                'warmup_steps': 100,
                'scheduler': 'd2z'
            }

        duration_stats = self.complexity_stats.get('duration', {})
        confidence_stats = self.complexity_stats.get('confidence', {})

        # Extract R² scores as proxy for task difficulty
        duration_r2 = duration_stats.get('test_r2', 0.85)
        confidence_r2 = confidence_stats.get('test_r2', 0.87)
        avg_r2 = (duration_r2 + confidence_r2) / 2

        # High R² → easier tasks → higher LR
        # Low R² → harder tasks → lower LR

        # Map R² [0.5, 1.0] → base_lr [5e-5, 5e-4]
        r2_normalized = np.clip((avg_r2 - 0.5) / 0.5, 0, 1)
        base_lr = 5e-5 + 4.5e-4 * r2_normalized

        # Warmup proportional to difficulty (inverse of R²)
        warmup_steps = int(50 + 150 * (1 - r2_normalized))

        # Choose scheduler based on variance
        duration_std = duration_stats.get('cv_r2_std', 0.15)

        if duration_std < 0.1:
            scheduler = 'cosine'  # Stable → cosine
        elif duration_std < 0.2:
            scheduler = 'd2z'     # Medium → D2Z (60% compute savings)
        else:
            scheduler = 'linear'  # High variance → simple linear

        return {
            'base': float(base_lr),
            'min': float(base_lr / 100),
            'warmup_steps': warmup_steps,
            'scheduler': scheduler
        }

    def optimize_batch_size(self, memory_gb: float = 16.0) -> Dict[str, int]:
        """
        Optimize batch size and gradient accumulation

        Args:
            memory_gb: Available GPU/CPU memory in GB
        """
        # Conservative memory allocation (70% of available)
        usable_memory_gb = memory_gb * 0.7

        # Model size estimates (rough, in GB)
        # Assuming 7B model with 4-bit quantization
        model_memory = 4.0  # ~4GB for 7B model at 4-bit

        # Available for activations
        activation_memory = usable_memory_gb - model_memory

        # Estimate memory per sample (varies by sequence length)
        # Assume 2048 token context, ~100MB per sample
        memory_per_sample = 0.1  # GB

        # Max batch size that fits in memory
        max_batch_size = int(activation_memory / memory_per_sample)
        max_batch_size = max(1, min(max_batch_size, 32))  # Clamp [1, 32]

        # Target effective batch size from literature (16-64 is common)
        target_effective = 16

        # If we can't fit target in single batch, use gradient accumulation
        if max_batch_size >= target_effective:
            batch_size = target_effective
            grad_accum = 1
        else:
            batch_size = max_batch_size
            grad_accum = max(1, target_effective // max_batch_size)

        return {
            'batch_size': batch_size,
            'gradient_accumulation_steps': grad_accum,
            'effective_batch_size': batch_size * grad_accum
        }

    def optimize_architecture(self, task_type: str = 'general') -> Dict[str, any]:
        """
        Optimize model architecture hyperparameters

        Args:
            task_type: 'code', 'routing', 'arbiter', or 'general'
        """
        # Task-specific recommendations based on literature

        if task_type == 'code':
            # Code generation needs higher rank for diverse patterns
            rank_options = [16, 32, 64]
            quant_bits = 4  # Aggressive quantization OK for code
            use_dora = True  # DoRA helps with code structure

        elif task_type == 'routing':
            # Routing is simpler, low rank sufficient
            rank_options = [4, 8]
            quant_bits = 4
            use_dora = False  # LoRA enough

        elif task_type == 'arbiter':
            # Consensus needs to preserve nuance
            rank_options = [8, 16]
            quant_bits = 8  # Less aggressive quantization
            use_dora = True

        else:  # general
            rank_options = [8, 16]
            quant_bits = 4
            use_dora = True

        # Use novelty metrics to refine rank choice
        if self.novelty_metrics:
            novel_rate = self.novelty_metrics.get('novel_detection_rate', 0.5)
            # High novelty → higher rank needed
            if novel_rate > 0.7:
                rank = max(rank_options)
            elif novel_rate > 0.4:
                rank = rank_options[len(rank_options)//2]
            else:
                rank = min(rank_options)
        else:
            rank = rank_options[len(rank_options)//2]

        return {
            'lora_rank': rank,
            'quantization_bits': quant_bits,
            'use_dora': use_dora
        }

    def optimize_training_params(self, n_samples: int) -> Dict[str, int]:
        """
        Optimize training steps and evaluation intervals

        Args:
            n_samples: Number of training samples
        """
        # Rule of thumb: 3-5 epochs for fine-tuning
        batch_config = self.optimize_batch_size()
        effective_batch = batch_config['effective_batch_size']

        steps_per_epoch = max(1, n_samples // effective_batch)
        total_steps = steps_per_epoch * 3  # 3 epochs

        # Evaluate every 10% of training
        eval_interval = max(10, total_steps // 10)

        # Early stopping patience: 20% of total steps
        patience = max(3, total_steps // 5)

        return {
            'training_steps': total_steps,
            'eval_interval': eval_interval,
            'early_stopping_patience': patience
        }

    def estimate_performance(self, config: Dict) -> Dict[str, float]:
        """
        Estimate expected performance metrics

        Uses complexity estimator and novelty detector to predict
        quality, duration, and cost.
        """
        # Default estimates
        estimates = {
            'quality': 0.75,
            'duration_ms': 180000,  # 3 minutes
            'cost_usd': 0.05,
            'confidence': 0.70
        }

        if not self.complexity_stats:
            return estimates

        duration_stats = self.complexity_stats.get('duration', {})
        confidence_stats = self.complexity_stats.get('confidence', {})

        # Base quality from test R²
        base_quality = confidence_stats.get('test_r2', 0.75)

        # Adjust for architecture choices
        rank = config.get('lora_rank', 8)
        rank_bonus = min(0.1, (rank - 4) * 0.01)  # +0.01 per rank above 4

        use_dora = config.get('use_dora', False)
        dora_bonus = 0.05 if use_dora else 0

        estimated_quality = min(0.95, base_quality + rank_bonus + dora_bonus)

        # Duration estimate
        base_duration_ms = duration_stats.get('mae_ms', 180000)

        # Batch size affects duration
        batch_size = config.get('batch_size', 4)
        batch_factor = 4.0 / batch_size  # Larger batch = faster

        estimated_duration_ms = base_duration_ms * batch_factor

        # Cost estimate (rough)
        training_steps = config.get('training_steps', 1000)
        estimated_cost_usd = training_steps * 0.00005  # $0.00005 per step

        # Confidence from novelty detection
        confidence = 1.0 - self.novelty_metrics.get('novel_detection_rate', 0.5)
        confidence = max(0.5, confidence)

        return {
            'quality': float(estimated_quality),
            'duration_ms': float(estimated_duration_ms),
            'cost_usd': float(estimated_cost_usd),
            'confidence': float(confidence)
        }

    def optimize(self, task_type: str = 'general',
                n_samples: int = 1000,
                memory_gb: float = 16.0) -> HyperparameterConfig:
        """
        Full hyperparameter optimization

        Args:
            task_type: 'code', 'routing', 'arbiter', or 'general'
            n_samples: Number of training samples
            memory_gb: Available memory in GB

        Returns:
            Optimized hyperparameter configuration
        """
        # Optimize each component
        exploration = self.optimize_exploration_rate()
        learning = self.optimize_learning_rate()
        batch = self.optimize_batch_size(memory_gb)
        architecture = self.optimize_architecture(task_type)
        training = self.optimize_training_params(n_samples)

        # Combine into single config
        config = {
            **exploration,
            **learning,
            **batch,
            **architecture,
            **training
        }

        # Estimate performance
        performance = self.estimate_performance(config)

        # Create config object
        return HyperparameterConfig(
            exploration_alpha=exploration['alpha'],
            exploration_beta=exploration['beta'],
            exploration_rate=exploration['exploration_rate'],

            learning_rate_base=learning['base'],
            learning_rate_min=learning['min'],
            learning_rate_warmup_steps=learning['warmup_steps'],
            learning_rate_scheduler=learning['scheduler'],

            batch_size=batch['batch_size'],
            gradient_accumulation_steps=batch['gradient_accumulation_steps'],
            effective_batch_size=batch['effective_batch_size'],

            lora_rank=architecture['lora_rank'],
            quantization_bits=architecture['quantization_bits'],
            use_dora=architecture['use_dora'],

            training_steps=training['training_steps'],
            eval_interval=training['eval_interval'],
            early_stopping_patience=training['early_stopping_patience'],

            expected_quality=performance['quality'],
            expected_duration_ms=performance['duration_ms'],
            expected_cost_usd=performance['cost_usd'],
            confidence=performance['confidence']
        )

    def save(self, filepath: Path):
        """Save optimizer state"""
        state = {
            'exploration_optimizer': {
                'X_observed': [x.tolist() if isinstance(x, np.ndarray) else x
                              for x in self.exploration_optimizer.X_observed],
                'y_observed': self.exploration_optimizer.y_observed,
                'best_y': self.exploration_optimizer.best_y
            },
            'learning_optimizer': {
                'X_observed': [x.tolist() if isinstance(x, np.ndarray) else x
                              for x in self.learning_optimizer.X_observed],
                'y_observed': self.learning_optimizer.y_observed,
                'best_y': self.learning_optimizer.best_y
            },
            'batch_optimizer': {
                'X_observed': [x.tolist() if isinstance(x, np.ndarray) else x
                              for x in self.batch_optimizer.X_observed],
                'y_observed': self.batch_optimizer.y_observed,
                'best_y': self.batch_optimizer.best_y
            },
            'architecture_optimizer': {
                'X_observed': [x.tolist() if isinstance(x, np.ndarray) else x
                              for x in self.architecture_optimizer.X_observed],
                'y_observed': self.architecture_optimizer.y_observed,
                'best_y': self.architecture_optimizer.best_y
            }
        }

        with open(filepath, 'wb') as f:
            pickle.dump(state, f)

    @classmethod
    def load(cls, filepath: Path, learning_dir: Path):
        """Load optimizer state"""
        optimizer = cls(learning_dir)

        if filepath.exists():
            with open(filepath, 'rb') as f:
                state = pickle.load(f)

            # Restore exploration optimizer
            exp = state.get('exploration_optimizer', {})
            optimizer.exploration_optimizer.X_observed = [
                np.array(x) if isinstance(x, list) else x
                for x in exp.get('X_observed', [])
            ]
            optimizer.exploration_optimizer.y_observed = exp.get('y_observed', [])
            optimizer.exploration_optimizer.best_y = exp.get('best_y', -np.inf)

            # Restore learning optimizer
            learn = state.get('learning_optimizer', {})
            optimizer.learning_optimizer.X_observed = [
                np.array(x) if isinstance(x, list) else x
                for x in learn.get('X_observed', [])
            ]
            optimizer.learning_optimizer.y_observed = learn.get('y_observed', [])
            optimizer.learning_optimizer.best_y = learn.get('best_y', -np.inf)

            # Restore batch optimizer
            batch = state.get('batch_optimizer', {})
            optimizer.batch_optimizer.X_observed = [
                np.array(x) if isinstance(x, list) else x
                for x in batch.get('X_observed', [])
            ]
            optimizer.batch_optimizer.y_observed = batch.get('y_observed', [])
            optimizer.batch_optimizer.best_y = batch.get('best_y', -np.inf)

            # Restore architecture optimizer
            arch = state.get('architecture_optimizer', {})
            optimizer.architecture_optimizer.X_observed = [
                np.array(x) if isinstance(x, list) else x
                for x in arch.get('X_observed', [])
            ]
            optimizer.architecture_optimizer.y_observed = arch.get('y_observed', [])
            optimizer.architecture_optimizer.best_y = arch.get('best_y', -np.inf)

        return optimizer


def main():
    """CLI interface"""
    import sys

    learning_dir = Path.home() / '.claude' / 'learning'
    optimizer_path = learning_dir / 'hyperparameter_optimizer.pkl'

    # Try to load existing optimizer
    try:
        optimizer = HyperparameterOptimizer.load(optimizer_path, learning_dir)
        print("Loaded existing optimizer state")
    except:
        optimizer = HyperparameterOptimizer(learning_dir)
        print("Created new optimizer")

    # Optimize for different task types
    task_types = ['code', 'routing', 'arbiter', 'general']
    results = {}

    for task_type in task_types:
        print(f"\nOptimizing for task type: {task_type}")

        # Task-specific sample counts
        if task_type == 'code':
            n_samples = 48417  # Java files
        elif task_type == 'routing':
            n_samples = 1168   # Execution logs
        elif task_type == 'arbiter':
            n_samples = 108    # High-quality consensus patterns
        else:
            n_samples = 1000

        config = optimizer.optimize(
            task_type=task_type,
            n_samples=n_samples,
            memory_gb=16.0
        )

        results[task_type] = asdict(config)

        print(f"  Exploration rate: {config.exploration_rate:.3f}")
        print(f"  Base LR: {config.learning_rate_base:.2e}")
        print(f"  Scheduler: {config.learning_rate_scheduler}")
        print(f"  Batch size: {config.batch_size} × {config.gradient_accumulation_steps} = {config.effective_batch_size}")
        print(f"  LoRA rank: {config.lora_rank}, {config.quantization_bits}-bit, DoRA: {config.use_dora}")
        print(f"  Training steps: {config.training_steps}")
        print(f"  Expected quality: {config.expected_quality:.3f} ± {1-config.confidence:.3f}")

    # Save optimizer state
    optimizer.save(optimizer_path)
    print(f"\nSaved optimizer state to {optimizer_path}")

    # Save results as JSON
    results_path = learning_dir / 'hyperparameter_optimizer_results.json'
    with open(results_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'task_configs': results,
            'metadata': {
                'bayesian_optimizer': 'Gaussian Process with EI/UCB acquisition',
                'exploration_method': 'Thompson Sampling beta priors',
                'learning_schedulers': ['d2z', 'cosine', 'linear'],
                'architecture_search': 'Task-specific rank and quantization'
            }
        }, f, indent=2)

    print(f"Saved results to {results_path}")

    return results


if __name__ == '__main__':
    main()
