# MCP Implementation Acceptance Criteria

## Phase 1: MCP Server Skeleton
- [ ] MCP server starts without errors
- [ ] Responds to tools/list with 3 tools
- [ ] Echo tool returns correct output
- [ ] Server handles malformed input gracefully
- [ ] Server exits cleanly on SIGTERM

## Phase 2: Fleet Integration
- [ ] Task executes on 3+ different workers
- [ ] Worker selection respects 'auto' and explicit modes
- [ ] SSH timeout produces clear error within 30s
- [ ] execution_host field populated in output

## Phase 3: Model Routing
- [ ] All 9 API providers accessible
- [ ] Model routing selects correct provider
- [ ] API authentication works for each provider
- [ ] Costs tracked accurately

## Phase 4: Result Tracking
- [ ] Database writes succeed for all tools
- [ ] execution_host and execution_hosts populated
- [ ] Metrics exported correctly
- [ ] Graceful degradation verified
