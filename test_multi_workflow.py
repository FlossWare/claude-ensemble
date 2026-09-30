#!/usr/bin/env python3
"""
Test multi-solve + multi-multi-review on GitHub issue #87
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrate import SolveReviewOrchestrator, OrchestrationConfig
from review.models import ReviewRequest, ArtifactRef

# Issue #87: GraphDB Service for Thompson
ISSUE_87_DESCRIPTION = """
## ARCH: Simple GraphDB Service for Thompson relationship queries

Build a lightweight, file-based graph database service following the pattern of Memory Service and Learning Service.

**Purpose:**
Enable Thompson and arbitration system to query relationships between models, tasks, and outcomes.

**Requirements:**
- Graph Storage (JSONL): nodes.jsonl and edges.jsonl
- REST API Endpoints: add-node, add-edge, node lookup, traverse, query
- Thompson Integration: query relationships to optimize model routing
- No external dependencies (optional: NetworkX)

**Design:**
- Service daemon: graph_service.py
- REST boundary: ensemble_server.py routes /graph/* endpoints
- File-based storage: JSONL for nodes and edges
- Single-threaded: like Learning Service
- SimpleGraphDB class: in-memory graph + file persistence

**Acceptance Criteria:**
- Graph service daemon running
- Nodes and edges stored to JSONL
- REST endpoints functional
- Traverse/query operations working
- Thompson bridge populates graph from arbitration outcomes
- Multi-phase review + production deployment
"""

def main():
    print("\n" + "=" * 150)
    print("TESTING MULTI-SOLVE + MULTI-MULTI-REVIEW")
    print("Issue #87: GraphDB Service for Thompson Relationship Queries")
    print("=" * 150)
    print()

    # Create orchestrator with:
    # - 2 solve stages (solve, meta-solve)
    # - 3 review stages (review, meta-review, meta-meta-review)
    config = OrchestrationConfig(
        review_stages=3,      # review, meta-review, meta-meta-review
        solve_stages=2,       # solve, meta-solve
        workers_per_stage=2
    )

    workspace = Path("/tmp/issue_87_workflow")
    workspace.mkdir(exist_ok=True)

    orchestrator = SolveReviewOrchestrator(config, workspace)

    # Step 1: Define problems to solve
    print("▶ PHASE 1: MULTI-SOLVE (2 stages)")
    print("-" * 150)
    problems = [
        "Design file-based graph storage (JSONL nodes.jsonl and edges.jsonl)",
        "Build REST API endpoints for graph operations (add-node, add-edge, traverse, query)",
        "Implement Thompson integration to populate graph from arbitration outcomes",
        "Create single-threaded service daemon following Memory Service pattern"
    ]

    print(f"\nProblems to solve: {len(problems)}")
    for i, problem in enumerate(problems, 1):
        print(f"  {i}. {problem}")
    print()

    # Run multi-solve
    print("Running 2-stage solve pipeline...")
    solve_result = orchestrator.run_solve(
        problems=problems,
        context="GraphDB service architecture for Thompson routing optimization",
        objective="Provide secure, performant, file-based solutions that integrate with Thompson"
    )
    print(f"✓ Solve complete: {solve_result['solutions'].num_stages} stages, {solve_result['solutions'].total_tokens:,} tokens")
    print()

    # Step 2: Review the proposed solutions
    print("▶ PHASE 2: MULTI-MULTI-REVIEW (3 stages)")
    print("-" * 150)

    artifact = ArtifactRef(
        location="issue_87_solutions.txt",
        format="text",
        language="english",
        size_bytes=len(ISSUE_87_DESCRIPTION)
    )
    artifact._content = ISSUE_87_DESCRIPTION

    print("Running 3-stage review pipeline (review → meta-review → meta-meta-review)...")
    review_result = orchestrator.run_review(
        artifact,
        objective="Validate and evaluate proposed solutions against requirements",
        criteria=[
            "Architectural soundness (file-based JSONL pattern consistency)",
            "API completeness (all endpoints functional)",
            "Thompson integration feasibility",
            "Implementation effort vs. value",
            "Separation of concerns (daemon vs. REST boundary)",
            "Production readiness"
        ]
    )
    stages_count = len(review_result['pipeline'].stage_costs)
    total_review_tokens = sum(sc.total_tokens for sc in review_result['pipeline'].stage_costs) if stages_count > 0 else 0
    print(f"✓ Review complete: {stages_count} stages, {total_review_tokens:,} tokens")
    print()

    # Step 3: Generate combined report
    print("▶ GENERATING COMBINED REPORT")
    print("-" * 150)
    print()

    report = orchestrator.generate_combined_report()
    print(report)

    # Save report to file
    report_path = workspace / "combined_report.txt"
    with open(report_path, 'w') as f:
        f.write(report)
    print()
    print(f"✓ Report saved to: {report_path}")


if __name__ == "__main__":
    main()
