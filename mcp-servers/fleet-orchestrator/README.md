# Fleet Orchestrator MCP Server

Distributed task execution across 8-node fleet with 9 API providers.

## Status

✅ **Production Ready**
- MCP Server: Working
- Tools: 2 (fleet-execute, fleet-status)
- Workers: 8 nodes
- Providers: 9 APIs
- Error Handling: Retry + Circuit Breaker
- Tests: 7 passing + integration

## Quick Start

\`\`\`bash
# Install
cd mcp-servers/fleet-orchestrator
npm install

# Test
npm test

# Run
node index.js
\`\`\`

## Architecture

\`\`\`
Claude Desktop
    ↓ (stdio)
MCP Server (index.js)
    ↓
Tools (fleet-execute, fleet-status)
    ↓
SSH → 8 Workers
    ↓
9 API Providers
    ↓
PostgreSQL (execution tracking)
\`\`\`

## Tools

### fleet-execute

Execute task on distributed fleet.

**Input:**
\`\`\`json
{
  "task": "Analyze code for bugs",
  "model": "opus",
  "worker": "auto"
}
\`\`\`

**Output:**
\`\`\`json
{
  "success": true,
  "model": "opus",
  "worker": "server-01",
  "execution_host": "server-01",
  "output": "..."
}
\`\`\`

### fleet-status

Get fleet health.

**Input:**
\`\`\`json
{ "detailed": true }
\`\`\`

**Output:**
\`\`\`json
{
  "total_workers": 8,
  "healthy_workers": 8,
  "workers": [...]
}
\`\`\`

## Files

- \`index.js\` - MCP server entry point
- \`tools/fleet-execute.js\` - Distributed execution
- \`tools/fleet-status.js\` - Health monitoring
- \`lib/retry.js\` - Exponential backoff
- \`lib/circuit-breaker.js\` - Failure protection
- \`test/\` - Test suite (7 failure + integration)

## Claude Desktop Config

Add to \`~/.claude/claude_desktop_config.json\`:

\`\`\`json
{
  "mcpServers": {
    "fleet-orchestrator": {
      "command": "node",
      "args": ["/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/mcp-servers/fleet-orchestrator/index.js"]
    }
  }
}
\`\`\`

## Testing

\`\`\`bash
# Unit tests
npm test

# Manual test
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node index.js

# Fleet status
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"fleet-status","arguments":{}}}' | node index.js
\`\`\`

## Integration Complete

- ✅ Retry logic active
- ✅ Circuit breaker active  
- ✅ SSH distribution working
- ✅ Database tracking enabled
- ✅ All tests passing
