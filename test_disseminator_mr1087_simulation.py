#!/usr/bin/env python3
"""
End-to-end multi-stage review test simulating disseminator MR 1087.

This test demonstrates how a proper multi-stage review would have caught
the 4 critical issues missed in the initial implementation:

1. Interface signature mismatch (lastRecordId parameter)
2. Data loss in DownloadsSourceGeneratePollQueryComponent
3. Bracket syntax error in Solr query ({...] instead of {...})
4. Silent failure on missing 'id' field

Stage 1: Initial implementation (as Claude wrote it)
Stage 2: Independent challenge review (what should have happened)

All 4 issues should be discovered as NEW findings in Stage 2.
"""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from review.models import (
    ReviewRequest, ArtifactRef, Finding, FindingSeverity, FindingCategory,
    FindingDisposition, WorkerOutput, ArbiterOutput, StageReview,
    MultiStageReviewResult
)
from review.storage import ReviewStorage


def test_disseminator_mr1087_stage1_initial_implementation():
    """
    Stage 1: What Claude initially implemented

    Findings: Basic functionality works, but misses critical issues
    """
    print("\n" + "="*80)
    print("STAGE 1: INITIAL IMPLEMENTATION (MR 1087 as submitted)")
    print("="*80)

    # Simulated Stage 1 findings (basic, misses critical issues)
    stage1_findings = [
        Finding(
            id="stage1-001",
            subject="RecrawlCloudAccessPollQueryComponent",
            description="Compound predicate implementation for keyset pagination",
            evidence="Added conditional: if (useCompoundPredicate && StringUtils.isNotBlank(lastRecordId))",
            severity=FindingSeverity.INFO,
            category=FindingCategory.CORRECTNESS,
            confidence=0.9,
            disposition=FindingDisposition.NEW,
        ),
        Finding(
            id="stage1-002",
            subject="Query assembly",
            description="Uses StringTransformEnum.ESCAPE to sanitize IDs",
            evidence="String escapedId = StringTransformEnum.ESCAPE.transform(lastRecordId);",
            severity=FindingSeverity.LOW,
            category=FindingCategory.SECURITY,
            confidence=0.85,
            disposition=FindingDisposition.NEW,
        ),
    ]

    worker1 = WorkerOutput(
        worker_id="haiku-stage1",
        model="haiku",
        stage=1,
        findings=stage1_findings,
        summary="Implemented keyset pagination compound predicates for 4 components",
        confidence=0.8,
    )

    stage1_review = StageReview(
        stage_number=1,
        workers=[worker1],
        findings=stage1_findings,
        overall_confidence=0.8,
    )

    print(f"\nStage 1 Findings: {len(stage1_findings)}")
    for f in stage1_findings:
        print(f"  - [{f.severity.value.upper()}] {f.subject}: {f.description}")

    return stage1_review


def test_disseminator_mr1087_stage2_challenge_review():
    """
    Stage 2: Independent challenge review

    This is what SHOULD happen with proper multi-stage review.
    Stage 2 independently examines the code and finds 4 critical issues.
    """
    print("\n" + "="*80)
    print("STAGE 2: INDEPENDENT CHALLENGE REVIEW")
    print("="*80)

    # Stage 2 findings: 4 critical issues discovered through independent examination
    stage2_findings = [
        Finding(
            id="stage2-001",
            subject="GeneratePollQueryComponent interface",
            description="Interface signature missing lastRecordId parameter",
            evidence="""Interface declares:
    public Map<String, Object> generate(String endTime, String lastRecordTimestamp, int start, int rows);
But implementations call with 5 parameters including lastRecordId.
This violates the interface contract and could cause runtime errors.""",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.CORRECTNESS,
            confidence=0.99,
            disposition=FindingDisposition.NEW,
            impact="Contract violation between interface and implementations. Could cause ClassCastException or silent method not found errors.",
            recommendation="Add lastRecordId parameter to interface signature to match all implementations.",
        ),

        Finding(
            id="stage2-002",
            subject="DownloadsSourceGeneratePollQueryComponent",
            description="Missing parameter in method override - silent data loss",
            evidence="""Override method signature:
    public Map<String, Object> generate(String endTime, String lastRecordTimestamp, int start, int rows) {
        Map<String, Object> map = super.generate(endTime, lastRecordTimestamp, start, rows);
    }

The lastRecordId parameter is NOT in the signature and NOT passed to super.generate().
This means keyset pagination state is lost for HTTP data sources.""",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.CORRECTNESS,
            confidence=0.98,
            disposition=FindingDisposition.NEW,
            impact="Silent data loss: HTTP API pagination loses keyset state. Will silently revert to offset pagination without operator awareness.",
            recommendation="Add lastRecordId parameter to override signature AND pass it to parent method.",
        ),

        Finding(
            id="stage2-003",
            subject="NrtGeneratePollQueryComponent Solr query syntax",
            description="Invalid bracket syntax in range query: id:{escapedId TO *]",
            evidence="""Current code:
    baseQuery += " AND id:{" + escapedId + " TO *]";

Solr bracket syntax error:
- Opening bracket: { (exclusive start)
- Closing bracket: ] (inclusive end)
- MISMATCH: Solr requires either {} or [], not {]

Correct syntax:
    baseQuery += " AND id:{" + escapedId + " TO *}";""",
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.CORRECTNESS,
            confidence=0.99,
            disposition=FindingDisposition.NEW,
            impact="Malformed Solr query. Solr parser rejects the range query syntax. Keyset pagination fails completely.",
            recommendation="Change closing bracket from ] to } to match opening { bracket.",
        ),

        Finding(
            id="stage2-004",
            subject="AbstractJsonResponseToSdProcessor - missing null check",
            description="No validation if Solr documents missing 'id' field",
            evidence="""Current code:
    String lastRecordId = (String) lastDoc.getFieldValue("id");
    params.setLastRecordId(lastRecordId);  // May be null

If 'id' field is missing:
- lastRecordId becomes null
- Keyset pagination silently reverts to offset pagination
- Operators have NO indication the pagination mode changed
- Silent degradation in performance and consistency""",
            severity=FindingSeverity.HIGH,
            category=FindingCategory.MAINTAINABILITY,
            confidence=0.95,
            disposition=FindingDisposition.NEW,
            impact="Silent failure: Operators won't know pagination reverted to offset mode. Makes debugging impossible.",
            recommendation="Add null-safety validation. Log warning if 'id' field missing to alert operators.",
        ),

        # Also confirm Stage 1 finding about escaping
        Finding(
            id="stage2-005",
            subject="RecrawlCloudAccessPollQueryComponent",
            description="Compound predicate implementation is correctly using StringTransformEnum.ESCAPE",
            evidence="String escapedId = StringTransformEnum.ESCAPE.transform(lastRecordId); correctly sanitizes ID",
            severity=FindingSeverity.LOW,
            category=FindingCategory.SECURITY,
            confidence=0.9,
            disposition=FindingDisposition.CONFIRMED,
            prior_finding_id="stage1-002",
            challenge_reasoning="Independent inspection confirms proper escaping prevents Solr injection.",
        ),
    ]

    worker2 = WorkerOutput(
        worker_id="opus-stage2",
        model="opus",
        stage=2,
        findings=stage2_findings,
        summary="Found 4 critical issues: interface contract violation, data loss, Solr syntax error, missing validation",
        confidence=0.97,
    )

    stage2_review = StageReview(
        stage_number=2,
        workers=[worker2],
        findings=stage2_findings,
        overall_confidence=0.97,
    )

    print(f"\nStage 2 Findings: {len(stage2_findings)}")
    critical = [f for f in stage2_findings if f.severity == FindingSeverity.CRITICAL]
    high = [f for f in stage2_findings if f.severity == FindingSeverity.HIGH]

    print(f"\n  CRITICAL ({len(critical)}):")
    for f in critical:
        print(f"    • {f.subject}")
        print(f"      {f.description}")

    print(f"\n  HIGH ({len(high)}):")
    for f in high:
        print(f"    • {f.subject}")
        print(f"      {f.description}")

    confirmed = [f for f in stage2_findings if f.disposition == FindingDisposition.CONFIRMED]
    print(f"\n  CONFIRMED from Stage 1 ({len(confirmed)}):")
    for f in confirmed:
        print(f"    ✓ {f.subject} (was: {f.prior_finding_id})")

    return stage2_review


def test_disseminator_mr1087_synthesize_result():
    """Synthesize final multi-stage result"""
    print("\n" + "="*80)
    print("FINAL SYNTHESIS")
    print("="*80)

    with TemporaryDirectory() as tmpdir:
        storage = ReviewStorage(Path(tmpdir))

        # Original artifact
        artifact_content = """
// MR 1087: Keyset Pagination Implementation

// Interface (MISSING parameter)
public interface GeneratePollQueryComponent {
    public Map<String, Object> generate(String endTime, String lastRecordTimestamp, int start, int rows);
    // Missing: String lastRecordId parameter
}

// DownloadsSourceGeneratePollQueryComponent (DATA LOSS)
@Override
public Map<String, Object> generate(String endTime, String lastRecordTimestamp, int start, int rows) {
    // Missing lastRecordId parameter
    Map<String, Object> map = super.generate(endTime, lastRecordTimestamp, start, rows);
    // Parameter lost - not passed to parent
}

// NrtGeneratePollQueryComponent (BRACKET SYNTAX ERROR)
if (useCompoundPredicate && StringUtils.isNotBlank(lastRecordId)) {
    String escapedId = StringTransformEnum.ESCAPE.transform(lastRecordId);
    baseQuery += " AND id:{" + escapedId + " TO *]";  // MISMATCH: { with ]
}

// AbstractJsonResponseToSdProcessor (MISSING VALIDATION)
String lastRecordId = (String) lastDoc.getFieldValue("id");
params.setLastRecordId(lastRecordId);  // null check missing
"""

        artifact = ArtifactRef(
            location="MR1087_keyset_pagination.java",
            format="code",
            language="java",
        )

        request = ReviewRequest(
            id="disseminator-mr1087",
            artifact_type="code",
            objective="Review keyset pagination implementation for correctness, interface contracts, and edge case handling",
            artifacts=[artifact],
            criteria=["correctness", "interface contracts", "data flow", "null safety", "Solr syntax"],
        )

        workspace = storage.create_review_workspace(request)
        storage.save_artifact(request.id, "MR1087_keyset_pagination.java", artifact_content)

        # Build full result
        stage1 = test_disseminator_mr1087_stage1_initial_implementation()
        stage2 = test_disseminator_mr1087_stage2_challenge_review()

        storage.save_stage_review(request.id, stage1)
        storage.save_stage_review(request.id, stage2)

        # Synthesize findings
        all_findings = stage1.findings + stage2.findings
        critical = [f for f in all_findings if f.severity == FindingSeverity.CRITICAL]
        high = [f for f in all_findings if f.severity == FindingSeverity.HIGH]
        new_findings = [f for f in all_findings if f.disposition == FindingDisposition.NEW]
        confirmed_findings = [f for f in all_findings if f.disposition == FindingDisposition.CONFIRMED]

        result = MultiStageReviewResult(
            request=request,
            stages=[stage1, stage2],
            final_findings=all_findings,
            consensus_score=0.93,
            open_questions=[
                "Are there other missing id field cases beyond the ones identified?",
                "Should we add explicit logging for pagination mode switches?",
            ],
            next_steps=[
                f"FIX IMMEDIATELY: Address {len(critical)} critical issues",
                f"Review and fix {len(high)} high-severity issues",
                "Add tests for all edge cases",
                "Update interface documentation",
            ],
        )

        storage.save_final_result(request.id, result)

        print(f"\nFinal Synthesis:")
        print(f"  Total Findings: {len(all_findings)}")
        print(f"  Critical: {len(critical)} ⚠️ {[f.subject for f in critical]}")
        print(f"  High: {len(high)} ⚠️")
        print(f"  New (Stage 2): {len(new_findings)}")
        print(f"  Confirmed: {len(confirmed_findings)} ✓")
        print(f"\n  Next Steps:")
        for step in result.next_steps:
            print(f"    → {step}")

        return result


def test_information_recovery():
    """
    Verify that structured findings preserve enough information
    for independent verification of all 4 issues.
    """
    print("\n" + "="*80)
    print("INFORMATION RECOVERY TEST")
    print("="*80)
    print("\nCan a later reviewer independently verify each finding from the evidence?")

    stage2 = test_disseminator_mr1087_stage2_challenge_review()

    for finding in stage2.findings:
        if finding.severity == FindingSeverity.CRITICAL:
            # Check if evidence is sufficient for independent verification
            has_evidence = len(finding.evidence) > 50
            has_location = finding.subject != ""
            has_impact = len(finding.impact) > 0
            has_fix = len(finding.recommendation) > 0

            status = "✓" if all([has_evidence, has_location, has_impact, has_fix]) else "✗"
            print(f"\n{status} {finding.subject}")
            print(f"   Evidence: {len(finding.evidence)} chars")
            print(f"   Can explain impact: {has_impact}")
            print(f"   Has actionable fix: {has_fix}")

            if not all([has_evidence, has_location, has_impact, has_fix]):
                print(f"   ⚠️  MISSING INFORMATION for independent verification")


if __name__ == '__main__':
    try:
        print("\n" + "="*80)
        print("DISSEMINATOR MR 1087: MULTI-STAGE REVIEW SIMULATION")
        print("="*80)
        print("\nThis test demonstrates how a 2-stage review would have caught")
        print("the 4 critical issues missed in the initial MR submission:")
        print("  1. Interface signature mismatch")
        print("  2. Data loss in override")
        print("  3. Bracket syntax error")
        print("  4. Missing null validation")

        test_disseminator_mr1087_stage1_initial_implementation()
        test_disseminator_mr1087_stage2_challenge_review()
        result = test_disseminator_mr1087_synthesize_result()
        test_information_recovery()

        print("\n" + "="*80)
        print("✓ MULTI-STAGE REVIEW SIMULATION COMPLETE")
        print("="*80)
        print("\nKey insights:")
        print("  • Stage 1 (initial impl): Found basic correct things, missed critical issues")
        print("  • Stage 2 (challenge): Independently examined, found all 4 critical issues")
        print("  • Information preserved: All findings have evidence, impact, recommendations")
        print("  • Dispositions tracked: Confirmed/new findings are clearly marked")
        print("\nThis is what the claude-ensemble review system should achieve.")

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
