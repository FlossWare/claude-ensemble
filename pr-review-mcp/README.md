# PR Review MCP Service

This service establishes the transport boundary for autonomous merge-request
review without duplicating the review engine.

## Transports

- MCP stdio exposes `review_merge_request`.
- GitLab webhook HTTP exposes `POST /webhooks/gitlab`.

Both transports normalize to the same `ReviewRequest` contract.

## Review engine boundary

Set `REVIEW_COMMAND` to an executable that:

1. reads one JSON `ReviewRequest` from stdin;
2. performs the review;
3. writes one JSON `ReviewResult` to stdout.

The adapter fails closed when `REVIEW_COMMAND` is missing. This keeps
transport concerns separate from model/review logic and avoids creating a
second implementation of the existing `tools/code-pr-review.js`.

Set `GITLAB_WEBHOOK_SECRET` to require `X-Gitlab-Token` validation.

## Next migration step

Create a review-engine adapter around the existing workflow, preserving its
analysis, Thompson selection, compression/caching, learning, and canonical
cost tracking. Then point `REVIEW_COMMAND` at that adapter. Do not duplicate
the review algorithm in this service.
