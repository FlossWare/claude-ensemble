---
name: flossware-architecture
description: Understand and enforce FlossWare architectural principles across all FlossWare repositories
tags: [flossware, architecture, review, design]
---

# FlossWare Architecture

Understand and enforce FlossWare architectural principles. Use this skill when designing, reviewing, or modifying any FlossWare component.

## Activation

Use when:
- Proposing architectural changes to any FlossWare repository
- Reviewing whether a design aligns with FlossWare principles
- Choosing between implementation approaches in FlossWare projects
- Answering questions about how FlossWare systems are structured

## Before You Act

1. **Read the canonical sources.** Do not rely on memory or assumptions.
   - Org-level architecture: `FlossWare/.github` repo — `ARCHITECTURE.md`, `docs/philosophy.md`
   - ADRs: `FlossWare/engineering-standards` repo — `adr/` directory (20 ADRs as of 2026-08)
   - Reference architecture: `FlossWare/engineering-standards` — `docs/architecture/reference-architecture.md`
   - Per-repo architecture: each repo's own `ARCHITECTURE.md` if present
2. **Inspect before proposing.** Check the current implementation and documentation in the relevant repository before suggesting changes.
3. **Never invent infrastructure, APIs, services, or implementation status.** If you cannot verify it exists, say so.

## Core Principles (verify against ADR-0009)

- Configuration is the source of truth (ADR-0016)
- Minimal defaults; capabilities are explicitly opted into (ADR-0001)
- Components are modular and composable
- Open standards and free/open-source components preferred (ADR-0008)
- Loose coupling through stable contracts
- Agent-neutral: the platform does not require a specific agent runtime (ADR-0017)
- Capability before protocol (ADR-0020)

## Architectural Layers (verify against reference architecture)

```
Clients / Agents
       |
REST APIs / MCP Tool Interfaces
       |
Service / Capability Layer
       |
AI Orchestration (provider abstraction, bandit selection, consensus)
       |
Message Bus (opt-in event-driven)     Stored Procedures (selective)
       |                                       |
Event Consumers                           Databases
```

## Key Boundaries

- **REST** is the external service contract (ADR-0010)
- **MCP** is an integration boundary for agents/tools, not a transport for everything (ADR-0004, ADR-0018)
- **Databases are adapters.** PostgreSQL, Redis, OrientDB are implementations, not requirements (verify against `flossware-agent` ADR-0001)
- **Cross-cutting behaviors** (events, metrics, tracing, MCP exposure) are explicit opt-in via decorators/interceptors (ADR-0001, ADR-0006)
- **AI provider abstraction** separates model access from provider specifics (ADR-0002); no local inference by default (ADR-0003)
- **`flossware-agent`** defines domain contracts; **`flossware-agent-platform`** provides concrete implementations. Do not mix these responsibilities.

## Current Infrastructure (verify before citing)

- Orchestrator: `aio-01:5000` (REST API gateway)
- Storage: PostgreSQL+pgvector, Redis (queues/cache), OrientDB (graph)
- Fleet: SSH-based distributed workers (not Kubernetes)
- Models: 500+ via API providers (API-only since 2026-06-28)
- Routing: Thompson Sampling (bandit-based model selection, ADR-0013)
- Quality gates: Multi-model consensus (ADR-0012)

## Constraints

- Do not redesign infrastructure without an ADR
- Do not introduce database-specific concepts into domain contracts
- Do not hardcode model providers, hostnames, or deployment details into domain logic
- Do not bypass the REST API from fleet workers (workers never touch databases directly)
- Respect the `flossware-agent` / `flossware-agent-platform` separation
- Both agent repos are in early architecture phase with no implementation code yet — do not claim otherwise

## ADR Reference

When a decision is needed, check `FlossWare/engineering-standards/adr/` for an existing ADR. If none exists and the decision is significant, propose a new ADR using `adr/TEMPLATE.md`. Use RFC 2119 keywords consistently (SHALL/SHOULD/MAY).
