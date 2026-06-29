# MCP Server Deployment Checklist

## Pre-Deployment
- [ ] All 8 workers accessible via SSH
- [ ] PostgreSQL connection validated
- [ ] API credentials verified on all workers
- [ ] Database migrations applied

## Deployment
- [ ] npm install in mcp-servers/fleet-orchestrator
- [ ] Update ~/.claude/claude_desktop_config.json
- [ ] Start MCP server
- [ ] Verify tools/list response

## Post-Deployment
- [ ] Run smoke tests
- [ ] Check execution_host populated
- [ ] Monitor error rates

## Rollback
- [ ] Remove from claude_desktop_config.json
- [ ] Restart Claude Desktop
- [ ] Verify workflows fall back to local execution
