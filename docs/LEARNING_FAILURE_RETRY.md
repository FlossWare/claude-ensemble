# Learning Service Failure and Retry Semantics

## Contract

Learning ingestion is a durable, recoverable side effect of execution. It must not make an otherwise completed execution fail merely because the Learning or Thompson dependency is unavailable.

For process_outcome:

1. The outcome payload is persisted before downstream Thompson learning is marked complete.
2. A durable ingestion checkpoint is advanced only after downstream learning succeeds, or when no Thompson dependency is configured.
3. A retry with the same task_id and equivalent payload resumes the pending ingestion. The persisted outcome is the source of truth.
4. A retry with the same task_id but a different payload is rejected as a conflict and never advances the checkpoint.
5. Dependency failures are reported as recoverable while retry attempts remain. The response includes retryable=true, the current attempt count, and the configured maximum.
6. Automatic retries are not performed inside the Learning Service. The caller controls when to retry, avoiding hidden blocking or retry storms.
7. The default retry budget is three ingestion attempts per task. Attempt state is persisted in ingestion_retry_state.json, so a service restart does not reset the budget.
8. Once the retry budget is exhausted, the task enters a terminal ingestion-failure state. Further requests return retryable=false and do not invoke downstream learning.
9. A successful retry advances the checkpoint. Subsequent identical submissions are idempotent duplicates and do not invoke downstream learning again.
10. Outcome and retry-state writes use atomic file replacement.

## Execution behavior

Execution should continue when learning ingestion fails. The failure is operationally recoverable and should be surfaced in the learning response/logs rather than treated as an execution-result failure.

The service owns idempotency and the bounded retry budget. It does not own retry scheduling or backoff.

## Recovery after restart

On restart:

- persisted outcome payloads remain available;
- retry-attempt state remains available;
- completed tasks are recognized by the checkpoint and treated as idempotent duplicates;
- pending tasks can be retried with the original payload;
- exhausted tasks remain terminal until a future explicit recovery mechanism is introduced.

## Failure states

| State | Meaning | Retry |
| --- | --- | --- |
| pending | Outcome persisted, downstream learning not completed | Yes, while budget remains |
| completed | Outcome persisted and checkpoint advanced | No, duplicate only |
| conflict | Same task ID supplied with a different payload | No |
| exhausted | Retry budget consumed without downstream success | No |

The wire protocol exposes these states through ok, duplicate, conflict, checkpoint_advanced, retryable, attempts, and max_attempts.
