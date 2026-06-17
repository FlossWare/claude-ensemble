"""
Genetic Algorithm Engine for Fleet Orchestration Optimization
"""

import random
from typing import List, Dict, Any


class FleetChromosome:
    """
    Represents a fleet orchestration configuration as a chromosome for genetic optimization.

    Genes:
    - workers: List of {model: str, host: str} configurations
    - arbiter: {model: str, host: str} configuration
    - consensus: Consensus strategy (single/weighted/majority/rotating/pairwise)
    - timeout_ms: Timeout in milliseconds (15000-90000)
    - num_workers: Number of workers (2-8)
    - host_preference: Ordered list of preferred hosts
    """

    VALID_CONSENSUS_STRATEGIES = ['single', 'weighted', 'majority', 'rotating', 'pairwise']
    MIN_TIMEOUT_MS = 15000
    MAX_TIMEOUT_MS = 90000
    MIN_WORKERS = 2
    MAX_WORKERS = 8

    def __init__(
        self,
        workers: List[Dict[str, str]] = None,
        arbiter: Dict[str, str] = None,
        consensus: str = 'majority',
        timeout_ms: int = 30000,
        num_workers: int = 3,
        host_preference: List[str] = None
    ):
        """
        Initialize a FleetChromosome.

        Args:
            workers: List of worker configurations [{model: str, host: str}, ...]
            arbiter: Arbiter configuration {model: str, host: str}
            consensus: Consensus strategy
            timeout_ms: Timeout in milliseconds
            num_workers: Number of workers
            host_preference: Ordered list of preferred hosts
        """
        self.workers = workers or []
        self.arbiter = arbiter or {}
        self.consensus = consensus
        self.timeout_ms = timeout_ms
        self.num_workers = num_workers
        self.host_preference = host_preference or []

        # Fitness score (set after evaluation)
        self.fitness = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert chromosome to dictionary representation.

        Returns:
            Dictionary with all gene values and fitness score
        """
        return {
            'workers': self.workers,
            'arbiter': self.arbiter,
            'consensus': self.consensus,
            'timeout_ms': self.timeout_ms,
            'num_workers': self.num_workers,
            'host_preference': self.host_preference,
            'fitness': self.fitness
        }

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate chromosome configuration.

        Returns:
            Tuple of (is_valid: bool, errors: List[str])
        """
        errors = []

        # Validate workers
        if not isinstance(self.workers, list):
            errors.append("workers must be a list")
        else:
            for i, worker in enumerate(self.workers):
                if not isinstance(worker, dict):
                    errors.append(f"workers[{i}] must be a dict")
                elif 'model' not in worker or 'host' not in worker:
                    errors.append(f"workers[{i}] must have 'model' and 'host' keys")
                elif not isinstance(worker['model'], str) or not isinstance(worker['host'], str):
                    errors.append(f"workers[{i}] 'model' and 'host' must be strings")

        # Validate arbiter
        if not isinstance(self.arbiter, dict):
            errors.append("arbiter must be a dict")
        elif 'model' not in self.arbiter or 'host' not in self.arbiter:
            errors.append("arbiter must have 'model' and 'host' keys")
        elif not isinstance(self.arbiter['model'], str) or not isinstance(self.arbiter['host'], str):
            errors.append("arbiter 'model' and 'host' must be strings")

        # Validate consensus
        if self.consensus not in self.VALID_CONSENSUS_STRATEGIES:
            errors.append(
                f"consensus must be one of {self.VALID_CONSENSUS_STRATEGIES}, got '{self.consensus}'"
            )

        # Validate timeout_ms
        if not isinstance(self.timeout_ms, int):
            errors.append("timeout_ms must be an integer")
        elif not (self.MIN_TIMEOUT_MS <= self.timeout_ms <= self.MAX_TIMEOUT_MS):
            errors.append(
                f"timeout_ms must be between {self.MIN_TIMEOUT_MS} and {self.MAX_TIMEOUT_MS}, "
                f"got {self.timeout_ms}"
            )

        # Validate num_workers
        if not isinstance(self.num_workers, int):
            errors.append("num_workers must be an integer")
        elif not (self.MIN_WORKERS <= self.num_workers <= self.MAX_WORKERS):
            errors.append(
                f"num_workers must be between {self.MIN_WORKERS} and {self.MAX_WORKERS}, "
                f"got {self.num_workers}"
            )

        # Validate host_preference
        if not isinstance(self.host_preference, list):
            errors.append("host_preference must be a list")
        else:
            for i, host in enumerate(self.host_preference):
                if not isinstance(host, str):
                    errors.append(f"host_preference[{i}] must be a string")

        # Validate workers count matches num_workers
        if isinstance(self.workers, list) and len(self.workers) != self.num_workers:
            errors.append(
                f"workers list length ({len(self.workers)}) must match num_workers ({self.num_workers})"
            )

        return (len(errors) == 0, errors)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"FleetChromosome(num_workers={self.num_workers}, "
            f"consensus={self.consensus}, timeout_ms={self.timeout_ms}, "
            f"fitness={self.fitness})"
        )

    def __eq__(self, other) -> bool:
        """Equality comparison based on gene values."""
        if not isinstance(other, FleetChromosome):
            return False
        return self.to_dict() == other.to_dict()


if __name__ == '__main__':
    # Example usage
    chromosome = FleetChromosome(
        workers=[
            {'model': 'opus', 'host': 'laptop-01'},
            {'model': 'sonnet', 'host': 'server-02'},
            {'model': 'haiku', 'host': 'server-03'}
        ],
        arbiter={'model': 'gpt4o', 'host': 'api'},
        consensus='majority',
        timeout_ms=45000,
        num_workers=3,
        host_preference=['laptop-01', 'server-02', 'server-03', 'api']
    )

    is_valid, errors = chromosome.validate()
    print(f"Valid: {is_valid}")
    if errors:
        print(f"Errors: {errors}")

    print(f"\nChromosome: {chromosome}")
    print(f"\nDict representation:\n{chromosome.to_dict()}")
