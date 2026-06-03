#!/usr/bin/env bash
# CodeSolve skill - Autonomous code issue resolution
# Command: /code-solve (matches code-solve.md)

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

# Show help if requested
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    cat << 'EOF'
/code-solve - Autonomous Issue Resolution

USAGE:
  /code-solve [ISSUE_NUMBER] [OPTIONS]
  /code-solve loop [OPTIONS]
  /code-solve --help

EXAMPLES:
  /code-solve 123                                           # Default: rotating + parallel
  /code-solve 123 --consensus=weighted --execution=cascade  # Adaptive smart
  /code-solve 123 --consensus=single --execution=parallel   # Fast single arbiter
  /code-solve 123 --comment-ai                              # Show AI attribution
  /code-solve loop                                          # Resolve ALL issues continuously
  /code-solve loop --consensus=weighted --execution=cascade # Continuous adaptive

CONSENSUS STRATEGIES:
  rotating    Democratic - each AI judges others (most thorough, default)
  single      One arbiter judges all (fast)
  majority    Simple majority vote (no arbiter overhead)
  pairwise    Workers in pairs (balanced)
  weighted    Confidence-based voting (quality-aware)

EXECUTION STRATEGIES:
  parallel    All workers simultaneously (fastest, default)
  sequential  One at a time (resource-friendly)
  batched     Process in batches (balanced)
  cascade     Fast workers first, escalate if needed (adaptive, recommended)
  weighted-parallel  Priority-based parallel (smart)

OPTIONS:
  --consensus=MODE     Consensus strategy (default: rotating)
  --execution=MODE     Worker execution strategy (default: parallel)
  --comment-ai         Add comments showing which AI models found/verified issues
                       (Default: OFF - no AI attribution comments added)

LOOP MODE:
  Continuously resolves all open issues until:
  - No issues remain
  - You press Ctrl+C
  - Error occurs

REQUIREMENTS:
  - GITLAB_TOKEN or GITHUB_TOKEN environment variable
  - Ollama running with models (codellama:13b, mistral:7b)
  - Optional: GEMINI_API_KEY for cloud arbiter

DOCUMENTATION:
  See: code-solve.md
  Strategy Guide: MULTI_AI_STRATEGIES.md
  Or:  https://gitlab.cee.redhat.com/sfloess/universal-ai
EOF
    exit 0
fi

# Get arguments
ISSUE_NUM="${1:-}"
ARBITER_MODE="${2:-rotating}"
LOOP_MODE=false
COMMENT_AI_LEVEL="none"

# Parse all arguments for flags
for arg in "$@"; do
    if [[ "$arg" == "--comment-ai" ]]; then
        COMMENT_AI_LEVEL="detailed"  # Default level when just --comment-ai
    elif [[ "$arg" =~ ^--comment-ai=(.*) ]]; then
        COMMENT_AI_LEVEL="${BASH_REMATCH[1]}"
    elif [[ "$arg" =~ ^--comment-ai-.* ]]; then
        # Individual flags will be passed to Python
        :
    fi
done

# Check if loop mode
if [[ "$ISSUE_NUM" == "loop" ]]; then
    LOOP_MODE=true
    ISSUE_NUM=""
    # Arbiter mode might be second arg when first is "loop"
    if [[ -n "${2:-}" ]] && [[ "${2:-}" != "--comment-ai" ]]; then
        ARBITER_MODE="$2"
    fi
fi

# Validate arbiter mode
if [[ "$ARBITER_MODE" != "single" ]] && [[ "$ARBITER_MODE" != "rotating" ]]; then
    echo -e "${RED}❌ Invalid arbiter mode: $ARBITER_MODE${RESET}"
    echo -e "${YELLOW}   Use 'single' or 'rotating'${RESET}"
    exit 1
fi

# If loop mode, show different header
if [[ "$LOOP_MODE" == "true" ]]; then
    echo -e "${BLUE}${BOLD}🔄 Autonomous Issue Resolver - LOOP MODE${RESET}"
    echo -e "${BLUE}   Will continuously resolve ALL open issues${RESET}"
    echo -e "${BLUE}   Arbiter: ${GREEN}$ARBITER_MODE${RESET}"
    echo -e "${YELLOW}   Press Ctrl+C to stop${RESET}"
    echo ""
else
    # If no issue number, prompt for it
    if [[ -z "$ISSUE_NUM" ]]; then
        echo "📋 Enter issue number to resolve (or 'loop' for continuous):"
        read -r ISSUE_NUM

        if [[ -z "$ISSUE_NUM" ]]; then
            echo -e "${RED}❌ No issue number provided${RESET}"
            exit 1
        fi

        if [[ "$ISSUE_NUM" == "loop" ]]; then
            LOOP_MODE=true
            ISSUE_NUM=""
        fi
    fi

    # Validate issue number is numeric (if not loop mode)
    if [[ "$LOOP_MODE" == "false" ]] && ! [[ "$ISSUE_NUM" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}❌ Issue number must be numeric: $ISSUE_NUM${RESET}"
        exit 1
    fi

    if [[ "$LOOP_MODE" == "false" ]]; then
        echo "🤖 Autonomous Issue Resolver"
        echo "   Issue: #$ISSUE_NUM"
        echo "   Arbiter: $ARBITER_MODE"
        echo ""
    else
        echo "🔄 Autonomous Issue Resolver - LOOP MODE"
        echo "   Will continuously resolve ALL open issues"
        echo "   Arbiter: $ARBITER_MODE"
        echo "   Press Ctrl+C to stop"
        echo ""
    fi
fi

# Export variables for Python
export LOOP_MODE="$LOOP_MODE"
export ISSUE_NUM="$ISSUE_NUM"
export COMMENT_AI_LEVEL="$COMMENT_AI_LEVEL"
export AI_ATTRIBUTION_ARGS="$*"

# Run the autonomous solver
python3 <<EOF
import sys
import os

# Add project to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import and run
try:
    if "$ARBITER_MODE" == "rotating":
        # Rotating arbiter implementation
        from autodev_ai.hybrid_workers import create_hybrid_pool
        from autodev_ai.rotating_arbiter import RotatingArbiterPool
        from autodev_ai.pr_creator import PRCreator
        import requests

        # Configuration
        GITLAB_TOKEN = os.getenv('GITLAB_TOKEN')
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        GITLAB_API = os.getenv('GITLAB_API', 'https://gitlab.cee.redhat.com/api/v4')
        PROJECT_ID = os.getenv('GITLAB_PROJECT_ID', 'sfloess/autodev-ai')

        def resolve_single_issue(issue_num, issue, worker_pool, GITLAB_TOKEN, GEMINI_API_KEY, GITLAB_API, PROJECT_ID):
            """Resolve a single issue and return success status"""
            # Parse attribution options
            import sys
            sys.path.insert(0, os.path.expanduser('~/.claude/skills/cli'))
            from ai_attribution_levels import parse_attribution_args, format_attribution_comment, explain_while_working_update

            args = os.getenv('AI_ATTRIBUTION_ARGS', '').split()
            attribution_options = parse_attribution_args(args)

            # Create prompt
            prompt = f"""
Task: {issue['title']}

Context:
{issue.get('description', '')[:500]}

Generate a Python code solution that:
1. Solves the problem described
2. Includes all necessary imports
3. Has clear function/class names
4. Includes docstrings
5. Handles errors appropriately

Format your response as:
File: path/to/file.py
\`\`\`python
# Your code here
\`\`\`

Provide working, tested code.
""".strip()

            # Initialize pools if needed
            if worker_pool is None:
                worker_pool = create_hybrid_pool(use_gemini=bool(GEMINI_API_KEY))
                print(f"✅ Workers: {worker_pool.total_workers}")

            rotating = RotatingArbiterPool(worker_pool)

            # Run rotating arbitration
            result = rotating.run_rotating_arbitration(
                prompt=prompt,
                iterations=None,
                use_ai_arbiter=bool(GEMINI_API_KEY),
                gemini_api_key=GEMINI_API_KEY
            )

            # Create PR
            pr_creator = PRCreator(
                gitlab_token=GITLAB_TOKEN,
                gitlab_api=GITLAB_API,
                project_id=PROJECT_ID
            )

            pr_result = pr_creator.create_pr_from_solution(
                issue_number=issue_num,
                issue_title=issue['title'],
                solution=result.consensus_solution,
                worker_name=f"{result.consensus_winner} (consensus)"
            )

            if pr_result.success:
                print(f"✅ Pull request created!")
                print(f"   URL: {pr_result.pr_url}")
                print(f"   Branch: {pr_result.branch_name}")
                return True
            else:
                print(f"❌ PR creation failed: {pr_result.error_message}")
                return False

        if not GITLAB_TOKEN:
            print("❌ GITLAB_TOKEN environment variable not set")
            print("   Set it with: export GITLAB_TOKEN='your-token'")
            sys.exit(1)

        loop_mode = os.getenv('LOOP_MODE', 'false') == 'true'
        issue_num = int(os.getenv('ISSUE_NUM', '0')) if os.getenv('ISSUE_NUM') else None

        if loop_mode:
            # LOOP MODE: Fetch all open issues and resolve them one by one
            print("🔍 Fetching all open issues...")
            url = f"{GITLAB_API}/projects/{PROJECT_ID.replace('/', '%2F')}/issues"
            headers = {'PRIVATE-TOKEN': GITLAB_TOKEN}
            params = {'state': 'opened', 'order_by': 'priority', 'sort': 'desc', 'per_page': 100}
            response = requests.get(url, headers=headers, params=params)

            if response.status_code != 200:
                print(f"❌ Failed to fetch issues: {response.status_code}")
                sys.exit(1)

            issues = response.json()
            print(f"✅ Found {len(issues)} open issues")

            if not issues:
                print("🎉 No open issues to resolve!")
                sys.exit(0)

            # Resolve each issue in loop
            iteration = 0
            resolved_count = 0

            while issues:
                iteration += 1
                issue = issues.pop(0)  # Take first (highest priority)
                issue_num = issue['iid']

                print("")
                print("─" * 50)
                print(f"Iteration {iteration}: Resolving #{issue_num}: {issue['title']}")
                print("─" * 50)
                print("")

                try:
                    # Process this issue (same logic as single mode below)
                    result = resolve_single_issue(
                        issue_num=issue_num,
                        issue=issue,
                        worker_pool=None,  # Will create
                        GITLAB_TOKEN=GITLAB_TOKEN,
                        GEMINI_API_KEY=GEMINI_API_KEY,
                        GITLAB_API=GITLAB_API,
                        PROJECT_ID=PROJECT_ID
                    )

                    if result:
                        resolved_count += 1
                        print(f"✅ Issue #{issue_num} resolved!")
                    else:
                        print(f"⚠️  Issue #{issue_num} skipped (failed)")

                except KeyboardInterrupt:
                    print("")
                    print("🛑 Loop interrupted by user")
                    print(f"   Resolved: {resolved_count}/{iteration}")
                    sys.exit(0)
                except Exception as e:
                    print(f"❌ Error resolving #{issue_num}: {e}")
                    print("   Continuing to next issue...")
                    continue

                # Check for more issues every 5 iterations
                if iteration % 5 == 0:
                    print("")
                    print("🔍 Checking for new issues...")
                    response = requests.get(url, headers=headers, params=params)
                    if response.status_code == 200:
                        new_issues = response.json()
                        # Add any new issues not already processed
                        processed_ids = {issue['iid'] for issue in issues}
                        for new_issue in new_issues:
                            if new_issue['iid'] not in processed_ids:
                                issues.append(new_issue)
                        if len(new_issues) > len(issues):
                            print(f"   Found {len(new_issues) - len(issues)} new issues")

            print("")
            print("🎉 All issues resolved!")
            print(f"   Total: {resolved_count} issues")
            sys.exit(0)

        else:
            # SINGLE MODE: Fetch one issue
            print("📥 Fetching issue...")
            url = f"{GITLAB_API}/projects/{PROJECT_ID.replace('/', '%2F')}/issues/{issue_num}"
            headers = {'PRIVATE-TOKEN': GITLAB_TOKEN}
            response = requests.get(url, headers=headers)

            if response.status_code != 200:
                print(f"❌ Failed to fetch issue: {response.status_code}")
                print(f"   URL: {url}")
                sys.exit(1)

            issue = response.json()
            print(f"✅ Issue: {issue['title']}")

            # Resolve the issue
            print("🔧 Initializing workers...")
            success = resolve_single_issue(
                issue_num=issue_num,
                issue=issue,
                worker_pool=None,
                GITLAB_TOKEN=GITLAB_TOKEN,
                GEMINI_API_KEY=GEMINI_API_KEY,
                GITLAB_API=GITLAB_API,
                PROJECT_ID=PROJECT_ID
            )

            if success:
                print("")
                print(f"✅ Issue #{issue_num} resolved autonomously!")
            else:
                sys.exit(1)

    else:
        # Single arbiter implementation
        print("⚠️  Single arbiter mode - using scripts/autonomous-issue-solver.py")
        print("    (Update that script to handle single issue if needed)")

        import subprocess
        result = subprocess.run(
            ['python3', 'scripts/autonomous-issue-solver.py'],
            cwd=project_root
        )
        sys.exit(result.returncode)

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("   Make sure you're in the autodev-ai project directory")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF
