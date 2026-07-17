export const meta = {
  name: 'self-learning-resolve',
  description: 'Self-learning issue resolver: categorize→fix→review→record→evolve. Learns from past runs via Thompson Sampling + GA.',
  whenToUse: 'When resolving GitHub/GitLab issues. Automatically categorizes, applies the right strategy per type, records outcomes, and evolves. Set platform:"gitlab" for GitLab MRs.',
  phases: [
    { title: 'Learn', detail: 'Query Thompson Sampling + GA state from PostgreSQL' },
    { title: 'Fetch & Categorize', detail: 'Fetch open issues, 3-agent weighted consensus categorization' },
    { title: 'Execute', detail: 'Route by category: fix, track, close, or decompose' },
    { title: 'Review', detail: 'Adversarial review-of-review with weighted consensus' },
    { title: 'Commit', detail: 'Commit consensus-approved fixes, discard rejections' },
    { title: 'Record', detail: 'Store outcomes to Thompson Sampling + experience memory' },
    { title: 'Evolve', detail: 'Mini GA step: crossover + mutation on strategy chromosome' },
    { title: 'Audit', detail: 'Independent final audit of all actions' },
  ],
}

const parsedArgs = typeof args === 'string' ? JSON.parse(args) : (args || {})
const REPO = parsedArgs.repo || 'FlossWare/VirtOS'
const DRY_RUN = parsedArgs.dryRun || false
const TRAINING_MODE = parsedArgs.trainingMode || false
const SKIP_FIXES = parsedArgs.skipFixes || false
const PR_MODE = parsedArgs.prMode || false
const PR_ASSIGNEE = parsedArgs.prAssignee || 'sfloess'
const PLATFORM = parsedArgs.platform || 'github'
const GITLAB_HOST = parsedArgs.gitlabHost || 'gitlab.cee.redhat.com'
const IS_GITLAB = PLATFORM === 'gitlab'
const IS_BITBUCKET = PLATFORM === 'bitbucket'
const IS_SOURCEFORGE = PLATFORM === 'sourceforge'
const SF_TRACKER = parsedArgs.sfTracker || 'tickets'
const USE_GITLAB_API = IS_GITLAB && GITLAB_HOST !== 'gitlab.cee.redhat.com'
const GL_API = `https://${GITLAB_HOST}/api/v4/projects/${encodeURIComponent(REPO)}`
const SF_API = `https://sourceforge.net/rest/p/${REPO}/${SF_TRACKER}`
const CLI = IS_GITLAB ? `GITLAB_HOST=${GITLAB_HOST} glab` : IS_BITBUCKET ? 'curl -s' : 'gh'
const MR_OR_PR = IS_GITLAB ? 'mr' : IS_BITBUCKET ? 'pr' : 'pr'
const REPO_FLAG = IS_GITLAB ? `-R "${GITLAB_HOST}/${REPO}"` : IS_BITBUCKET ? '' : `--repo ${REPO}`
const BB_API = `https://api.bitbucket.org/2.0/repositories/${REPO}`
const issueViewCmd = (num) => IS_SOURCEFORGE ? `curl -s "${SF_API}/${num}" | python3 -c "import sys,json; t=json.load(sys.stdin).get('ticket',{}); print(f\\"#{t.get('ticket_num','')} {t.get('summary','')}\\\\n{t.get('description','')}\\")"` : IS_BITBUCKET ? `curl -s "${BB_API}/issues/${num}" | python3 -m json.tool` : USE_GITLAB_API ? `curl -s "${GL_API}/issues/${num}" | python3 -m json.tool` : IS_GITLAB ? `${CLI} issue view ${num} ${REPO_FLAG}` : `gh issue view ${num} --repo ${REPO}`
const issueListCmd = IS_SOURCEFORGE ? `curl -s "${SF_API}/?limit=50" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\\"#{t['ticket_num']} {t['summary']}\\") for t in d.get('tickets',[])]"` : IS_BITBUCKET ? `curl -s "${BB_API}/issues?status=new&status=open&pagelen=50" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\\"#{i['id']} {i['title']}\\") for i in d.get('values',[])]"` : USE_GITLAB_API ? `curl -s "${GL_API}/issues?state=opened&per_page=50" | python3 -c "import sys,json; issues=json.load(sys.stdin); [print(f\\"#{i['iid']} {i['title']}\\") for i in issues]"` : IS_GITLAB ? `${CLI} issue list ${REPO_FLAG} --per-page 100` : `gh issue list --state open --repo ${REPO} --json number,title,labels,body --limit 100`
const issueCommentsCmd = (num) => IS_SOURCEFORGE ? `curl -s "${SF_API}/${num}" | python3 -c "import sys,json; t=json.load(sys.stdin).get('ticket',{}); [print(p.get('text','')) for p in t.get('discussion_thread',{}).get('posts',[])]"` : IS_BITBUCKET ? `curl -s "${BB_API}/issues/${num}/comments" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(c.get('content',{}).get('raw','')) for c in d.get('values',[])]"` : USE_GITLAB_API ? `curl -s "${GL_API}/issues/${num}/notes?per_page=20" | python3 -c "import sys,json; notes=json.load(sys.stdin); [print(n.get('body','')) for n in notes]"` : IS_GITLAB ? `${CLI} api "projects/:id/issues/${num}/notes" ${REPO_FLAG}` : `gh api repos/${REPO}/issues/${num}/comments --jq '.[].body'`
const cloneUrl = IS_SOURCEFORGE ? `https://svn.code.sf.net/p/${REPO}/code` : IS_BITBUCKET ? `https://bitbucket.org/${REPO}.git` : IS_GITLAB ? `https://${GITLAB_HOST}/${REPO}.git` : `https://github.com/${REPO}.git`
const DB_HOST = 'aio-01'
const DB_PORT = '5433'
const DB_USER = 'claude'
const DB_PASS = 'learning'
const DB_NAME = 'learning'
const API_BASE = 'http://aio-01:5000'

const PSQL = `PGPASSWORD=${DB_PASS} psql -h localhost -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -t -A`
const SSH_PSQL = (sql) => `ssh claude@${DB_HOST} 'bash -c "${PSQL} -c \\"${sql.replace(/"/g, '\\\\\\"')}\\""'`

const externalMetrics = { calls: [], agreement: [], phases: {} }

const COLD_START_DEFAULTS = {
  categories: ['code_fix', 'security_fix', 'milestone', 'enhancement', 'decompose'],
  consensus_threshold: 0.5,
  review_depth: 3,
  confidence_weight_threshold: 0.6,
  category_thresholds: { security_fix: 0.7, code_fix: 0.5, enhancement: 0.3 },
  category_review_depths: { security_fix: 4, code_fix: 3, enhancement: 1, milestone: 0 },
  retry_on_reject: false,
  max_retries: 0,
  max_fix_lines: 200,
  categorizer_count: 3,
  enhancement_strategy: 'label_and_close',
  decompose_sub_count: 5,
  require_test_evidence: false,
  fix_isolation: 'shared',
  fix_model_tier: 'default',
  review_model_tier: 'default',
  max_prior_failures: 2,
  fix_concurrency_limit: 4,
  preflight_gate: 'syntax',
  past_fix_lookup: false,
  few_shot_past_fixes: 0,
  reasoning_depth: 'analyze_first',
  scope_file_limit: 5,
  issue_priority_order: 'fifo',
  code_context_radius: 50,
  error_diagnostic_depth: 'issue_body',
  fix_candidates: 1,
  external_model_count: 3,
  external_model_weight: 0.4,
  external_providers: ['groq', 'cerebras', 'cohere'],
}

const VALID_MODELS = ['sonnet', 'haiku', 'opus']
const tierToModel = (tier) => {
  if (!tier || tier === 'default') return undefined
  if (VALID_MODELS.includes(tier)) return tier
  if (tier === 'high') return 'sonnet'
  if (tier === 'mid' || tier === 'medium') return 'sonnet'
  if (tier === 'low' || tier === 'fast') return 'haiku'
  return undefined
}
const modelOpts = (tier) => {
  const m = tierToModel(tier)
  return m ? { model: m } : {}
}

const CATEGORIZE_SCHEMA = {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          number: { type: 'number' },
          title: { type: 'string' },
          category: { type: 'string' },
          confidence: { type: 'number' },
          reasoning: { type: 'string' },
        },
        required: ['number', 'title', 'category', 'confidence'],
      },
    },
  },
  required: ['issues'],
}

const EXTERNAL_CATEGORIZE_SCHEMA = {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          number: { type: 'number' },
          title: { type: 'string' },
          category: { type: 'string' },
          confidence: { type: 'number' },
          reasoning: { type: 'string' },
          source: { type: 'string' },
        },
        required: ['number', 'title', 'category', 'confidence'],
      },
    },
    model_metrics: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          model: { type: 'string' },
          success: { type: 'boolean' },
          latency_ms: { type: 'number' },
          error: { type: 'string' },
          prompt_tokens: { type: 'number' },
          completion_tokens: { type: 'number' },
          total_tokens: { type: 'number' },
          parseable_json: { type: 'boolean' },
        },
        required: ['model', 'success'],
      },
    },
  },
  required: ['issues'],
}

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    issue_number: { type: 'number' },
    fix_applied: { type: 'boolean' },
    files_changed: { type: 'array', items: { type: 'string' } },
    description: { type: 'string' },
    test_evidence: { type: 'string' },
  },
  required: ['issue_number', 'fix_applied', 'description'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    issue_number: { type: 'number' },
    fix_correct: { type: 'boolean' },
    introduces_bugs: { type: 'boolean' },
    introduces_security_issues: { type: 'boolean' },
    recommendation: { type: 'string', enum: ['approve', 'request_changes', 'reject'] },
    specific_objection: { type: 'string' },
    reasoning: { type: 'string' },
  },
  required: ['issue_number', 'fix_correct', 'recommendation', 'reasoning'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    issue_number: { type: 'number' },
    agrees_with_review: { type: 'boolean' },
    confidence: { type: 'number' },
    missed_issues: { type: 'array', items: { type: 'string' } },
    false_positives: { type: 'array', items: { type: 'string' } },
    reasoning: { type: 'string' },
  },
  required: ['issue_number', 'agrees_with_review', 'confidence', 'reasoning'],
}

const STRATEGY_SCHEMA = {
  type: 'object',
  properties: {
    categories: { type: 'array', items: { type: 'string' } },
    consensus_threshold: { type: 'number' },
    review_depth: { type: 'number' },
    confidence_weight_threshold: { type: 'number' },
    category_thresholds: { type: 'object' },
    category_review_depths: { type: 'object' },
    retry_on_reject: { type: 'boolean' },
    max_retries: { type: 'number' },
    max_fix_lines: { type: 'number' },
    categorizer_count: { type: 'number' },
    enhancement_strategy: { type: 'string' },
    decompose_sub_count: { type: 'number' },
    require_test_evidence: { type: 'boolean' },
    fix_isolation: { type: 'string' },
    fix_model_tier: { type: 'string' },
    review_model_tier: { type: 'string' },
    max_prior_failures: { type: 'number' },
    fix_concurrency_limit: { type: 'number' },
    preflight_gate: { type: 'string' },
    past_fix_lookup: { type: 'boolean' },
    few_shot_past_fixes: { type: 'number' },
    reasoning_depth: { type: 'string' },
    scope_file_limit: { type: 'number' },
    issue_priority_order: { type: 'string' },
    code_context_radius: { type: 'number' },
    error_diagnostic_depth: { type: 'string' },
    fix_candidates: { type: 'number' },
    external_model_count: { type: 'number' },
    external_model_weight: { type: 'number' },
    external_providers: { type: 'array', items: { type: 'string' } },
    source: { type: 'string' },
    repo_context: { type: 'string' },
    reasoning: { type: 'string' },
  },
  required: ['categories', 'consensus_threshold', 'review_depth', 'source'],
}

// ═══════════════════════════════════════════════════════
// PHASE 0: LEARN FROM HISTORY
// ═══════════════════════════════════════════════════════
phase('Learn')
log('Querying Thompson Sampling state and GA chromosomes from PostgreSQL...')

const learnedStrategy = await agent(`Query the learning database to determine the best strategy for resolving GitHub issues.

Run these commands and synthesize:

1. Get Thompson Sampling state for issue resolution strategies:
   curl -s ${API_BASE}/learning/strategies | python3 -m json.tool
   Look for strategies containing "issue", "resolve", "categorize", "fix", "milestone"

2. Get past issue resolution experiences:
   ${SSH_PSQL("SELECT problem_type, strategy, success, reward, context->>'category' as category FROM learning.experiences WHERE problem_type LIKE '%issue%' OR problem_type LIKE '%resolve%' ORDER BY timestamp DESC LIMIT 20")}

3. Get GA-evolved chromosomes (stored in experiment_results):
   ${SSH_PSQL("SELECT experiment_name, method, success_rate, avg_reward, strategy_counts FROM learning.experiment_results WHERE experiment_name LIKE '%issue_resolution%' ORDER BY success_rate DESC LIMIT 5")}

4. Get past workflow execution outcomes:
   ${SSH_PSQL("SELECT workflow_name, outcome, total_duration_ms FROM workflow.executions WHERE workflow_name LIKE '%resolve%' OR workflow_name LIKE '%issue%' ORDER BY started_at DESC LIMIT 10")}

5. Get repo-specific outcomes (how this specific repo performed in past runs):
   ${SSH_PSQL("SELECT context->>'category' as cat, COUNT(*) as total, SUM(CASE WHEN success THEN 1 ELSE 0 END) as ok, SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as fail FROM learning.experiences WHERE problem_type = 'issue_resolution_${REPO.replace('/', '_')}' GROUP BY context->>'category'")}

6. Get repo-specific failure reasons (what went wrong before):
   ${SSH_PSQL("SELECT context->>'category', context->>'action', context FROM learning.experiences WHERE problem_type = 'issue_resolution_${REPO.replace('/', '_')}' AND NOT success ORDER BY timestamp DESC LIMIT 5")}

SYNTHESIZE into a strategy object with ALL 27 genes:
- If GA chromosomes exist with success_rate > 0.7, use the best one (extract ALL fields from strategy_counts JSON)
- If Thompson Sampling shows clear winners (alpha >> beta), prefer those
- Old GA chromosomes may have fewer genes — that's fine, missing genes get defaults automatically
- If no data exists (cold start), all 27 genes will use defaults

The 27 genes to extract/set:
  categories, consensus_threshold, review_depth, confidence_weight_threshold,
  category_thresholds, category_review_depths, retry_on_reject, max_retries,
  max_fix_lines, categorizer_count, enhancement_strategy, decompose_sub_count,
  require_test_evidence, fix_isolation, fix_model_tier, review_model_tier,
  max_prior_failures, fix_concurrency_limit, preflight_gate, past_fix_lookup,
  few_shot_past_fixes, reasoning_depth, scope_file_limit, issue_priority_order,
  code_context_radius, error_diagnostic_depth, fix_candidates,
  external_model_count, external_model_weight, external_providers

REPO-SPECIFIC OVERRIDES (apply on top of GA/Thompson data):
- If repo-specific data shows a category with >30% failure rate, increase that category's review depth by 1 in category_review_depths
- If repo has had security_fix failures, increase security_fix threshold in category_thresholds
- If retry data shows retries rescued fixes, keep retry_on_reject=true
- If repo has many repeat-failure issues, increase max_prior_failures
- Set repo_context to a short description of what kind of codebase this is

Set source to "ga_evolved", "thompson_sampling", or "cold_start" based on what you used.`, {
  label: 'learn-from-history',
  phase: 'Learn',
  schema: STRATEGY_SCHEMA,
})

const strategy = { ...COLD_START_DEFAULTS, ...(learnedStrategy || {}) }
// Normalize tier names to valid model IDs (GA may evolve "mid"/"high" which aren't valid)
strategy.fix_model_tier = tierToModel(strategy.fix_model_tier) || 'default'
strategy.review_model_tier = tierToModel(strategy.review_model_tier) || 'default'
log(`Strategy source: ${strategy.source || 'cold_start'}`)
log(`Categories: ${JSON.stringify(strategy.categories)}`)
log(`Consensus threshold: ${strategy.consensus_threshold} (per-cat: ${JSON.stringify(strategy.category_thresholds || {})})`)
log(`Review depth: ${strategy.review_depth} (per-cat: ${JSON.stringify(strategy.category_review_depths || {})})`)
log(`Categorizer count: ${strategy.categorizer_count}, Max fix lines: ${strategy.max_fix_lines}`)
log(`Retry: ${strategy.retry_on_reject ? 'yes (max ' + strategy.max_retries + ')' : 'no'}, Enhancement: ${strategy.enhancement_strategy}`)
log(`Fix model: ${strategy.fix_model_tier}, Review model: ${strategy.review_model_tier}, Isolation: ${strategy.fix_isolation}`)
log(`Test evidence required: ${strategy.require_test_evidence}, Decompose count: ${strategy.decompose_sub_count}`)
log(`Prior failure skip: ${strategy.max_prior_failures}, Concurrency: ${strategy.fix_concurrency_limit}, Preflight: ${strategy.preflight_gate}`)
log(`Past fix lookup: ${strategy.past_fix_lookup}, Few-shot: ${strategy.few_shot_past_fixes}, Reasoning: ${strategy.reasoning_depth}`)
log(`Scope limit: ${strategy.scope_file_limit} files, Priority: ${strategy.issue_priority_order}, Context: ${strategy.code_context_radius} lines`)
log(`Diagnostics: ${strategy.error_diagnostic_depth}, Candidates: ${strategy.fix_candidates}`)
log(`External models: count=${strategy.external_model_count}, weight=${strategy.external_model_weight}, providers=${JSON.stringify(strategy.external_providers)}`)
if (TRAINING_MODE) log(`🏋️ TRAINING MODE — no remote writes, clone to ~/Development/training/${REPO.replace('/', '-')}`)
if (strategy.repo_context) log(`Repo context: ${strategy.repo_context}`)

// ═══════════════════════════════════════════════════════
// PHASE 1: FETCH & CATEGORIZE ISSUES
// ═══════════════════════════════════════════════════════
phase('Fetch & Categorize')
log(`Fetching open issues from ${REPO} and categorizing with 3-agent weighted consensus...`)

const voterCount = strategy.categorizer_count || 3
const categorizations = await parallel(Array.from({ length: voterCount }, (_, i) => i).map(voterIdx => () =>
  agent(`You are VOTER ${voterIdx + 1} of 3 in a weighted consensus categorization of ${IS_SOURCEFORGE ? 'SourceForge' : IS_GITLAB ? 'GitLab' : IS_BITBUCKET ? 'Bitbucket' : 'GitHub'} issues.

1. Fetch all open issues: ${IS_SOURCEFORGE ? `curl -s "${SF_API}/?limit=50" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(json.dumps({'ticket_num':t['ticket_num'],'summary':t['summary'],'description':t.get('description','')})) for t in d.get('tickets',[])]"` : IS_BITBUCKET ? `curl -s "${BB_API}/issues?status=new&status=open&pagelen=50" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(json.dumps({'id':i['id'],'title':i['title'],'content':i.get('content',{}).get('raw','')})) for i in d.get('values',[])]"` : USE_GITLAB_API ? `curl -s "${GL_API}/issues?state=opened&per_page=50" | python3 -c "import sys,json; issues=json.load(sys.stdin); [print(json.dumps({'iid':i['iid'],'title':i['title'],'description':i.get('description','')})) for i in issues]"` : IS_GITLAB ? `${CLI} issue list ${REPO_FLAG} --per-page 100` : `gh issue list --state open --repo ${REPO} --json number,title,labels,body --limit 100`}
2. For EACH issue, read its full content: ${IS_SOURCEFORGE ? `curl -s "${SF_API}/NUMBER" | python3 -c "import sys,json; t=json.load(sys.stdin).get('ticket',{}); print(json.dumps({'ticket_num':t.get('ticket_num'),'summary':t.get('summary',''),'description':t.get('description',''),'status':t.get('status',''),'labels':t.get('labels',[])}))"` : IS_BITBUCKET ? `curl -s "${BB_API}/issues/NUMBER" | python3 -m json.tool` : USE_GITLAB_API ? `curl -s "${GL_API}/issues/NUMBER" | python3 -m json.tool` : IS_GITLAB ? `${CLI} issue view NUMBER ${REPO_FLAG}` : `gh issue view NUMBER --repo ${REPO}`}
${IS_SOURCEFORGE ? 'NOTE: SourceForge uses "ticket_num" for issue numbers. Map ticket_num→number in your output.' : IS_BITBUCKET ? 'NOTE: Bitbucket issues use "id" instead of "number". Map id→number in your output.' : USE_GITLAB_API ? 'NOTE: GitLab uses "iid" for issue numbers. Map iid→number in your output.' : ''}
3. Categorize each into one of: ${JSON.stringify(strategy.categories)}

Category definitions:
- code_fix: Has a specific bug that can be fixed in <200 lines of code
- security_fix: Security vulnerability requiring a targeted fix
- milestone: Long-term tracking issue, infrastructure-dependent, or requires manual testing
- enhancement: Feature request or improvement that's not a bug
- decompose: Large scope requiring breakdown into sub-issues (>200 lines or multi-system)

For each issue, provide your confidence (0.0-1.0) in the categorization.
High confidence (0.8+) = clear-cut category. Low (0.3-) = ambiguous.

Be INDEPENDENT — don't try to guess what other voters will say.`, {
    label: `categorize-voter-${voterIdx}`,
    phase: 'Fetch & Categorize',
    schema: CATEGORIZE_SCHEMA,
  })
))

const validVotes = categorizations.filter(Boolean)
log(`Got ${validVotes.length}/${voterCount} categorization votes`)

// ── External model categorization (free APIs) ──
const extModelCount = strategy.external_model_count || 0
const extWeight = strategy.external_model_weight || 0.4
const extProviders = strategy.external_providers || ['groq', 'cerebras', 'cohere']
const PROVIDER_MODELS = {
  groq: 'groq/llama-3.3-70b-versatile',
  cerebras: 'cerebras/gpt-oss-120b',
  cohere: 'cohere/command-a-03-2025',
  openrouter: 'openrouter/meta-llama/llama-3.3-70b-instruct:free',
  deepseek: 'deepseek/deepseek-chat',
  mistral: 'mistral/mistral-large-latest',
  deepinfra: 'deepinfra/meta-llama/Meta-Llama-3.1-70B-Instruct',
}
const extModels = extProviders.slice(0, extModelCount).map(p => PROVIDER_MODELS[p] || `${p}/default`).join(',')

if (extModelCount > 0 && validVotes.length > 0) {
  log(`Querying ${extModelCount} external models for categorization: ${extModels}`)
  const issueList = validVotes[0]?.issues?.map(i => `#${i.number} "${i.title}"`).join(', ') || 'no issues'
  const externalCatResult = await agent(`Query external free API models for issue categorization.

Run this command:
~/.claude/lib/multi-model-query.sh --prompt 'Categorize these GitHub issues into one of: ${JSON.stringify(strategy.categories)}. Issues: ${issueList.replace(/'/g, "\\'")}

Category definitions:
- code_fix: specific bug fixable in <200 lines
- security_fix: security vulnerability
- milestone: long-term tracking, infrastructure-dependent
- enhancement: feature request, not a bug
- decompose: large scope, needs breakdown

Reply with JSON: {"issues": [{"number": N, "title": "...", "category": "...", "confidence": 0.0-1.0}]}' --models '${extModels}' --task-type categorization --timeout 25 --max-tokens 1024

Parse the JSON output array. Each element has {model, success, response, error, latency_ms, prompt_tokens, completion_tokens, total_tokens, parseable_json}.

For each SUCCESSFUL model response:
1. Parse its response as JSON (handle markdown code fences)
2. Extract the issues array
3. Add "source" field with the model name to each issue

Return TWO things:
1. "issues": ALL models' categorizations combined as a single issues array
2. "model_metrics": array of {model, success, latency_ms, error, prompt_tokens, completion_tokens, total_tokens, parseable_json} for EVERY model (including failures). Copy these fields directly from the multi-model-query.sh output.

If a model failed or returned unparseable output, still include it in model_metrics with success=false and parseable_json=false.`, {
    label: 'external-categorize',
    phase: 'Fetch & Categorize',
    schema: EXTERNAL_CATEGORIZE_SCHEMA,
  })

  if (externalCatResult) {
    // ── Dim 3: Response parseability + Dim 4: Token usage ──
    if (externalCatResult.model_metrics) {
      for (const m of externalCatResult.model_metrics) {
        externalMetrics.calls.push({ ...m, phase: 'categorize', repo: REPO })
      }
      const succeeded = externalCatResult.model_metrics.filter(m => m.success).length
      const parseable = externalCatResult.model_metrics.filter(m => m.parseable_json).length
      const avgLatency = externalCatResult.model_metrics.filter(m => m.success && m.latency_ms).reduce((s, m) => s + m.latency_ms, 0) / (succeeded || 1)
      const totalTokens = externalCatResult.model_metrics.reduce((s, m) => s + (m.total_tokens || 0), 0)
      externalMetrics.phases.categorize = {
        models_called: externalCatResult.model_metrics.length,
        models_succeeded: succeeded,
        models_parseable: parseable,
        avg_latency_ms: Math.round(avgLatency),
        total_tokens: totalTokens,
        per_model_tokens: externalCatResult.model_metrics.map(m => ({ model: m.model, tokens: m.total_tokens || 0, parseable: m.parseable_json || false })),
      }
      log(`External model metrics: ${succeeded}/${externalCatResult.model_metrics.length} succeeded, ${parseable} parseable, avg latency ${Math.round(avgLatency)}ms, ${totalTokens} tokens total`)
    }
    const extIssuesBefore = externalCatResult.issues ? [...externalCatResult.issues] : []
    if (externalCatResult.issues && externalCatResult.issues.length > 0) {
      const extVoteCount = externalCatResult.issues.length
      for (const issue of externalCatResult.issues) {
        issue.confidence = (issue.confidence || 0.5) * extWeight
      }
      validVotes.push(externalCatResult)
      log(`Added ${extVoteCount} external categorization votes (weight=${extWeight})`)
    }
    externalMetrics._extCatVotes = extIssuesBefore
  }
}

// ── Dim 1: Consensus influence — compute WITH and WITHOUT external votes ──
const claudeOnlyVotes = validVotes.slice(0, voterCount)
const claudeOnlyMap = {}
for (const vote of claudeOnlyVotes) {
  if (!vote.issues) continue
  for (const issue of vote.issues) {
    if (!claudeOnlyMap[issue.number]) claudeOnlyMap[issue.number] = { number: issue.number, votes: [] }
    claudeOnlyMap[issue.number].votes.push({ category: issue.category, confidence: issue.confidence || 0.5 })
  }
}
const claudeOnlyResults = {}
for (const [num, issue] of Object.entries(claudeOnlyMap)) {
  const cw = {}
  for (const v of issue.votes) cw[v.category] = (cw[v.category] || 0) + v.confidence
  const best = Object.entries(cw).sort((a, b) => b[1] - a[1])[0]
  claudeOnlyResults[num] = best ? best[0] : 'milestone'
}

const issueMap = {}
for (const vote of validVotes) {
  if (!vote.issues) continue
  for (const issue of vote.issues) {
    if (!issueMap[issue.number]) {
      issueMap[issue.number] = { number: issue.number, title: issue.title, votes: [], sources: [] }
    }
    issueMap[issue.number].votes.push({
      category: issue.category,
      confidence: issue.confidence || 0.5,
    })
    if (issue.source) issueMap[issue.number].sources.push(issue.source)
  }
}

const categorizedIssues = Object.values(issueMap).map(issue => {
  const categoryWeights = {}
  for (const vote of issue.votes) {
    categoryWeights[vote.category] = (categoryWeights[vote.category] || 0) + vote.confidence
  }
  const bestCategory = Object.entries(categoryWeights).sort((a, b) => b[1] - a[1])[0]
  return {
    number: issue.number,
    title: issue.title,
    category: bestCategory ? bestCategory[0] : 'milestone',
    totalWeight: bestCategory ? bestCategory[1] : 0,
    voteCount: issue.votes.length,
  }
})

// ── Dim 1 (cont): Count how many issues external votes flipped ──
let flipped = 0, unflipped = 0
const flippedIssues = []
for (const ci of categorizedIssues) {
  const claudeOnly = claudeOnlyResults[ci.number]
  if (claudeOnly) {
    if (claudeOnly !== ci.category) {
      flipped++
      flippedIssues.push({ issue: ci.number, claude_only: claudeOnly, with_external: ci.category })
    } else unflipped++
  }
}
externalMetrics.influence = { flipped, unflipped, flipped_issues: flippedIssues }
if (flipped > 0) log(`External votes FLIPPED ${flipped} categorizations: ${flippedIssues.map(f => `#${f.issue}: ${f.claude_only}→${f.with_external}`).join(', ')}`)
else log(`External votes reinforced all ${unflipped} categorizations (no flips)`)

// ── Dim 2: Per-category agreement + Dim 6: Response diversity ──
if (externalMetrics._extCatVotes && externalMetrics._extCatVotes.length > 0) {
  const consensusMap = {}
  for (const ci of categorizedIssues) consensusMap[ci.number] = ci.category

  let agree = 0, disagree = 0
  const perCatAgreement = {}
  const perSourceAgreement = {}

  for (const ext of externalMetrics._extCatVotes) {
    if (!consensusMap[ext.number]) continue
    const cat = consensusMap[ext.number]
    const source = ext.source || 'unknown'

    if (!perCatAgreement[cat]) perCatAgreement[cat] = { agree: 0, disagree: 0 }
    if (!perSourceAgreement[source]) perSourceAgreement[source] = { agree: 0, disagree: 0 }

    if (ext.category === cat) {
      agree++
      perCatAgreement[cat].agree++
      perSourceAgreement[source].agree++
    } else {
      disagree++
      perCatAgreement[cat].disagree++
      perSourceAgreement[source].disagree++
      externalMetrics.agreement.push({ issue: ext.number, external: ext.category, consensus: cat, source })
    }
  }

  const total = agree + disagree
  const rate = total > 0 ? (agree / total * 100).toFixed(1) : 'N/A'

  // Per-category agreement rates
  const catRates = {}
  for (const [cat, data] of Object.entries(perCatAgreement)) {
    const ct = data.agree + data.disagree
    catRates[cat] = { agreed: data.agree, disagreed: data.disagree, rate: ct > 0 ? data.agree / ct : null }
  }

  // Per-source (model) agreement rates — Dim 6: diversity
  const sourceRates = {}
  for (const [source, data] of Object.entries(perSourceAgreement)) {
    const st = data.agree + data.disagree
    sourceRates[source] = { agreed: data.agree, disagreed: data.disagree, rate: st > 0 ? data.agree / st : null }
  }

  // Dim 6: diversity score — how much models disagree with EACH OTHER (not just with consensus)
  const extVotesByIssue = {}
  for (const ext of externalMetrics._extCatVotes) {
    if (!extVotesByIssue[ext.number]) extVotesByIssue[ext.number] = []
    extVotesByIssue[ext.number].push(ext.category)
  }
  let diverseIssues = 0, unanimousIssues = 0
  for (const cats of Object.values(extVotesByIssue)) {
    if (new Set(cats).size > 1) diverseIssues++
    else unanimousIssues++
  }
  const diversityScore = (diverseIssues + unanimousIssues) > 0 ? diverseIssues / (diverseIssues + unanimousIssues) : 0

  externalMetrics.phases.categorize = {
    ...(externalMetrics.phases.categorize || {}),
    agreement_rate: total > 0 ? agree / total : null,
    agreed: agree,
    disagreed: disagree,
    per_category: catRates,
    per_source: sourceRates,
    diversity_score: diversityScore,
    diverse_issues: diverseIssues,
    unanimous_issues: unanimousIssues,
  }

  log(`External model agreement with consensus: ${agree}/${total} (${rate}%)`)
  log(`Per-category: ${Object.entries(catRates).map(([c, d]) => `${c}=${d.agreed}/${d.agreed + d.disagreed}`).join(', ')}`)
  log(`Per-model: ${Object.entries(sourceRates).map(([s, d]) => `${s}=${((d.rate || 0) * 100).toFixed(0)}%`).join(', ')}`)
  log(`Diversity: ${diverseIssues}/${diverseIssues + unanimousIssues} issues had model disagreement (score=${diversityScore.toFixed(2)})`)
  if (disagree > 0) log(`Disagreements: ${externalMetrics.agreement.slice(0, 5).map(d => `#${d.issue}: ext=${d.external} vs consensus=${d.consensus}`).join(', ')}${externalMetrics.agreement.length > 5 ? ` (+${externalMetrics.agreement.length - 5} more)` : ''}`)
  delete externalMetrics._extCatVotes
}

const groups = {}
for (const issue of categorizedIssues) {
  if (!groups[issue.category]) groups[issue.category] = []
  groups[issue.category].push(issue)
}

log(`Categorized ${categorizedIssues.length} issues:`)
for (const [cat, issues] of Object.entries(groups)) {
  log(`  ${cat}: ${issues.length} issues (${issues.map(i => '#' + i.number).join(', ')})`)
}

if (DRY_RUN) {
  log('DRY RUN — stopping after categorization')
  return { strategy, categorizedIssues, groups, dryRun: true }
}

// ═══════════════════════════════════════════════════════
// PHASE 2: EXECUTE BY CATEGORY
// ═══════════════════════════════════════════════════════
phase('Execute')

const milestones = groups['milestone'] || []
const enhancements = groups['enhancement'] || []
const codeFixes = groups['code_fix'] || []
const securityFixes = groups['security_fix'] || []
const allFixes = [...codeFixes, ...securityFixes]
const decompose = groups['decompose'] || []
const outcomes = []

if (milestones.length > 0) {
  if (TRAINING_MODE) {
    log(`[TRAINING] Recording ${milestones.length} milestones (no remote writes)`)
  } else {
    log(`Converting ${milestones.length} issues to tracking milestones...`)
    await agent(`For these issues in ${REPO} on ${IS_GITLAB ? 'GitLab (' + GITLAB_HOST + ')' : 'GitHub'}, add a comment explaining they are tracking milestones (not immediate fix candidates), then add the "milestone" label if possible.

Issues: ${milestones.map(i => `#${i.number} "${i.title}"`).join(', ')}

For each:
1. ${IS_GITLAB ? `${CLI} issue view NUMBER ${REPO_FLAG}` : `gh issue view NUMBER --repo ${REPO}`}
2. ${IS_GITLAB ? `${CLI} issue note NUMBER ${REPO_FLAG} -m "Reclassifying as tracking milestone. This requires infrastructure, manual testing, or multi-MR decomposition. Remaining open as tracking issue."` : `gh issue comment NUMBER --repo ${REPO} --body "Reclassifying as tracking milestone. This requires infrastructure, manual testing, or multi-PR decomposition. Remaining open as tracking issue."`}
3. ${IS_GITLAB ? `${CLI} issue update NUMBER ${REPO_FLAG} --label milestone 2>/dev/null || true` : `gh issue edit NUMBER --repo ${REPO} --add-label "milestone" 2>/dev/null || true`}

Do NOT close any. Report what you did for each.`, {
      label: 'convert-milestones',
      phase: 'Execute',
    })
  }
  for (const m of milestones) {
    outcomes.push({ number: m.number, category: 'milestone', action: TRAINING_MODE ? 'training_categorized' : 'labeled', success: true, reward: 0.8 })
  }
}

const enhStrategy = strategy.enhancement_strategy || 'label_and_close'
if (enhancements.length > 0 && enhStrategy !== 'skip') {
  if (TRAINING_MODE) {
    log(`[TRAINING] Recording ${enhancements.length} enhancements (no remote writes)`)
  } else {
    log(`Processing ${enhancements.length} enhancement issues (strategy: ${enhStrategy})...`)
    const enhInstructions = enhStrategy === 'label_only'
      ? `For these enhancement/feature-request issues in ${REPO} on ${IS_GITLAB ? 'GitLab (' + GITLAB_HOST + ')' : 'GitHub'}, add a backlog label. Do NOT close any issues.

Issues: ${enhancements.map(i => `#${i.number} "${i.title}"`).join(', ')}

For each:
1. ${IS_GITLAB ? `${CLI} issue view NUMBER ${REPO_FLAG}` : `gh issue view NUMBER --repo ${REPO}`} — read full context
2. Add "backlog" label: ${IS_GITLAB ? `${CLI} issue update NUMBER ${REPO_FLAG} --label backlog 2>/dev/null || true` : `gh issue edit NUMBER --repo ${REPO} --add-label "backlog" 2>/dev/null || true`}

Report what you did.`
      : `For these enhancement/feature-request issues in ${REPO} on ${IS_GITLAB ? 'GitLab (' + GITLAB_HOST + ')' : 'GitHub'}, add a backlog label or close with rationale if they're already addressed.

Issues: ${enhancements.map(i => `#${i.number} "${i.title}"`).join(', ')}

For each:
1. ${IS_GITLAB ? `${CLI} issue view NUMBER ${REPO_FLAG}` : `gh issue view NUMBER --repo ${REPO}`} — read full context
2. If the feature already exists in the codebase, close with comment explaining it's resolved
3. If it's a valid future enhancement, add "backlog" label: ${IS_GITLAB ? `${CLI} issue update NUMBER ${REPO_FLAG} --label backlog 2>/dev/null || true` : `gh issue edit NUMBER --repo ${REPO} --add-label "backlog" 2>/dev/null || true`}
4. If it's premature for the current project stage, close with rationale: ${IS_GITLAB ? `${CLI} issue close NUMBER ${REPO_FLAG}` : `gh issue close NUMBER --repo ${REPO}`}

Report what you did.`

    await agent(enhInstructions, {
      label: 'process-enhancements',
      phase: 'Execute',
    })
  }
  for (const e of enhancements) {
    outcomes.push({ number: e.number, category: 'enhancement', action: TRAINING_MODE ? 'training_categorized' : 'processed', success: true, reward: 0.7 })
  }
} else if (enhancements.length > 0 && enhStrategy === 'skip') {
  log(`Skipping ${enhancements.length} enhancements (enhancement_strategy=skip)`)
}

if (decompose.length > 0) {
  if (TRAINING_MODE) {
    log(`[TRAINING] Recording ${decompose.length} decompose candidates (no remote writes)`)
  } else {
    log(`Decomposing ${decompose.length} large-scope issues...`)
    const subCount = strategy.decompose_sub_count || 5
    await agent(`These issues in ${REPO} on ${IS_GITLAB ? 'GitLab (' + GITLAB_HOST + ')' : 'GitHub'} are too large for a single fix. Decompose each into ${Math.max(2, subCount - 2)}-${subCount + 2} sub-issues.

Issues: ${decompose.map(i => `#${i.number} "${i.title}"`).join(', ')}

For each:
1. ${IS_GITLAB ? `${CLI} issue view NUMBER ${REPO_FLAG}` : `gh issue view NUMBER --repo ${REPO}`} — understand full scope
2. Break into concrete sub-issues: ${IS_GITLAB ? `${CLI} issue create ${REPO_FLAG} -t "SUB_TITLE" -d "Part of #NUMBER: ..."` : `gh issue create --repo ${REPO} --title "SUB_TITLE" --body "Part of #NUMBER: ..."`}
3. Add comment to parent: ${IS_GITLAB ? `${CLI} issue note NUMBER ${REPO_FLAG} -m "Decomposed into sub-issues: #X, #Y, #Z"` : `gh issue comment NUMBER --repo ${REPO} --body "Decomposed into sub-issues: #X, #Y, #Z"`}
4. Do NOT close the parent — it becomes the tracking issue

Report sub-issues created.`, {
      label: 'decompose-issues',
      phase: 'Execute',
    })
  }
  for (const d of decompose) {
    outcomes.push({ number: d.number, category: 'decompose', action: TRAINING_MODE ? 'training_categorized' : 'decomposed', success: true, reward: 0.8 })
  }
}

// ── Skip fixes mode: record fix-category issues as categorized, jump to Record ──
if (SKIP_FIXES && allFixes.length > 0) {
  log(`[SKIP_FIXES] Recording ${allFixes.length} code/security issues as categorized (no fix attempts)`)
  for (const f of allFixes) {
    outcomes.push({ number: f.number, category: f.category || 'code_fix', action: 'training_categorized', success: true, reward: 0.5 })
  }
}

if (SKIP_FIXES) {
  log(`[SKIP_FIXES] Skipping fix/review/commit phases — proceeding to Record + Evolve`)
} else {

// ── Filter repeat failures ──
let filteredFixes = [...allFixes]
const maxPriorFail = strategy.max_prior_failures
if (maxPriorFail > 0 && filteredFixes.length > 0) {
  const priorFailCheck = await agent(`Check learning.experiences for prior failed attempts on these issues.

Run: ${SSH_PSQL("SELECT context->>'issue_number' as issue, COUNT(*) as fails FROM learning.experiences WHERE problem_type LIKE '%issue_resolution%' AND NOT success AND context->>'issue_number' IN (" + filteredFixes.map(f => "'" + f.number + "'").join(',') + ") GROUP BY context->>'issue_number'")}

Return the result as JSON.`, {
    label: 'check-prior-failures',
    phase: 'Execute',
    schema: { type: 'object', properties: { failures: { type: 'object' } }, required: ['failures'] },
  })
  if (priorFailCheck && priorFailCheck.failures) {
    const skipped = []
    filteredFixes = filteredFixes.filter(f => {
      const fails = priorFailCheck.failures[String(f.number)] || 0
      if (fails >= maxPriorFail) {
        skipped.push(f)
        outcomes.push({ number: f.number, category: f.category, action: 'skipped_repeat_failure', success: false, reward: 0, reason: `${fails} prior failures >= threshold ${maxPriorFail}` })
        return false
      }
      return true
    })
    if (skipped.length > 0) log(`Skipped ${skipped.length} issues with ${maxPriorFail}+ prior failures: ${skipped.map(s => '#' + s.number).join(', ')}`)
  }
}

// ── Sort by priority order ──
const priorityOrder = strategy.issue_priority_order || 'fifo'
if (priorityOrder === 'newest_first') {
  filteredFixes.sort((a, b) => b.number - a.number)
} else if (priorityOrder === 'confidence_desc') {
  filteredFixes.sort((a, b) => (b.totalWeight || 0) - (a.totalWeight || 0))
} else if (priorityOrder === 'complexity_asc') {
  filteredFixes.sort((a, b) => (a.title.length || 0) - (b.title.length || 0))
}
if (priorityOrder !== 'fifo') log(`Sorted ${filteredFixes.length} fixes by ${priorityOrder}`)

let fixResults = []
if (filteredFixes.length > 0) {
  log(`Fixing ${filteredFixes.length} code/security issues with weighted consensus...`)

  const maxLines = strategy.max_fix_lines || 200
  const fixModelOpts = modelOpts(strategy.fix_model_tier)
  const fixIsolation = strategy.fix_isolation === 'worktree' ? { isolation: 'worktree' } : {}
  const concurrencyLimit = strategy.fix_concurrency_limit || 4
  const candidates = strategy.fix_candidates || 1
  const reasoningInstr = strategy.reasoning_depth === 'root_cause_chain'
    ? '\n0. BEFORE writing any code: trace the root cause chain. Identify the EXACT function, line, and condition that causes the bug. Write your chain of reasoning. Only then write the fix.'
    : strategy.reasoning_depth === 'analyze_first'
    ? '\n0. BEFORE writing any code: analyze the issue. Identify the affected files and functions. Understand the expected vs actual behavior. Then write the fix.'
    : ''
  const contextInstr = strategy.code_context_radius > 0
    ? `\n2b. For each file you identify as relevant, read at least ${strategy.code_context_radius} lines around the bug site to understand surrounding invariants.`
    : ''
  const diagnosticInstr = strategy.error_diagnostic_depth === 'body_plus_comments'
    ? `\n1b. Also read issue comments for additional diagnostics: ${issueCommentsCmd('{issue_number}')}`
    : strategy.error_diagnostic_depth === 'body_plus_linked'
    ? `\n1b. Read issue comments AND linked PRs for diagnostics: ${issueCommentsCmd('{issue_number}')}\n1c. Check for linked PRs and read their diffs for context.`
    : ''

  // ── Get external model fix suggestions (lightweight, before fix waves) ──
  let externalFixSuggestions = {}
  if (extModelCount > 0 && filteredFixes.length > 0) {
    log(`Getting external model fix suggestions for ${filteredFixes.length} issues...`)
    const issueDescs = filteredFixes.map(f => `#${f.number} "${f.title}" (${f.category})`).join('; ')
    const extFixResult = await agent(`Query external models for fix suggestions.

Run: ~/.claude/lib/multi-model-query.sh --prompt 'For each of these code issues, briefly suggest a fix approach (1-2 sentences each, no code). Issues: ${issueDescs.replace(/'/g, "\\'")}. Reply with JSON: {"suggestions": [{"number": N, "approach": "..."}]}' --models '${extModels}' --task-type code_generation --timeout 25 --max-tokens 1024

Parse output. Merge suggestions by issue number. Return combined.`, {
      label: 'external-fix-suggestions',
      phase: 'Execute',
      schema: {
        type: 'object',
        properties: {
          suggestions: { type: 'object' },
        },
        required: ['suggestions'],
      },
    })
    if (extFixResult && extFixResult.suggestions) {
      externalFixSuggestions = extFixResult.suggestions
      log(`Got external fix suggestions for ${Object.keys(externalFixSuggestions).length} issues`)
    }
  }

  // ── Build per-issue fix prompts with enrichment ──
  const buildFixPrompt = (issue, pastInfo, fewShotExamples) => {
    let prompt = `Fix issue #${issue.number} "${issue.title}" in ${REPO}.
Category: ${issue.category}
Repo context: ${strategy.repo_context || 'general'}
${reasoningInstr}
1. Read the full issue: ${issueViewCmd(issue.number)}${diagnosticInstr.replace(/\{issue_number\}/g, issue.number)}
2. Understand the codebase context${contextInstr}
3. Implement a MINIMAL, SCOPED fix (<${maxLines} lines, max ${strategy.scope_file_limit || 5} files)
4. If the fix exists in config/custom-scripts/, apply the same fix to packages/virtos-tools/src/usr/local/bin/ (keep in sync)
5. Stage changes: git add <specific files>
6. Verify syntax: bash -n on shell scripts, python3 -c "import ast; ast.parse(open('file').read())" on Python
7. Do NOT touch build/ directory
${strategy.require_test_evidence ? '\nTEST EVIDENCE IS REQUIRED: You MUST provide concrete test evidence (command output, before/after, or test results). Fixes without test evidence will be rejected.' : '\nTEST EVIDENCE: Show before/after behavior or explain what the fix does.'}`

    if (TRAINING_MODE) prompt += `\n\nTRAINING MODE: This is a READ-ONLY training run on an external repo you do NOT own.
- Clone the repo if not already there: git clone ${cloneUrl} ~/Development/training/${REPO.replace('/', '-')} 2>/dev/null || true
- Work in the cloned directory: cd ~/Development/training/${REPO.replace('/', '-')}
- Do NOT push, do NOT create PRs, do NOT comment on issues, do NOT close issues
- Stage your fix locally (git add) so the reviewer can see git diff --staged
- This is purely for learning — the fix quality still matters for GA training`

    if (pastInfo) prompt += `\n\nPAST ATTEMPTS ON THIS ISSUE:\n${pastInfo}\nIf prior attempts failed, use a DIFFERENT approach. Do NOT repeat the same mistake.`
    if (fewShotExamples) prompt += `\n\nSIMILAR SUCCESSFUL FIXES (for reference):\n${fewShotExamples}`
    const extSugg = externalFixSuggestions[String(issue.number)]
    if (extSugg) prompt += `\n\nEXTERNAL MODEL SUGGESTIONS (consider but verify independently):\n${typeof extSugg === 'string' ? extSugg : JSON.stringify(extSugg)}`
    prompt += `\nIf the fix would be >${maxLines} lines or touch >${strategy.scope_file_limit || 5} files, set fix_applied to false and explain why.`
    return prompt
  }

  // ── Gather past fix data and few-shot examples if enabled ──
  let pastFixData = {}
  let fewShotData = {}

  if (strategy.past_fix_lookup || strategy.few_shot_past_fixes > 0) {
    const lookupResult = await agent(`Query the learning database for past fix data.

${strategy.past_fix_lookup ? `1. Get prior outcomes for these specific issues:
${SSH_PSQL("SELECT context->>'issue_number' as issue, success, reward, context->>'action' as action FROM learning.experiences WHERE problem_type LIKE '%issue_resolution%' AND context->>'issue_number' IN (" + filteredFixes.map(f => "'" + f.number + "'").join(',') + ") ORDER BY timestamp DESC")}` : ''}

${strategy.few_shot_past_fixes > 0 ? `2. Get ${strategy.few_shot_past_fixes} similar SUCCESSFUL fixes using semantic search:
curl -s "${API_BASE}/learning/experiences/similar?query=code+fix+${REPO.replace('/', '+')}&limit=${strategy.few_shot_past_fixes}&success_only=true" | python3 -m json.tool` : ''}

Return structured data with per-issue past outcomes and few-shot examples.`, {
      label: 'lookup-past-fixes',
      phase: 'Execute',
      schema: {
        type: 'object',
        properties: {
          past_outcomes: { type: 'object' },
          few_shot_examples: { type: 'array', items: { type: 'object', properties: { title: { type: 'string' }, approach: { type: 'string' }, outcome: { type: 'string' } } } },
        },
        required: ['past_outcomes'],
      },
    })
    if (lookupResult) {
      pastFixData = lookupResult.past_outcomes || {}
      fewShotData = lookupResult.few_shot_examples || []
    }
  }

  const fewShotStr = fewShotData.length > 0
    ? fewShotData.map(ex => `- "${ex.title}": ${ex.approach} → ${ex.outcome}`).join('\n')
    : null

  // ── Fix in waves with concurrency limit ──
  const fixOneIssue = (issue) => {
    const pastInfo = pastFixData[String(issue.number)]
      ? (Array.isArray(pastFixData[String(issue.number)])
        ? pastFixData[String(issue.number)].map(p => `  ${p.success ? 'OK' : 'FAIL'}: ${p.action || 'unknown'}`).join('\n')
        : JSON.stringify(pastFixData[String(issue.number)]))
      : null
    const prompt = buildFixPrompt(issue, pastInfo, fewShotStr)

    if (candidates <= 1) {
      return agent(prompt, {
        label: `fix-#${issue.number}`,
        phase: 'Execute',
        schema: FIX_SCHEMA,
        ...fixModelOpts,
        ...fixIsolation,
      })
    }
    return parallel(Array.from({ length: candidates }, (_, ci) => () =>
      agent(prompt, {
        label: `fix-#${issue.number}-c${ci}`,
        phase: 'Execute',
        schema: FIX_SCHEMA,
        ...fixModelOpts,
        ...fixIsolation,
      })
    )).then(results => {
      const applied = results.filter(Boolean).filter(r => r.fix_applied)
      if (applied.length === 0) return results.find(Boolean) || null
      if (applied.length === 1) return applied[0]
      return applied.sort((a, b) => (a.files_changed || []).length - (b.files_changed || []).length)[0]
    })
  }

  // Execute in waves respecting concurrency limit
  for (let i = 0; i < filteredFixes.length; i += concurrencyLimit) {
    const wave = filteredFixes.slice(i, i + concurrencyLimit)
    const waveResults = await parallel(wave.map(issue => () => fixOneIssue(issue)))
    fixResults.push(...waveResults)
  }

  // ── Preflight gate: validate fixes before expensive review ──
  const gate = strategy.preflight_gate || 'syntax'
  const scopeLimit = strategy.scope_file_limit || 5
  for (const fix of fixResults.filter(Boolean).filter(f => f.fix_applied)) {
    if ((fix.files_changed || []).length > scopeLimit) {
      fix.fix_applied = false
      fix.description = `Scope exceeded: ${(fix.files_changed || []).length} files modified, limit is ${scopeLimit}. ${fix.description}`
      log(`  #${fix.issue_number}: scope-rejected (${(fix.files_changed || []).length} > ${scopeLimit} files)`)
    }
  }
}

const appliedFixes = fixResults.filter(Boolean).filter(f => f.fix_applied)
log(`${appliedFixes.length}/${filteredFixes.length} fixes applied`)

// ═══════════════════════════════════════════════════════
// PHASE 3: REVIEW (adversarial review-of-review)
// ═══════════════════════════════════════════════════════
phase('Review')

let approved = []
let notApproved = []

if (appliedFixes.length > 0) {
  const reviewModelOpts = modelOpts(strategy.review_model_tier)
  const catReviewDepths = strategy.category_review_depths || {}
  const catThresholds = strategy.category_thresholds || {}

  const fixesNeedingReview = []
  const autoApproved = []
  for (const fix of appliedFixes) {
    const fixCat = categorizedIssues.find(i => i.number === fix.issue_number)?.category || 'code_fix'
    const depth = catReviewDepths[fixCat] !== undefined ? catReviewDepths[fixCat] : (strategy.review_depth || 3)
    if (depth === 0) {
      log(`  #${fix.issue_number}: auto-approved (${fixCat} review_depth=0)`)
      autoApproved.push({ ...fix, issue_number: fix.issue_number, recommendation: 'approve', verified: true, agree_ratio: '1.00', agree_weight: '0', disagree_weight: '0', votes_agree: 0, votes_disagree: 0 })
    } else {
      fixesNeedingReview.push({ fix, category: fixCat, depth })
    }
  }

  log(`Reviewing ${fixesNeedingReview.length} fixes (${autoApproved.length} auto-approved by depth=0)...`)

  const testEvidenceRule = strategy.require_test_evidence
    ? '\n7. REJECT if no test evidence was provided — test_evidence field must contain concrete proof.'
    : ''
  const trainingDir = TRAINING_MODE ? `\nWORKING DIRECTORY: cd ~/Development/training/${REPO.replace('/', '-')} before reviewing.` : ''

  const reviewResults = await parallel(fixesNeedingReview.map(({ fix }) => () =>
    agent(`INDEPENDENT CODE REVIEW of fix for issue #${fix.issue_number} in ${REPO}.${trainingDir}

Fix: ${fix.description}
Files: ${JSON.stringify(fix.files_changed || [])}
Test evidence: ${fix.test_evidence || 'none'}

REVIEW:
1. git diff --staged to see changes
2. Read each changed file IN FULL
3. Verify fix against issue: ${issueViewCmd(fix.issue_number)}
4. Check for: injection, path traversal, off-by-one, missing error handling, race conditions
5. Verify config/ and packages/ copies are in sync
6. Check no build/ files touched${testEvidenceRule}

If you reject, provide a SPECIFIC objection with the exact bug, line, or missing piece.
Vague objections like "too risky" are not acceptable.`, {
      label: `review-#${fix.issue_number}`,
      phase: 'Review',
      schema: REVIEW_SCHEMA,
      ...reviewModelOpts,
    })
  ))

  const completedReviews = reviewResults.filter(Boolean)

  // ── External model reviews (free APIs) ──
  if (extModelCount > 0 && completedReviews.length > 0) {
    log(`Getting external model reviews from ${extModelCount} providers...`)
    const fixSummaries = fixesNeedingReview.map(({ fix }) =>
      `#${fix.issue_number}: ${(fix.description || '').substring(0, 200)} | files: ${(fix.files_changed || []).join(', ')}`
    ).join('\\n')

    const externalReviewResult = await agent(`Query external free API models for code review opinions.

Run this command:
~/.claude/lib/multi-model-query.sh --prompt 'Review these code fixes. For each, say whether it is correct and should be approved or rejected. Be specific about any bugs or issues.

Fixes:
${fixSummaries.replace(/'/g, "\\'")}

Reply with JSON: {"reviews": [{"issue_number": N, "fix_correct": true/false, "recommendation": "approve"/"reject", "reasoning": "..."}]}' --models '${extModels}' --task-type code_review --timeout 30 --max-tokens 2048

Parse the output. For each successful model response, extract its reviews array.
Combine all reviews. For each issue, if multiple models reviewed it, use majority vote.
Return the final merged reviews.`, {
      label: 'external-review',
      phase: 'Review',
      schema: {
        type: 'object',
        properties: {
          reviews: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                issue_number: { type: 'number' },
                fix_correct: { type: 'boolean' },
                recommendation: { type: 'string' },
                reasoning: { type: 'string' },
              },
              required: ['issue_number', 'fix_correct', 'recommendation'],
            },
          },
        },
        required: ['reviews'],
      },
    })

    if (externalReviewResult && externalReviewResult.reviews) {
      for (const extReview of externalReviewResult.reviews) {
        completedReviews.push({
          issue_number: extReview.issue_number,
          fix_correct: extReview.fix_correct,
          introduces_bugs: false,
          introduces_security_issues: false,
          recommendation: extReview.recommendation || 'approve',
          specific_objection: '',
          reasoning: `[external-model] ${extReview.reasoning || ''}`,
        })
      }
      log(`Added ${externalReviewResult.reviews.length} external model reviews`)
    }
  }

  log(`${completedReviews.length} reviews completed. Running review-of-review...`)

  const verifiedReviews = await pipeline(
    completedReviews,
    (review) => {
      const fixCat = categorizedIssues.find(i => i.number === review.issue_number)?.category || 'code_fix'
      const depth = catReviewDepths[fixCat] !== undefined ? catReviewDepths[fixCat] : (strategy.review_depth || 3)
      const voters = Array.from({ length: depth }, (_, i) => i)
      return parallel(voters.map(i => () =>
        agent(`REVIEW THE REVIEW for issue #${review.issue_number} in ${REPO}.

Reviewer said: correct=${review.fix_correct}, bugs=${review.introduces_bugs}, security=${review.introduces_security_issues}
Recommendation: ${review.recommendation}
Specific objection: ${review.specific_objection || 'none'}
Reasoning: ${review.reasoning}

YOUR JOB:
1. git diff --staged — see actual changes
2. Read changed files in full
3. Did reviewer MISS bugs?
4. Did reviewer flag FALSE POSITIVES?
5. If reviewer rejected — is the objection valid and concrete?
6. Rate your CONFIDENCE (0.0-1.0). High (0.8+) = thoroughly verified.`, {
          label: `verify-#${review.issue_number}-v${i}`,
          phase: 'Review',
          schema: VERIFY_SCHEMA,
          ...reviewModelOpts,
        })
      )).then(votes => {
        const valid = votes.filter(Boolean)
        const weightedAgree = valid.filter(v => v.agrees_with_review).reduce((sum, v) => sum + (v.confidence || 0.5), 0)
        const weightedDisagree = valid.filter(v => !v.agrees_with_review).reduce((sum, v) => sum + (v.confidence || 0.5), 0)
        const totalWeight = weightedAgree + weightedDisagree
        const agreeRatio = totalWeight > 0 ? weightedAgree / totalWeight : 0
        const threshold = catThresholds[fixCat] !== undefined ? catThresholds[fixCat] : (strategy.consensus_threshold || 0.5)

        return {
          ...review,
          verified: agreeRatio >= threshold,
          agree_weight: weightedAgree.toFixed(2),
          disagree_weight: weightedDisagree.toFixed(2),
          agree_ratio: agreeRatio.toFixed(2),
          votes_agree: valid.filter(v => v.agrees_with_review).length,
          votes_disagree: valid.filter(v => !v.agrees_with_review).length,
        }
      })
    }
  )

  approved = [...autoApproved, ...verifiedReviews.filter(r => r.verified && r.recommendation === 'approve')]
  notApproved = verifiedReviews.filter(r => !r.verified || r.recommendation !== 'approve')

  log(`TALLY: ${approved.length} approved (${autoApproved.length} auto), ${notApproved.length} rejected`)
  notApproved.forEach(r => log(`  #${r.issue_number}: ${r.recommendation}, weight=${r.agree_weight}/${r.disagree_weight}`))
}

// ── RETRY LOOP: re-attempt rejected fixes with reviewer feedback ──
if (strategy.retry_on_reject && (strategy.max_retries || 0) > 0 && notApproved.length > 0) {
  const maxRetries = Math.min(strategy.max_retries, 2)
  const fixModelOpts = modelOpts(strategy.fix_model_tier)
  const reviewModelOpts2 = modelOpts(strategy.review_model_tier)
  const catReviewDepths2 = strategy.category_review_depths || {}
  const catThresholds2 = strategy.category_thresholds || {}

  for (let attempt = 1; attempt <= maxRetries && notApproved.length > 0; attempt++) {
    log(`Retry attempt ${attempt}/${maxRetries} for ${notApproved.length} rejected fixes...`)

    const retryResults = await parallel(notApproved.map(rejected => () =>
      agent(`RETRY FIX for issue #${rejected.issue_number} in ${REPO}.

The previous fix was REJECTED. Here is the reviewer's objection:
"${rejected.specific_objection || rejected.reasoning}"

Your job:
1. Read the issue: ${issueViewCmd(rejected.issue_number)}
2. Understand the objection and what went wrong
3. Write a NEW fix that addresses the objection
4. Keep changes under ${strategy.max_fix_lines || 200} lines
${strategy.require_test_evidence ? '5. You MUST provide test evidence (run tests, show output)\n' : ''}
Return the fix details.`, {
        label: `retry-#${rejected.issue_number}-a${attempt}`,
        phase: 'Review',
        schema: FIX_SCHEMA,
        ...fixModelOpts,
        ...(strategy.fix_isolation === 'worktree' ? { isolation: 'worktree' } : {}),
      })
    ))

    const retryFixes = retryResults.filter(Boolean)
    if (retryFixes.length === 0) break

    const retryReviews = await parallel(retryFixes.map(fix => () =>
      agent(`INDEPENDENT CODE REVIEW of RETRY fix for issue #${fix.issue_number} in ${REPO}.

This is retry attempt ${attempt}. The previous fix was rejected.
Fix: ${fix.description}
Files: ${JSON.stringify(fix.files_changed || [])}
Test evidence: ${fix.test_evidence || 'none'}

REVIEW with extra scrutiny — this fix addresses a prior rejection.
1. git diff --staged to see changes
2. Read each changed file IN FULL
3. Check the fix actually addresses the prior objection
4. Check for: injection, path traversal, off-by-one, missing error handling
${strategy.require_test_evidence ? '5. REJECT if no test evidence was provided\n' : ''}
If you reject, provide a SPECIFIC objection.`, {
        label: `retry-review-#${fix.issue_number}-a${attempt}`,
        phase: 'Review',
        schema: REVIEW_SCHEMA,
        ...reviewModelOpts2,
      })
    ))

    const retryReviewsValid = retryReviews.filter(Boolean)
    const newApproved = []
    const stillRejected = []

    for (const review of retryReviewsValid) {
      const fixCat = categorizedIssues.find(i => i.number === review.issue_number)?.category || 'code_fix'
      const depth = catReviewDepths2[fixCat] !== undefined ? catReviewDepths2[fixCat] : (strategy.review_depth || 3)
      const threshold = catThresholds2[fixCat] !== undefined ? catThresholds2[fixCat] : (strategy.consensus_threshold || 0.5)

      if (depth === 0 || (review.recommendation === 'approve' && review.fix_correct)) {
        newApproved.push({ ...review, verified: true, agree_ratio: '1.00', retried: attempt })
      } else if (review.recommendation !== 'approve') {
        stillRejected.push(review)
      } else {
        const votes = await parallel(Array.from({ length: depth }, (_, i) => () =>
          agent(`Quick verify: retry fix #${review.issue_number} — reviewer approved. Agree? Confidence 0.0-1.0.`, {
            label: `retry-verify-#${review.issue_number}-a${attempt}-v${i}`,
            phase: 'Review',
            schema: VERIFY_SCHEMA,
            ...reviewModelOpts2,
          })
        ))
        const valid = votes.filter(Boolean)
        const wAgree = valid.filter(v => v.agrees_with_review).reduce((s, v) => s + (v.confidence || 0.5), 0)
        const wDisagree = valid.filter(v => !v.agrees_with_review).reduce((s, v) => s + (v.confidence || 0.5), 0)
        const total = wAgree + wDisagree
        const ratio = total > 0 ? wAgree / total : 0
        if (ratio >= threshold) {
          newApproved.push({ ...review, verified: true, agree_ratio: ratio.toFixed(2), retried: attempt })
        } else {
          stillRejected.push({ ...review, agree_ratio: ratio.toFixed(2) })
        }
      }
    }

    approved.push(...newApproved)
    notApproved = stillRejected
    log(`  Retry ${attempt}: ${newApproved.length} rescued, ${stillRejected.length} still rejected`)
    if (stillRejected.length === 0) break
  }
}

// ═══════════════════════════════════════════════════════
// PHASE 4: COMMIT VERIFIED FIXES
// ═══════════════════════════════════════════════════════
phase('Commit')

if (TRAINING_MODE) {
  log(`[TRAINING] Skipping commit phase — recording ${approved.length} approved, ${notApproved.length} rejected as training data`)
  for (const a of approved) {
    const originalCat = categorizedIssues.find(i => i.number === a.issue_number)?.category || 'code_fix'
    outcomes.push({ number: a.issue_number, category: originalCat, action: 'training_approved', success: true, reward: 1.0 })
  }
  for (const r of notApproved) {
    const originalCat = categorizedIssues.find(i => i.number === r.issue_number)?.category || 'code_fix'
    outcomes.push({ number: r.issue_number, category: originalCat, action: 'training_rejected', success: false, reward: 0.0, reason: r.specific_objection || r.reasoning })
  }
} else if (approved.length > 0 || notApproved.length > 0) {
  const prCreateCmd = IS_GITLAB
    ? `${CLI} mr create ${REPO_FLAG} --title "fix: resolve issue #NUMBER" --description "Fixes #NUMBER. Verified by weighted adversarial consensus (ratio: RATIO)." --assignee ${PR_ASSIGNEE}`
    : `gh pr create --repo ${REPO} --title "fix: resolve issue #NUMBER" --body "Fixes #NUMBER. Verified by weighted adversarial consensus (ratio: RATIO)." --assignee ${PR_ASSIGNEE}`
  const issueCloseCmd = IS_GITLAB
    ? `${CLI} issue close NUMBER ${REPO_FLAG}`
    : `gh issue close NUMBER --repo ${REPO} --comment "Fixed. Verified by weighted adversarial consensus (ratio: RATIO)."`
  const defaultBranch = IS_GITLAB ? 'main' : 'main'

  const commitInstructions = PR_MODE
    ? `Execute actions on ${REPO} using ${IS_GITLAB ? 'MERGE REQUEST' : 'PULL REQUEST'} mode on ${IS_GITLAB ? 'GitLab (' + GITLAB_HOST + ')' : 'GitHub'}.

APPROVED FIXES (passed weighted consensus):
${approved.map(f => `- #${f.issue_number}: agree_ratio=${f.agree_ratio}`).join('\n') || 'None'}

${approved.length > 0 ? `For each approved fix:
1. git diff --staged to see what's staged for this fix
2. Create a branch: git checkout -b fix/issue-NUMBER
3. git commit -m "fix: resolve issue #NUMBER - description

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
4. git push -u origin fix/issue-NUMBER
5. Create a ${MR_OR_PR} assigned to ${PR_ASSIGNEE}:
   ${prCreateCmd}
6. Return to ${defaultBranch} branch: git checkout ${defaultBranch}
7. Do NOT close the issue — the ${MR_OR_PR} will close it when merged` : ''}

REJECTED FIXES (discard):
${notApproved.map(f => `- #${f.issue_number}: ${f.recommendation}, objection: ${f.specific_objection || f.reasoning}`).join('\n') || 'None'}

${notApproved.length > 0 ? 'For each rejected fix: git checkout -- <files>' : ''}

Verify git status is clean after.`
    : `Execute actions on ${REPO} on ${IS_GITLAB ? 'GitLab (' + GITLAB_HOST + ')' : 'GitHub'}.

APPROVED FIXES (passed weighted consensus):
${approved.map(f => `- #${f.issue_number}: agree_ratio=${f.agree_ratio}`).join('\n') || 'None'}

${approved.length > 0 ? `For each approved fix:
1. git diff --staged to verify
2. git commit -m "fix: resolve issue #NUMBER - description

   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
3. git push
4. ${issueCloseCmd}` : ''}

REJECTED FIXES (discard):
${notApproved.map(f => `- #${f.issue_number}: ${f.recommendation}, objection: ${f.specific_objection || f.reasoning}`).join('\n') || 'None'}

${notApproved.length > 0 ? 'For each rejected fix: git checkout -- <files>' : ''}

Verify git status is clean after.`

  await agent(commitInstructions, {
    label: 'commit-fixes',
    phase: 'Commit',
  })

  for (const a of approved) {
    const originalCat = categorizedIssues.find(i => i.number === a.issue_number)?.category || 'code_fix'
    outcomes.push({ number: a.issue_number, category: originalCat, action: 'fixed_and_closed', success: true, reward: 1.0 })
  }
  for (const r of notApproved) {
    const originalCat = categorizedIssues.find(i => i.number === r.issue_number)?.category || 'code_fix'
    outcomes.push({ number: r.issue_number, category: originalCat, action: 'rejected', success: false, reward: 0.0, reason: r.specific_objection || r.reasoning })
  }
}
} // end SKIP_FIXES else block

// ═══════════════════════════════════════════════════════
// PHASE 5: RECORD OUTCOMES (THE LEARNING STEP)
// ═══════════════════════════════════════════════════════
phase('Record')
log(`Recording ${outcomes.length} outcomes to Thompson Sampling + experience memory...`)

if (outcomes.length > 0) {
  await agent(`Record issue resolution outcomes to the learning database.

OUTCOMES TO RECORD:
${outcomes.map(o => `- #${o.number}: category=${o.category}, action=${o.action}, success=${o.success}, reward=${o.reward}${o.reason ? ', reason=' + o.reason : ''}`).join('\n')}

STEP 1: Update Thompson Sampling for each category strategy.
For each unique category in outcomes, compute success count and failure count, then UPSERT:

${outcomes.map(o => {
  const stratName = `issue_resolve_${o.category}`
  if (o.success) {
    return `ssh claude@${DB_HOST} 'bash -c "PGPASSWORD=${DB_PASS} psql -h localhost -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -c \\"INSERT INTO learning.strategy_performance (strategy, successes, failures, alpha, beta, total_reward, avg_reward) VALUES ('"'"'${stratName}'"'"', 1, 0, 2.0, 1.0, ${o.reward}, ${o.reward}) ON CONFLICT (strategy) DO UPDATE SET successes = learning.strategy_performance.successes + 1, alpha = learning.strategy_performance.alpha + 1, total_reward = learning.strategy_performance.total_reward + ${o.reward}, avg_reward = (learning.strategy_performance.total_reward + ${o.reward}) / (learning.strategy_performance.successes + learning.strategy_performance.failures + 1), last_updated = NOW()\\""'`
  } else {
    return `ssh claude@${DB_HOST} 'bash -c "PGPASSWORD=${DB_PASS} psql -h localhost -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -c \\"INSERT INTO learning.strategy_performance (strategy, successes, failures, alpha, beta, total_reward, avg_reward) VALUES ('"'"'${stratName}'"'"', 0, 1, 1.0, 2.0, 0, 0) ON CONFLICT (strategy) DO UPDATE SET failures = learning.strategy_performance.failures + 1, beta = learning.strategy_performance.beta + 1, avg_reward = learning.strategy_performance.total_reward / GREATEST(learning.strategy_performance.successes + learning.strategy_performance.failures + 1, 1), last_updated = NOW()\\""'`
  }
}).join('\n\n')}

STEP 2: Store experiences.
For each outcome, insert into learning.experiences:

${outcomes.map(o => `ssh claude@${DB_HOST} 'bash -c "PGPASSWORD=${DB_PASS} psql -h localhost -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -c \\"INSERT INTO learning.experiences (problem_type, problem_hash, strategy, success, reward, context) VALUES ('"'"'issue_resolution_${REPO.replace('/', '_')}'"'"', '"'"'issue_${o.number}_${o.category}'"'"', '"'"'${o.category}_${o.action}'"'"', ${o.success}, ${o.reward}, '"'"'{\\\\\\\"issue_number\\\\\\\": ${o.number}, \\\\\\\"category\\\\\\\": \\\\\\\"${o.category}\\\\\\\", \\\\\\\"action\\\\\\\": \\\\\\\"${o.action}\\\\\\\"}'"'"'::jsonb)\\""'`).join('\n\n')}

STEP 3: Store overall session learning via REST API:
curl -s -X POST ${API_BASE}/learning/memory -H "Content-Type: application/json" -d '${JSON.stringify({
  name: "issue_resolution_session_" + categorizedIssues.length,
  description: "Issue resolution session: " + outcomes.filter(o => o.success).length + "/" + outcomes.length + " successful",
  memory_type: "reference",
  content: "Strategy: " + (strategy.source || 'cold_start') + ". Results: " + outcomes.map(o => "#" + o.number + "=" + (o.success ? "OK" : "FAIL")).join(", ")
})}'

Run all commands and report results.`, {
    label: 'record-outcomes',
    phase: 'Record',
  })
}

// ── Record external model metrics (all 6 dimensions) ──
if (externalMetrics.calls.length > 0) {
  const catPhase = externalMetrics.phases.categorize || {}
  const influence = externalMetrics.influence || {}

  const extMetricsResult = await agent(`Record external model performance metrics to the database. Execute ALL commands.

METRICS SUMMARY (6 dimensions):
1. CONSENSUS INFLUENCE: ${influence.flipped || 0} flipped, ${influence.unflipped || 0} reinforced${influence.flipped_issues ? '. Flipped: ' + influence.flipped_issues.map(f => `#${f.issue}: ${f.claude_only}→${f.with_external}`).join(', ') : ''}
2. PER-CATEGORY AGREEMENT: ${JSON.stringify(catPhase.per_category || {})}
3. RESPONSE PARSEABILITY: ${catPhase.models_parseable || 0}/${catPhase.models_called || 0} returned valid JSON
4. TOKEN USAGE: ${catPhase.total_tokens || 0} total. ${(catPhase.per_model_tokens || []).map(m => `${m.model}: ${m.tokens}`).join(', ')}
5. PROVIDER RELIABILITY: ${externalMetrics.calls.map(c => `${c.model}: ${c.success ? 'OK' : 'FAIL'} ${c.latency_ms || 0}ms`).join(', ')}
6. RESPONSE DIVERSITY: score=${(catPhase.diversity_score || 0).toFixed(2)}, ${catPhase.diverse_issues || 0} diverse / ${catPhase.unanimous_issues || 0} unanimous

Run these commands:

STEP 1: Create/update monitoring table (add new columns if needed):
${SSH_PSQL("CREATE TABLE IF NOT EXISTS monitoring.external_model_metrics (id SERIAL PRIMARY KEY, timestamp TIMESTAMPTZ DEFAULT NOW(), repo TEXT, phase TEXT, model TEXT, success BOOLEAN, latency_ms INTEGER, error TEXT, prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0, parseable_json BOOLEAN DEFAULT false, agreed_with_consensus BOOLEAN)")}
${SSH_PSQL("ALTER TABLE monitoring.external_model_metrics ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER DEFAULT 0")}
${SSH_PSQL("ALTER TABLE monitoring.external_model_metrics ADD COLUMN IF NOT EXISTS completion_tokens INTEGER DEFAULT 0")}
${SSH_PSQL("ALTER TABLE monitoring.external_model_metrics ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0")}
${SSH_PSQL("ALTER TABLE monitoring.external_model_metrics ADD COLUMN IF NOT EXISTS parseable_json BOOLEAN DEFAULT false")}
${SSH_PSQL("ALTER TABLE monitoring.external_model_metrics ADD COLUMN IF NOT EXISTS agreed_with_consensus BOOLEAN")}

STEP 2: Insert per-call metrics with all dimensions:
${externalMetrics.calls.map(c => {
  const agreedVal = externalMetrics.agreement.find(a => a.source === c.model) ? 'false' : 'true'
  return SSH_PSQL(`INSERT INTO monitoring.external_model_metrics (repo, phase, model, success, latency_ms, error, prompt_tokens, completion_tokens, total_tokens, parseable_json, agreed_with_consensus) VALUES ('${REPO}', '${c.phase}', '${c.model}', ${c.success}, ${c.latency_ms || 0}, '${(c.error || '').replace(/'/g, "''")}', ${c.prompt_tokens || 0}, ${c.completion_tokens || 0}, ${c.total_tokens || 0}, ${c.parseable_json || false}, ${c.success ? agreedVal : 'NULL'})`)
}).join('\n')}

STEP 3: Create consensus influence table and insert:
${SSH_PSQL("CREATE TABLE IF NOT EXISTS monitoring.consensus_influence (id SERIAL PRIMARY KEY, timestamp TIMESTAMPTZ DEFAULT NOW(), repo TEXT, phase TEXT, flipped INTEGER, reinforced INTEGER, details JSONB)")}
${SSH_PSQL(`INSERT INTO monitoring.consensus_influence (repo, phase, flipped, reinforced, details) VALUES ('${REPO}', 'categorize', ${influence.flipped || 0}, ${influence.unflipped || 0}, '${JSON.stringify(influence.flipped_issues || []).replace(/'/g, "''")}'::jsonb)`)}

STEP 4: Query provider reliability trend (Dim 5):
${SSH_PSQL("SELECT model, COUNT(*) as total_calls, SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes, ROUND(AVG(latency_ms)) as avg_latency, ROUND(AVG(CASE WHEN success THEN latency_ms END)) as avg_success_latency, SUM(total_tokens) as total_tokens, ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 1) as success_pct FROM monitoring.external_model_metrics WHERE timestamp > NOW() - INTERVAL '7 days' GROUP BY model ORDER BY success_pct DESC")}

Report the trend query results — these show 7-day provider reliability.

STEP 5: Store full metrics summary via REST API:
curl -s -X POST ${API_BASE}/learning/memory -H "Content-Type: application/json" -d '${JSON.stringify({
  name: "ext_model_metrics_" + REPO.replace('/', '_'),
  description: "External model metrics for " + REPO + " (6 dimensions)",
  memory_type: "reference",
  content: JSON.stringify({
    repo: REPO,
    dimensions: {
      consensus_influence: influence,
      per_category_agreement: catPhase.per_category || {},
      parseability: { parseable: catPhase.models_parseable || 0, total: catPhase.models_called || 0 },
      token_usage: { total: catPhase.total_tokens || 0, per_model: catPhase.per_model_tokens || [] },
      provider_calls: externalMetrics.calls.length,
      diversity: { score: catPhase.diversity_score || 0, diverse: catPhase.diverse_issues || 0, unanimous: catPhase.unanimous_issues || 0 },
    },
  })
})}'

Run all commands and report results.`, {
    label: 'record-ext-metrics',
    phase: 'Record',
    schema: {
      type: 'object',
      properties: {
        recorded: { type: 'boolean' },
        provider_trend: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              model: { type: 'string' },
              total_calls: { type: 'number' },
              success_pct: { type: 'number' },
              avg_latency: { type: 'number' },
              total_tokens: { type: 'number' },
            },
          },
        },
      },
      required: ['recorded'],
    },
  })

  // ── Dim 5: Store provider trend data for GA ──
  if (typeof externalMetricsResult !== 'undefined' && externalMetricsResult && externalMetricsResult.provider_trend) {
    externalMetrics.provider_trend = externalMetricsResult.provider_trend
    log(`Provider 7-day trend: ${externalMetricsResult.provider_trend.map(p => `${p.model}: ${p.success_pct}% success, ${p.avg_latency}ms avg`).join(', ')}`)
  }
  log(`Recorded ${externalMetrics.calls.length} external model metrics across 6 dimensions`)
}

// ═══════════════════════════════════════════════════════
// PHASE 6: EVOLVE (Mini GA)
// ═══════════════════════════════════════════════════════
phase('Evolve')

const CATEGORY_WEIGHTS = {
  code_fix: 3.0,
  security_fix: 3.5,
  decompose: 1.5,
  milestone: 1.0,
  enhancement: 1.0,
  refactor: 2.0,
}

let weightedSuccess = 0, weightedTotal = 0
for (const o of outcomes) {
  const w = CATEGORY_WEIGHTS[o.category] || 1.0
  weightedTotal += w
  if (o.success) weightedSuccess += w
}
const successRate = weightedTotal > 0 ? weightedSuccess / weightedTotal : 0
const efficiency = outcomes.length > 0 ? outcomes.reduce((s, o) => s + o.reward, 0) / outcomes.length : 0
const fitness = successRate * 0.7 + efficiency * 0.3

if (outcomes.length === 0) {
  log('No outcomes — skipping GA evolution (no signal to evolve on)')
} else {
log('Running mini GA evolution step...')

log(`Current generation fitness: ${fitness.toFixed(3)} (success=${successRate.toFixed(2)}, efficiency=${efficiency.toFixed(2)})`)

// ── Get external mutation advice ──
let externalMutationAdvice = ''
if (extModelCount > 0) {
  const outcomesSummary = outcomes.map(o => `#${o.number}: ${o.category}→${o.success ? 'OK' : 'FAIL'}`).join(', ')
  const extEvolveResult = await agent(`Query external models for GA evolution advice.

Run: ~/.claude/lib/multi-model-query.sh --prompt 'Given these issue resolution outcomes: ${outcomesSummary.replace(/'/g, "\\'")}. Current fitness: ${fitness.toFixed(3)}. Which strategy parameters should be adjusted and why? Focus on: consensus_threshold, review_depth, max_fix_lines, retry_on_reject, external_model_count, external_model_weight. Reply concisely.' --models '${extModels}' --task-type evolution --timeout 20 --max-tokens 512

Combine the responses into a brief summary of mutation recommendations.`, {
    label: 'external-evolve-advice',
    phase: 'Evolve',
  })
  if (extEvolveResult) {
    externalMutationAdvice = typeof extEvolveResult === 'string' ? extEvolveResult : JSON.stringify(extEvolveResult)
    log(`Got external evolution advice`)
  }
}

await agent(`Run a mini Genetic Algorithm evolution step for issue resolution strategy.

CURRENT CHROMOSOME (this run — 30 genes):
- categories: ${JSON.stringify(strategy.categories)}
- consensus_threshold: ${strategy.consensus_threshold}
- review_depth: ${strategy.review_depth}
- confidence_weight_threshold: ${strategy.confidence_weight_threshold || 0.6}
- category_thresholds: ${JSON.stringify(strategy.category_thresholds || {})}
- category_review_depths: ${JSON.stringify(strategy.category_review_depths || {})}
- retry_on_reject: ${strategy.retry_on_reject || false}
- max_retries: ${strategy.max_retries || 0}
- max_fix_lines: ${strategy.max_fix_lines || 200}
- categorizer_count: ${strategy.categorizer_count || 3}
- enhancement_strategy: ${strategy.enhancement_strategy || 'label_and_close'}
- decompose_sub_count: ${strategy.decompose_sub_count || 5}
- require_test_evidence: ${strategy.require_test_evidence || false}
- fix_isolation: ${strategy.fix_isolation || 'shared'}
- fix_model_tier: ${strategy.fix_model_tier || 'default'}
- review_model_tier: ${strategy.review_model_tier || 'default'}
- max_prior_failures: ${strategy.max_prior_failures || 2}
- fix_concurrency_limit: ${strategy.fix_concurrency_limit || 4}
- preflight_gate: ${strategy.preflight_gate || 'syntax'}
- past_fix_lookup: ${strategy.past_fix_lookup || false}
- few_shot_past_fixes: ${strategy.few_shot_past_fixes || 0}
- reasoning_depth: ${strategy.reasoning_depth || 'analyze_first'}
- scope_file_limit: ${strategy.scope_file_limit || 5}
- issue_priority_order: ${strategy.issue_priority_order || 'fifo'}
- code_context_radius: ${strategy.code_context_radius || 50}
- error_diagnostic_depth: ${strategy.error_diagnostic_depth || 'issue_body'}
- fix_candidates: ${strategy.fix_candidates || 1}
- external_model_count: ${strategy.external_model_count || 3}
- external_model_weight: ${strategy.external_model_weight || 0.4}
- external_providers: ${JSON.stringify(strategy.external_providers || ['groq', 'cerebras', 'cohere'])}
- fitness: ${fitness.toFixed(3)} (success_rate=${successRate.toFixed(2)} * 0.7 + efficiency=${efficiency.toFixed(2)} * 0.3)

OUTCOMES THIS RUN:
${outcomes.map(o => `  #${o.number}: ${o.category} → ${o.success ? 'SUCCESS' : 'FAIL'}${o.retried ? ' (retried x' + o.retried + ')' : ''}${o.reason ? ' — ' + o.reason : ''}`).join('\n')}

STEP 1: Get best historical chromosome (only from runs with real data):
${SSH_PSQL("SELECT strategy_counts, success_rate, avg_reward FROM learning.experiment_results WHERE experiment_name = 'ga_issue_resolution' AND total_tasks > 0 ORDER BY avg_reward DESC LIMIT 1")}

STEP 2: CROSSOVER + MUTATION.
If a historical best exists with higher fitness, do structured crossover:
- Take per-category overrides (category_thresholds, category_review_depths) from the FITTER parent
- Take numeric globals (consensus_threshold, review_depth, max_fix_lines, fix_concurrency_limit, code_context_radius) from the OTHER parent
- Take boolean flags (retry_on_reject, require_test_evidence, past_fix_lookup) from the FITTER parent
- Take enum/issue-selection genes from the FITTER parent

Then apply MUTATION (each gene independently):

NUMERIC GENES (15% mutation chance each, gaussian step):
  - consensus_threshold: ±0.1, clamp [0.3, 0.9]
  - review_depth: ±1, clamp [1, 5]
  - confidence_weight_threshold: ±0.1, clamp [0.3, 0.9]
  - max_fix_lines: ±50, clamp [50, 500]
  - categorizer_count: ±1, clamp [1, 5]
  - decompose_sub_count: ±1, clamp [2, 10]
  - max_retries: ±1, clamp [0, 2]
  - max_prior_failures: ±1, clamp [0, 5]
  - fix_concurrency_limit: ±1, clamp [1, 8]
  - few_shot_past_fixes: ±1, clamp [0, 3]
  - scope_file_limit: ±1, clamp [1, 10]
  - code_context_radius: ±25, clamp [0, 200]
  - fix_candidates: ±1, clamp [1, 3]
  - external_model_count: ±1, clamp [0, 6]
  - external_model_weight: ±0.1, clamp [0.1, 0.9]

PER-CATEGORY MAP GENES (15% chance to mutate ONE entry):
  - category_thresholds: pick one category, ±0.1, clamp [0.2, 0.9]
  - category_review_depths: pick one category, ±1, clamp [0, 5]

BOOLEAN GENES (10% flip chance each):
  - retry_on_reject: flip true↔false
  - require_test_evidence: flip true↔false
  - past_fix_lookup: flip true↔false

ENUM GENES (10% chance to rotate to next value):
  - enhancement_strategy: cycle [label_and_close → label_only → skip → label_and_close]
  - fix_isolation: cycle [shared → worktree → shared]
  - fix_model_tier: cycle [default → sonnet → haiku → default]
  - review_model_tier: cycle [default → sonnet → haiku → default]
  - preflight_gate: cycle [none → syntax → lint → build → none]
  - reasoning_depth: cycle [direct_fix → analyze_first → root_cause_chain → direct_fix]
  - issue_priority_order: cycle [fifo → newest_first → confidence_desc → complexity_asc → fifo]
  - error_diagnostic_depth: cycle [issue_body → body_plus_comments → body_plus_linked → issue_body]

ARRAY GENES:
  - categories: 10% chance to add or remove a category from [code_fix, security_fix, milestone, enhancement, decompose, refactor]
  - external_providers: 10% chance to add or remove a provider from [groq, cerebras, cohere, openrouter, deepseek, mistral, deepinfra]

If no historical best exists, use current as Gen 0 (still apply mutation).

STEP 3: Store the new generation (ALL 30 genes in the JSON):
ssh claude@${DB_HOST} 'bash -c "PGPASSWORD=${DB_PASS} psql -h localhost -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME} -c \\"INSERT INTO learning.experiment_results (experiment_name, method, total_tasks, success_count, success_rate, avg_reward, strategy_counts) VALUES ('ga_issue_resolution', 'gen_N', ${outcomes.length}, ${outcomes.filter(o => o.success).length}, ${successRate}, ${fitness}, '{NEW_CHROMOSOME_JSON}'::jsonb)\\""'

Replace gen_N with the next generation number and NEW_CHROMOSOME_JSON with the full 30-gene evolved chromosome.

Report: which genes mutated, what changed, and why (relate mutations to outcomes above).
${externalMutationAdvice ? '\nEXTERNAL MODEL MUTATION ADVICE (consider but use your own judgment):\n' + externalMutationAdvice : ''}
${externalMetrics.calls.length > 0 ? `\nEXTERNAL MODEL PERFORMANCE DATA (use to guide external_model_count/weight/providers mutations):
- API calls: ${externalMetrics.calls.length} total, ${externalMetrics.calls.filter(c => c.success).length} succeeded
- Per-model: ${externalMetrics.calls.map(c => `${c.model}: ${c.success ? 'OK' : 'FAIL'} ${c.latency_ms || 0}ms`).join(', ')}
- Categorize agreement: ${externalMetrics.phases.categorize ? `${externalMetrics.phases.categorize.agreed || 0}/${(externalMetrics.phases.categorize.agreed || 0) + (externalMetrics.phases.categorize.disagreed || 0)} (${((externalMetrics.phases.categorize.agreement_rate || 0) * 100).toFixed(1)}%)` : 'N/A'}
- If agreement is high (>80%), consider increasing external_model_weight. If low (<50%), decrease it or swap providers.
- If a provider consistently fails, remove it from external_providers.` : ''}`, {
  label: 'ga-evolve',
  phase: 'Evolve',
})
} // end outcomes.length > 0 guard

// ═══════════════════════════════════════════════════════
// PHASE 7: FINAL AUDIT
// ═══════════════════════════════════════════════════════
phase('Audit')
log('Running independent final audit...')

const auditResult = await agent(`FINAL AUDIT of self-learning issue resolution session on ${REPO}.

Commands:
1. ${IS_SOURCEFORGE ? `curl -s "${SF_API}/?limit=20" | python3 -c "import sys,json; [print(f\\"#{t['ticket_num']} {t['summary']}\\") for t in json.load(sys.stdin).get('tickets',[])]"` : IS_BITBUCKET ? `curl -s "${BB_API}/issues?status=new&status=open&pagelen=20" | python3 -c "import sys,json; [print(f\\"#{i['id']} {i['title']}\\") for i in json.load(sys.stdin).get('values',[])]"` : USE_GITLAB_API ? `curl -s "${GL_API}/issues?state=opened&per_page=20" | python3 -c "import sys,json; [print(f\\"#{i['iid']} {i['title']}\\") for i in json.load(sys.stdin)]"` : IS_GITLAB ? `${CLI} issue list ${REPO_FLAG} --per-page 20` : `gh issue list --state open --repo ${REPO} --json number,title`}
2. ${IS_SOURCEFORGE ? `curl -s "${SF_API}/?limit=20&status=closed" | python3 -c "import sys,json; [print(f\\"#{t['ticket_num']} {t['summary']}\\") for t in json.load(sys.stdin).get('tickets',[])]"` : IS_BITBUCKET ? `curl -s "${BB_API}/issues?status=resolved&status=closed&pagelen=20" | python3 -c "import sys,json; [print(f\\"#{i['id']} {i['title']}\\") for i in json.load(sys.stdin).get('values',[])]"` : USE_GITLAB_API ? `curl -s "${GL_API}/issues?state=closed&per_page=20" | python3 -c "import sys,json; [print(f\\"#{i['iid']} {i['title']}\\") for i in json.load(sys.stdin)]"` : IS_GITLAB ? `${CLI} issue list ${REPO_FLAG} --closed --per-page 20` : `gh issue list --state closed --repo ${REPO} --limit 20 --json number,title,closedAt`}
3. git log --oneline -15
4. git status
5. git diff && git diff --staged

Session used ${strategy.source || 'cold_start'} strategy:
- Code fixes: ${approved.length} approved, ${notApproved.length} rejected
- Milestones: ${milestones.length} labeled
- Enhancements: ${enhancements.length} processed
- Decomposed: ${decompose.length}
- Total outcomes: ${outcomes.length}
- Fitness: ${fitness.toFixed(3)}

Verify: clean working tree, correct closures, no build artifacts, files in sync.
Check that NO build/workspace/ files were committed.
Verdict: CLEAN, WARNINGS, or ERRORS.`, {
  label: 'final-audit',
  phase: 'Audit',
})

log('═'.repeat(50))
log('SESSION COMPLETE')
log(`Strategy: ${strategy.source || 'cold_start'}`)
log(`Issues processed: ${categorizedIssues.length}`)
log(`Fixes approved: ${approved.length}`)
log(`Fixes rejected: ${notApproved.length}`)
log(`Fitness: ${fitness.toFixed(3)}`)
log(`Outcomes recorded to PostgreSQL for next run`)
log('═'.repeat(50))

return {
  strategy: strategy.source || 'cold_start',
  categorizedIssues,
  outcomes,
  approved: approved.map(a => ({ num: a.issue_number, ratio: a.agree_ratio })),
  rejected: notApproved.map(r => ({ num: r.issue_number, objection: r.specific_objection || r.reasoning })),
  fitness,
  audit: auditResult,
}
