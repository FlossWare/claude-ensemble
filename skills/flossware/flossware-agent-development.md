---
name: flossware-agent-development
description: Standards for implementing FlossWare AI agents — domain model, MCP, sessions, memory, orchestration
tags: [flossware, agent, mcp, development, standards]
---

# FlossWare Agent Development

Standards for implementing FlossWare AI agents. Use this skill when building or modifying agent-related code in `flossware-agent` or `flossware-agent-platform`.

## Activation

Use when:
- Implementing agent domain contracts or platform services
- Designing MCP tool integrations
- Working with sessions, memory, tasks, or interactions
- Adding model/provider integrations
- Reviewing agent-related code or architecture

## Before You Act

1. **Read the current architecture docs:**
   - `FlossWare/flossware-agent/ARCHITECTURE.md` — domain boundary and contracts
   - `FlossWare/flossware-agent/docs/adr/` — architecture decisions (ADR-0001: library boundary)
   - `FlossWare/flossware-agent-platform/ARCHITECTURE.md` — platform boundary and integration layers
2. **Check existing issues.** Both repos have open issues defining the implementation sequence.
3. **Inspect existing code** before creating new abstractions. As of 2026-08, both repos are in early architecture phase — verify current state before assuming what exists.

## Two-Repository Architecture

### `flossware-agent` (Contracts Library)

Owns domain concepts and stable contracts. Does NOT contain:
- Database schemas or adapters
- REST endpoints
- MCP server implementation
- Redis/queue implementations
- Authentication infrastructure
- Any specific model provider dependency

Domain model (verify against ARCHITECTURE.md):
- **Agent** — configured autonomous or assisted actor
- **Session** — durable, resumable conversation/execution context
- **Interaction** — unit of exchange within a session (provenance for messages, tool calls, responses)
- **Message** — typed communication with roles and metadata (provider-neutral)
- **Context** — information assembled for a particular operation
- **Memory** — durable information retained for later recall (distinct from raw history)
- **Task** — durable unit of work that may outlive a single interaction
- **Tool** — provider-neutral capability an agent may invoke
- **Model / Provider** — logical inference capability and its access implementation
- **Event** — domain change or lifecycle transition fact
- **Artifact** — durable output associated with an agent operation

### `flossware-agent-platform` (Concrete Platform)

Consumes `flossware-agent` contracts and provides:
- REST APIs (OpenAPI as source of truth for HTTP contract)
- MCP integration boundary
- Persistent sessions and interactions
- Memory lifecycle and recall
- Task/work execution
- Model/provider integration
- Storage adapters (PostgreSQL, Redis, OrientDB)
- Event-driven processing
- Authentication/authorization boundaries
- Observability

## Design Principles

1. **Contracts before implementations.** Define the interface in `flossware-agent`, implement in `flossware-agent-platform` or other consumers.
2. **Infrastructure neutrality.** The domain library does not depend on PostgreSQL, Redis, OrientDB, or any specific database.
3. **Provider neutrality.** The library does not depend on Claude, OpenAI, MCP, or a particular SDK.
4. **Persistence is explicit.** Sessions, interactions, and memories must be serializable and recoverable across process restarts.
5. **Stable identifiers and lifecycle semantics.** Domain objects require stable IDs. Lifecycle state must be explicit.
6. **Testable contracts.** Define contract tests that any adapter implementation can run.

## MCP Integration Rules (verify against ADRs)

- MCP is an integration boundary, not a transport for everything (ADR-0004)
- MCP-specific concerns stay at the integration layer and do not leak into the domain (ADR-0018)
- Capability first, protocol second — implement the capability, then expose it via MCP where appropriate (ADR-0020)
- Tool authorization uses explicit capability-based grants, not implicit trust (ADR-0019)
- MCP exposure is opt-in (ADR-0001)

## Memory vs History

Raw interaction history is preserved separately from durable memories. Memory:
- Is intentionally derived from interactions
- Has provenance pointing back to its source context
- Has its own lifecycle (creation, recall, decay, removal)
- Is distinct from conversation logs

## Error Handling

- Use explicit error types at domain boundaries
- Provider/infrastructure failures must not corrupt domain state
- Sessions must remain resumable after failures
- Tool invocation failures must be representable in the interaction record

## Testing

- Contract tests in `flossware-agent` validate adapter behavior
- Integration tests in `flossware-agent-platform` test concrete implementations
- Do not mock domain contracts in platform tests where a real adapter can be used

## Do Not

- Add infrastructure dependencies to `flossware-agent`
- Couple domain contracts to a specific model provider's message format
- Skip the contract layer and implement directly in the platform
- Claim features are implemented without verifying the code exists
- Design for a specific agent client (Claude, Crush, etc.) — the platform is agent-neutral (ADR-0017)
