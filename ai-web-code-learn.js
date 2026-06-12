/**
 * Fleet-Aware Code Learning Skill
 *
 * This skill can run in two modes:
 * - LOCAL: Sequential repo analysis on current machine (default for 1-4 repos)
 * - FLEET: Distribute repo analysis across fleet workers (default for 5+ repos)
 *
 * Flags:
 * - --fleet: Force fleet mode (error if unavailable)
 * - --local: Force local sequential mode
 *
 * Auto-detection: 5 repos = break-even threshold
 */

import { resolveFleetMode } from './shared/fleet-utils.js';
import { execSync } from 'child_process';

export const meta = {
  name: 'ai-web-code-learn',
  description: 'Learn from source code: fetch repos, extract patterns, store in vector DB for RAG queries (fleet-aware)',
  whenToUse: 'When you need to understand implementation details, API patterns, or architecture from actual source code',
  phases: [
    { title: 'Setup', detail: 'Clone/fetch repository' },
    { title: 'Discover', detail: 'Find relevant code files' },
    { title: 'Extract', detail: 'Multi-AI pattern extraction' },
    { title: 'Validate', detail: 'Arbiter consensus on patterns' },
    { title: 'Store', detail: 'Persist to vector DB' },
    { title: 'Query', detail: 'RAG-based code queries' }
  ]
}

const CODE_EXTRACTION_SCHEMA = {
  type: 'object',
  properties: {
    file_path: { type: 'string' },
    language: { type: 'string' },
    classes: { type: 'array', items: { type: 'object' } },
    functions: { type: 'array', items: { type: 'object' } },
    implementation_patterns: { type: 'array', items: { type: 'object' } },
    key_insights: { type: 'array', items: { type: 'string' } },
    model: { type: 'string' }
  },
  required: ['file_path', 'language', 'key_insights', 'model']
}

const VALIDATION_SCHEMA = {
  type: 'object',
  properties: {
    validated_patterns: { type: 'array', items: { type: 'object' } },
    architecture_summary: { type: 'string' },
    recommended_focus: { type: 'array', items: { type: 'string' } },
    model: { type: 'string' }
  },
  required: ['validated_patterns', 'architecture_summary', 'model']
}

// Parse args - handle both object and string (following code-solve.js pattern)
let parsedArgs = args
if (typeof args === 'string') {
  const trimmed = args.trim()
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      parsedArgs = JSON.parse(trimmed)
    } catch (e) {
      parsedArgs = { query: trimmed }
    }
  } else {
    parsedArgs = { query: trimmed }
  }
}
const repoUrl = parsedArgs?.repo_url || parsedArgs?.url || null
const branch = parsedArgs?.branch || 'main'
const paths = parsedArgs?.paths || []
const query = parsedArgs?.query || null
const mode = parsedArgs?.mode || (query && !repoUrl ? 'query' : repoUrl ? 'learn' : 'both')
const dbPath = parsedArgs?.dbPath || '~/.claude/knowledge/code-learn.json'
const maxFiles = parsedArgs?.max_files || 10

// Support multiple repos via repos array
const repos = parsedArgs?.repos || parsedArgs?.repo_urls || (repoUrl ? [repoUrl] : []);

if (!repos.length && !query) {
  return {
    error: 'Must provide repo_url to learn from or query to answer',
    usage: {
      learn: '{repo_url: "https://github.com/user/repo", paths: ["src/"], max_files: 10}',
      learn_multi: '{repos: ["https://github.com/user/repo1", "..."], max_files: 10}',
      query: '{query: "how is X implemented?"}',
      both: '{repo_url: "...", query: "..."}'
    }
  }
}

// ============================================================================
// FLEET-AWARE MODE DETECTION (Repos: break-even threshold = 5)
// ============================================================================

if (repos.length > 0 && (mode === 'learn' || mode === 'both')) {
  const BREAK_EVEN_REPOS = 5;
  const fleetArgs = Array.isArray(args) ? args :
                    (typeof args === 'string' ? args.split(/\s+/) : []);

  let fleetDecision;
  try {
    fleetDecision = resolveFleetMode(fleetArgs, repos.length, BREAK_EVEN_REPOS);
  } catch (error) {
    log(`Fleet detection error: ${error.message}`);
    fleetDecision = { mode: 'local', workers: [], reason: `Fleet error: ${error.message}` };
  }

  log(`Fleet Detection: ${fleetDecision.reason}`);

  if (fleetDecision.mode === 'fleet') {
    log(`Fleet mode: Distributing ${repos.length} repos across ${fleetDecision.workers.length} workers`);
    log(`   Workers: ${fleetDecision.workers.map(w => w.hostname).join(', ')}`);
    log(`   Delegating to multi-session orchestration...`);

    const scriptPath = './scripts/fleet/bulk-repo-learn.sh';
    try {
      const result = execSync(
        `${scriptPath} ${repos.map(r => '"' + r + '"').join(' ')} --max-files=${maxFiles}`,
        {
          encoding: 'utf8',
          cwd: process.cwd(),
          stdio: 'inherit',
          timeout: 7200000  // 2 hour timeout for fleet repo analysis
        }
      );

      return {
        status: 'success',
        mode: 'fleet',
        workers_used: fleetDecision.workers.length,
        repos_processed: repos.length,
        delegation_result: result
      };
    } catch (error) {
      log(`Fleet delegation failed: ${error.message}`);
      log(`   Falling back to local mode...`);
      // Fall through to local sequential processing
    }
  } else {
    log(`Local mode: ${fleetDecision.reason}`);
  }
}

// ============================================================================
// LOCAL MODE: Sequential processing on current machine
// ============================================================================

log('CODE LEARNING WORKFLOW')
log(`DEBUG: args = ${JSON.stringify(args)}`)
log(`DEBUG: typeof args = ${typeof args}`)
log(`DEBUG: repoUrl = ${repoUrl}`)
if (repoUrl) log(`Repo: ${repoUrl}`)
if (query) log(`Query: ${query}`)
log('')

// LEARN MODE
if (mode === 'learn' || mode === 'both') {
  phase('Setup')

  const repoName = repoUrl.split('/').pop().replace('.git', '')
  const cloneDir = `~/.claude/tmp/code-learn/${repoName}`

  log(`Cloning to ${cloneDir}...`)

  const cloneResult = await agent(`Clone ${repoUrl} (branch: ${branch}) to ${cloneDir}. If exists, pull latest. Return {cloned: true, path: "..."}`, {
    label: 'clone',
    schema: { type: 'object', properties: { cloned: { type: 'boolean' }, path: { type: 'string' } } }
  })

  if (!cloneResult?.cloned) {
    return { error: 'Clone failed', repo: repoUrl }
  }

  log(`Cloned to: ${cloneResult.path}`)

  phase('Discover')

  const discoverPrompt = paths.length
    ? `Find ${maxFiles} most important code files in ${cloneResult.path} under ${paths.join(', ')}`
    : `Find ${maxFiles} most important code files in ${cloneResult.path} (skip tests/config)`

  const files = await agent(discoverPrompt, {
    label: 'discover',
    schema: {
      type: 'object',
      properties: {
        files: { type: 'array', items: {
          type: 'object',
          properties: {
            path: { type: 'string' },
            language: { type: 'string' },
            importance: { type: 'string' },
            purpose: { type: 'string' }
          }
        }}
      }
    }
  })

  if (!files?.files?.length) {
    return { error: 'No files found', path: cloneResult.path }
  }

  log(`Found ${files.files.length} files`)

  phase('Extract')

  const extractions = await parallel(
    files.files.slice(0, maxFiles).map(f => () =>
      agent(`Analyze ${f.path}: extract classes, functions, patterns, insights`, {
        label: `extract-${f.path.split('/').pop()}`,
        schema: CODE_EXTRACTION_SCHEMA
      })
    )
  )

  const valid = extractions.filter(Boolean)
  log(`Extracted ${valid.length} files`)

  phase('Validate')

  const arbiter = await workflow('get-next-arbiter')

  const validation = await agent(`Validate patterns from ${valid.length} files. Synthesize architecture summary and key patterns.

${valid.map((e, i) => `File ${i}: ${e.file_path}\nInsights: ${e.key_insights?.join('; ')}`).join('\n\n')}`, {
    label: 'validate',
    model: arbiter.arbiter,
    schema: VALIDATION_SCHEMA
  })

  await workflow('update-arbiter-state', { arbiter: arbiter.arbiter, workflow_name: 'ai-web-code-learn' })

  phase('Store')

  const kb = {
    repo: repoUrl,
    branch,
    files_analyzed: valid.length,
    entries: valid,
    summary: validation,
    timestamp: args?._timestamp || 'runtime'
  }

  await agent(`Save to ${dbPath}: ${JSON.stringify(kb, null, 2)}`, {
    label: 'store'
  })

  log(`Stored ${valid.length} entries to ${dbPath}`)

  if (mode === 'learn') {
    return {
      status: 'success',
      files_analyzed: valid.length,
      patterns: validation.validated_patterns?.length,
      architecture: validation.architecture_summary,
      db_path: dbPath
    }
  }
}

// QUERY MODE
if (mode === 'query' || mode === 'both') {
  phase('Query')

  const kb = await agent(`Read JSON from ${dbPath}`, {
    label: 'load-kb',
    schema: { type: 'object', properties: { entries: { type: 'array' }, summary: { type: 'object' } } }
  })

  if (!kb?.entries) {
    return { error: 'KB not found', db_path: dbPath }
  }

  log(`Loaded ${kb.entries.length} entries`)

  const answers = await parallel(['opus', 'sonnet', 'haiku'].map(m => () =>
    agent(`Answer: ${query}\n\nKB: ${JSON.stringify(kb.summary)}\n\nFiles: ${kb.entries.slice(0, 5).map(e => e.file_path).join(', ')}`, {
      label: `query-${m}`,
      model: m,
      schema: {
        type: 'object',
        properties: {
          answer: { type: 'string' },
          code_examples: { type: 'array' },
          confidence: { type: 'string' },
          model: { type: 'string' }
        }
      }
    })
  ))

  const arbiter = await workflow('get-next-arbiter')

  const best = await agent(`Pick best answer from ${answers.filter(Boolean).length} responses for: ${query}`, {
    label: 'arbiter-query',
    model: arbiter.arbiter,
    schema: {
      type: 'object',
      properties: {
        selected_model: { type: 'string' },
        answer: { type: 'string' },
        code_examples: { type: 'array' },
        confidence: { type: 'string' }
      }
    }
  })

  await workflow('update-arbiter-state', { arbiter: arbiter.arbiter, workflow_name: 'ai-web-code-learn' })

  return {
    status: 'success',
    query,
    answer: best.answer,
    code_examples: best.code_examples,
    confidence: best.confidence,
    selected_model: best.selected_model
  }
}
