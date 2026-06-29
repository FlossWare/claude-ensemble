#!/usr/bin/env node
export const meta = {
  name: 'git-commit-deployment',
  description: 'Commit MCP fleet orchestrator deployment using fleet for verification',
  phases: [
    { title: 'Pre-commit Review', detail: 'Fleet reviews changes before commit' },
    { title: 'Git Operations', detail: 'Commit and document changes' }
  ]
};

export default async function({ args, phase, log, agent, parallel }) {

phase('Pre-commit Review');

log('Fleet reviewing changes before commit...');

const review = await agent(`Review changes for git commit:

Run these checks:

1. Git status - what files changed?
2. Check for sensitive data (API keys in code)
3. Verify all new files are documented
4. Check that tests pass

Return JSON:
{
  "files_changed": [],
  "sensitive_data_found": false,
  "ready_to_commit": true/false,
  "recommendations": []
}`,
{ label: 'Pre-commit review', model: 'sonnet', effort: 'medium' });

log('Pre-commit review complete');

phase('Git Operations');

const commit = await agent(`Create git commit for MCP fleet orchestrator:

1. Stage all relevant files:
   - mcp-servers/fleet-orchestrator/**
   - shared/execute-on-worker.js
   - shared/fleet-utils.js (modified)
   - scripts/sync-fleet.sh
   - scripts/distribute-credentials.sh
   - scripts/test-distributed-execution.sh
   - scripts/monitor-fleet-activity.sh
   - MCP_FLEET_ORCHESTRATOR_COMPLETE.md
   - FLEET_REVIEW_RESULTS.md

2. Create commit with message:
   "feat: MCP fleet orchestrator with true distributed execution

   - Implement execute-on-worker.js for SSH-based distribution
   - Workers actually execute API calls (not just metadata)
   - Distribute credentials to all 8 workers
   - Add fleet sync and monitoring scripts
   - Comprehensive documentation and deployment guide

   Verified working:
   - 8/8 workers online
   - Groq, Google, Cohere APIs working
   - True distributed execution confirmed
   - Database tracking execution_host

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

3. Do NOT commit:
   - ~/.bashrc (has API keys)
   - credentials.json (sensitive)
   - .env files

Return JSON:
{
  "committed": true/false,
  "commit_hash": "...",
  "files_committed": []
}`,
{ label: 'Git commit', model: 'opus', effort: 'high' });

log('Git operations complete');

return {
  review,
  commit,
  success: review?.ready_to_commit && commit?.committed
};

}
