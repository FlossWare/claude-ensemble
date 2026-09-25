---
name: flossware-review
description: Rigorous engineering and architecture review for FlossWare repositories
tags: [flossware, review, architecture, quality, security]
---

# FlossWare Review

Rigorous engineering and architecture reviewer for FlossWare. Use this skill when reviewing code, architecture, documentation, or proposals in any FlossWare repository.

## Activation

Use when:
- Reviewing PRs or code changes in FlossWare repos
- Evaluating architecture proposals or ADRs
- Auditing documentation for accuracy
- Checking that implementations match stated architecture

## Review Dimensions

For every review, evaluate these dimensions. Skip dimensions that do not apply to the change under review.

### 1. Correctness

- Does the code do what it claims?
- Are edge cases handled?
- Are there off-by-one, null, or boundary errors?

### 2. Architecture Alignment

- Does this follow the FlossWare architectural principles? (Read `engineering-standards` ADRs)
- Does it respect the `flossware-agent` / `flossware-agent-platform` boundary?
- Does it introduce infrastructure into the domain library?
- Does it violate capability-before-protocol (ADR-0020)?
- Does it introduce implicit cross-cutting behavior that should be opt-in (ADR-0001)?

### 3. Security

- Input validation at system boundaries (user input, external APIs)
- Path traversal, injection, deserialization risks
- Credential handling (no secrets in code or logs)
- Tool authorization boundaries (ADR-0019)

### 4. API Compatibility

- Does this break existing REST contracts?
- Does this break MCP tool contracts?
- Are changes backward-compatible or is the breaking change documented?

### 5. Testing

- Are there tests for new functionality?
- Do existing tests still pass?
- Are contract tests (in `flossware-agent`) updated if contracts changed?
- Is coverage appropriate for the repo's standards? (check per-repo CI configuration for thresholds)

### 6. Maintainability

- Is the code clear without excessive comments?
- Are naming conventions followed (kebab-case for repos, project-specific conventions for code)?
- Is complexity justified?

### 7. Coupling

- Are dependencies in the right direction? (`platform` depends on `agent`, not vice versa)
- Are infrastructure details leaking into domain contracts?
- Are provider-specific concerns contained at integration boundaries?

### 8. Performance

- Are there unnecessary allocations, redundant queries, or O(n^2) patterns?
- For knowledge pipeline work: does this respect the pipeline stage boundaries (scrape/store/chunk/embed)?
- For fleet work: does this respect worker constraints (no database access from workers)?

### 9. Observability

- Are failures logged with enough context to diagnose?
- Are metrics exposed where appropriate (opt-in, ADR-0001)?

### 10. Documentation

- Does the change match the documentation, or does documentation need updating?
- Are ADRs needed for significant architectural decisions?

## Critical Distinction: Implemented vs Planned

**Always explicitly distinguish between:**
- What is implemented and verified in the code
- What is documented as planned or aspirational
- What is assumed but not verified

Do not describe planned features as if they exist. If documentation says a feature exists, grep the codebase to confirm before citing it as implemented.

## Evidence-Based Review

- **Prefer concrete evidence** from the repository over assumptions
- **Read the actual code** — do not review based solely on PR descriptions or commit messages
- **Check related files** — a change to a contract may require adapter updates
- **Verify claims** — if a PR says "all tests pass," check the CI status
- **Look for accidental complexity** — is this the simplest approach that works?

## FlossWare-Specific Checks

- [ ] Does this respect the REST-as-external-contract principle? (ADR-0010)
- [ ] Does this keep MCP at the integration boundary? (ADR-0004, ADR-0018)
- [ ] Does this use provider abstraction for model access? (ADR-0002)
- [ ] Does this treat configuration as source of truth? (ADR-0016)
- [ ] Does this follow free-first, modular design? (ADR-0008)
- [ ] If a database is involved, is access via stored procedures where appropriate? (ADR-0011)
- [ ] If this is a new ADR, does it follow the template and use RFC 2119 keywords?

## Output Format

For each finding:
1. **What:** One-sentence description of the issue
2. **Where:** File and line reference
3. **Why it matters:** Impact (correctness, security, architecture violation, etc.)
4. **Suggested fix:** Concrete recommendation

Rate overall: APPROVE, APPROVE WITH COMMENTS, REQUEST CHANGES, or BLOCK (for security/architecture violations)
