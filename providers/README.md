# Model Providers

Claude Ensemble's `ModelProvider` contract is provider-neutral. `ModelRequest.timeout`
is a hard execution deadline for providers that support bounded subprocess execution.

## Claude Code provider

`ClaudeCodeProvider` runs the installed `claude` CLI as a subprocess.

### Timeout contract

- `ModelRequest.timeout` must be greater than zero.
- The timeout covers the Claude Code process execution and input/output exchange.
- A timeout raises Python's built-in `TimeoutError`; no successful `ModelResponse`
  is returned.
- Claude Code is started in its own process group on POSIX systems. On timeout,
  the provider terminates that group so descendants do not continue running after
  the provider call has failed.
- The provider waits briefly for graceful termination and escalates to `SIGKILL`
  if the process group does not exit.
- Windows uses a dedicated process group, but the provider currently performs
  direct process termination only. Descendant cleanup is guaranteed by the POSIX
  process-group implementation; Windows descendant cleanup is not guaranteed by
  this provider. Native Windows service installation is outside this repository's
  supported installer path.
- A timed-out invocation is not retried by the provider. Retry policy belongs to
  the caller/workflow layer, where it can account for idempotency and cost.
- A timeout does not fabricate a response, usage, or cost record.

This lifecycle is intentionally enforced at the provider boundary rather than
delegated to callers. On POSIX, a caller that supplies a timeout can rely on the
Claude Code process group being cleaned up before the timeout is reported.
