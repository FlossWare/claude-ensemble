# Workflow Migration Guide

## Before (Current)
\`\`\`javascript
const result = await agent(prompt, { model: 'opus' });
// Runs locally, Anthropic only
\`\`\`

## After (MCP Fleet Orchestrator)
\`\`\`javascript
const result = await useTool('fleet-orchestrator', {
  model: 'gpt-4o',
  prompt: prompt,
  worker: 'auto',
  task_type: 'code_review'
});
// Runs on fleet, any provider
\`\`\`

## Migration Steps
1. Add MCP import to workflow
2. Replace agent() calls with useTool('fleet-orchestrator')
3. Update model names (opus/sonnet/haiku)
4. Test workflow execution
5. Verify execution_host populated in database

## Backward Compatibility
Use agent-shim for gradual migration - works with or without MCP server.
