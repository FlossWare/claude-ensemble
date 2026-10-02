# Model Providers

Claude Ensemble exposes a small provider-neutral ModelProvider contract.

## Direct API providers

AnthropicProvider and GoogleProvider invoke their public model APIs directly
and normalize responses into ModelResponse. They use the standard library HTTP
client, so provider support does not add an SDK dependency.

Credentials are read from:

- ANTHROPIC_API_KEY
- GOOGLE_API_KEY

Requests are bounded by ModelRequest.timeout. Provider-specific HTTP failures
are surfaced as actionable exceptions and are not silently converted into fake
successful responses.

## Claude Code

ClaudeCodeProvider remains available for the Claude Code CLI workflow. It
deliberately treats Claude Code as the authentication/runtime boundary rather
than reading Claude Code credentials itself.

## Selecting providers

ProviderRegistry maps Claude model names to Anthropic and Gemini model names
to Google. Additional providers can be explicitly registered without changing
the request/response contract.

The compatibility facade in arbitration/api_client.py keeps the existing
MultiModelClient.call_model() API while exposing call_model_response() for
normalized usage and metadata.

## Smoke test

With credentials configured, a real call can be exercised without modifying
the test suite:

    python -c 'from arbitration.api_client import MultiModelClient; print(MultiModelClient().call_model("gemini-2.5-flash", "Reply with one word."))'

Use the Anthropic model name appropriate to the account for an Anthropic smoke
test. Tests use mocked HTTP responses and never require live credentials.
