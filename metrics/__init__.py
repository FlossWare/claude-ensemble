"""
Prompt Performance Metrics System
==================================

Adaptive compression/caching tuning through workflow-based performance tracking.

Modules:
- classifier: Identify workflow type per API call
- logger: Record compression/cache effectiveness metrics
- analyzer: Find patterns in which workflows benefit from compression/caching
- tuner: Auto-generate configuration recommendations
- aggregator: Daily/weekly performance summaries

Quick Start:
    from metrics.classifier import WorkflowClassifier
    from metrics.logger import PerformanceLogger

    classifier = WorkflowClassifier()
    logger = PerformanceLogger()

    # Classify a workflow
    workflow_type = classifier.classify(task_description="Code review for PR #123")

    # Log performance metrics
    logger.log_call(
        workflow_type=workflow_type,
        compression_original=12500,
        compression_output=7300,
        cache_hit=True,
        quality_score=0.94
    )
"""

__version__ = "1.0.0-phase1"
__all__ = ["classifier", "logger", "analyzer", "tuner", "aggregator"]
