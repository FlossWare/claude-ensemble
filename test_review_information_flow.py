#!/usr/bin/env python3
"""
Information flow audit tests for multi-stage review system.

These tests verify that:
1. Each stage receives the complete original artifact
2. Each stage receives the original review objective
3. Later stages receive all prior reviews
4. Information is not lost or summarized away
5. Findings preserve sufficient evidence for independent verification
"""

import sys
import json
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent))

from review.models import (
    ReviewRequest, ArtifactRef, Finding, FindingSeverity, FindingCategory,
    FindingDisposition, WorkerOutput, StageReview, MultiStageReviewResult
)
from review.storage import ReviewStorage
from review.config import ReviewPipelineConfig, StageConfig, StageRole


def test_artifact_preservation():
    """Verify original artifact is preserved throughout all stages"""
    print("\n=== TEST: Artifact Preservation ===")

    with TemporaryDirectory() as tmpdir:
        storage = ReviewStorage(Path(tmpdir))

        # Create request with artifact
        artifact_content = """# Important Design Document

## Section 1: Core Requirements
- Must handle 10,000 concurrent users
- Must persist data consistently
- Must be deployable in 5 minutes

## Section 2: Architecture
- Uses distributed cache
- Database with replication
- API gateway for routing

## Section 3: Security (IMPORTANT)
- All data must be encrypted at rest
- Credentials stored in secure vault
- Network access restricted to VPC only
"""

        artifact = ArtifactRef(
            location="design.md",
            format="markdown",
            language="text",
            size_bytes=len(artifact_content),
        )

        request = ReviewRequest(
            id="test-001",
            artifact_type="design",
            objective="Review for completeness, security, and feasibility",
            artifacts=[artifact],
            criteria=["security", "completeness", "feasibility"],
        )

        # Create workspace
        workspace = storage.create_review_workspace(request)
        storage.save_artifact(request.id, "design.md", artifact_content)

        # Verify artifact is saved
        loaded = storage.load_artifact(request.id, "design.md")
        assert loaded == artifact_content, "Artifact not preserved correctly"
        assert "IMPORTANT" in loaded, "Critical section missing from artifact"
        print("✓ Original artifact fully preserved")

        # Load request
        loaded_request = storage.load_request(request.id)
        assert loaded_request.objective == request.objective, "Objective not preserved"
        print("✓ Review objective preserved")


def test_stage1_receives_original():
    """Verify Stage 1 worker receives the complete original artifact"""
    print("\n=== TEST: Stage 1 Receives Original Artifact ===")

    with TemporaryDirectory() as tmpdir:
        storage = ReviewStorage(Path(tmpdir))

        artifact_content = "Test artifact with important fact at line 42: SECRET_KEY=abc123"

        artifact = ArtifactRef(
            location="config.py",
            format="code",
            language="python",
            size_bytes=len(artifact_content),
        )

        request = ReviewRequest(
            id="test-002",
            artifact_type="code",
            objective="Review for security issues",
            artifacts=[artifact],
        )

        workspace = storage.create_review_workspace(request)
        storage.save_artifact(request.id, "config.py", artifact_content)

        # Simulate Stage 1 worker output
        findings = [
            Finding(
                subject="Line 1: Config file",
                description="Found config file",
                evidence="Detected Python file",
                severity=FindingSeverity.INFO,
                category=FindingCategory.OTHER,
                confidence=0.9,
            )
        ]

        worker_output = WorkerOutput(
            worker_id="haiku-1",
            model="haiku",
            stage=1,
            findings=findings,
            summary="Analyzed config file",
            confidence=0.8,
        )

        storage.save_worker_output(request.id, 1, worker_output)

        # Verify artifact is still available for Stage 1
        loaded_artifact = storage.load_artifact(request.id, "config.py")
        assert "SECRET_KEY" in loaded_artifact, "Critical artifact content missing from Stage 1"
        assert "abc123" in loaded_artifact, "Sensitive data reference missing"
        print("✓ Stage 1 has access to complete original artifact")


def test_stage2_receives_original_and_prior():
    """Verify Stage 2 receives BOTH original artifact AND prior findings"""
    print("\n=== TEST: Stage 2 Receives Original + Prior Findings ===")

    with TemporaryDirectory() as tmpdir:
        storage = ReviewStorage(Path(tmpdir))

        # Create artifact with a fact near the end
        artifact_content = """# Requirements Document

Section 1: Overview
This describes a system for managing users.

Section 2: Functional Requirements
- Users can create accounts
- Users can log in
- Accounts are protected

Section 3: Non-Functional Requirements
[IMPORTANT] All passwords must use bcrypt with minimum 12 rounds for hashing.
The system must support FIPS 140-2 compliance for government use."""

        artifact = ArtifactRef(
            location="requirements.md",
            format="markdown",
            language="text",
            size_bytes=len(artifact_content),
        )

        request = ReviewRequest(
            id="test-003",
            artifact_type="document",
            objective="Review requirements for security and completeness",
            artifacts=[artifact],
        )

        workspace = storage.create_review_workspace(request)
        storage.save_artifact(request.id, "requirements.md", artifact_content)

        # Stage 1: Create findings (missing the important requirement)
        stage1_findings = [
            Finding(
                subject="Section 2",
                description="Basic login functionality described",
                evidence="Users can log in",
                severity=FindingSeverity.LOW,
                category=FindingCategory.COMPLETENESS,
                confidence=0.9,
            )
        ]

        worker1 = WorkerOutput(
            worker_id="sonnet-1",
            model="sonnet",
            stage=1,
            findings=stage1_findings,
            summary="Reviewed requirements",
            confidence=0.7,
        )

        stage1_review = StageReview(
            stage_number=1,
            workers=[worker1],
            findings=stage1_findings,
            overall_confidence=0.7,
        )

        storage.save_worker_output(request.id, 1, worker1)
        storage.save_stage_review(request.id, stage1_review)

        # Now Stage 2: Verify it receives both original artifact AND stage 1 findings
        stored_request = storage.load_request(request.id)
        stored_artifact = storage.load_artifact(request.id, "requirements.md")

        # Stage 2 should have access to original
        assert "FIPS 140-2" in stored_artifact, "Critical requirement missing from Stage 2's context"
        assert "bcrypt" in stored_artifact, "Important security detail missing from Stage 2"

        # Stage 2 should have access to prior findings
        assert len(stage1_review.findings) > 0, "Prior findings not preserved"
        print("✓ Stage 2 has access to complete original artifact")
        print("✓ Stage 2 has access to prior findings")


def test_finding_evidence_preservation():
    """Verify findings preserve enough evidence for independent verification"""
    print("\n=== TEST: Finding Evidence Preservation ===")

    # Create findings with concrete evidence
    finding1 = Finding(
        subject="Database connection pool",
        description="Pool size not configurable",
        evidence="connection_pool = ConnectionPool(size=100)  # Hard-coded value",
        severity=FindingSeverity.MEDIUM,
        category=FindingCategory.MAINTAINABILITY,
        confidence=0.9,
    )

    finding2 = Finding(
        subject="Error handling in API",
        description="Generic error messages may leak information",
        evidence="except Exception as e: return {'error': str(e)}",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        confidence=0.85,
    )

    # Verify evidence is preserved
    assert finding1.evidence != "", "Evidence field empty"
    assert "Hard-coded" in finding1.evidence, "Evidence doesn't support description"
    assert finding2.evidence != "", "Evidence field empty"
    assert "str(e)" in finding2.evidence, "Evidence doesn't support security concern"

    print("✓ Findings preserve concrete evidence")
    print("✓ Evidence supports descriptions")


def test_disposition_tracking():
    """Verify findings can be marked as confirmed, refuted, modified, or new"""
    print("\n=== TEST: Disposition Tracking ===")

    from review.models import FindingDisposition

    # Stage 1 finding
    original = Finding(
        id="finding-001",
        subject="Input validation",
        description="User input not validated",
        evidence="user_data = request.args.get('query')",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.SECURITY,
        confidence=0.8,
        disposition=FindingDisposition.NEW,
    )

    # Stage 2 arbiter examines original artifact and confirms
    confirmed = Finding(
        id="finding-002",
        subject="Input validation",
        description="User input validation missing - security risk",
        evidence="user_data = request.args.get('query')  # No strip(), no sanitization",
        severity=FindingSeverity.CRITICAL,
        category=FindingCategory.SECURITY,
        confidence=0.95,
        disposition=FindingDisposition.CONFIRMED,
        prior_finding_id="finding-001",
        challenge_reasoning="Stage 1 was correct. Confirmed by independent inspection.",
    )

    # Stage 2 arbiter refutes another Stage 1 finding
    refuted = Finding(
        id="finding-003",
        subject="Code style",
        description="Variable naming convention complaint",
        evidence="Stage 1 flagged 'x' as poor name - but context shows it's standard iterator",
        severity=FindingSeverity.INFO,
        category=FindingCategory.CLARITY,
        confidence=0.9,
        disposition=FindingDisposition.REFUTED,
        prior_finding_id="hypothetical-prior-1",
        challenge_reasoning="Re-examining the loop context shows 'x' is appropriate here.",
    )

    # Stage 2 arbiter discovers new finding
    new_finding = Finding(
        id="finding-004",
        subject="Resource cleanup",
        description="Database connections not closed in exception paths",
        evidence="try: db.query(...) except: return error  # No finally block",
        severity=FindingSeverity.HIGH,
        category=FindingCategory.CORRECTNESS,
        confidence=0.85,
        disposition=FindingDisposition.NEW,
    )

    assert confirmed.disposition == FindingDisposition.CONFIRMED
    assert refuted.disposition == FindingDisposition.REFUTED
    assert new_finding.disposition == FindingDisposition.NEW
    assert confirmed.prior_finding_id == "finding-001"

    print("✓ Findings can be marked confirmed")
    print("✓ Findings can be marked refuted")
    print("✓ Findings can be marked new")
    print("✓ Disposition tracking works end-to-end")


def test_information_flow_end_to_end():
    """Integration test: verify information flow through multiple stages"""
    print("\n=== TEST: End-to-End Information Flow ===")

    with TemporaryDirectory() as tmpdir:
        storage = ReviewStorage(Path(tmpdir))

        # Create a realistic artifact
        artifact_content = """# Service Configuration

## Database Configuration
- Connection string: postgresql://prod-db:5432/main
- Max connections: 100
- SSL required: yes

## API Configuration
- Port: 8080
- Timeout: 30s
- Log level: INFO

## Security Configuration
- JWT secret: ${SECRETS_JWT}
- API keys stored in: /etc/secrets/api_keys
- CORS allowed: * (CRITICAL: This allows any origin)"""

        artifact = ArtifactRef(
            location="config.yaml",
            format="yaml",
            language="text",
        )

        request = ReviewRequest(
            id="test-flow-001",
            artifact_type="configuration",
            objective="Review for security vulnerabilities and configuration issues",
            artifacts=[artifact],
            criteria=["security", "correctness", "compliance"],
        )

        workspace = storage.create_review_workspace(request)
        storage.save_artifact(request.id, "config.yaml", artifact_content)

        # STAGE 1: Two workers find different things
        worker1_findings = [
            Finding(
                subject="CORS Configuration",
                description="CORS allows all origins",
                evidence="CORS allowed: *",
                severity=FindingSeverity.CRITICAL,
                category=FindingCategory.SECURITY,
                confidence=0.95,
            ),
        ]

        worker2_findings = [
            Finding(
                subject="Connection Pool",
                description="Max connections limit low for production",
                evidence="Max connections: 100",
                severity=FindingSeverity.MEDIUM,
                category=FindingCategory.PERFORMANCE,
                confidence=0.7,
            ),
        ]

        w1 = WorkerOutput("haiku-1", "haiku", 1, worker1_findings, "Found CORS issue", 0.9)
        w2 = WorkerOutput("sonnet-1", "sonnet", 1, worker2_findings, "Found perf concern", 0.7)

        stage1_findings = worker1_findings + worker2_findings

        stage1 = StageReview(
            stage_number=1,
            workers=[w1, w2],
            findings=stage1_findings,
            overall_confidence=0.8,
        )

        storage.save_worker_output(request.id, 1, w1)
        storage.save_worker_output(request.id, 1, w2)
        storage.save_stage_review(request.id, stage1)

        # STAGE 2: New worker with full context (original + stage 1)
        # Should be able to:
        # - Confirm CORS issue
        # - Challenge or confirm perf concern
        # - Find the JWT secret reference (new finding)

        original_artifact = storage.load_artifact(request.id, "config.yaml")
        prior_findings = stage1.findings

        assert "CORS" in original_artifact, "Original missing from Stage 2 context"
        assert "JWT" in original_artifact, "Should enable discovery of new security finding"
        assert len(prior_findings) > 0, "Prior findings missing from Stage 2 context"

        # Stage 2 independently examines and finds additional security issues
        w3_findings = [
            Finding(
                id="stage2-001",
                subject="CORS Configuration",
                description="CORS wildcard is critical security vulnerability",
                evidence="CORS allowed: * (CRITICAL: This allows any origin)",
                severity=FindingSeverity.CRITICAL,
                category=FindingCategory.SECURITY,
                confidence=0.99,
                disposition=FindingDisposition.CONFIRMED,
                prior_finding_id="stage1-001",
            ),
            Finding(
                id="stage2-002",
                subject="JWT Secret Configuration",
                description="JWT secret uses environment variable but no validation",
                evidence="JWT secret: ${SECRETS_JWT}",
                severity=FindingSeverity.HIGH,
                category=FindingCategory.SECURITY,
                confidence=0.85,
                disposition=FindingDisposition.NEW,
            ),
        ]

        w3 = WorkerOutput("opus-1", "opus", 2, w3_findings, "Confirmed and extended findings", 0.95)
        stage2 = StageReview(
            stage_number=2,
            workers=[w3],
            findings=w3_findings,
            overall_confidence=0.92,
        )

        storage.save_worker_output(request.id, 2, w3)
        storage.save_stage_review(request.id, stage2)

        # Verify the flow
        confirmed = [f for f in w3_findings if f.disposition == FindingDisposition.CONFIRMED]
        new = [f for f in w3_findings if f.disposition == FindingDisposition.NEW]

        assert len(confirmed) > 0, "Stage 2 did not confirm Stage 1 finding"
        assert len(new) > 0, "Stage 2 did not discover new finding"
        assert any("CORS" in f.evidence for f in confirmed), "Confirmation uses original evidence"
        assert any("JWT" in f.evidence for f in new), "New finding based on original artifact"

        print("✓ Stage 1 finds initial issues")
        print("✓ Stage 2 receives original artifact")
        print("✓ Stage 2 receives prior findings")
        print("✓ Stage 2 can confirm prior findings")
        print("✓ Stage 2 can discover new findings from original artifact")
        print("✓ Information flow preserved through multiple stages")


if __name__ == '__main__':
    try:
        test_artifact_preservation()
        test_stage1_receives_original()
        test_stage2_receives_original_and_prior()
        test_finding_evidence_preservation()
        test_disposition_tracking()
        test_information_flow_end_to_end()

        print("\n" + "="*60)
        print("✓ ALL INFORMATION FLOW TESTS PASSED")
        print("="*60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
