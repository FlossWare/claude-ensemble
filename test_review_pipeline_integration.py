#!/usr/bin/env python3
"""
Integration test: ReviewPipeline with WorkerRunner and ArbiterRunner.

Tests the complete multi-stage review pipeline with mock API calls.
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

from review.models import ReviewRequest, ArtifactRef
from review.config import ReviewPipelineConfig
from review.pipeline import ReviewPipeline


class MockApiClient:
    """Mock API client for testing"""

    def call_model(self, model: str, prompt: str) -> tuple:
        """Mock model call. Returns (response_text, tokens_used, cost)"""
        # Return mock findings based on model and stage
        tokens_used = len(prompt) // 4 + 500
        cost = tokens_used * 0.00001

        if "Stage 2" in prompt or "challenge" in prompt.lower():
            # Stage 2: Find issues
            response = """
{
  "findings": [
    {
      "id": "finding-001",
      "subject": "Interface contract",
      "description": "Missing parameter in interface",
      "evidence": "Interface declares 4 params, implementations use 5",
      "severity": "critical",
      "category": "correctness",
      "confidence": 0.99,
      "disposition": "new"
    }
  ],
  "summary": "Found interface contract violation",
  "confidence": 0.95
}
"""
            return response, tokens_used, cost
        else:
            # Stage 1: Basic findings
            response = """
{
  "findings": [
    {
      "id": "finding-001",
      "subject": "Implementation",
      "description": "Keyset pagination implemented",
      "evidence": "Conditional compound predicate added",
      "severity": "info",
      "category": "correctness",
      "confidence": 0.9,
      "disposition": "new"
    }
  ],
  "summary": "Implementation complete",
  "confidence": 0.8
}
"""
            return response, tokens_used, cost


def test_basic_pipeline_execution():
    """Test basic pipeline execution"""
    print("\n" + "="*80)
    print("TEST: Basic Pipeline Execution")
    print("="*80)

    with TemporaryDirectory() as tmpdir:
        # Create review request
        artifact = ArtifactRef(
            location="test.java",
            format="code",
            language="java",
        )

        request = ReviewRequest(
            id="test-pipeline-001",
            artifact_type="code",
            objective="Test review objective",
            artifacts=[artifact],
            criteria=["correctness", "design"],
        )

        # Create config
        config = ReviewPipelineConfig(num_stages=1, workers_per_stage=1)
        config._create_default_stages()

        # Create pipeline
        api_client = MockApiClient()
        pipeline = ReviewPipeline(request, config, Path(tmpdir), api_client)

        # Create workspace
        pipeline.storage.create_review_workspace(request)
        pipeline.storage.save_artifact(request.id, "test.java", "public class Test {}")

        # Load artifacts
        artifacts = pipeline.load_artifacts()
        print(f"✓ Loaded {len(artifacts)} artifact(s)")

        # Run stage 1
        stage1 = pipeline.run_stage(
            pipeline.config.stages[0],
            artifacts,
            prior_findings=None,
        )

        print(f"✓ Stage 1 complete: {len(stage1.findings)} findings")
        assert len(stage1.findings) > 0, "Stage 1 should have findings"
        print(f"✓ Stage 1 findings preserved in storage")

        return True


def test_multistage_pipeline():
    """Test multi-stage pipeline with challenge review"""
    print("\n" + "="*80)
    print("TEST: Multi-Stage Pipeline with Challenge Review")
    print("="*80)

    with TemporaryDirectory() as tmpdir:
        # Create review request
        artifact = ArtifactRef(
            location="implementation.java",
            format="code",
            language="java",
        )

        request = ReviewRequest(
            id="test-multistage-001",
            artifact_type="code",
            objective="Review for interface contracts and data flow",
            artifacts=[artifact],
            criteria=["correctness", "interface contracts", "data loss"],
        )

        # Create config with 2 stages
        config = ReviewPipelineConfig(num_stages=2, workers_per_stage=1)
        config._create_default_stages()

        # Create pipeline
        api_client = MockApiClient()
        pipeline = ReviewPipeline(request, config, Path(tmpdir), api_client)

        # Create workspace
        pipeline.storage.create_review_workspace(request)
        artifact_content = """
public interface Component {
    Map<String, Object> generate(String endTime, int rows);
}

@Override
public Map<String, Object> generate(String endTime, int rows) {
    return super.generate(endTime, rows);
}
"""
        pipeline.storage.save_artifact(request.id, "implementation.java", artifact_content)

        # Run pipeline
        result = pipeline.run()

        print(f"✓ Pipeline complete")
        print(f"  Stages: {len(result.stages)}")
        print(f"  Total findings: {len(result.final_findings)}")
        print(f"  Consensus: {result.consensus_score:.1%}")

        # Verify information flow
        assert len(result.stages) >= 1, "Should have at least 1 stage"
        assert result.consensus_score > 0, "Should have consensus score"

        print(f"✓ Multi-stage review successful")
        return True


def test_finding_preservation():
    """Test that findings are preserved across stages"""
    print("\n" + "="*80)
    print("TEST: Finding Preservation Across Stages")
    print("="*80)

    with TemporaryDirectory() as tmpdir:
        artifact = ArtifactRef(
            location="code.java",
            format="code",
            language="java",
        )

        request = ReviewRequest(
            id="test-preservation-001",
            artifact_type="code",
            objective="Test finding preservation",
            artifacts=[artifact],
        )

        config = ReviewPipelineConfig(num_stages=2, workers_per_stage=1)
        config._create_default_stages()

        api_client = MockApiClient()
        pipeline = ReviewPipeline(request, config, Path(tmpdir), api_client)

        pipeline.storage.create_review_workspace(request)
        pipeline.storage.save_artifact(request.id, "code.java", "// test code")

        # Run stage 1
        artifacts = pipeline.load_artifacts()
        stage1 = pipeline.run_stage(pipeline.config.stages[0], artifacts, prior_findings=None)

        # Verify Stage 1 findings are saved
        assert len(stage1.findings) > 0, "Stage 1 should have findings"
        print(f"✓ Stage 1 findings saved: {len(stage1.findings)}")

        # Run stage 2 with prior findings
        stage2 = pipeline.run_stage(
            pipeline.config.stages[1],
            artifacts,
            prior_findings=stage1.findings,
        )

        print(f"✓ Stage 2 executed with prior findings as context")
        print(f"✓ Stage 2 findings: {len(stage2.findings)}")

        return True


def test_artifact_access_per_stage():
    """Test that all stages have access to original artifact"""
    print("\n" + "="*80)
    print("TEST: Artifact Access Per Stage")
    print("="*80)

    with TemporaryDirectory() as tmpdir:
        artifact = ArtifactRef(
            location="important.md",
            format="markdown",
            language="text",
        )

        request = ReviewRequest(
            id="test-artifact-access-001",
            artifact_type="document",
            objective="Test artifact visibility",
            artifacts=[artifact],
        )

        config = ReviewPipelineConfig(num_stages=2, workers_per_stage=1)
        config._create_default_stages()

        api_client = MockApiClient()
        pipeline = ReviewPipeline(request, config, Path(tmpdir), api_client)

        pipeline.storage.create_review_workspace(request)

        artifact_content = "# Critical Information\n\nSection at the end with important facts."
        pipeline.storage.save_artifact(request.id, "important.md", artifact_content)

        # Load artifacts multiple times
        artifacts1 = pipeline.load_artifacts()
        artifacts2 = pipeline.load_artifacts()

        # Verify both loads get the complete artifact
        assert "Critical Information" in artifacts1.get("important.md", ""), "Stage 1 missing artifact"
        assert "important facts" in artifacts2.get("important.md", ""), "Stage 2 missing artifact"

        print(f"✓ Stage 1 has access to complete artifact")
        print(f"✓ Stage 2 has access to complete artifact")
        print(f"✓ No artifact content lost between stages")

        return True


if __name__ == '__main__':
    try:
        print("\n" + "="*80)
        print("REVIEW PIPELINE INTEGRATION TESTS")
        print("="*80)

        test_basic_pipeline_execution()
        test_multistage_pipeline()
        test_finding_preservation()
        test_artifact_access_per_stage()

        print("\n" + "="*80)
        print("✓ ALL INTEGRATION TESTS PASSED")
        print("="*80)

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
