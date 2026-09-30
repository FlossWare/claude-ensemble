#!/usr/bin/env python3
"""
Multi-stage generic review system for claude-ensemble.

Supports reviewing any artifact (code, documents, designs, proposals, etc.)
through multiple independent stages with worker/arbiter orchestration.

Core principle: Every stage independently reviews the ORIGINAL artifact,
with prior reviews treated as untrusted evidence to challenge.
"""

from .models import (
    Finding,
    FindingSeverity,
    FindingDisposition,
    FindingCategory,
    ArtifactRef,
    WorkerOutput,
    ArbiterOutput,
    StageReview,
    ReviewRequest,
    MultiStageReviewResult,
)

from .config import (
    ReviewPipelineConfig,
    StageConfig,
    StageRole,
    create_default_config,
    get_config,
    set_config,
)

from .storage import ReviewStorage

from .prompts import (
    build_worker_prompt,
    build_arbiter_prompt,
    WorkerPromptBuilder,
    ArbiterPromptBuilder,
)

from .cli import ReviewCLI

__all__ = [
    # Models
    "Finding",
    "FindingSeverity",
    "FindingDisposition",
    "FindingCategory",
    "ArtifactRef",
    "WorkerOutput",
    "ArbiterOutput",
    "StageReview",
    "ReviewRequest",
    "MultiStageReviewResult",
    # Config
    "ReviewPipelineConfig",
    "StageConfig",
    "StageRole",
    "create_default_config",
    "get_config",
    "set_config",
    # Storage
    "ReviewStorage",
    # Prompting
    "build_worker_prompt",
    "build_arbiter_prompt",
    "WorkerPromptBuilder",
    "ArbiterPromptBuilder",
    # CLI
    "ReviewCLI",
]

__version__ = "1.0.0"
