# MCP Fleet Orchestrator - Phase Acceptance Criteria

**Document Status:** Complete  
**Created:** 2026-06-28  
**Updated:** mcp-fleet-orchestrator-design.md with concrete acceptance criteria and validation scripts

## Phase 1: MCP Server Skeleton - 5 Acceptance Criteria

### Criteria

1. **MCP server starts without errors**
   - Server process starts successfully when invoked
   - No uncaught exceptions during startup
   - Process listens on stdio properly
   - Startup time < 2 seconds
   - **Validation:** `tests/phase-1-acceptance.sh` - test_server_startup()

2. **Responds to tools/list with 3 tools**
   - MCP client can list available tools
   - Returns exactly 3 tools: `fleet-execute`, `fleet-status`, `fleet-consensus`
   - Each tool has name, description, and input schema
   - Schemas are valid JSON per MCP spec
   - **Validation:** `tests/phase-1-acceptance.sh` - test_tools_list()

3. **Echo tool returns correct output**
   - Test tool accepts simple string input
   - Returns echoed output with proper formatting
   - Handles empty input gracefully
   - Timeout doesn't occur for simple operations
   - **Validation:** `tests/phase-1-acceptance.sh` - test_echo_tool()

4. **Server handles malformed input gracefully**
   - Rejects invalid JSON in requests with error response
   - Missing required fields produce clear error messages
   - Invalid tool names return "tool not found" error
   - No server crashes on bad input
   - **Validation:** `tests/phase-1-acceptance.sh` - test_malformed_input()

5. **Server exits cleanly on SIGTERM**
   - Process terminates within 2 seconds of SIGTERM
   - No zombie processes left behind
   - Database connections (if any) closed properly
   - Exit code 0 on clean shutdown
   - **Validation:** `tests/phase-1-acceptance.sh` - test_clean_shutdown()

**Test Script:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tests/phase-1-acceptance.sh`

---

## Phase 2: Fleet Integration - 4 Acceptance Criteria

### Criteria

1. **Task executes on 3+ different workers**
   - Same task assigned to different workers executes successfully
   - execution_host field populated with different values
   - Each worker returns distinct execution_host in 3+ test runs
   - No single worker always selected (proper distribution)
   - **Validation:** `tests/phase-2-acceptance.sh` - test_multi_worker_distribution()

2. **Worker selection respects 'auto' and explicit modes**
   - When worker='auto', selects available worker from pool
   - When worker='server-01', executes on server-01 specifically
   - When specified worker unavailable, returns clear error (not fallback)
   - Selection algorithm picks least-loaded worker in 'auto' mode
   - **Validation:** `tests/phase-2-acceptance.sh` - test_worker_selection_modes()

3. **SSH timeout produces clear error within 30 seconds**
   - SSH command timeout returns within 30 seconds
   - Error message clearly indicates SSH timeout
   - No hung processes left after timeout
   - Graceful cleanup of SSH connection
   - **Validation:** `tests/phase-2-acceptance.sh` - test_ssh_timeout_handling()

4. **execution_host field populated in output**
   - All execution results include execution_host field
   - Hostname matches actual execution location
   - Format is valid hostname (e.g., 'server-01', 'laptop-01')
   - Populated even on error conditions (where applicable)
   - **Validation:** `tests/phase-2-acceptance.sh` - test_execution_host_tracking()

**Test Script:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tests/phase-2-acceptance.sh`

---

## Phase 3: Model Routing - 4 Acceptance Criteria

### Criteria

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
   - **Validation:** `tests/phase-3-acceptance.sh` - test_all_providers_accessible()

2. **Model routing selects correct provider**
   - Model name 'gpt-4o' routes to OpenAI provider
   - Model name 'gemini-2.0-flash' routes to Google provider
   - Model name 'claude-opus-4' routes to Anthropic
   - All 9 provider mappings correct
   - No cross-provider routing errors
   - **Validation:** `tests/phase-3-acceptance.sh` - test_model_routing_correct()

3. **API authentication works for each provider**
   - API keys read from environment variables
   - Each provider validates credentials before execution
   - Invalid credentials return auth error (not generic error)
   - Credentials not logged or exposed in output
   - All 9 providers authenticate successfully
   - **Validation:** `tests/phase-3-acceptance.sh` - test_api_authentication()

4. **Costs tracked accurately**
   - Input and output tokens counted per provider
   - Cost calculation correct per provider pricing
   - Cost appears in execution output
   - All 9 providers tracked with correct formulas
   - Total cost sum matches individual provider costs
   - **Validation:** `tests/phase-3-acceptance.sh` - test_cost_tracking()

**Test Script:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tests/phase-3-acceptance.sh`

---

## Phase 4: Result Tracking - 4 Acceptance Criteria

### Criteria

1. **Database writes succeed for all tools**
   - fleet-execute results written to workflow.worker_results
   - fleet-status results written to workflow.executions
   - fleet-consensus results written to workflow.arbiter_decisions
   - No SQL errors on insertion
   - All 3 tools store data successfully
   - **Validation:** `tests/phase-4-acceptance.sh` - test_database_writes()

2. **execution_host and execution_hosts populated**
   - Single execution: execution_host field has hostname
   - Consensus/multi-worker: execution_hosts array populated
   - All execution results include host information
   - Host data persists in PostgreSQL queries
   - No NULL values where hosts should exist
   - **Validation:** `tests/phase-4-acceptance.sh` - test_host_fields_populated()

3. **Metrics exported correctly**
   - Prometheus metrics exported at /metrics endpoint
   - Metrics include: execution_count, cost_total, duration_ms_histogram
   - Each metric tagged with provider, model, worker
   - Metrics incrementally update across requests
   - Grafana can query and display metrics
   - **Validation:** `tests/phase-4-acceptance.sh` - test_metrics_export()

4. **Graceful degradation verified**
   - When PostgreSQL unavailable, tool executes but skips database write
   - When metrics unavailable, tool executes normally
   - All execution results returned even if database fails
   - Error messages distinguish between execution and storage failures
   - No cascading failures to MCP tool output
   - **Validation:** `tests/phase-4-acceptance.sh` - test_graceful_degradation()

**Test Script:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/tests/phase-4-acceptance.sh`

---

## Test Scripts Created

### Phase 1: `tests/phase-1-acceptance.sh`
- 5 test functions
- Tests: Startup, tools/list response, echo tool, error handling, clean shutdown
- Status: ✅ Created and executable

### Phase 2: `tests/phase-2-acceptance.sh`
- 4 test functions
- Tests: Multi-worker distribution, worker selection modes, SSH timeout, host tracking
- Status: ✅ Created and executable

### Phase 3: `tests/phase-3-acceptance.sh`
- 4 test functions
- Tests: Provider accessibility, model routing, authentication, cost tracking
- Status: ✅ Created and executable

### Phase 4: `tests/phase-4-acceptance.sh`
- 4 test functions
- Tests: Database writes, host fields, metrics, graceful degradation
- Status: ✅ Created and executable

---

## Running the Tests

### Run all phase tests:
```bash
bash tests/phase-1-acceptance.sh
bash tests/phase-2-acceptance.sh
bash tests/phase-3-acceptance.sh
bash tests/phase-4-acceptance.sh
```

### Run specific test:
```bash
bash tests/phase-1-acceptance.sh 2>&1 | grep PASS
```

### Integration in CI/CD:
```bash
#!/bin/bash
for phase in 1 2 3 4; do
    echo "Running Phase $phase..."
    bash tests/phase-$phase-acceptance.sh || exit 1
done
echo "All phases passed!"
```

---

## Summary

| Phase | Criteria | Test Functions | Test Script |
|-------|----------|-----------------|-------------|
| 1: MCP Skeleton | 5 | 5 | phase-1-acceptance.sh |
| 2: Fleet Integration | 4 | 4 | phase-2-acceptance.sh |
| 3: Model Routing | 4 | 4 | phase-3-acceptance.sh |
| 4: Result Tracking | 4 | 4 | phase-4-acceptance.sh |
| **Total** | **17** | **17** | **4 scripts** |

---

## Documentation Updates

**Primary Document:** `docs/mcp-fleet-orchestrator-design.md`
- Phase 1 section: Updated with 5 concrete acceptance criteria
- Phase 2 section: Updated with 4 concrete acceptance criteria
- Phase 3 section: Updated with 4 concrete acceptance criteria
- Phase 4 section: Updated with 4 concrete acceptance criteria
- Each phase section references its validation script

**Secondary Document:** `docs/PHASE-ACCEPTANCE-CRITERIA.md` (this file)
- Comprehensive reference for all acceptance criteria
- Links to all test scripts
- Test execution instructions
- Summary table

---

## Next Steps

1. **Implement Phase 1:** Create MCP server skeleton (`~/.claude/mcp-servers/fleet-orchestrator/server.mjs`)
2. **Run Phase 1 Tests:** `bash tests/phase-1-acceptance.sh`
3. **Implement Phase 2:** Add fleet integration (worker selection, SSH)
4. **Run Phase 2 Tests:** `bash tests/phase-2-acceptance.sh`
5. **Implement Phase 3:** Add model routing (9 providers)
6. **Run Phase 3 Tests:** `bash tests/phase-3-acceptance.sh`
7. **Implement Phase 4:** Add result tracking (database, metrics)
8. **Run Phase 4 Tests:** `bash tests/phase-4-acceptance.sh`
9. **Integration Testing:** Run all tests together
10. **Documentation:** Phase 5 (README, migration guides)
