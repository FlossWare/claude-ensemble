# Claude Code Context Hook Lifecycle

Issue #311 establishes one canonical prompt-time context retrieval path.

## Contracts

Claude Ensemble keeps two concepts distinct even when they share the Memory service:

- **Memory**: episodic experience and observations, meaning what happened.
- **Knowledge**: durable Claude Code material that represents what is currently known or believed.

The `UserPromptSubmit` hook exposes these as separate sections in its `additionalContext` payload. Claude Code does not need to know how the service stores either category.

## Retrieval lifecycle

1. Claude Code submits a user prompt.
2. `~/.claude/hooks/memory-search-on-prompt.js` receives the event.
3. The complete prompt is used as the retrieval query. Retrieval is relevance-driven and does not depend on trigger words such as `remember`, `recall`, or `prior`.
4. The hook calls the loopback Memory REST endpoint `POST /memory/search`.
5. Results are validated against the canonical `{ok: true, results: []}` envelope and require a string `content` field.
6. Results are deduplicated by source, file, section, and content.
7. Results are partitioned into Memory and Knowledge. Claude Code-ingested documents (`source=claude-code` or `claude-code-*` documents) are treated as Knowledge; other Memory service search results remain Memory.
8. The hook emits `UserPromptSubmit.hookSpecificOutput.additionalContext`.
9. Memory failures remain fail-open and never block prompt submission.

## Legacy hooks

`hooks/user-prompt-submit.sh` and `hooks/ingest-prompt` are compatibility shims only. They no longer perform retrieval in the repository. The installer also recognizes the known deployed legacy implementations by their exact content hashes and removes only those owned registrations during upgrade. The legacy files themselves are left in place unless the user removes them. Arbitrary same-named or modified scripts are not migrated.

Workflow-specific context loaders remain available for workflow orchestration. They are not additional Claude Code prompt hooks and should not register a second `UserPromptSubmit` retrieval path.

## Capture versus retrieval

Session-end learning and workflow-completion hooks capture experience. They must not also retrieve prompt context.

The lifecycle therefore separates:

- **Retrieve**: prompt-time context loading.
- **Capture**: session/workflow experience persistence.
- **Learning**: extraction and evaluation of captured experience.
- **Promotion**: durable knowledge creation or update from validated learning.

Promotion is intentionally not implemented by the prompt hook. The hook is a read-only context augmentation path.

## Duplicate prevention

The canonical retrieval path deduplicates identical returned context items. Legacy prompt retrieval hooks are disabled as compatibility shims so an older Claude Code registration cannot perform a second retrieval.

Future cross-hook deduplication should use the query hash exposed in the hook metadata rather than introducing another retrieval implementation.
