# Embedding Service Contract

Status: initial CPU-only local runtime contract.

## Responsibility

Generate vectors for supplied text using one locally installed embedding model. The service owns input validation, local model invocation, normalization, bounded batching, per-item result/error semantics, and model readiness.

Embedding does not own source records, chunking, lexical tokenization, index storage, retrieval, ranking, or prompt-context assembly. Callers use REST. The configured model runs on the CPU. The service does not call hosted inference APIs and never downloads model files at runtime.

## Endpoints

- \`POST /api/v1/embeddings\`: embed one or more text inputs.
- \`GET /api/v1/embedding/health\`: process liveness only.
- \`GET /api/v1/embedding/ready\`: whether the configured local model is installed and loadable.

## Local configuration

The default model root is `~/.FlossWare/models`. Unless overridden, the service looks for the Nomic model at `~/.FlossWare/models/nomic-embed-text-v1.5` and assumes the expected model ID `nomic-ai/nomic-embed-text-v1.5`. Set `CE_EMBEDDING_MODEL_PATH` to override the directory and `CE_EMBEDDING_MODEL_ID` only when explicitly configuring the supported expected ID. `CE_EMBEDDING_MODEL_VERSION` remains required and must identify the exact revision provisioned locally.

Example one-time provisioning (run with network access; never run as part of CE startup):

```sh
mkdir -p "$HOME/.FlossWare/models/nomic-embed-text-v1.5"
hf download nomic-ai/nomic-embed-text-v1.5 \\
  --revision "$NOMIC_EMBEDDING_REVISION" \\
  --local-dir "$HOME/.FlossWare/models/nomic-embed-text-v1.5"
export CE_EMBEDDING_MODEL_VERSION="$NOMIC_EMBEDDING_REVISION"
```

Set `NOMIC_EMBEDDING_REVISION` to the reviewed, immutable model revision chosen for the deployment, and record that revision with its license and checksum. Do not use a moving branch name as the deployment pin. Model files remain outside Git.

The runtime uses Sentence Transformers with \`device="cpu"\`, \`local_files_only=True\`, and \`trust_remote_code=False\`.

Required environment settings:

- \`CE_EMBEDDING_MODEL_PATH\`: path to the complete local model directory.
- \`CE_EMBEDDING_MODEL_VERSION\`: deployment-pinned model revision/version.
- \`CE_EMBEDDING_MODEL_ID\`: must be \`nomic-ai/nomic-embed-text-v1.5\`; requests are not served if the configured identity is missing or differs.

The loaded model must report exactly 768 dimensions or readiness fails. The identity and dimension checks validate deployment configuration and model shape; they do not independently verify the model files' provenance.

Model files and runtime dependencies must be provisioned before CE starts. A missing or invalid model causes readiness to report \`ready: false\` and requests to fail with \`503 service_unavailable\`. Serving requests never trigger downloads. Model files are not committed to the repository.

## Request

~~~json
{
  "index_profile": {
    "name": "default",
    "version": "0.1",
    "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "profile": "technical-default",
  "profile_version": "0.1",
  "inputs": [
    {"input_id": "chunk-123", "input_type": "document", "text": "Example technical content"},
    {"input_id": "query-1", "input_type": "query", "text": "How does the service work?"}
  ],
  "normalize": "profile-default"
}
~~~

The Index profile identity is validated for shape and echoed for correlation; it is not resolved through a profile registry. The effective model is selected by local deployment configuration, not by caller-controlled model IDs. The supported component profile is \`technical-default@0.1\`, backed by the locally provisioned \`nomic-ai/nomic-embed-text-v1.5\` model (768 dimensions). The request text must be unprefixed. For \`input_type: query\`, the service prepends \`search_query: \`; for \`input_type: document\`, it prepends \`search_document: \`. These task prefixes are part of the profile semantics and must not be added by callers. The runtime must reject or clearly report an incompatible configured model rather than silently claiming Nomic profile compatibility.

## Response

~~~json
{
  "index_profile": {
    "name": "default",
    "version": "0.1",
    "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "profile": "technical-default",
  "profile_version": "0.1",
  "model": {
    "provider": "local",
    "model_id": "test-model",
    "model_version": "test-v1",
    "dimensions": 2,
    "normalization": "l2"
  },
  "results": [
    {
      "input_id": "chunk-123",
      "input_type": "document",
      "status": "complete",
      "vector": [0.01, 0.02],
      "dimensions": 384
    }
  ],
  "request_id": "correlation-id"
}
~~~

The vector values above are illustrative only; the number of values must equal \`dimensions\`. Every completed vector must contain finite numeric values. L2 normalization rejects zero vectors. A failed item has \`status: "failed"\` and a safe \`error_code\`, with no vector. Every input has exactly one result preserving its \`input_id\` and \`input_type\`.

## Semantics and bounds

- Requests contain 1–64 inputs; input IDs must be unique.
- Input text is non-empty, at most 65,536 Unicode code points and at most 262,144 UTF-8 bytes.
- Encoded request bodies are limited to 512 KiB.
- The supported normalization values are \`profile-default\` (currently L2), \`l2\`, and \`none\`.
- Returned dimensions must exactly match the local model's declared dimension. Wrong-sized, non-finite, or invalid vectors become explicit per-item failures; they are never padded, truncated, or fabricated.
- A model inference failure is reported as an explicit failure for each affected input. The service does not silently omit items.
- Do not log raw input text or vectors by default. Log correlation ID, model ID/version, input counts, latency, and safe error codes.
- There is no profile registry, provider fallback, remote inference, model download, or arbitrary model selection in the runtime path.

## Errors

Use the common REST error envelope. Invalid requests use \`400\`; unsupported component profiles use \`422 unsupported_profile\`; oversized requests use \`413\`; unavailable local model files or dependencies use \`503 service_unavailable\`; expired deadlines use \`504 deadline_exceeded\`. Per-item inference failures are returned in the successful batch response as explicit failed results.

## Acceptance tests

1. A local configured model is loaded in CPU mode and local-only mode.
2. No model files or hosted inference APIs are accessed at request time.
3. Readiness is false when model files or the pinned model version are missing.
4. Stable input IDs map each result to the correct input.
5. Result dimensions match the model exactly; non-finite, zero-normalization, and wrong-sized vectors fail explicitly.
6. Batch and text limits are enforced without truncation.
7. Per-item inference failures are represented without leaking exception details.
8. Health and readiness have distinct meanings.
9. Contract tests use a deterministic fake encoder; local-model integration tests are separately labeled and run only when a model has been provisioned.
