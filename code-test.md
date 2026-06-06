# code-test

Comprehensive automated application testing with multi-AI consensus validation.

## What it does

Tests applications including UI validation and validates open issues using the arbiter/worker pattern:

1. **Detects Application Type** - Identifies app type, framework, and test infrastructure
2. **Fetches Open Issues** - Gets open issues to validate during testing
3. **Generates Test Plans** - Multiple AI models (Opus, Sonnet, Haiku) propose test strategies in parallel
4. **Selects Best Plan** - Arbiter AI selects the optimal test plan via consensus
5. **Executes Tests** - Runs automated tests (unit, integration, UI, e2e) based on app type
6. **Validates Issues** - Tests each open issue to see if it's reproducible
7. **Multi-Model Review** - Failed tests and reproduced issues reviewed by 3 AIs for consensus
8. **Reports Results** - Creates/updates GitHub/GitLab issues with findings and full AI attribution

## Usage

```bash
# Test current application and validate all open issues
/code-test

# Limit number of issues to test
/code-test maxIssues=5

# Disable automatic issue creation
/code-test create-issues=false

# Interactive mode (ask before creating issues)
/code-test autonomous=false
```

## Features

- **Multi-AI Consensus**: 3 worker AIs generate test plans, 1 arbiter selects best
- **Full AI Attribution**: Tracks which models found issues, consensus votes, rejected proposals
- **UI Testing**: Automatically detects and tests web UIs, desktop apps
- **Issue Validation**: Tests every open issue to confirm it's still reproducible
- **Multiple Test Types**: Unit, integration, e2e, UI, API tests based on app type
- **Autonomous Operation**: Runs fully automated by default (no user prompts)
- **Platform Support**: GitHub and GitLab

## Configuration

Controlled via `args`:
- `maxIssues` (default: 10) - Max open issues to validate
- `autonomous` (default: true) - No prompts, auto-create issues
- `create-issues` (default: true) - Create GitHub/GitLab issues for findings

## Output

Returns structured results:
```json
{
  "status": "complete",
  "app_type": "web|cli|api|library|desktop|mobile",
  "framework": "react|vue|express|etc",
  "test_summary": {
    "total": 15,
    "passed": 12,
    "failed": 3
  },
  "issue_summary": {
    "total": 10,
    "reproduced": 3,
    "fixed": 7
  },
  "findings": [...],
  "ai_attribution": {...}
}
```

## When to use

- Comprehensive application testing needed
- Need to validate open issues are still reproducible
- Want multi-AI consensus on test results
- Testing UIs and integration points
- Before releases or major changes
- Automated quality gates in CI/CD

## Requirements

- Git repository
- GitHub CLI (`gh`) or GitLab CLI (`glab`)
- Application must be runnable/testable
