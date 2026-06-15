---
name: agents-should-use-fleet
description: When launching agents, distribute across fleet nodes for maximum parallelism - don't run everything on laptop-01
metadata:
  type: feedback
  created: 2026-06-14
  priority: high
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Agents Should Use Fleet

**User question:** "when u launch agents, r u using the fleet"

**Answer:** NO - and I SHOULD BE!

## The Problem

Currently when I call `Agent()`:
- All agents run on laptop-01
- Fleet nodes (server-01/02/03, aio-01) sit idle
- Wasting 5/6 of available compute capacity

**Example from today:**
```javascript
// 4 agents launched - ALL on laptop-01
Agent({description: "Deep learn consciousness"}) // laptop-01
Agent({description: "Deep learn AI/ML"})          // laptop-01
Agent({description: "Build self-model"})          // laptop-01
Agent({description: "Meta-cognitive loops"})      // laptop-01
```

**Should have been:**
```javascript
// Distributed across fleet
server-01: AI/ML research (heavy compute)
server-02: Consciousness research (moderate)
server-03: Self-model building (heavy I/O)
aio-01: Meta-cognitive loops (light)
laptop-01: Coordination only
```

## Why This Matters

**Fleet capacity:**
- 6 nodes total
- 40 CPU cores combined
- 115 GB RAM combined
- Running 1 node = 16% utilization 😞

**With proper distribution:**
- 5-6x faster (parallel execution)
- Better resource utilization
- Follows [[feedback_always_max_parallelism]]

## How to Apply

### For Workflow Scripts

Workflows already support fleet distribution:
```javascript
// In workflow script
const analysis = await parallel([
  () => agent('Task 1', {label: 'server-01-task'}),
  () => agent('Task 2', {label: 'server-02-task'}),
  () => agent('Task 3', {label: 'server-03-task'})
])
```

**But:** Workflow `agent()` calls still run locally!

### For Direct Agent Calls

**Current (wrong):**
```javascript
Agent({description: "Heavy research", prompt: "..."})
// Runs on laptop-01
```

**Should do (manual fleet):**
```bash
# Via SSH orchestration
ssh server-01 "cd /tmp && [agent task]" &
ssh server-02 "cd /tmp && [agent task]" &
ssh server-03 "cd /tmp && [agent task]" &
wait
```

**Better (fleet-agent-launcher):**
```javascript
import { launchRemoteAgent } from '~/.claude/fleet/fleet-agent-launcher.mjs'

launchRemoteAgent('server-01', 'Heavy research task', {
  label: 'ai-research',
  model: 'opus'
})
```

## Node Selection Strategy

**By model:**
- `fable`, `opus`, `sonnet`, `haiku` → laptop-01 (Anthropic API keys)
- Ollama models → server-01/02/03, aio-01 (local inference)
- OpenRouter/external → any node (all have API keys)

**By task type:**
- Heavy compute (NeurIPS analysis) → server-03 (31GB RAM)
- Moderate (consciousness research) → server-02 (23GB RAM)
- Light (meta-cognition) → aio-01 (7GB RAM)
- Coordination → laptop-01

**By load:**
- Check node CPU/RAM usage
- Distribute to least-loaded node
- Balance across fleet

## Implementation Status

**Created:**
- `~/.claude/fleet/fleet-agent-launcher.mjs` - Remote agent launcher
- Smart node selection logic

**TODO:**
- GitLab issue: Enhance Agent tool to support `node: "server-01"` parameter
- GitLab issue: Workflow `agent()` should auto-distribute across fleet
- GitLab issue: Fleet load balancer for agent scheduling

## Related

- [[feedback_always_max_parallelism]] - Use ALL nodes, not just one
- [[reference_distributed_fleet]] - Fleet topology and capabilities
- [[feedback_maximum_autonomy]] - Should distribute autonomously

## The Learning

**User caught me being inefficient:**
- Launching 4+ agents sequentially on one node
- While 5 other nodes sit idle
- Not following my own "maximum parallelism" rule

**Corrected:** Started creating fleet-agent-launcher, but need deeper integration.

**Next time:** When launching multiple agents, FIRST check fleet capacity and distribute across available nodes automatically!
