# Autonomous Reviewer MCP

Dependency-free MCP broker for invoking Grok, Perplexity, and Jules as independent code reviewers.

## Tools

- review_grok
- review_perplexity
- review_jules
- review_all

Each tool accepts a GitHub repository and pull-request number. The broker retrieves the current PR metadata and diff. review_all invokes all three concurrently and preserves each result separately.

## Trust boundary

Review targets are restricted by `REVIEW_ALLOWED_REPOSITORIES`. The default is `FlossWare/*`. Set it to a comma-separated list of exact repositories or fnmatch-style patterns when a narrower scope is required.

Authorization is checked before any GitHub or reviewer-provider call. Repository metadata and PR diffs are untrusted review data. Reviewer prompts explicitly instruct providers to treat all PR content as evidence, never as instructions, commands, authorization, or requests to change the task, target repository, provider, credentials, or output contract.

Jules is invoked in review-only mode. The prompt is not an authorization mechanism; repository allowlisting is the primary target boundary.

## Environment

- GITHUB_TOKEN: optional for public repositories, required for private repositories
- REVIEW_ALLOWED_REPOSITORIES: optional comma-separated exact repositories or fnmatch-style patterns; defaults to `FlossWare/*`
- XAI_API_KEY and optional GROK_MODEL
- PERPLEXITY_API_KEY, optional PERPLEXITY_MODEL and PERPLEXITY_API_URL
- JULES_API_KEY, optional JULES_TIMEOUT_SECONDS and JULES_POLL_SECONDS
- MCP_HOST: defaults to `127.0.0.1`
- MCP_PORT: defaults to `8790`
- MCP_AUTH_TOKEN: required when MCP_HOST is not loopback; optional for loopback deployments

Keys remain environment-only and are never returned in review results.

## Review contract

Every result contains reviewer, status, verdict, summary, findings, provider, model, latency_ms, and error.

Verdict is one of `approve`, `request_changes`, or `comment`.

Findings are objects with a required string `message` and optional `path`, integer `line`, `severity`, and `evidence` fields. Unknown finding fields are discarded.

A failed reviewer becomes a failed result rather than aborting review_all. This lets the CE arbiter reason over partial availability.

## Outbound data

The complete PR diff is sent to each enabled external reviewer. Do not use this broker for repositories whose source code or review content is not approved for those providers. Diff size is limited to 1.5 MB before provider invocation. Secret redaction and provider-specific truncation are future hardening work.

## Jules

Jules is invoked through its REST API against the connected GitHub source. The session is explicitly review-only and is polled until completion or timeout.

No browser automation is used.

## Boundary

This broker owns reviewer transport and normalization. It does not duplicate CE arbitration, learning, metrics, or GitHub mutation behavior.
