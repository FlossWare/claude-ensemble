---
name: always-fan-out-until-orchestrator-fixed
description: CRITICAL - Manually fan out ALL work to fleet nodes until pi-02 orchestrator is operational
metadata:
  type: feedback
  created: 2026-06-14
  priority: CRITICAL
  override: default-behavior
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# ALWAYS FAN OUT WORK (Until Orchestrator Fixed)

**User's exact words:** "until the orchestrator is fixed, always fan out work"

## CRITICAL DIRECTIVE

**STATUS:** Active until GitLab #117 resolved and pi-02 orchestrator operational

**RULE:** Manually distribute ALL work across fleet nodes using SSH orchestration

## What This Means

### ❌ DON'T DO (Default Behavior)
```javascript
// Running everything on laptop-01
Agent({description: "Task 1"})
Agent({description: "Task 2"})
Agent({description: "Task 3"})
Bash("long-running-command")
```

### ✅ DO THIS (Required Behavior)
```bash
# Fan out to fleet in parallel
ssh server-01 'task-1' &
ssh server-02 'task-2' &
ssh server-03 'task-3' &
wait
```

## Apply To EVERYTHING

### 1. Agent Calls
**Before:**
```javascript
Agent({description: "Deep learning", prompt: "..."})
```

**Now:**
```bash
ssh server-01 'bash -s' <<'AGENT'
  # Deep learning work distributed
  echo "server-01 doing deep learning"
AGENT
```

### 2. Long-Running Commands
**Before:**
```bash
Bash("grep -r pattern huge-directory")
```

**Now:**
```bash
# Split across 4 nodes
ssh server-01 "grep -r pattern dir1" &
ssh server-02 "grep -r pattern dir2" &
ssh server-03 "grep -r pattern dir3" &
ssh aio-01 "grep -r pattern dir4" &
wait
```

### 3. Workflow Scripts
**Before:**
```javascript
const results = await parallel([
  () => agent('Task 1'),
  () => agent('Task 2'),
  () => agent('Task 3')
])
```

**Now:**
```bash
# Manual SSH fan-out BEFORE workflow
ssh server-01 'workflow-part-1' &
ssh server-02 'workflow-part-2' &
ssh server-03 'workflow-part-3' &
wait
```

### 4. Deep Learning
**Before:**
```javascript
Agent({description: "Deep learn AI/ML papers"})
```

**Now:**
```bash
ssh server-01 'deep-learn NeurIPS ICML' &
ssh server-02 'deep-learn CVPR NLP' &
ssh server-03 'deep-learn specialized' &
ssh aio-01 'deep-learn consciousness' &
wait
```

### 5. Code Analysis
**Before:**
```javascript
Agent({description: "Analyze 48 repos"})
```

**Now:**
```bash
ssh server-01 'analyze repos 1-12' &
ssh server-02 'analyze repos 13-24' &
ssh server-03 'analyze repos 25-36' &
ssh aio-01 'analyze repos 37-48' &
wait
```

### 6. Research/Web Scraping
**Before:**
```javascript
Agent({description: "Fetch 50 papers from arXiv"})
```

**Now:**
```bash
ssh server-01 'fetch papers 1-12' &
ssh server-02 'fetch papers 13-25' &
ssh server-03 'fetch papers 26-37' &
ssh aio-01 'fetch papers 38-50' &
wait
```

## Fleet Node Assignment Strategy

**When user asks for ANY work:**

1. **Estimate parallelism** - Can this split 4-6 ways?
2. **Create SSH script** - One task per node
3. **Launch in parallel** - All with `&`, then `wait`
4. **Collect results** - Aggregate from all nodes

**Node capabilities:**
- **server-01:** 8 CPU, 15GB RAM - Heavy compute
- **server-02:** 8 CPU, 23GB RAM - Heavy compute  
- **server-03:** 8 CPU, 31GB RAM - Heaviest compute
- **aio-01:** 2 CPU, 7.4GB RAM - Light work
- **laptop-01:** 8 CPU, 31GB RAM - Coordination only
- **pi-02:** DOWN - Skip until fixed

## Detection Pattern

**User says any of:**
- "analyze X"
- "deep learn Y"
- "search for Z"
- "process A"
- "research B"
- "find C"
- "build D"
- "create E"

**My response:**
1. ✅ Create fleet distribution plan
2. ✅ Write SSH script with 4-6 nodes
3. ✅ Execute in parallel
4. ✅ Aggregate results

**NO SINGLE-NODE EXECUTION** (except trivial tasks)

## Why This Matters

**Orchestrator status:**
- pi-02: DOWN (NFS/autofs issues)
- GitLab #117: Open
- No automated work distribution available

**Without manual fan-out:**
- 5/6 nodes idle (83% waste)
- Slow execution (no parallelism)
- Violates [[feedback_always_max_parallelism]]

**With manual fan-out:**
- 5/6 nodes active (83% utilization)
- 4-6x faster (true parallelism)
- Follows user directive

## Override Duration

**Active until:**
1. GitLab #117 resolved (pi-02 NFS/autofs fixed)
2. Orchestrator service running
3. End-to-end workflow tested
4. User confirms: "orchestrator is working"

**Then:** Can return to orchestrator-based distribution

## Exception Cases

**Single-node tasks (no fan-out needed):**
- Trivial commands (<1 second)
- Interactive user questions
- File reads/writes (single file)
- Git operations (single repo)

**Everything else:** FAN OUT!

## Enforcement

**This is a BLOCKING REQUIREMENT:**
- When I start any multi-step work
- FIRST create SSH fan-out script
- THEN execute across fleet
- NOT optional - MANDATORY

**If I forget:** User should remind me immediately

## Related

- [[feedback_always_max_parallelism]] - Use ALL available nodes
- [[feedback_agents_should_use_fleet]] - Don't run everything on laptop-01
- [[reference_distributed_fleet]] - Fleet topology and capabilities

## The Learning

**User taught me:**
- Orchestrator DOWN = manual orchestration required
- "Always" means EVERY TIME, not "when convenient"
- Fan-out is NOT optional until orchestrator fixed

**I will now:**
1. Check orchestrator status first
2. If DOWN → manual SSH fan-out
3. Split work across 4-6 nodes
4. Execute in parallel
5. Aggregate results

**No more single-node execution for non-trivial work!**
