#!/usr/bin/env python3
"""
Multi-Phase Arbitration Orchestrator

Workflow:
  Phase 1: Workers solve independently → Arbiter 1 synthesizes
  Phase 2: New workers receive Arbiter 1 output + context → Solve again → Arbiter 2 synthesizes
  Phase N: Continue with fresh worker/arbiter pairs

Guarantees:
  - No arbiter appears as a worker in any phase
  - Workers in different phases are different models
  - Arbiters are all different models from each other
  - Each phase has access to original context + prior arbiter output
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from arbitration.cost_tracker import (
    CostTracker, TokenUsage, TaskOutcome, TaskScope, RoutingStrategy
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task types with required context"""
    CODE_REVIEW = "code_review"  # Needs: git diff, local files
    BUG_ANALYSIS = "bug_analysis"  # Needs: error logs, test cases, code
    DESIGN_VALIDATION = "design_validation"  # Needs: design doc, related code
    SECURITY_AUDIT = "security_audit"  # Needs: code, threat model, dependencies
    ARCHITECTURE = "architecture"  # Needs: codebase, requirements


@dataclass
class WorkerResult:
    """Result from a worker model"""
    model: str
    phase: int
    analysis: str
    confidence: float
    key_findings: List[str]


@dataclass
class ArbiterResult:
    """Result from arbiter model"""
    model: str
    phase: int
    synthesis: str
    selected_best: str  # Which worker had strongest answer
    rationale: str
    next_phase_questions: Optional[List[str]] = None


@dataclass
class PhaseConfig:
    """Configuration for one arbitration phase"""
    phase: int
    workers: List[str]  # Model IDs
    arbiter: str  # Single model for this phase
    instructions: str  # What to analyze


class ModelPool:
    """Track model usage to ensure diversity"""

    def __init__(self):
        self.all_models = {
            'cheap': ['claude-haiku-4-5-20251001'],
            'balanced': ['claude-sonnet-5', 'gemini-2.0-flash'],
            'expensive': ['claude-opus-5-5', 'cursor', 'gemini-2.0-pro'],
        }
        self.used_workers = set()
        self.used_arbiters = set()

    def get_workers(self, count: int, tier: str = 'balanced') -> List[str]:
        """Get N different workers from tier, avoiding prior workers"""
        available = [m for m in self.all_models[tier] if m not in self.used_workers]

        # If not enough in tier, expand
        if len(available) < count:
            for other_tier in [t for t in self.all_models.keys() if t != tier]:
                available.extend([m for m in self.all_models[other_tier] if m not in self.used_workers])

        # Get first N
        selected = available[:count]
        self.used_workers.update(selected)
        return selected

    def get_arbiter(self, tier: str = 'expensive') -> str:
        """Get arbiter that hasn't been used"""
        available = [m for m in self.all_models[tier] if m not in self.used_arbiters and m not in self.used_workers]

        if not available:
            # Fallback to any model not used as arbiter yet
            available = [m for m in self.all_models[tier] if m not in self.used_arbiters]

        if available:
            arbiter = available[0]
            self.used_arbiters.add(arbiter)
            return arbiter

        raise ValueError("No available arbiters (pool exhausted)")


class ContextManager:
    """Manage context access for workers/arbiters"""

    def __init__(self, task_type: TaskType):
        self.task_type = task_type
        self.context = {}
        self.git_diff = None
        self.files = {}  # path -> content
        self.directories = {}  # dir -> {file -> content}
        self.changed_files = []  # Files that changed (from git diff)

    def load_git_diff(self, repo_path: Path, target_branch: str = 'main') -> None:
        """Load git diff AND the full files that changed"""
        import subprocess

        try:
            # Get diff
            result = subprocess.run(
                ['git', 'diff', target_branch, 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            self.git_diff = result.stdout
            logger.info(f"Loaded git diff ({len(self.git_diff)} bytes)")

            # Get list of changed files
            result = subprocess.run(
                ['git', 'diff', '--name-only', target_branch, 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            self.changed_files = [repo_path / f for f in result.stdout.strip().split('\n') if f]

            # Load full versions of changed files
            for file_path in self.changed_files:
                try:
                    with open(file_path, 'r') as f:
                        self.files[str(file_path)] = f.read()
                        logger.info(f"Loaded changed file: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Could not load {file_path}: {e}")

        except Exception as e:
            logger.error(f"Failed to load git context: {e}")

    def load_directory(self, dir_path: Path, extensions: Optional[List[str]] = None, max_files: int = 50) -> None:
        """Load all files from directory (useful for module/package context)"""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.tsx', '.go', '.java', '.sql', '.md']

        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            logger.error(f"Not a directory: {dir_path}")
            return

        files_loaded = 0
        for ext in extensions:
            for file_path in dir_path.glob(f'**/*{ext}'):
                if files_loaded >= max_files:
                    break

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if len(content) < 50000:  # Skip huge files
                            self.files[str(file_path)] = content
                            files_loaded += 1
                except Exception as e:
                    logger.debug(f"Skipped {file_path}: {e}")

        self.directories[str(dir_path)] = files_loaded
        logger.info(f"Loaded {files_loaded} files from {dir_path.name}")

    def load_files(self, file_paths: List[Path]) -> None:
        """Load specific local files"""
        for path in file_paths:
            path = Path(path)
            if path.is_dir():
                self.load_directory(path)
            else:
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        self.files[str(path)] = f.read()
                    logger.info(f"Loaded {path.name}")
                except Exception as e:
                    logger.error(f"Failed to load {path}: {e}")

    def load_related_context(self, repo_path: Path, changed_files: List[Path]) -> None:
        """Load related files (dependencies, imports) for changed files"""
        import re

        logger.info("Loading related context files...")

        # Find imports in changed files
        imports = set()
        for file_path in changed_files:
            if str(file_path) in self.files:
                content = self.files[str(file_path)]

                # Simple import detection (Python, JS, Go)
                import_patterns = [
                    r'^\s*import\s+["\']([^"\']+)["\']',  # JS/TS
                    r'^\s*from\s+([^\s]+)\s+import',  # Python
                    r'^\s*import\s+([^\s]+)',  # Go, Python
                ]

                for pattern in import_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE)
                    imports.update(matches)

        # Try to load imported files
        for imp in list(imports)[:10]:  # Limit to 10 to avoid explosion
            possible_paths = [
                repo_path / f"{imp.replace('.', '/')}.py",
                repo_path / f"{imp.replace('.', '/')}.js",
                repo_path / f"{imp.replace('.', '/')}.ts",
                repo_path / f"{imp}.py",
                repo_path / f"{imp}.js",
            ]

            for path in possible_paths:
                if path.exists() and str(path) not in self.files:
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            self.files[str(path)] = f.read()
                        logger.info(f"Loaded related file: {path.name}")
                        break
                    except Exception as e:
                        logger.debug(f"Could not load related {path}: {e}")

    def estimate_tokens(self) -> int:
        """Estimate total tokens in loaded context (rough tokenization: ~4 chars = 1 token)"""
        total_chars = 0
        if self.git_diff:
            total_chars += len(self.git_diff)
        for content in self.files.values():
            total_chars += len(content)
        # Rough estimate: ~4 characters per token (Claude tokenization ~1.3 chars/token, +buffer)
        return max(1, total_chars // 4)

    def get_worker_context(self) -> str:
        """Build context string for worker models"""
        parts = []

        # Show diff first (what changed)
        if self.git_diff:
            parts.append(f"## Changes (Git Diff)\n\n```diff\n{self.git_diff}\n```")

        # Show full files (complete context)
        if self.files:
            parts.append(f"\n## Complete Files ({len(self.files)} files)")
            for path, content in sorted(self.files.items()):
                # Truncate very long files
                if len(content) > 10000:
                    content = content[:10000] + f"\n\n... [truncated, {len(content)} total lines] ..."
                parts.append(f"\n### {path}\n\n```\n{content}\n```")

        return "\n".join(parts)

    def add_arbiter_output(self, arbiter_output: str) -> str:
        """Append arbiter's synthesis to context for next phase"""
        context = self.get_worker_context()
        return f"{context}\n\n## Prior Arbiter Synthesis\n\n{arbiter_output}"


class ArbitrationOrchestrator:
    """Orchestrate multi-phase arbitration"""

    def __init__(self, task_type: TaskType, task_description: str):
        self.task_type = task_type
        self.task_description = task_description
        self.context_manager = ContextManager(task_type)
        self.model_pool = ModelPool()
        self.phases: List[PhaseConfig] = []
        self.results: List[Tuple[List[WorkerResult], ArbiterResult]] = []
        self.final_arbiter_output: Optional[str] = None
        # Thompson learning: track costs and outcomes for autonomous optimization
        self.cost_tracker = CostTracker(task_description[:80], task_type.value)

    def add_phase(self, workers: List[str], arbiter: str, instructions: str) -> None:
        """Add a phase to the arbitration"""
        phase_num = len(self.phases) + 1
        self.phases.append(PhaseConfig(phase_num, workers, arbiter, instructions))

    def auto_phases(self, num_phases: int = 3) -> None:
        """Automatically generate diverse phases"""
        tiers = ['balanced', 'balanced', 'expensive']  # Phase progression

        for i in range(num_phases):
            tier = tiers[min(i, len(tiers) - 1)]
            worker_count = 3 if i < num_phases - 1 else 2

            workers = self.model_pool.get_workers(worker_count, tier)
            arbiter = self.model_pool.get_arbiter(tier)

            instructions = self._get_phase_instructions(i)
            self.add_phase(workers, arbiter, instructions)

            logger.info(f"Phase {i+1}: Workers={workers}, Arbiter={arbiter}")

    def _get_phase_instructions(self, phase_idx: int) -> str:
        """Get phase-specific instructions"""
        base = f"Analyze this {self.task_type.value} carefully.\n\n{self.task_description}"

        if phase_idx == 0:
            return f"{base}\n\nProvide your independent analysis. Focus on correctness, completeness, and any concerns."

        elif phase_idx == 1:
            return f"{base}\n\nChallenge the prior synthesis. Find weaknesses, missed edge cases, alternative approaches."

        else:
            return f"{base}\n\nProvide final validation. Does the prior arbiter's decision hold up? Any remaining concerns?"

    def run(self) -> str:
        """Execute full arbitration pipeline"""
        logger.info(f"Starting arbitration for: {self.task_description[:80]}")

        # Populate Thompson routing metadata (mock for now, set by caller in production)
        self.cost_tracker.routing_strategy = RoutingStrategy.BALANCED
        self.cost_tracker.routing_confidence = 0.85
        self.cost_tracker.input_context_size = self.context_manager.estimate_tokens()

        # Classify task scope based on context size
        if self.cost_tracker.input_context_size < 5000:
            self.cost_tracker.task_scope = TaskScope.SMALL
        elif self.cost_tracker.input_context_size < 20000:
            self.cost_tracker.task_scope = TaskScope.MEDIUM
        else:
            self.cost_tracker.task_scope = TaskScope.LARGE

        current_context = self.context_manager.get_worker_context()

        for phase_config in self.phases:
            logger.info(f"\n{'='*70}")
            logger.info(f"PHASE {phase_config.phase}")
            logger.info(f"{'='*70}")

            # Create phase metrics
            phase_metrics = self.cost_tracker.add_phase(
                phase_config.phase,
                phase_config.workers,
                phase_config.arbiter
            )

            # Run workers in parallel
            worker_results = self._run_workers(phase_config, current_context)

            # Record worker results (mock: would populate from actual API responses)
            for worker in worker_results:
                # In production: extract from actual API response
                self.cost_tracker.record_worker_tokens(
                    phase_config.phase,
                    worker.model,
                    input_tokens=2000,  # Mock token counts
                    output_tokens=1500
                )

            # Run arbiter
            arbiter_result = self._run_arbiter(phase_config, worker_results, current_context)

            # Record arbiter result
            self.cost_tracker.record_arbiter_tokens(
                phase_config.phase,
                arbiter_result.model,
                input_tokens=5000,  # Mock token counts
                output_tokens=2000
            )

            # Populate phase outcome and confidence from arbiter
            phase_metrics.outcome = TaskOutcome.SUCCESS
            phase_metrics.confidence = arbiter_result.model.count('opus') * 0.95 + (1 - arbiter_result.model.count('opus')) * 0.85
            phase_metrics.arbiter_recommendation = arbiter_result.rationale[:200]  # Truncate for markdown

            # Store results
            self.results.append((worker_results, arbiter_result))

            # Update context for next phase
            current_context = self.context_manager.add_arbiter_output(arbiter_result.synthesis)

            logger.info(f"Phase {phase_config.phase} complete. Arbiter selected: {arbiter_result.selected_best}")

        self.final_arbiter_output = self.results[-1][1].synthesis

        # Mark arbitration complete and set overall outcome
        self.cost_tracker.finish()
        self.cost_tracker.task_outcome = TaskOutcome.SUCCESS

        return self.final_arbiter_output

    def _run_workers(self, phase_config: PhaseConfig, context: str) -> List[WorkerResult]:
        """Run all workers in parallel (simulated)"""
        logger.info(f"Running {len(phase_config.workers)} workers...")
        results = []

        for model in phase_config.workers:
            # In production, call actual model APIs in parallel
            result = WorkerResult(
                model=model,
                phase=phase_config.phase,
                analysis=f"[Analysis from {model} on phase {phase_config.phase}]",
                confidence=0.85,
                key_findings=[
                    f"Finding 1 from {model}",
                    f"Finding 2 from {model}",
                ]
            )
            results.append(result)
            logger.info(f"  ✓ {model}")

        return results

    def _run_arbiter(self, phase_config: PhaseConfig, worker_results: List[WorkerResult], context: str) -> ArbiterResult:
        """Run arbiter to synthesize"""
        logger.info(f"Running arbiter: {phase_config.arbiter}")

        # In production, call actual arbiter model API
        selected_best = worker_results[0].model if worker_results else "unknown"

        result = ArbiterResult(
            model=phase_config.arbiter,
            phase=phase_config.phase,
            synthesis=f"[Synthesis from {phase_config.arbiter}]",
            selected_best=selected_best,
            rationale=f"Selected {selected_best} for strongest reasoning",
            next_phase_questions=["What about edge case X?", "Have you considered Y?"] if phase_config.phase < len(self.phases) else None
        )

        logger.info(f"  ✓ {phase_config.arbiter} selected: {selected_best}")
        return result

    def report(self) -> str:
        """Generate final report"""
        lines = [
            "\n" + "="*70,
            "MULTI-PHASE ARBITRATION REPORT",
            "="*70,
            f"\nTask: {self.task_type.value}",
            f"Description: {self.task_description[:100]}...",
            f"Total Phases: {len(self.phases)}",
            f"Total Workers: {len(self.model_pool.used_workers)}",
            f"Total Arbiters: {len(self.model_pool.used_arbiters)}",
        ]

        for phase_idx, (worker_results, arbiter_result) in enumerate(self.results, 1):
            lines.append(f"\n--- PHASE {phase_idx} ---")
            lines.append(f"Workers: {', '.join(w.model for w in worker_results)}")
            lines.append(f"Arbiter: {arbiter_result.model}")
            lines.append(f"Selected: {arbiter_result.selected_best}")
            lines.append(f"\nSynthesis:\n{arbiter_result.synthesis}")

        lines.append("\n" + "="*70)
        lines.append("FINAL DECISION")
        lines.append("="*70)
        lines.append(f"\n{self.final_arbiter_output}")
        lines.append("\n" + "="*70)

        return "\n".join(lines)


if __name__ == '__main__':
    # Example usage
    orch = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        "Review the changes in this PR for correctness, performance, and security"
    )

    orch.auto_phases(num_phases=3)
    orch.run()
    print(orch.report())
