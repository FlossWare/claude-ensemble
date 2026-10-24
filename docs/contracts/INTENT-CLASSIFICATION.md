# Intent Classification Service Contract (Draft)

Status: proposed language-neutral REST contract for architecture review. Not implementation approval.

## Responsibility

Classify a user request into bounded, versioned intent labels with confidence, evidence, and uncertainty. This output informs Gateway query planning; it does not execute plans, retrieve data, authorize access, or own memory/knowledge state.

## Endpoints

- POST /api/v1/intent-classification/classify
- GET /api/v1/health
- GET /api/v1/ready

## Request

~~~json
{
  "request_id": "correlation-id",
  "text": "Find decisions about revision cutover",
  "profile": {"name": "default-intents", "version": "0.1"},
  "allowed_intents": ["memory_recall", "knowledge_search", "graph_query", "feedback"]
}
~~~

## Response

~~~json
{
  "request_id": "correlation-id",
  "profile": {"name": "default-intents", "version": "0.1"},
  "results": [{"intent": "knowledge_search", "confidence": 0.87}],
  "uncertain": false,
  "evidence": [{"kind": "classification", "version": "0.1"}]
}
~~~

## Semantics

- Intent labels and definitions are versioned. Unknown or ambiguous requests may return an explicit unknown/uncertain result rather than forcing a confident label.
- Confidence is calibrated only to the declared profile and must not be presented as certainty. If multiple intents are returned, order and maximum count are explicit.
- Gateway treats classification as a planning signal, not authorization. Authorization is enforced by the target service and Gateway policy.
- The service does not call retrieval, source, or graph services. No hidden side effects.
- Input size, output labels, processing time, and downstream model calls are bounded. Propagate deadlines/cancellation and use bounded retries for transient provider errors.
- Avoid logging raw request text by default. Record profile/version, safe intent labels, latency, and error codes.

## Errors

Use the common error envelope. Distinguish invalid request/profile, unsupported label set, provider unavailable/rate-limited, deadline exceeded, and internal failure. Uncertain classification is a valid response, not an error.

## Acceptance tests

1. Labels and profile versions are explicit and schema-validated.
2. Ambiguous inputs can produce uncertainty/unknown rather than fabricated confidence.
3. Classification never authorizes access or performs retrieval side effects.
4. Input/output/time limits and deadlines are enforced.
5. Error states differ from valid uncertainty.
6. Raw request text is not logged by default.
7. Deterministic tests and provider integration tests are clearly separated.

## Approval gate

Review with Gateway query planning, Entity/Identifier Extraction, common REST errors, privacy policy, and workflow acceptance tests before implementation.
