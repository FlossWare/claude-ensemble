#!/usr/bin/env python3
"""
Configuration for multi-stage solution solving.
"""

from dataclasses import dataclass
from typing import List, Optional

# Import GA config
try:
    from ga_config import GAConfig, DEFAULT_GA_CONFIG
except ImportError:
    GAConfig = None
    DEFAULT_GA_CONFIG = None


@dataclass
class SolveStageConfig:
    """Configuration for a single solve stage"""
    stage_number: int
    workers: int = 2
    arbiter: str = "claude-opus-5"
    worker_models: List[str] = None

    def __post_init__(self):
        if self.worker_models is None:
            # Default: escalate with stages
            if self.stage_number == 1:
                self.worker_models = ["claude-haiku-4", "claude-haiku-4"]
            elif self.stage_number == 2:
                self.worker_models = ["claude-sonnet-5", "claude-sonnet-5"]
            else:
                self.worker_models = ["claude-opus-5", "claude-opus-5"]


@dataclass
class SolvePipelineConfig:
    """Configuration for multi-stage solving pipeline"""
    num_stages: int = 1  # solve, meta-solve, meta-meta-solve, etc.
    workers_per_stage: int = 2
    stages: List[SolveStageConfig] = None
    ga_config: Optional[GAConfig] = None  # GA tuning parameters

    def __post_init__(self):
        if self.stages is None:
            self._create_default_stages()
        if self.ga_config is None and DEFAULT_GA_CONFIG is not None:
            import copy
            self.ga_config = copy.deepcopy(DEFAULT_GA_CONFIG)

    def _create_default_stages(self):
        """Create default stage configurations"""
        self.stages = []
        for i in range(1, self.num_stages + 1):
            self.stages.append(SolveStageConfig(stage_number=i, workers=self.workers_per_stage))
