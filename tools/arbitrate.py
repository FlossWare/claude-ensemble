#!/usr/bin/env python3
"""
Arbitration CLI Tool

Usage:
  arbitrate code-review <repo_path> [--target-branch main] [--phases 3]
  arbitrate bug-analysis <code_files...> [--phases 2]
  arbitrate security-audit <code_files...> [--phases 3]
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitration.orchestrator import ArbitrationOrchestrator, TaskType
from arbitration.api_client import MultiModelClient

logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
logger = logging.getLogger(__name__)


def cmd_code_review(args):
    """Run arbitration on code changes"""
    repo_path = Path(args.repo_path)

    if not repo_path.exists():
        logger.error(f"Repository not found: {repo_path}")
        sys.exit(1)

    orch = ArbitrationOrchestrator(
        TaskType.CODE_REVIEW,
        f"Review changes in {repo_path.name} against {args.target_branch}"
    )

    # Load git diff AND full changed files
    orch.context_manager.load_git_diff(repo_path, args.target_branch)

    # Load related context (imports, dependencies)
    if orch.context_manager.changed_files:
        orch.context_manager.load_related_context(repo_path, orch.context_manager.changed_files)

    # Optionally load entire module context
    if args.context_dir:
        orch.context_manager.load_directory(Path(args.context_dir), max_files=30)

    # Auto-generate phases
    orch.auto_phases(num_phases=args.phases)

    # Run
    orch.run()
    print(orch.report())

    # Print cost report
    if hasattr(orch, 'cost_tracker'):
        print("\n")
        print(orch.cost_tracker.generate_report())


def cmd_bug_analysis(args):
    """Run arbitration on bug analysis"""
    files = [Path(f) for f in args.files]

    orch = ArbitrationOrchestrator(
        TaskType.BUG_ANALYSIS,
        f"Analyze bug across {len(files)} files"
    )

    # Load files
    orch.context_manager.load_files(files)

    # Auto-generate phases
    orch.auto_phases(num_phases=args.phases)

    # Run
    orch.run()
    print(orch.report())

    # Print cost report
    if hasattr(orch, 'cost_tracker'):
        print("\n")
        print(orch.cost_tracker.generate_report())


def cmd_security_audit(args):
    """Run security-focused arbitration"""
    files = [Path(f) for f in args.files]

    orch = ArbitrationOrchestrator(
        TaskType.SECURITY_AUDIT,
        f"Security audit of {len(files)} files"
    )

    # Load files
    orch.context_manager.load_files(files)

    # Auto-generate phases with security focus
    orch.auto_phases(num_phases=args.phases)

    # Run
    orch.run()
    print(orch.report())

    # Print cost report
    if hasattr(orch, 'cost_tracker'):
        print("\n")
        print(orch.cost_tracker.generate_report())


def main():
    parser = argparse.ArgumentParser(description='Multi-phase model arbitration')
    subparsers = parser.add_subparsers(dest='command')

    # Code review
    review_parser = subparsers.add_parser('code-review', help='Arbitrate on code changes')
    review_parser.add_argument('repo_path', help='Repository path')
    review_parser.add_argument('--target-branch', default='main', help='Target branch for diff')
    review_parser.add_argument('--context-dir', help='Load entire module/package for context (e.g., src/mymodule)')
    review_parser.add_argument('--phases', type=int, default=3, help='Number of phases')
    review_parser.set_defaults(func=cmd_code_review)

    # Bug analysis
    bug_parser = subparsers.add_parser('bug-analysis', help='Arbitrate on bug analysis')
    bug_parser.add_argument('files', nargs='+', help='Code files to analyze')
    bug_parser.add_argument('--phases', type=int, default=2, help='Number of phases')
    bug_parser.set_defaults(func=cmd_bug_analysis)

    # Security audit
    sec_parser = subparsers.add_parser('security-audit', help='Arbitrate on security')
    sec_parser.add_argument('files', nargs='+', help='Code files to audit')
    sec_parser.add_argument('--phases', type=int, default=3, help='Number of phases')
    sec_parser.set_defaults(func=cmd_security_audit)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == '__main__':
    main()
