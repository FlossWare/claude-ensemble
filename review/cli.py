#!/usr/bin/env python3
"""
CLI interface for multi-stage reviews.

Supports arbitrary stage counts via "meta-" prefixes:
  review artifact           (1 stage)
  meta-review artifact     (2 stages)
  meta-meta-review artifact (3 stages)
  meta-meta-meta-review artifact (4 stages)
  ... etc

Also supports:
  review --stages 5 artifact
  review --tiers 5 artifact
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import Optional

from .models import ReviewRequest, ArtifactRef
from .config import ReviewPipelineConfig
from .pipeline import ReviewPipeline

logger = logging.getLogger(__name__)


class ReviewCLI:
    """CLI handler for multi-stage reviews"""

    def __init__(self):
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        """Build argument parser"""
        parser = argparse.ArgumentParser(
            description="Multi-stage review system for any artifact",
            epilog="""
Examples:
  review ./code.py                    # Single-stage review
  meta-review ./design.md             # Two-stage review
  meta-meta-review PR#123             # Three-stage review
  review --stages 5 ./architecture    # 5-stage review
  review --workers 3 --stages 2 ./doc # 3 workers, 2 stages
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        parser.add_argument(
            "artifact",
            help="Artifact to review (file path, PR#, URL, etc.)",
        )

        parser.add_argument(
            "--stages",
            "--tiers",
            type=int,
            default=None,
            help="Number of review stages (default: auto-detect from command name)",
        )

        parser.add_argument(
            "--workers",
            type=int,
            default=3,
            help="Workers per stage (default: 3)",
        )

        parser.add_argument(
            "--objective",
            "-o",
            default=None,
            help="Review objective/question (optional, will be inferred from artifact type)",
        )

        parser.add_argument(
            "--artifact-type",
            "-t",
            default=None,
            help="Artifact type: code, document, design, proposal, etc. (optional, auto-detected)",
        )

        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Verbose output",
        )

        parser.add_argument(
            "--output",
            "-o",
            default=None,
            help="Output file for results (JSON)",
        )

        parser.add_argument(
            "--workspace",
            "-w",
            default=None,
            help="Workspace directory for review state (default: /tmp/review-{id})",
        )

        return parser

    def run(self, args: Optional[list] = None) -> int:
        """Execute CLI"""
        parsed = self.parser.parse_args(args)

        if parsed.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        try:
            # Auto-detect stage count from command name if not specified
            if parsed.stages is None:
                parsed.stages = self._detect_stages_from_argv()

            logger.info(f"Starting {parsed.stages}-stage review")
            logger.info(f"Artifact: {parsed.artifact}")
            logger.info(f"Workers per stage: {parsed.workers}")

            # Execute review
            result, pipeline = self._execute_review(
                artifact=parsed.artifact,
                stages=parsed.stages,
                workers=parsed.workers,
                objective=parsed.objective,
                artifact_type=parsed.artifact_type,
                workspace=parsed.workspace,
            )

            # Output results
            self._output_results(result, parsed.output, pipeline)

            return 0

        except Exception as e:
            logger.error(f"Review failed: {e}", exc_info=parsed.verbose)
            return 1

    def _detect_stages_from_argv(self) -> int:
        """Detect stage count from command name"""
        # Get the script name (review, meta-review, meta-meta-review, etc.)
        script_name = Path(sys.argv[0]).stem

        # Count "meta-" prefixes
        meta_count = script_name.count("meta-")

        # Stage count = meta_count + 1
        # review = 0 metas + 1 = 1 stage
        # meta-review = 1 meta + 1 = 2 stages
        # meta-meta-review = 2 metas + 1 = 3 stages
        stages = meta_count + 1

        logger.info(f"Detected {stages} stage(s) from command: {script_name}")
        return stages

    def _execute_review(
        self,
        artifact: str,
        stages: int,
        workers: int,
        objective: Optional[str],
        artifact_type: Optional[str],
        workspace: Optional[str],
    ) -> tuple:
        """Execute the multi-stage review. Returns (result, pipeline)"""
        # Create workspace
        if not workspace:
            import uuid
            workspace = f"/tmp/review-{uuid.uuid4().hex[:12]}"

        workspace_path = Path(workspace)
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Detect artifact type if not specified
        if not artifact_type:
            artifact_type = self._detect_artifact_type(artifact)

        # Build objective if not specified
        if not objective:
            objective = self._build_objective(artifact, artifact_type)

        # Load artifact content
        artifact_content = self._load_artifact(artifact)

        # Create review request
        artifact_ref = ArtifactRef(
            location=artifact,
            format=self._get_format(artifact),
            language=self._get_language(artifact),
            size_bytes=len(artifact_content),
        )

        request = ReviewRequest(
            artifact_type=artifact_type,
            objective=objective,
            artifacts=[artifact_ref],
            criteria=self._get_criteria(artifact_type),
        )

        # Create config
        config = ReviewPipelineConfig(
            num_stages=stages,
            workers_per_stage=workers,
        )
        config._create_default_stages()

        # Create and run pipeline
        # TODO: Connect to real API client
        pipeline = ReviewPipeline(request, config, workspace_path, api_client=None)

        pipeline.storage.create_review_workspace(request)
        pipeline.storage.save_artifact(request.id, Path(artifact).name, artifact_content)

        result = pipeline.run()

        logger.info(f"Review complete: {len(result.final_findings)} findings")
        return result, pipeline

    def _load_artifact(self, artifact: str) -> str:
        """Load artifact content"""
        if artifact.startswith("PR#"):
            # TODO: Load from GitHub
            raise NotImplementedError("GitHub PR loading not yet implemented")
        elif artifact.startswith("http"):
            # TODO: Load from URL
            raise NotImplementedError("URL loading not yet implemented")
        else:
            # Load from file
            artifact_path = Path(artifact)
            if not artifact_path.exists():
                raise FileNotFoundError(f"Artifact not found: {artifact}")
            return artifact_path.read_text()

    def _detect_artifact_type(self, artifact: str) -> str:
        """Detect artifact type from path/identifier"""
        if artifact.startswith("PR#"):
            return "code"
        elif "architecture" in artifact.lower() or "adr" in artifact.lower():
            return "architecture"
        elif "design" in artifact.lower():
            return "design"
        elif "docs" in artifact.lower() or artifact.endswith(".md"):
            return "document"
        elif artifact.endswith(".sql"):
            return "database-schema"
        elif artifact.endswith((".py", ".js", ".go", ".java", ".ts")):
            return "code"
        else:
            return "generic"

    def _build_objective(self, artifact: str, artifact_type: str) -> str:
        """Build review objective based on artifact type"""
        artifact_name = Path(artifact).name if not artifact.startswith("PR#") else artifact

        objectives = {
            "code": f"Review {artifact_name} for correctness, security, and best practices",
            "document": f"Review {artifact_name} for clarity, completeness, and accuracy",
            "design": f"Review {artifact_name} for feasibility, clarity, and alignment with requirements",
            "architecture": f"Review {artifact_name} for scalability, maintainability, and failure modes",
            "database-schema": f"Review {artifact_name} for normalization, performance, and data integrity",
            "generic": f"Review {artifact_name} comprehensively",
        }

        return objectives.get(artifact_type, f"Review {artifact_name}")

    def _get_format(self, artifact: str) -> str:
        """Get artifact format"""
        if artifact.endswith(".py"):
            return "python"
        elif artifact.endswith((".js", ".ts")):
            return "javascript"
        elif artifact.endswith(".go"):
            return "go"
        elif artifact.endswith(".sql"):
            return "sql"
        elif artifact.endswith(".md"):
            return "markdown"
        elif artifact.endswith((".json", ".yaml", ".yml")):
            return artifact.split(".")[-1]
        else:
            return "text"

    def _get_language(self, artifact: str) -> str:
        """Get artifact language"""
        format_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".java": "java",
            ".sql": "sql",
            ".md": "markdown",
            ".rs": "rust",
            ".sh": "bash",
        }

        for ext, lang in format_map.items():
            if artifact.endswith(ext):
                return lang

        return None

    def _get_criteria(self, artifact_type: str) -> list:
        """Get default review criteria for artifact type"""
        criteria_map = {
            "code": ["correctness", "security", "performance", "maintainability"],
            "document": ["clarity", "completeness", "accuracy", "consistency"],
            "design": ["feasibility", "clarity", "alignment", "scalability"],
            "architecture": ["scalability", "maintainability", "failure-modes", "complexity"],
            "database-schema": ["normalization", "performance", "data-integrity", "scalability"],
        }

        return criteria_map.get(artifact_type, ["correctness", "completeness", "clarity"])

    def _output_results(self, result, output_file: Optional[str], pipeline=None) -> None:
        """Output review results"""
        print("\n" + "=" * 80)
        print("REVIEW RESULTS")
        print("=" * 80)

        print(f"\nTotal Findings: {len(result.final_findings)}")

        # Group by severity
        by_severity = {}
        for finding in result.final_findings:
            sev = finding.severity.value
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(finding)

        for severity in ["critical", "high", "medium", "low", "info"]:
            if severity in by_severity:
                findings = by_severity[severity]
                print(f"\n{severity.upper()} ({len(findings)}):")
                for f in findings:
                    status = "✓" if f.disposition.value == "confirmed" else "●"
                    print(f"  {status} {f.subject}")
                    print(f"     {f.description}")

        print(f"\nConsensus Score: {result.consensus_score:.1%}")

        if result.next_steps:
            print("\nNext Steps:")
            for step in result.next_steps:
                print(f"  → {step}")

        # Show cost summary if available
        if pipeline:
            print(pipeline.report_costs())

        if output_file:
            output_path = Path(output_file)
            output_path.write_text(result.to_json())
            print(f"\nResults saved to: {output_file}")

        print("\n" + "=" * 80)


def main():
    """Entry point"""
    cli = ReviewCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()
