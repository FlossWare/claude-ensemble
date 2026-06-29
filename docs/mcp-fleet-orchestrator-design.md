# MCP Fleet Orchestrator - Design Document

**Status:** Planning  
**Timeline:** 5-7 days  
**Issue:** #10

## Overview

Build an MCP (Model Context Protocol) server that exposes fleet orchestration capabilities to Claude Code workflows and other tools.

## Goals

1. **Enable workflows to use all 9 API providers** (not just Anthropic)
2. **Enable workflows to distribute across 8 fleet workers** (not just localhost)
3. **Track execution_host** for all workflow agents
4. **Reusable across tools** (not just workflows)
5. **Future-proof architecture** (proper service boundary)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Claude Code Workflows                                │
│ ┌─────────────────────────────────────────────────┐ │
│ │ await useTool('fleet-orchestrator', {           │ │
│ │   model: 'gpt-4o',                              │ │
│ │   prompt: 'Implement feature',                  │ │
│ │   worker: 'auto'                                │ │
│ │ })                                              │ │
│ └─────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │ MCP Protocol (stdio)
                       ▼
┌─────────────────────────────────────────────────────┐
│ MCP Fleet Orchestrator Server                       │
│ (~/.claude/mcp-servers/fleet-orchestrator/)         │
│                                                      │
│ ├─ Server (stdio handler)                          │
│ ├─ Tools:                                          │
│ │  ├─ fleet-execute                               │
│ │  ├─ fleet-status                                │
│ │  └─ fleet-consensus                             │
│ │                                                  │
│ └─ Core Logic:                                     │
│    ├─ Worker Selection (fleet-utils.js)           │
│    ├─ Model Routing (fleet-orchestrator.js)       │
│    ├─ SSH Execution (remoteExec)                  │
│    └─ Result Tracking (workflow-storage)          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Fleet Infrastructure (Existing)                     │
│                                                      │
│ ├─ 8 Workers (SSH accessible)                      │
│ ├─ 9 API Providers (configured)                    │
│ ├─ fleet-utils.js (getWorkers, remoteExec)        │
│ ├─ fleet-orchestrator.js (model routing)          │
│ └─ workflow-storage-adapter.cjs (tracking)        │
└─────────────────────────────────────────────────────┘
```

## MCP Tools Exposed

### 1. `fleet-execute`

Execute a task on the fleet with automatic worker selection.

**Input Schema:**
```json
{
  "model": "gpt-4o",           // Any of 9 providers
  "prompt": "string",          // Task prompt
  "worker": "auto",            // Or specific: "server-01"
  "task_type": "code_review",  // For Thompson Sampling
  "timeout": 120000            // Optional
}
```

**Output:**
```json
{
  "result": "string",
  "execution_host": "server-01",
  "model_used": "gpt-4o",
  "provider": "openai",
  "tokens": {"input": 1500, "output": 800},
  "cost_usd": 0.05,
  "duration_ms": 5000
}
```

### 2. `fleet-status`

Get current fleet health and availability.

**Input Schema:**
```json
{
  "detailed": true  // Include per-worker stats
}
```

**Output:**
```json
{
  "total_workers": 8,
  "healthy_workers": 8,
  "workers": [
    {"hostname": "server-01", "status": "healthy", "load": 0.3},
    {"hostname": "server-02", "status": "healthy", "load": 0.5}
  ],
  "providers": ["anthropic", "openai", "google", ...]
}
```

### 3. `fleet-consensus`

Run multi-model consensus across fleet.

**Input Schema:**
```json
{
  "question": "string",
  "models": ["opus", "gpt-4o", "gemini-2.0-flash"],
  "task_type": "code_review"
}
```

**Output:**
```json
{
  "consensus": "Answer A",
  "confidence": 0.87,
  "votes": [
    {"model": "opus", "answer": "A", "confidence": 0.92},
    {"model": "gpt-4o", "answer": "A", "confidence": 0.85}
  ],
  "workers_used": ["server-01", "server-02", "server-03"]
}
```

## Implementation Plan

### Phase 1: MCP Server Skeleton (Day 1)

**Files to create:**
- `~/.claude/mcp-servers/fleet-orchestrator/package.json`
- `~/.claude/mcp-servers/fleet-orchestrator/server.mjs`
- `~/.claude/mcp-servers/fleet-orchestrator/tools/fleet-execute.mjs`

**Tasks:**
1. Set up MCP server with stdio transport
2. Implement tool registration
3. Test with simple echo tool

**Acceptance Criteria:**

1. **MCP server starts without errors**
   - Server process starts successfully when invoked
   - No uncaught exceptions during startup
   - Process listens on stdio properly
   - Startup time < 2 seconds

2. **Responds to tools/list with 3 tools**
   - MCP client can list available tools
   - Returns exactly 3 tools: `fleet-execute`, `fleet-status`, `fleet-consensus`
   - Each tool has name, description, and input schema
   - Schemas are valid JSON per MCP spec

3. **Echo tool returns correct output**
   - Test tool accepts simple string input
   - Returns echoed output with proper formatting
   - Handles empty input gracefully
   - Timeout doesn't occur for simple operations

4. **Server handles malformed input gracefully**
   - Rejects invalid JSON in requests with error response
   - Missing required fields produce clear error messages
   - Invalid tool names return "tool not found" error
   - No server crashes on bad input

5. **Server exits cleanly on SIGTERM**
   - Process terminates within 2 seconds of SIGTERM
   - No zombie processes left behind
   - Database connections (if any) closed properly
   - Exit code 0 on clean shutdown

**Validation Script:** `tests/phase-1-acceptance.sh`

### Phase 2: Fleet Integration (Day 2-3)

**Files to modify:**
- `~/.claude/mcp-servers/fleet-orchestrator/lib/worker-selector.mjs`
- `~/.claude/mcp-servers/fleet-orchestrator/lib/ssh-executor.mjs`
- `~/.claude/mcp-servers/fleet-orchestrator/lib/model-router.mjs`

**Tasks:**
1. Import fleet-utils.js (getWorkers, remoteExec)
2. Import fleet-orchestrator.js (model routing)
3. Implement worker selection logic
4. Implement SSH execution wrapper
5. Handle execution_host tracking

**Acceptance Criteria:**

1. **Task executes on 3+ different workers**
   - Same task assigned to different workers executes successfully
   - execution_host field populated with different values
   - Each worker returns distinct execution_host in 3+ test runs
   - No single worker always selected (proper distribution)

2. **Worker selection respects 'auto' and explicit modes**
   - When worker='auto', selects available worker from pool
   - When worker='server-01', executes on server-01 specifically
   - When specified worker unavailable, returns clear error (not fallback)
   - Selection algorithm picks least-loaded worker in 'auto' mode

3. **SSH timeout produces clear error within 30 seconds**
   - SSH command timeout returns within 30 seconds
   - Error message clearly indicates SSH timeout
   - No hung processes left after timeout
   - Graceful cleanup of SSH connection

4. **execution_host field populated in output**
   - All execution results include execution_host field
   - Hostname matches actual execution location
   - Format is valid hostname (e.g., 'server-01', 'laptop-01')
   - Populated even on error conditions (where applicable)

**Validation Script:** `tests/phase-2-acceptance.sh`

### Phase 3: Model Routing (Day 4)

**Files:**
- `~/.claude/mcp-servers/fleet-orchestrator/lib/provider-router.mjs`

**Tasks:**
1. Map model names to providers
2. Route to correct API (OpenAI, Google, Groq, etc.)
3. Handle API credentials
4. Error handling and fallbacks

**Acceptance Criteria:**

1. **All 9 API providers accessible**
   - Anthropic: Can execute with claude-opus-4
   - OpenAI: Can execute with gpt-4o
   - Google: Can execute with gemini-2.0-flash
   - Groq: Can execute with mixtral-8x7b-32768
   - Together: Can execute with llama-3-70b
   - Mistral: Can execute with mistral-large
   - HuggingFace: Can execute with available model
   - Cohere: Can execute with command-r-plus
   - Ollama: Can execute with local model
   - Each returns successful response with tokens

2. **Model routing selects correct provider**
   - Model name 'gpt-4o' routes to OpenAI provider
   - Model name 'gemini-2.0-flash' routes to Google provider
   - Model name 'claude-opus-4' routes to Anthropic
   - All 9 provider mappings correct
   - No cross-provider routing errors

3. **API authentication works for each provider**
   - API keys read from environment variables
   - Each provider validates credentials before execution
   - Invalid credentials return auth error (not generic error)
   - Credentials not logged or exposed in output
   - All 9 providers authenticate successfully

4. **Costs tracked accurately**
   - Input and output tokens counted per provider
   - Cost calculation correct per provider pricing
   - Cost appears in execution output
   - All 9 providers tracked with correct formulas
   - Total cost sum matches individual provider costs

**Validation Script:** `tests/phase-3-acceptance.sh`

### Phase 4: Result Tracking (Day 5)

**Files:**
- `~/.claude/mcp-servers/fleet-orchestrator/lib/result-tracker.mjs`

**Tasks:**
1. Integrate workflow-storage-adapter.cjs
2. Store execution_host, model, tokens, cost
3. Update PostgreSQL workflow.worker_results

**Acceptance Criteria:**

1. **Database writes succeed for all tools**
   - fleet-execute results written to workflow.worker_results
   - fleet-status results written to workflow.executions
   - fleet-consensus results written to workflow.arbiter_decisions
   - No SQL errors on insertion
   - All 3 tools store data successfully

2. **execution_host and execution_hosts populated**
   - Single execution: execution_host field has hostname
   - Consensus/multi-worker: execution_hosts array populated
   - All execution results include host information
   - Host data persists in PostgreSQL queries
   - No NULL values where hosts should exist

3. **Metrics exported correctly**
   - Prometheus metrics exported at /metrics endpoint
   - Metrics include: execution_count, cost_total, duration_ms_histogram
   - Each metric tagged with provider, model, worker
   - Metrics incrementally update across requests
   - Grafana can query and display metrics

4. **Graceful degradation verified**
   - When PostgreSQL unavailable, tool executes but skips database write
   - When metrics unavailable, tool executes normally
   - All execution results returned even if database fails
   - Error messages distinguish between execution and storage failures
   - No cascading failures to MCP tool output

**Validation Script:** `tests/phase-4-acceptance.sh`

### Phase 5: Testing & Documentation (Day 6-7)

**Files:**
- `~/.claude/mcp-servers/fleet-orchestrator/README.md`
- `~/.claude/mcp-servers/fleet-orchestrator/tests/`
- Example workflows using the MCP server

**Tasks:**
1. Unit tests for each tool
2. Integration tests (SSH, database)
3. Documentation with examples
4. Migration guide for existing workflows

**Validation:** All tests pass, docs complete

## Configuration

**~/.claude/config/claude_desktop_config.json:**
```json
{
  "mcpServers": {
    "fleet-orchestrator": {
      "command": "node",
      "args": ["/home/sfloess/.claude/mcp-servers/fleet-orchestrator/server.mjs"],
      "env": {
        "FLEET_CONFIG": "/home/sfloess/.claude/fleet.json"
      }
    }
  }
}
```

## Migration Path

**Before (current):**
```javascript
const result = await agent(prompt, { model: 'opus' });
// Runs locally, Anthropic only
```

**After (with MCP):**
```javascript
const result = await useTool('fleet-orchestrator', {
  model: 'gpt-4o',
  prompt: prompt,
  worker: 'auto',
  task_type: 'code_review'
});
// Runs on fleet, any provider
```

## Success Metrics

1. ✅ Workflows can use all 9 API providers
2. ✅ Tasks distributed across 8 fleet workers
3. ✅ execution_host tracked in database
4. ✅ No performance regression vs local execution
5. ✅ Reusable by CLI tools, not just workflows

## Dependencies

**Existing (reuse):**
- fleet-utils.js
- fleet-orchestrator.js
- workflow-storage-adapter.cjs
- fleet.json

**New (install):**
- @modelcontextprotocol/sdk (npm package)

## Risk Mitigation

1. **Risk:** MCP server crashes → workflows fail
   - **Mitigation:** Graceful fallback to local execution

2. **Risk:** SSH connection failures
   - **Mitigation:** Retry with backoff, fallback to other workers

3. **Risk:** API key issues
   - **Mitigation:** Pre-flight validation, clear error messages

4. **Risk:** Performance slower than local
   - **Mitigation:** Measure and optimize, parallel execution

## Timeline

- **Day 1:** MCP skeleton + tool registration
- **Day 2-3:** Fleet integration (SSH, workers)
- **Day 4:** Model routing (9 providers)
- **Day 5:** Result tracking (database)
- **Day 6-7:** Testing + documentation

**Total:** 5-7 days to production-ready MCP server

## Next Steps

1. Create Issue #10 implementation task
2. Set up MCP server directory structure
3. Install @modelcontextprotocol/sdk
4. Begin Phase 1 implementation
