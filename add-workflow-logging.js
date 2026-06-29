export const meta = {
  name: 'add-workflow-logging',
  description: 'Add log() calls to workflows for real-time status visibility',
  phases: [
    { title: 'Analyze', detail: 'Find workflows missing log() calls' },
    { title: 'Enhance', detail: 'Add strategic log() points' }
  ]
}

export default async function({ args, phase, log, agent, parallel }) {

// Adds log() calls to workflows so you can see what they're doing in real-time

phase('Analyze')

const targetWorkflows = [
  'ai-consensus.js',
  'ai-consensus-weighted.js',
  'ai-consensus-filtered.js',
  'ai-consensus-debate.js',
  'ai-consensus-refinement.js',
  'ai-task-router.js',
  'ai-cost-tracker.js'
]

log(`Will add logging to ${targetWorkflows.length} workflows`)

phase('Enhance')

const results = []

for (const workflow of targetWorkflows) {
  const filePath = `~/.claude/repos/claude-global-skills/${workflow}`
  
  log(`Processing ${workflow}...`)
  
  const enhanced = await agent(
    `Read ${filePath} and add log() calls at strategic points to report:
    - When starting a phase
    - When spawning workers (e.g., "Spawning 3 workers: opus, sonnet, haiku")
    - When waiting for results (e.g., "Waiting for worker responses...")
    - When arbiter is analyzing (e.g., "Arbiter evaluating 3 worker responses")
    - When making decisions (e.g., "Confidence threshold met: 85% > 80%")
    - When entering loops (e.g., "Refinement round 2/3")
    
    Use log() liberally so the user can understand what's happening.
    Return ONLY the updated file contents.`,
    { 
      label: `enhance-${workflow}`,
      phase: 'Enhance'
    }
  )
  
  // Write the enhanced version
  await agent(
    `Write the following content to ${filePath}:
    
    ${enhanced}`,
    { label: `write-${workflow}`, phase: 'Enhance' }
  )
  
  results.push({
    workflow: workflow,
    status: 'enhanced',
    path: filePath
  })
}

return {
  status: 'success',
  enhanced_count: results.length,
  workflows: results
}

}
