import { coordinateWork, createIssueClaimer } from '../shared/work-coordinator.js'

export const meta = {
  name: 'code-debug',
  description: 'Multi-AI debugging workflow with remote execution support',
  phases: [
    { title: 'Discovery', detail: 'Discover available AI models' },
    { title: 'Analyze Bug', detail: 'Analyze the bug report' },
    { title: 'Generate Fixes', detail: 'Multiple AIs propose debugging solutions' },
    { title: 'Select Best', detail: 'Choose best fix via consensus' },
    { title: 'Apply Fix', detail: 'Apply fix with optional remote execution' },
  ],
}

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000); // 30s timeout

  try {
    const response = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        prompt: prompt.slice(0, 200),
        job_type: jobType,
        estimated_ram: model === 'opus' || model === 'fable' ? 2.0 : model === 'haiku' ? 0.5 : 1.5,
        estimated_duration: 60
      }),
      signal: controller.signal
    });
    clearTimeout(timeout);
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    clearTimeout(timeout);
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000); // 30s timeout

  try {
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
      signal: controller.signal
    });
    clearTimeout(timeout);
  } catch (e) {
    clearTimeout(timeout);
  }
}

// FIX 1: Fixed recursion - was _agent calling _agent, now calls agent
// FIX 3: Remote execution via SSH when dispatch.server is not localhost
const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent';
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);

  const start = Date.now();

  // PHASE 3: Remote execution via SSH when server is not localhost
  const isRemote = dispatch.server && dispatch.server !== 'localhost' && dispatch.server !== '127.0.0.1';

  try {
    let result;

    if (isRemote) {
      // Execute on remote server via SSH
      const remotePrompt = JSON.stringify(prompt).replace(/"/g, '\\"');
      const remoteOpts = JSON.stringify(opts).replace(/"/g, '\\"');

      const sshCommand = `ssh ${dispatch.server} "cd /home/claude/claude-global-skills && node -e \\"const {agent} = require('./shared/agent-utils.js'); agent('${remotePrompt}', ${remoteOpts}).then(r => console.log(JSON.stringify(r)));\\""`

      result = await agent(`Execute this command to run agent remotely:
${sshCommand}

Parse the JSON output and return it.`, {
        label: `Remote Agent on ${dispatch.server}`,
        schema: opts.schema
      });
    } else {
      // Local execution
      result = await agent(prompt, opts);
    }

    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


// AUTONOMOUS WORKFLOW - No user prompts or confirmations
const AUTONOMOUS = args?.autonomous !== false
log(`🤖 Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)

// PHASE 0: Model Discovery
phase('Discovery')
log('🔍 Discovering available AI models...')

const availableModels = await discoverAvailableModels()
if (availableModels.length === 0) {
  log('❌ FATAL: No AI models available. Check API keys and model access.')
  return { status: 'error', message: 'No AI models available' }
}
log(`✅ Available models: ${availableModels.join(', ')}`)

// Parse bug report from args
const bugReport = args?.bug || args?.description || 'No bug description provided'
const severity = args?.severity || 'medium'

log(`🐛 Bug Report: ${bugReport}`)
log(`⚠️  Severity: ${severity}`)

// PHASE 1: Analyze Bug
phase('Analyze Bug')

const analysisPrompt = `Analyze this bug report:

**Bug**: ${bugReport}
**Severity**: ${severity}

Provide:
1. **root_cause** - Likely root cause
2. **affected_components** - Which parts of the system are affected
3. **reproduction_steps** - How to reproduce the bug
4. **fix_strategy** - High-level strategy to fix it`

const bugAnalysis = await _agent(analysisPrompt, {
  label: 'Analyze Bug',
  schema: {
    type: 'object',
    properties: {
      root_cause: { type: 'string' },
      affected_components: { type: 'array', items: { type: 'string' } },
      reproduction_steps: { type: 'string' },
      fix_strategy: { type: 'string' }
    },
    required: ['root_cause', 'fix_strategy']
  }
})

log(`✅ Root cause: ${bugAnalysis.root_cause}`)
log(`   Strategy: ${bugAnalysis.fix_strategy}`)

// PHASE 2: Generate Fixes
phase('Generate Fixes')

log('🤖 Generating fixes from multiple AI models...')

const workerModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'].filter(m =>
  availableModels.includes(m)
)
log(`🔄 Worker models: ${workerModels.join(', ')} (${workerModels.length} models)`)

const fixSchema = {
  type: 'object',
  properties: {
    approach: { type: 'string', description: 'High-level approach to fix' },
    code_changes: { type: 'string', description: 'Detailed code changes' },
    files_modified: { type: 'array', items: { type: 'string' } },
    rationale: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 100 },
    test_plan: { type: 'string' },
  },
  required: ['approach', 'code_changes', 'confidence']
}

const fixPrompt = `Generate a fix for this bug:

**Bug**: ${bugReport}
**Root Cause**: ${bugAnalysis.root_cause}
**Fix Strategy**: ${bugAnalysis.fix_strategy}

Provide:
1. **approach** - High-level fix strategy
2. **code_changes** - Specific code modifications needed
3. **files_modified** - List of files to change
4. **rationale** - Why this fix works
5. **confidence** - Your confidence level (0-100)
6. **test_plan** - How to verify the fix works

Be specific and implementable.`

// Generate fixes from all worker models in parallel
const fixes = await parallel(
  workerModels.map(model => () =>
    _agent(fixPrompt, {
      label: `${model} Fix`,
      schema: fixSchema,
      model: model
    })
  )
).then(results => results.filter(Boolean))

const validFixes = fixes

if (validFixes.length === 0) {
  log('❌ No valid fixes generated')
  return { status: 'error', message: 'Failed to generate fixes' }
}

log(`✅ Generated ${validFixes.length} fixes`)

// PHASE 3: Select Best Fix
phase('Select Best')

log(`⚖️ Selecting best fix via arbiter...`)

const arbiterPrompt = `Review these ${validFixes.length} proposed fixes for bug: "${bugReport}"

${validFixes.map((fix, i) => `
**Fix ${i + 1}** (from ${workerModels[i] || 'AI'}):
- Approach: ${fix.approach}
- Confidence: ${fix.confidence}%
- Files: ${fix.files_modified?.join(', ') || 'unspecified'}
- Rationale: ${fix.rationale}
`).join('\n')}

Select the BEST fix based on:
1. Correctness and completeness
2. Confidence level
3. Implementation clarity
4. Minimal risk

Return:
- **selected_index** - Which fix to use (0 to ${validFixes.length - 1})
- **reasoning** - Why this fix is best
- **consensus_score** - Overall confidence in selection (0-100)`

const decision = await _agent(arbiterPrompt, {
  model: 'fable',
  phase: 'Select Best',
  label: 'Arbiter',
  schema: {
    type: 'object',
    properties: {
      selected_index: { type: 'number' },
      reasoning: { type: 'string' },
      consensus_score: { type: 'number', minimum: 0, maximum: 100 },
    },
    required: ['selected_index', 'reasoning']
  }
})

const selectedFix = validFixes[decision.selected_index]
if (!selectedFix || decision.selected_index < 0 || decision.selected_index >= validFixes.length) {
  throw new Error(`Arbiter selected invalid index: ${decision.selected_index}`)
}

log(`✅ Selected Fix #${decision.selected_index + 1}`)
log(`   Reasoning: ${decision.reasoning}`)
log(`   Consensus: ${decision.consensus_score}%`)

// PHASE 4: Apply Fix
phase('Apply Fix')

log('📝 Applying fix to codebase...')

await _agent(`Apply this debugging fix:

**Fix**: ${selectedFix.code_changes}

**Files to modify**: ${selectedFix.files_modified?.join(', ') || 'determine from code_changes'}

1. Make the necessary code changes
2. Stage the changes: git add <files>
3. Commit: git commit -m "fix: ${bugReport}

${selectedFix.approach}

Co-Authored-By: Claude Code <noreply@anthropic.com>"

Return list of files modified.`, {
  label: 'Apply and Commit Fix',
  schema: {
    type: 'object',
    properties: {
      files_modified: { type: 'array', items: { type: 'string' } },
      status: { type: 'string' }
    }
  }
})

log(`✅ Applied and committed fix`)

return {
  status: 'success',
  bug_report: bugReport,
  root_cause: bugAnalysis.root_cause,
  fix_approach: selectedFix.approach,
  confidence: selectedFix.confidence,
  consensus_score: decision.consensus_score,
}

/**
 * Discover available models dynamically
 */
async function discoverAvailableModels() {
  const ALL_MODELS = [
    'fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini',
    'ollama/llama3', 'ollama/llama3:70b',
    'ollama/codestral', 'ollama/deepseek-coder', 'ollama/deepseek-coder:33b',
    'ollama/qwen2.5-coder', 'ollama/qwen2.5-coder:14b'
  ]
  const available = []

  for (const model of ALL_MODELS) {
    try {
      await agent('test', {
        model,
        schema: {type: 'object', properties: {ok: {type: 'boolean'}}, required: ['ok']}
      })
      available.push(model)
      log(`✓ ${model} available`)
    } catch (e) {
      log(`✗ ${model} unavailable`)
    }
  }

  return available
}
