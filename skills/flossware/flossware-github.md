---
name: flossware-github
description: Work with FlossWare GitHub repositories, issues, branches, labels, pull requests, and CI conventions
tags: [flossware, github, issues, ci, workflow]
---

# FlossWare GitHub

Define how Claude works with FlossWare repositories. Use this skill when creating issues, PRs, branches, labels, or interacting with CI across any FlossWare repo.

## Activation

Use when:
- Creating or triaging issues in FlossWare repos
- Opening pull requests
- Working with branches or labels
- Understanding CI/CD pipeline conventions
- Checking repository conventions before contributing

## Before You Act

1. **Check existing issues** before creating new ones. Search for duplicates.
2. **Check existing labels** in the target repo before creating new ones.
3. **Read the repo's `.github/` directory** for issue templates, PR templates, CODEOWNERS, and workflows.
4. **Treat GitHub as durable work state.** The repository is the source of truth for code, documentation, and architectural decisions.

## Organization

- **Owner:** `FlossWare` (GitHub org)
- **Profile:** `FlossWare/.github/profile/README.md`
- **Org-level docs:** `FlossWare/.github` repo (ARCHITECTURE.md, docs/)
- **Engineering standards:** `FlossWare/engineering-standards` (ADRs, reference architecture)

## Issue Conventions

### Agent Attribution Prefix

Issues created with AI assistance use a bracketed prefix indicating the agent:
- `[chatgpt]` — designed/created with ChatGPT
- `[grok]` — created with Grok
- `[claude]` — use this prefix when Claude creates issues

Examples from the codebase:
- `[chatgpt] Define core agent domain model and public contracts`
- `[grok] Perform substance review of key architectural decisions`

When creating issues, use the `[claude]` prefix. Do not invent other prefixes.

### Labels

Common labels observed across repos (check the specific repo before using):
- `architecture` — architectural design issues
- `api` — API contract changes
- `feature` — new functionality
- `enhancement` — improvements to existing functionality
- `bug` — defects
- `security` — security-related issues
- `documentation` — documentation changes
- `refactoring` — code restructuring without functional change

Do not create labels that duplicate existing ones. Check with `gh label list` first.

### Issue Templates (where present)

`commons-java` has structured templates: `bug_report.yml`, `feature_request.yml`, `migration_feedback.yml`, `question.yml`, `security_vulnerability.md`. Other repos may have different or no templates. Check before filing.

## Pull Request Conventions

Where a PR template exists (e.g., `commons-java`), follow it. The standard structure includes:
- Description with issue link (`Fixes #N`)
- Type of change (bug fix, feature, breaking, docs, refactoring, dependency)
- Changes made (bulleted list)
- Testing checklist
- Code quality checklist

When no template exists, use a concise format:
- Summary (what and why)
- Test plan
- Related issues

## Branch Conventions

- Default branch: `main` (verify per repo)
- Feature branches: descriptive kebab-case names
- Do not create tags — the user handles all versioning (X.Y format, not X.Y.Z)

## CI/CD Patterns

### Java Repos (Maven)

Typical workflows (verify per repo):
- `quality-gate.yml` — Checkstyle, PMD, SpotBugs, JaCoCo coverage
- `main.yml` — Build and test on push/PR
- `codeql.yml` — GitHub CodeQL security analysis
- `sonarcloud.yml` — SonarCloud quality gate (where configured)

Quality tools: Checkstyle (`checkstyle.xml`), PMD (`pmd-rules.xml` or `pmd-ruleset.xml`), SpotBugs (`spotbugs-exclude.xml`), JaCoCo (coverage)

### Python Repos

Typical workflows (verify per repo):
- `quality.yml` / `test.yml` — Linting + test suite
- `release.yml` / `create-release.yml` — Release automation

### Shell Repos

Minimal or no CI. `build-tools` has `quality-gate.yml`.

## Naming Convention

All FlossWare repos use **lowercase kebab-case**. No PascalCase for repository names.

## Key Repositories to Know

| Repo | Role |
|---|---|
| `.github` | Org profile + architecture documentation |
| `engineering-standards` | ADRs, principles, reference architecture |
| `flossware-agent` | Agent domain contracts (library, no infrastructure) |
| `flossware-agent-platform` | Concrete agent platform (REST, MCP, persistence) |
| `build-tools` | Shared Maven quality tooling + scripts |
| `commons-java` | Shared Java utility library |

## Do Not

- Create redundant labels, issues, or branches
- Assume a convention from one repo applies to all repos — verify
- Push directly to main without a PR (where branch protection exists)
- Create git tags (user handles versioning)
- Create documentation files unless explicitly asked
