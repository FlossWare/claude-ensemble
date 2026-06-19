export const meta = {
  name: 'ai-extract-learning',
  description: 'Extract learnings from workflow execution (internal helper)',
  phases: [
    { title: 'Analyze', detail: 'Extract patterns from execution data' }
  ]
}

// Reusable learning extraction workflow
// Called by other workflows to extract insights from their execution

// ============================================================================
// STRATEGY CLASSES
// ============================================================================

class BaseStrategy {
  getWorkers() { return ['opus', 'sonnet', 'haiku'] }
  getArbiters() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
}

class MaximumCoverageStrategy extends BaseStrategy {
  getWorkers() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
  getArbiters() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
}

class QuantizedStrategy extends BaseStrategy {
  getWorkers() { return ['ollama/llama3', 'ollama/mistral', 'ollama/codellama', 'haiku', 'sonnet'] }
  getArbiters() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
}

class QuintupleVerificationStrategy extends BaseStrategy {
  getWorkers() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }
  getArbiters() { return ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'] }

  getVerificationStages() {
    return [
      { name: 'initial-review', workers: ['fable', 'opus', 'sonnet'], arbiter: 'fable' },
      { name: 'deep-analysis', workers: ['haiku', 'gpt-4o', 'gemini'], arbiter: 'opus' },
      { name: 'cross-validation', workers: ['fable', 'sonnet', 'gpt-4o'], arbiter: 'fable' },
      { name: 'edge-case-check', workers: ['opus', 'haiku', 'gemini'], arbiter: 'opus' },
      { name: 'final-consensus', workers: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o'], arbiter: 'fable' },
    ]
  }
}

const STRATEGIES = {
  'base': BaseStrategy,
  'maximum-coverage': MaximumCoverageStrategy,
  'quantized': QuantizedStrategy,
  'quintuple-verification': QuintupleVerificationStrategy,
}

function getStrategy(name) {
  const StrategyClass = STRATEGIES[name] || STRATEGIES['base']
  return new StrategyClass()
}

const strategy = getStrategy(args?.strategy)

// Parse args
const workflow_name = args?.workflow_name || 'unknown'
const execution_data = args?.execution_data || {}
const save_to_memory = args?.save_to_memory || false

phase('Analyze')
log(`📚 Extracting learnings from ${workflow_name} execution...`)
log(`📊 Strategy: ${args?.strategy || 'base'}`)
log(`   Workers: ${strategy.getWorkers().join(', ')}`)
log(`   Arbiters: ${strategy.getArbiters().join(', ')}`)

// Build workflow-specific learning prompt
const learningPrompt = buildLearningPrompt(workflow_name, execution_data)

const LEARNING_SCHEMA = {
  type: 'object',
  required: ['user_patterns', 'code_patterns', 'recommendations'],
  properties: {
    user_patterns: {
      type: 'object',
      description: 'Patterns about how user works',
      properties: {
        preferences: {
          type: 'array',
          items: { type: 'string' },
          description: 'User preferences observed (e.g., "prefers squash merges", "likes detailed commit messages")'
        },
        expertise_level: {
          type: 'object',
          additionalProperties: {
            type: 'string',
            enum: ['beginner', 'intermediate', 'advanced']
          },
          description: 'User expertise by domain'
        },
        workflow_usage: {
          type: 'array',
          items: { type: 'string' },
          description: 'How user invokes/uses workflows'
        }
      }
    },
    code_patterns: {
      type: 'object',
      description: 'Patterns in the codebase',
      properties: {
        common_bugs: {
          type: 'array',
          items: { type: 'string' },
          description: 'Bug patterns that appear repeatedly'
        },
        architecture_insights: {
          type: 'array',
          items: { type: 'string' },
          description: 'Key architectural decisions observed'
        },
        tech_stack: {
          type: 'array',
          items: { type: 'string' },
          description: 'Technologies/frameworks in use'
        },
        quality_trends: {
          type: 'array',
          items: { type: 'string' },
          description: 'Code quality trends (improving/degrading)'
        }
      }
    },
    recommendations: {
      type: 'array',
      items: { type: 'string' },
      description: 'Actionable recommendations for future'
    },
    memory_suggestions: {
      type: 'array',
      items: {
        type: 'object',
        required: ['type', 'content'],
        properties: {
          type: {
            type: 'string',
            enum: ['user', 'feedback', 'project', 'reference'],
            description: 'Memory type to save'
          },
          content: {
            type: 'string',
            description: 'What to remember'
          },
          priority: {
            type: 'string',
            enum: ['high', 'medium', 'low'],
            description: 'How important this learning is'
          }
        }
      },
      description: 'Suggested memory entries to save'
    }
  }
}

const learnings = await agent(learningPrompt, {
  label: 'Extract Learnings',
  schema: LEARNING_SCHEMA,
  model: strategy.getArbiters()[0],  // Use top arbiter for meta-level analysis
  phase: 'Analyze'
})

if (!learnings) {
  log(`❌ Learning extraction failed`)
  return {
    status: 'failed',
    workflow: workflow_name
  }
}

// Display learnings
displayLearnings(learnings)

// Save to database (always enabled for queryability)
let learningId = null;
try {
  const { storeLearnings } = require('~/.claude/learning/storage.js');

  log(`\n💾 Saving learnings to database...`)

  learningId = await storeLearnings(
    args?.run_id || `manual-${Date.now()}`,
    learnings,
    {
      executionId: args?.execution_id || null,
      workflowName: workflow_name,
      strategy: args?.strategy || 'base',
      qualityScore: args?.quality_score || null
    }
  );

  log(`✅ Stored as learning #${learningId}`)
} catch (err) {
  log(`⚠️ Failed to store learnings: ${err.message}`)
  log(`   Learnings are still available in return value`)
}

// Optionally save to memory files
if (save_to_memory) {
  log(`\n📝 Memory file save not yet implemented`)
  log(`   Use learning #${learningId} from database instead`)
}

log(`\n✅ Learning extraction complete`)

return {
  status: 'success',
  workflow: workflow_name,
  learnings,
  learning_id: learningId
  // Note: timestamp should be added by caller after workflow returns
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function buildLearningPrompt(workflow_name, data) {
  const basePrompt = `Analyze this ${workflow_name} execution and extract key learnings that will improve future runs.

Focus on:
1. **User patterns**: How the user works, their preferences, expertise level
2. **Code patterns**: Recurring issues, architecture insights, tech stack
3. **Recommendations**: Specific, actionable improvements
4. **Memory worthy**: What should be remembered long-term`

  const workflowPrompts = {
    'code-solve': `${basePrompt}

EXECUTION DATA:
- Issue #${data.issue_number || 'N/A'}: ${data.issue_title || 'N/A'}
- Fix approach: ${data.fix_approach || 'N/A'}
- Files changed: ${data.files_changed?.join(', ') || 'N/A'}
- Consensus score: ${data.consensus_score || 'N/A'}
- Commit: ${data.commit_hash || 'N/A'}

SPECIFIC LEARNINGS TO EXTRACT:
- Does user prefer certain fix patterns? (e.g., minimal changes vs comprehensive refactors)
- What types of bugs appear repeatedly in this codebase?
- Are there missing tests/docs that led to this bug?
- What architectural decisions are revealed by this fix?
- What should be remembered to prevent similar bugs?`,

    'code-review': `${basePrompt}

EXECUTION DATA:
- Findings: ${data.findings_count || 0} issues
- Severity: ${JSON.stringify(data.severity_breakdown || {})}
- Categories: ${data.categories?.join(', ') || 'N/A'}
- Review effort: ${data.effort_level || 'N/A'}

SPECIFIC LEARNINGS:
- What bug patterns repeat across files?
- What does user care most about? (correctness vs performance vs style)
- Are there systemic quality issues (missing error handling, no tests)?
- What frameworks/patterns are used?
- What areas need more scrutiny in future reviews?`,

    'code-test': `${basePrompt}

EXECUTION DATA:
- Tests run: ${data.tests_run || 0}
- Pass rate: ${data.pass_rate || 'N/A'}%
- Failures: ${data.failures?.length || 0}
- Build status: ${data.build_status || 'N/A'}

SPECIFIC LEARNINGS:
- What types of tests does user run? (unit/integration/e2e)
- Are failures clustered in specific areas?
- Is test coverage adequate?
- What's the testing stack? (jest/mocha/pytest/etc)
- What would improve test reliability?`,

    'code-pr-review': `${basePrompt}

EXECUTION DATA:
- PR #${data.pr_number || 'N/A'}: ${data.pr_title || 'N/A'}
- Decision: ${data.decision || 'N/A'}
- Breaking changes: ${data.breaking_changes || 'None'}
- Impact score: ${data.impact_score || 'N/A'}

SPECIFIC LEARNINGS:
- What are user's PR approval criteria?
- Does user prefer squash/merge/rebase?
- What makes a "good" vs "bad" PR in this project?
- Are there review process improvements needed?
- What commit message style is preferred?`,

    'code-security': `${basePrompt}

EXECUTION DATA:
- Vulnerabilities: ${data.vulnerabilities_count || 0}
- Severity: ${data.max_severity || 'N/A'}
- Categories: ${data.vuln_categories?.join(', ') || 'N/A'}
- OWASP: ${data.owasp_categories?.join(', ') || 'N/A'}

SPECIFIC LEARNINGS:
- What security issues appear repeatedly?
- Is there a security mindset in the codebase?
- What's the risk tolerance? (accept low/med vs fix all)
- Are there systemic gaps? (no input validation, missing auth)
- What security tools/practices should be adopted?`,

    'code-doc': `${basePrompt}

EXECUTION DATA:
- Docs generated: ${data.docs_generated || 0}
- Coverage: ${data.coverage || 'N/A'}%
- Gaps: ${data.gaps?.join(', ') || 'None'}
- Style: ${data.doc_style || 'N/A'}

SPECIFIC LEARNINGS:
- What documentation style does user prefer? (verbose/terse/examples-heavy)
- Which areas lack documentation most?
- Is code self-documenting or needs comments?
- What audience level? (beginners/experts)
- What would improve doc quality?`,

    'ai-prompt': `${basePrompt}

EXECUTION DATA:
- Question: ${data.question || 'N/A'}
- Models: ${data.models_used?.join(', ') || 'N/A'}
- Consensus: ${data.consensus_level || 'N/A'}

SPECIFIC LEARNINGS:
- What topics does user ask about?
- How does user prefer answers? (concise/detailed/examples)
- What's user expertise level in discussed topics?
- Are follow-up questions asked? (unclear answer indicator)
- What would make future answers more helpful?`,

    'ai-chat': `${basePrompt}

EXECUTION DATA:
- Turns: ${data.turns || 0}
- Topics: ${data.topics?.join(', ') || 'N/A'}
- History: ${JSON.stringify(data.history?.slice(-3) || [])}

SPECIFIC LEARNINGS:
- What are user's interests/expertise?
- How do they like conversations structured?
- What topics generate follow-ups? (interest indicators)
- Are answers too verbose/terse?
- What would improve future chats?`
  }

  return workflowPrompts[workflow_name] || `${basePrompt}

EXECUTION DATA:
${JSON.stringify(data, null, 2)}

Extract meaningful patterns and recommendations.`
}

function displayLearnings(learnings) {
  log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`)
  log(`📊 LEARNINGS EXTRACTED`)
  log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`)

  // User patterns
  if (learnings.user_patterns) {
    const up = learnings.user_patterns

    if (up.preferences?.length > 0) {
      log(`\n👤 USER PREFERENCES:`)
      up.preferences.forEach(p => log(`  • ${p}`))
    }

    if (up.expertise_level && Object.keys(up.expertise_level).length > 0) {
      log(`\n🎓 EXPERTISE LEVELS:`)
      Object.entries(up.expertise_level).forEach(([domain, level]) => {
        const emoji = level === 'advanced' ? '⭐' : level === 'intermediate' ? '📚' : '🌱'
        log(`  ${emoji} ${domain}: ${level}`)
      })
    }

    if (up.workflow_usage?.length > 0) {
      log(`\n⚙️ WORKFLOW USAGE:`)
      up.workflow_usage.forEach(w => log(`  • ${w}`))
    }
  }

  // Code patterns
  if (learnings.code_patterns) {
    const cp = learnings.code_patterns

    if (cp.common_bugs?.length > 0) {
      log(`\n🐛 COMMON BUG PATTERNS:`)
      cp.common_bugs.forEach(b => log(`  • ${b}`))
    }

    if (cp.architecture_insights?.length > 0) {
      log(`\n🏗️ ARCHITECTURE INSIGHTS:`)
      cp.architecture_insights.forEach(a => log(`  • ${a}`))
    }

    if (cp.tech_stack?.length > 0) {
      log(`\n🔧 TECH STACK:`)
      cp.tech_stack.forEach(t => log(`  • ${t}`))
    }

    if (cp.quality_trends?.length > 0) {
      log(`\n📈 QUALITY TRENDS:`)
      cp.quality_trends.forEach(q => log(`  • ${q}`))
    }
  }

  // Recommendations
  if (learnings.recommendations?.length > 0) {
    log(`\n💡 RECOMMENDATIONS:`)
    learnings.recommendations.forEach((r, idx) => {
      log(`  ${idx + 1}. ${r}`)
    })
  }

  // Memory suggestions
  if (learnings.memory_suggestions?.length > 0) {
    log(`\n📝 MEMORY SUGGESTIONS (${learnings.memory_suggestions.length}):`)
    const highPriority = learnings.memory_suggestions.filter(s => s.priority === 'high')
    const mediumPriority = learnings.memory_suggestions.filter(s => s.priority === 'medium')
    const lowPriority = learnings.memory_suggestions.filter(s => s.priority === 'low' || !s.priority)

    if (highPriority.length > 0) {
      log(`  🔴 HIGH PRIORITY:`)
      highPriority.forEach(s => log(`    [${s.type}] ${s.content}`))
    }
    if (mediumPriority.length > 0) {
      log(`  🟡 MEDIUM PRIORITY:`)
      mediumPriority.forEach(s => log(`    [${s.type}] ${s.content}`))
    }
    if (lowPriority.length > 0) {
      log(`  ⚪ LOW PRIORITY:`)
      lowPriority.forEach(s => log(`    [${s.type}] ${s.content}`))
    }

    log(`\n💾 Save these to ~/.claude/projects/.../memory/ for future sessions`)
  }

  log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`)
}
