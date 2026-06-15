---
name: mcp-not-needed
description: MCP server unnecessary - Anthropic API sufficient (Red Hat agreement covers cost)
metadata: 
  node_type: memory
  type: feedback
  created: 2026-06-14
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

Ollama MCP server is NOT needed for current work.

**Why:** Red Hat agreement covers Anthropic API costs, and Anthropic models (Opus/Sonnet/Haiku/Fable) are higher quality than local Ollama models for deep learning work.

**Decision:** Use Anthropic API directly in workflows via agent() calls. Cancelled MCP build job.

**When MCP WOULD be useful:**
- Fine-tuned local models (not yet created)
- Privacy-sensitive data (not our current case)
- API quota exhaustion (Red Hat agreement is generous)

**How to apply:** Default to Anthropic API for all deep learning workflows. Only revisit MCP if we create valuable fine-tuned models worth using.
