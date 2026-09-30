#!/usr/bin/env python3
"""
Configuration for multi-stage review pipelines.

Loads configuration from YAML files and provides stage/worker configuration
that can be reused across different artifact types.
"""

import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

# Import GA config
try:
    from ga_config import GAConfig, DEFAULT_GA_CONFIG
except ImportError:
    GAConfig = None
    DEFAULT_GA_CONFIG = None

logger = logging.getLogger(__name__)


class StageRole(Enum):
    """Semantic role for a stage"""
    DISCOVERY = "discovery"  # Initial comprehensive analysis
    CHALLENGE = "challenge"  # Challenge and refute prior findings
    VALIDATION = "validation"  # Final validation and confirmation


@dataclass
class StageConfig:
    """Configuration for a single review stage"""
    stage_number: int
    num_workers: int
    worker_models: Optional[List[str]] = None  # Explicit models, or None for auto-select
    worker_tier: str = "balanced"  # "cheap", "balanced", "expensive" if auto-selecting
    arbiter_model: Optional[str] = None  # Explicit arbiter, or None for auto-select
    arbiter_tier: str = "expensive"
    role: StageRole = StageRole.DISCOVERY
    temperature: float = 0.7
    max_tokens: int = 4000
    instructions_override: Optional[str] = None  # Custom instructions for this stage


@dataclass
class ReviewPipelineConfig:
    """Configuration for a multi-stage review pipeline"""
    num_stages: int = 3
    workers_per_stage: int = 3
    stages: List[StageConfig] = field(default_factory=list)

    # Review parameters
    artifact_types: List[str] = field(default_factory=list)  # "code", "document", "design", etc.
    default_artifact_type: str = "generic"

    # Model parameters
    ensure_worker_diversity: bool = True  # No worker model repeats across stages
    max_unique_models: int = 8  # Maximum distinct models to use

    # Cost and performance
    cost_budget_usd: Optional[float] = None  # Max cost for entire review
    time_budget_seconds: Optional[int] = None  # Max time for entire review

    # Confidence thresholds
    min_arbiter_confidence: float = 0.6  # Minimum arbiter confidence to include findings
    min_finding_confidence: float = 0.5  # Minimum finding confidence to report

    # Finding weights (for prioritization)
    finding_severity_weights: Dict[str, float] = field(default_factory=lambda: {
        "critical": 1.0,
        "high": 0.8,
        "medium": 0.6,
        "low": 0.3,
        "info": 0.1,
    })

    # Storage and integration
    persist_findings: bool = True  # Save to filesystem
    learning_integration: bool = False  # Send outcomes to learning service
    alert_on_critical: bool = True  # Alert if critical findings found

    # GA Tuning configuration
    ga_config: Optional[GAConfig] = None  # GA tuning parameters

    def __post_init__(self):
        """Initialize defaults after dataclass creation"""
        if self.ga_config is None and DEFAULT_GA_CONFIG is not None:
            import copy
            self.ga_config = copy.deepcopy(DEFAULT_GA_CONFIG)

        # Ensure stages are created if not provided
        if not self.stages:
            self.validate()  # This calls _create_default_stages

    def validate(self) -> bool:
        """Validate configuration"""
        if self.num_stages < 1:
            logger.error("num_stages must be >= 1")
            return False

        if self.workers_per_stage < 1:
            logger.error("workers_per_stage must be >= 1")
            return False

        if len(self.stages) == 0:
            logger.warning("No stages configured, using defaults")
            self._create_default_stages()

        return True

    def _create_default_stages(self) -> None:
        """Create default stage configurations"""
        roles = [StageRole.DISCOVERY, StageRole.CHALLENGE, StageRole.VALIDATION]

        for i in range(self.num_stages):
            role = roles[min(i, len(roles) - 1)]

            # Use Gemini models: cheap → standard → premium
            if i == 0:
                worker_models = ["gemini-2.5-flash-lite"] * self.workers_per_stage
                arbiter_model = "gemini-2.5-flash"
            elif i == 1:
                worker_models = ["gemini-2.5-flash"] * self.workers_per_stage
                arbiter_model = "gemini-2.5-pro"
            else:
                worker_models = ["gemini-2.5-pro"] * self.workers_per_stage
                arbiter_model = "gemini-2.5-pro"

            self.stages.append(StageConfig(
                stage_number=i + 1,
                num_workers=self.workers_per_stage,
                worker_models=worker_models,
                arbiter_model=arbiter_model,
                role=role,
            ))

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'ReviewPipelineConfig':
        """Load configuration from YAML file"""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)

        config = cls(
            num_stages=data.get('num_stages', 3),
            workers_per_stage=data.get('workers_per_stage', 3),
            artifact_types=data.get('artifact_types', []),
            default_artifact_type=data.get('default_artifact_type', 'generic'),
            ensure_worker_diversity=data.get('ensure_worker_diversity', True),
            max_unique_models=data.get('max_unique_models', 8),
            cost_budget_usd=data.get('cost_budget_usd'),
            time_budget_seconds=data.get('time_budget_seconds'),
            min_arbiter_confidence=data.get('min_arbiter_confidence', 0.6),
            min_finding_confidence=data.get('min_finding_confidence', 0.5),
            persist_findings=data.get('persist_findings', True),
            learning_integration=data.get('learning_integration', False),
            alert_on_critical=data.get('alert_on_critical', True),
        )

        # Load stage configurations if provided
        if 'stages' in data:
            for stage_data in data['stages']:
                role = StageRole(stage_data.get('role', 'discovery'))
                config.stages.append(StageConfig(
                    stage_number=stage_data['stage'],
                    num_workers=stage_data.get('num_workers', config.workers_per_stage),
                    worker_models=stage_data.get('worker_models'),
                    worker_tier=stage_data.get('worker_tier', 'balanced'),
                    arbiter_model=stage_data.get('arbiter_model'),
                    arbiter_tier=stage_data.get('arbiter_tier', 'expensive'),
                    role=role,
                    temperature=stage_data.get('temperature', 0.7),
                    max_tokens=stage_data.get('max_tokens', 4000),
                    instructions_override=stage_data.get('instructions_override'),
                ))

        if not config.validate():
            logger.warning("Configuration validation failed, using defaults")

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'num_stages': self.num_stages,
            'workers_per_stage': self.workers_per_stage,
            'stages': [
                {
                    'stage': s.stage_number,
                    'num_workers': s.num_workers,
                    'worker_models': s.worker_models,
                    'worker_tier': s.worker_tier,
                    'arbiter_model': s.arbiter_model,
                    'arbiter_tier': s.arbiter_tier,
                    'role': s.role.value,
                }
                for s in self.stages
            ],
            'artifact_types': self.artifact_types,
            'default_artifact_type': self.default_artifact_type,
            'ensure_worker_diversity': self.ensure_worker_diversity,
            'max_unique_models': self.max_unique_models,
            'cost_budget_usd': self.cost_budget_usd,
            'min_arbiter_confidence': self.min_arbiter_confidence,
            'min_finding_confidence': self.min_finding_confidence,
        }


def create_default_config() -> ReviewPipelineConfig:
    """Create sensible default configuration"""
    config = ReviewPipelineConfig(
        num_stages=3,
        workers_per_stage=3,
        artifact_types=['code', 'document', 'design', 'proposal'],
    )
    config._create_default_stages()
    return config


# Default global configuration
_default_config: Optional[ReviewPipelineConfig] = None


def get_config() -> ReviewPipelineConfig:
    """Get or create default configuration"""
    global _default_config
    if _default_config is None:
        _default_config = create_default_config()
    return _default_config


def set_config(config: ReviewPipelineConfig) -> None:
    """Set global configuration"""
    global _default_config
    _default_config = config
