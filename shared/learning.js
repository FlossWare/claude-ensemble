// Shared Learning Module for All Workflows
// Extracts insights from workflow execution to improve future runs

/**
 * Extract learnings from a workflow execution
 *
 * @param {Object} context - Workflow execution context
 * @param {string} context.workflow_name - Name of the workflow (code-solve, code-review, etc.)
 * @param {Object} context.execution_data - Data from workflow execution
 * @param {string} context.phase - Current phase (optional)
 * @returns {Promise<Object>} Learnings object with user patterns, code patterns, and recommendations
 */
export async function extractLearnings(context, agent, log) {
  const { workflow_name, execution_data, phase = 'Learning' } = context

  log(`\n📚 Extracting learnings from ${workflow_name}...`)

  const learningPrompt = buildLearningPrompt(workflow_name, execution_data)

  const LEARNING_SCHEMA = {
    type: 'object',
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
            additionalProperties: { type: 'string' },
            description: 'User expertise by domain (beginner/intermediate/advanced)'
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
          properties: {
            type: {
              type: 'string',
              enum: ['user', 'feedback', 'project', 'reference'],
              description: 'Memory type to save'
            },
            content: {
              type: 'string',
              description: 'What to remember'
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
    model: 'opus',  // Use opus for meta-learning
    phase
  })

  if (!learnings) {
    log(`⚠️ Learning extraction failed`)
    return null
  }

  // Display learnings
  displayLearnings(learnings, log)

  return learnings
}

/**
 * Build learning prompt based on workflow type
 */
function buildLearningPrompt(workflow_name, data) {
  const basePrompt = `Analyze this ${workflow_name} execution and extract key learnings.`

  const workflowPrompts = {
    'code-solve': `${basePrompt}

EXECUTION DATA:
- Issue: ${data.issue_title || 'N/A'}
- Fix approach: ${data.fix_approach || 'N/A'}
- Files changed: ${data.files_changed?.join(', ') || 'N/A'}
- Consensus score: ${data.consensus_score || 'N/A'}

Extract:
1. **User patterns**: How user reports/fixes bugs, preferred fix styles
2. **Code patterns**: Common bug types, architecture insights
3. **Recommendations**: What would make future fixes better/faster`,

    'code-review': `${basePrompt}

EXECUTION DATA:
- Findings: ${data.findings_count || 0} issues found
- Categories: ${data.categories?.join(', ') || 'N/A'}
- Severity: ${data.severity_breakdown || 'N/A'}

Extract:
1. **User patterns**: What types of issues user cares most about
2. **Code patterns**: Recurring bug patterns, quality gaps
3. **Recommendations**: How to prevent these issues`,

    'code-test': `${basePrompt}

EXECUTION DATA:
- Tests run: ${data.tests_run || 0}
- Pass rate: ${data.pass_rate || 'N/A'}
- Failures: ${data.failures?.join(', ') || 'None'}

Extract:
1. **User patterns**: Testing preferences, coverage expectations
2. **Code patterns**: Common failure modes, test gaps
3. **Recommendations**: Testing improvements`,

    'code-pr-review': `${basePrompt}

EXECUTION DATA:
- PRs reviewed: ${data.prs_reviewed || 0}
- Decision: ${data.decision || 'N/A'}
- Breaking changes: ${data.breaking_changes || 'None'}

Extract:
1. **User patterns**: PR review criteria, merge preferences
2. **Code patterns**: PR quality trends, common issues
3. **Recommendations**: PR process improvements`,

    'code-security': `${basePrompt}

EXECUTION DATA:
- Vulnerabilities: ${data.vulnerabilities_count || 0}
- Severity: ${data.severity || 'N/A'}
- Categories: ${data.vuln_categories?.join(', ') || 'N/A'}

Extract:
1. **User patterns**: Security priorities, risk tolerance
2. **Code patterns**: Common vulnerabilities, security gaps
3. **Recommendations**: Security hardening steps`,

    'code-doc': `${basePrompt}

EXECUTION DATA:
- Docs generated: ${data.docs_generated || 0}
- Coverage: ${data.coverage || 'N/A'}
- Gaps: ${data.gaps?.join(', ') || 'None'}

Extract:
1. **User patterns**: Documentation style preferences
2. **Code patterns**: Documentation gaps, complex areas
3. **Recommendations**: Doc quality improvements`
  }

  return workflowPrompts[workflow_name] || `${basePrompt}

DATA: ${JSON.stringify(data, null, 2)}

Extract user patterns, code patterns, and recommendations.`
}

/**
 * Display learnings in a readable format
 */
function displayLearnings(learnings, log) {
  log(`\n✅ Learnings extracted:`)

  if (learnings.user_patterns) {
    if (learnings.user_patterns.preferences?.length > 0) {
      log(`\n👤 User Preferences:`)
      learnings.user_patterns.preferences.forEach(p => log(`  • ${p}`))
    }

    if (learnings.user_patterns.expertise_level && Object.keys(learnings.user_patterns.expertise_level).length > 0) {
      log(`\n🎓 Expertise Levels:`)
      Object.entries(learnings.user_patterns.expertise_level).forEach(([domain, level]) => {
        log(`  • ${domain}: ${level}`)
      })
    }
  }

  if (learnings.code_patterns) {
    if (learnings.code_patterns.common_bugs?.length > 0) {
      log(`\n🐛 Common Bug Patterns:`)
      learnings.code_patterns.common_bugs.forEach(b => log(`  • ${b}`))
    }

    if (learnings.code_patterns.tech_stack?.length > 0) {
      log(`\n🔧 Tech Stack:`)
      learnings.code_patterns.tech_stack.forEach(t => log(`  • ${t}`))
    }
  }

  if (learnings.recommendations?.length > 0) {
    log(`\n💡 Recommendations:`)
    learnings.recommendations.forEach(r => log(`  • ${r}`))
  }

  if (learnings.memory_suggestions?.length > 0) {
    log(`\n📝 Suggested Memory Entries (${learnings.memory_suggestions.length}):`)
    learnings.memory_suggestions.forEach((s, idx) => {
      log(`  ${idx + 1}. [${s.type}] ${s.content}`)
    })
    log(`\n💾 Consider saving these to ~/.claude/projects/.../memory/ for future sessions`)
  }
}

/**
 * Auto-save learnings to memory (optional)
 * This would require file write access
 */
export async function saveLearningsToMemory(learnings, memoryPath, write) {
  // Implementation would use Write tool to save to memory files
  // For now, just return suggestions
  return learnings.memory_suggestions || []
}

// Export for use in workflows
export default {
  extractLearnings,
  saveLearningsToMemory
}
