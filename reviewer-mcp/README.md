# Autonomous Reviewer MCP

Dependency-free MCP broker for invoking Grok, Perplexity, and Jules as independent code reviewers.

## Tools

- review_grok
- review_perplexity
- review_jules
- review_all

Each tool accepts a GitHub repository and pull-request number. The broker retrieves the current PR metadata and diff. review_all invokes all three concurrently and preserves each result separately.

## Environment

- GITHUB_TOKEN: optional for public repositories, required for private repositories
- XAI_API_KEY and optional GROK_MODEL
- PERPLEXITY_API_KEY, optional PERPLEXITY_MODEL and PERPLEXITY_API_URL
- JULES_API_KEY, optional JULES_TIMEOUT_SECONDS and JULES_POLL_SECONDS

Keys remain environment-only and are never returned in review results.

## Review contract

Every result contains reviewer, status, verdict, summary, findings, provider, model, latency_ms, and error.

A failed reviewer becomes a failed result rather than aborting review_all. This lets the CE arbiter reason over partial availability.

## Jules

Jules is invoked through its REST API against the connected GitHub source. The session is explicitly review-only and is polled until completion or timeout.

No browser automation is used.

## Boundary

This broker owns reviewer transport and normalization. It does not duplicate CE arbitration, learning, metrics, or GitHub mutation behavior.
