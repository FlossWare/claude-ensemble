---
name: claude-fleet-deployment
description: Which nodes can run Claude Code workflows and how
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-14
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

Claude Code deployment across fleet:

## Nodes with Claude Code

**laptop-01**:
- Running: Web/Desktop Claude Code (this session)
- Can run workflows: YES (currently running)

**server-01**:
- Claude CLI: `/usr/bin/claude` version 2.1.175
- Can run workflows: YES (native binary works)

**server-02**:
- Claude CLI: `/usr/bin/claude` (crashes without env vars)
- Workaround: Uses Vertex AI
- Environment variables required:
  ```bash
  CLAUDE_CODE_USE_VERTEX=1
  ANTHROPIC_VERTEX_PROJECT_ID=itpc-gcp-uie-eng-claude
  ```
- Can run workflows: YES (with env vars set)

**server-03**:
- Claude CLI: `/usr/bin/claude` (crashes - "Illegal instruction")
- Same issue as server-02 (CPU instruction set incompatibility)
- Solution: Apply same Vertex AI workaround as server-02
- Can run workflows: YES (once env vars configured)

**aio-01**:
- No Claude Code
- Can run workflows: NO

## Why server-02/03 need Vertex AI

CPU instruction set issue - binary compiled for different CPU features. Vertex AI bypasses this by using API instead of local binary execution.

## Orchestrator routing for workflows

Workflows can be routed to:
1. laptop-01 (web/desktop session)
2. server-01 (native binary)
3. server-02 (Vertex AI - env vars already set)
4. server-03 (Vertex AI - NEEDS env vars configured first)

NOT: aio-01

## How to apply

When orchestrator routes workflows, eligible nodes are laptop-01, server-01, server-02, (server-03 after configuration).

Load balance across these nodes based on CPU/RAM/current jobs.
