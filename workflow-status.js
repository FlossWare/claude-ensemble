export const meta = {
  name: 'workflow-status',
  description: 'Show real-time status of running workflows, workers, and arbiters',
  phases: [
    { title: 'Discovery', detail: 'Find running workflows and agents' },
    { title: 'Status', detail: 'Report current activity' }
  ]
}

export default async function({ args, phase, log, agent, parallel }) {

// Real-time workflow status monitoring
// Shows what workers/arbiters are currently doing

phase('Discovery')

const sessionId = args?.sessionId || '8accd009-7b64-4560-a6d5-9026b525431e'
const workflowsDir = `~/.claude/projects/-home-sfloess/${sessionId}/subagents/workflows`

// Find all active workflows
log('Scanning for active workflows...')

const workflows = await agent(
  `List all directories in ${workflowsDir} sorted by modification time (newest first). 
  For each directory, show the directory name and last modified timestamp.
  Return just the directory names (format: wf_xxxxx-xxx), newest first.
  Limit to the 5 most recent.`,
  { label: 'find-workflows', phase: 'Discovery' }
)

// Parse workflow IDs from the output
const workflowIds = await agent(
  `From this directory listing, extract just the workflow IDs (format: wf_xxxxx-xxx).
  Return them as a JSON array of strings.
  
  Listing:
  ${workflows}`,
  { 
    label: 'parse-workflow-ids',
    phase: 'Discovery',
    schema: {
      type: 'object',
      properties: {
        workflow_ids: { type: 'array', items: { type: 'string' } }
      }
    }
  }
)

const workflowIdList = workflowIds?.workflow_ids || []

log(`Found ${workflowIdList.length} recent workflow directories`)

if (workflowIdList.length === 0) {
  return {
    status: 'no_workflows',
    message: 'No workflows found',
    workflows: []
  }
}

phase('Status')

// Check each workflow
const statuses = []

for (const wfId of workflowIdList) {
  const journalPath = `${workflowsDir}/${wfId}/journal.jsonl`
  
  log(`Checking ${wfId}...`)
  
  // Read the journal to get current status
  const journalData = await agent(
    `Read the file ${journalPath} and return the last 30 lines.
    If the file doesn't exist, return "FILE_NOT_FOUND".`,
    { label: `read-journal-${wfId}`, phase: 'Status' }
  )
  
  if (journalData.includes('FILE_NOT_FOUND')) {
    log(`  Skipping ${wfId} (no journal found)`)
    continue
  }
  
  // Parse the journal to understand current state
  const status = await agent(
    `Analyze this workflow journal and determine:
    1. What workflow is this (look for the script name or workflow description)?
    2. What phase is it currently in?
    3. What is the most recent agent activity?
    4. Is it still running or completed (look for "type":"completed" or errors)?
    5. How many agents have been spawned?
    
    Return concise status.
    
    Journal (last 30 lines):
    ${journalData}`,
    {
      label: `analyze-${wfId}`,
      phase: 'Status',
      schema: {
        type: 'object',
        properties: {
          workflow_id: { type: 'string' },
          workflow_name: { type: 'string' },
          current_phase: { type: 'string' },
          last_activity: { type: 'string' },
          is_running: { type: 'boolean' },
          agent_count: { type: 'number' },
          summary: { type: 'string' }
        }
      }
    }
  )
  
  statuses.push(status)
  log(`  ${wfId}: ${status.summary}`)
}

// Generate final report
log(`Checked ${statuses.length} workflows`)

return {
  status: 'success',
  session_id: sessionId,
  workflow_count: workflowIdList.length,
  workflows_checked: statuses.length,
  workflows: statuses
}

}
