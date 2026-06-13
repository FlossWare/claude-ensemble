// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'extract-learning',
  description: 'Extract learnings from skills, workflows, sessions, and AI projects',
  phases: [
    { title: 'Sessions', detail: 'Extract from session transcripts (via sub-workflow)' },
    { title: 'Analyze', detail: 'Review skills, workflows, and AI projects' },
    { title: 'Extract', detail: 'Extract patterns, decisions, and insights' },
    { title: 'Categorize', detail: 'Organize by memory type' },
    { title: 'Store', detail: 'Save to global memory' }
  ]
}

// Extract learnings from:
// 1. Session transcripts (all user interactions)
// 2. Skill execution results
// 3. Workflow execution results
// 4. Arbiter/worker consensus decisions
// 5. Error patterns and resolutions
// 6. FlossWare AI projects (consensus-ai, knowledge-ai, semantic-search-ai, etc.)

phase('Sessions')

// Skip session extraction for now - can be run separately
log('Skipping session transcript extraction (run extract-session-learnings separately)')
log('Focusing on skills and workflows in this repo')

phase('Analyze')

// Skip FlossWare AI projects per user request - only learn from .claude skills/workflows
log('Skipping FlossWare AI projects analysis (user preference)')

// Analyze all skills
const skillFiles = await _agent('List all skill files (*.md, *.sh, *.js) in skills/', {
  label: 'list-skills',
  schema: {
    type: 'object',
    properties: {
      skills: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            path: { type: 'string' },
            type: { type: 'string' },
            purpose: { type: 'string' }
          },
          required: ['path', 'type', 'purpose']
        }
      }
    },
    required: ['skills']
  }
})

// Analyze all workflows
const workflowFiles = await _agent('List all workflow files (*.js) in workflows/', {
  label: 'list-workflows',
  schema: {
    type: 'object',
    properties: {
      workflows: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            path: { type: 'string' },
            purpose: { type: 'string' },
            multiModel: { type: 'boolean' }
          },
          required: ['path', 'purpose']
        }
      }
    },
    required: ['workflows']
  }
})

// Analyze learnings directory
const existingLearnings = await _agent('Read learnings/ directory and summarize existing knowledge', {
  label: 'read-learnings',
  schema: {
    type: 'object',
    properties: {
      topics: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            topic: { type: 'string' },
            file: { type: 'string' },
            summary: { type: 'string' }
          },
          required: ['topic', 'file', 'summary']
        }
      }
    },
    required: ['topics']
  }
})

log(`Found ${skillFiles.skills.length} skills, ${workflowFiles.workflows.length} workflows, ${existingLearnings.topics.length} existing learnings`)

phase('Extract')

// Extract patterns from each category using multi-model consensus
const MODELS = ['claude-opus-4', 'claude-sonnet-4', 'gpt-4o', 'gemini-2.0-flash-exp']

// Extract from skills (with multi-AI consensus)
const skillLearnings = await pipeline(
  skillFiles.skills.slice(0, 10), // Limit for now
  skill => parallel(MODELS.slice(0, 3).map(model => () =>
    agent(`As ${model}, analyze skill ${skill.path} and extract:
      - Common patterns used
      - Decisions made (and why)
      - Best practices discovered
      - Anti-patterns avoided

      Read the file and identify learnings that would help future sessions.`, {
      label: `analyze-skill:${model}:${skill.path.split('/').pop()}`,
      phase: 'Extract',
      model: model.includes('claude') ? model.split('-')[1] : 'sonnet',
      schema: {
        type: 'object',
        properties: {
          patterns: { type: 'array', items: { type: 'string' } },
          decisions: { type: 'array', items: { type: 'string' } },
          bestPractices: { type: 'array', items: { type: 'string' } },
          antiPatterns: { type: 'array', items: { type: 'string' } }
        }
      }
    })
  )).then(results => {
    // Arbiter synthesizes worker results
    return _agent(`As arbiter, synthesize these ${results.filter(Boolean).length} worker analyses for skill ${skill.path}:

      ${JSON.stringify(results.filter(Boolean), null, 2)}

      Identify consensus learnings and resolve conflicts.`, {
      label: `arbiter:${skill.path.split('/').pop()}`,
      phase: 'Extract',
      model: 'opus',
      schema: {
        type: 'object',
        properties: {
          consensusLearnings: { type: 'array', items: { type: 'string' } },
          patterns: { type: 'array', items: { type: 'string' } },
          decisions: { type: 'array', items: { type: 'string' } },
          bestPractices: { type: 'array', items: { type: 'string' } }
        }
      }
    })
  })
)

// Extract from workflows (with arbiter consensus)
const workflowLearnings = await pipeline(
  workflowFiles.workflows.slice(0, 10), // Limit for now
  workflow => parallel(MODELS.slice(0, 3).map(model => () =>
    agent(`As ${model}, analyze workflow ${workflow.path} and extract:
      - Multi-model coordination patterns
      - Arbiter selection strategies
      - Worker distribution approaches
      - Consensus resolution methods

      Focus on learnings specific to multi-AI orchestration.`, {
      label: `analyze-wf:${model}:${workflow.path.split('/').pop()}`,
      phase: 'Extract',
      model: model.includes('claude') ? model.split('-')[1] : 'sonnet',
      schema: {
        type: 'object',
        properties: {
          coordination: { type: 'array', items: { type: 'string' } },
          arbiterStrategy: { type: 'array', items: { type: 'string' } },
          workerDistribution: { type: 'array', items: { type: 'string' } },
          consensusMethods: { type: 'array', items: { type: 'string' } }
        }
      }
    })
  )).then(results => {
    // Arbiter synthesizes worker results
    return _agent(`As arbiter, synthesize these ${results.filter(Boolean).length} worker analyses:

      ${JSON.stringify(results.filter(Boolean), null, 2)}

      Identify consensus learnings and resolve conflicts.`, {
      label: `arbiter:${workflow.path.split('/').pop()}`,
      phase: 'Extract',
      model: 'opus',
      schema: {
        type: 'object',
        properties: {
          consensusLearnings: { type: 'array', items: { type: 'string' } },
          conflicts: { type: 'array', items: { type: 'string' } },
          resolution: { type: 'string' }
        }
      }
    })
  })
)

log(`Extracted ${skillLearnings.filter(Boolean).length} skill learnings, ${workflowLearnings.filter(Boolean).length} workflow learnings`)

phase('Categorize')

// Categorize all learnings by type (with multi-AI consensus)
const categorizationWorkers = await parallel(
  MODELS.slice(0, 3).map(model => () =>
    agent(`As ${model}, categorize these learnings into memory types:

Skill Learnings:
${JSON.stringify(skillLearnings.filter(Boolean), null, 2)}

Workflow Learnings:
${JSON.stringify(workflowLearnings.filter(Boolean), null, 2)}

Categorize each learning as:
- feedback: User corrections/confirmations about approach
- user: User role, goals, preferences
- project: Ongoing work, initiatives
- reference: External system pointers
- technical: Code patterns, architecture decisions

For each learning, provide:
- type: memory type
- name: kebab-case slug
- description: one-line summary
- content: detailed markdown content
- why: reason/context
- howToApply: when to use this`, {
      label: `categorize:${model}`,
      phase: 'Categorize',
      model: model.includes('claude') ? model.split('-')[1] : 'sonnet',
      schema: {
        type: 'object',
        properties: {
          learnings: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                type: { type: 'string', enum: ['feedback', 'user', 'project', 'reference', 'technical'] },
                name: { type: 'string' },
                description: { type: 'string' },
                content: { type: 'string' },
                why: { type: 'string' },
                howToApply: { type: 'string' }
              },
              required: ['type', 'name', 'description', 'content']
            }
          }
        },
        required: ['learnings']
      }
    })
  )
)

// Arbiter synthesizes categorization consensus
const categorized = await _agent(`As arbiter, synthesize categorization from ${categorizationWorkers.filter(Boolean).length} workers:

${JSON.stringify(categorizationWorkers.filter(Boolean), null, 2)}

Create final categorized learning list:
- Merge duplicate learnings (same concept, different wording)
- Use best name/description from workers
- Ensure all learnings have required fields
- Resolve conflicts in categorization

Return consolidated list.`, {
  label: 'arbiter-categorize',
  phase: 'Categorize',
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      learnings: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            type: { type: 'string', enum: ['feedback', 'user', 'project', 'reference', 'technical'] },
            name: { type: 'string' },
            description: { type: 'string' },
            content: { type: 'string' },
            why: { type: 'string' },
            howToApply: { type: 'string' }
          },
          required: ['type', 'name', 'description', 'content']
        }
      }
    },
    required: ['learnings']
  }
})

log(`Categorized ${categorized.learnings.length} learnings`)

phase('Store')

// Store each learning to global memory
const stored = await pipeline(
  categorized.learnings,
  learning => agent(`Save this learning to global memory:

Type: ${learning.type}
Name: ${learning.name}
Description: ${learning.description}
Content: ${learning.content}
Why: ${learning.why || 'N/A'}
How to Apply: ${learning.howToApply || 'N/A'}

Create memory file at: memory/${learning.name}.md
Update memory/MEMORY.md index

Return confirmation with file path.`, {
    label: `store:${learning.name}`,
    phase: 'Store',
    schema: {
      type: 'object',
      properties: {
        stored: { type: 'boolean' },
        path: { type: 'string' },
        error: { type: 'string' }
      },
      required: ['stored']
    }
  })
)

const successful = stored.filter(Boolean).filter(s => s.stored).length
const failed = stored.filter(Boolean).filter(s => !s.stored).length

log(`Stored ${successful} learnings, ${failed} failed`)

return {
  skillsAnalyzed: skillFiles.skills.length,
  workflowsAnalyzed: workflowFiles.workflows.length,
  learningsExtracted: categorized.learnings.length,
  learningsStored: successful,
  failed: failed,
  summary: `Extracted and stored ${successful} learnings from ${skillFiles.skills.length} skills and ${workflowFiles.workflows.length} workflows`
}
