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

// Run session learning extraction as sub-workflow
log('Extracting learnings from session transcripts...')
const sessionLearnings = await workflow('extract-session-learnings')
log(`Session extraction complete: ${sessionLearnings.stored} learnings stored`)

phase('Analyze')

// Analyze FlossWare AI projects
const AI_PROJECTS = [
  '~/Development/github/FlossWare/consensus-ai',
  '~/Development/github/FlossWare/knowledge-ai',
  '~/Development/github/FlossWare/semantic-search-ai',
  '~/Development/github/FlossWare/skills-ai',
  '~/Development/github/FlossWare/vectordb-ai'
]

const aiProjectLearnings = await agent(`Analyze FlossWare AI projects for learnings:

Projects: ${AI_PROJECTS.join(', ')}

Extract:
- Architecture patterns (multi-AI, consensus, arbiter/worker)
- API design decisions
- Integration patterns
- Best practices discovered
- Lessons learned from implementation

Read README, documentation, and key source files.`, {
  label: 'analyze-ai-projects',
  schema: {
    type: 'object',
    properties: {
      projects: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            patterns: { type: 'array', items: { type: 'string' } },
            decisions: { type: 'array', items: { type: 'string' } },
            bestPractices: { type: 'array', items: { type: 'string' } },
            lessons: { type: 'array', items: { type: 'string' } }
          },
          required: ['name']
        }
      }
    },
    required: ['projects']
  }
})

log(`Analyzed ${aiProjectLearnings.projects.length} AI projects`)

// Analyze all skills
const skillFiles = await agent('List all skill files (*.md, *.sh, *.js) in skills/', {
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
const workflowFiles = await agent('List all workflow files (*.js) in workflows/', {
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
const existingLearnings = await agent('Read learnings/ directory and summarize existing knowledge', {
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

// Extract from skills
const skillLearnings = await pipeline(
  skillFiles.skills.slice(0, 10), // Limit for now
  skill => agent(`Analyze skill ${skill.path} and extract:
    - Common patterns used
    - Decisions made (and why)
    - Best practices discovered
    - Anti-patterns avoided

    Read the file and identify learnings that would help future sessions.`, {
    label: `extract:${skill.path.split('/').pop()}`,
    phase: 'Extract',
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
    return agent(`As arbiter, synthesize these ${results.filter(Boolean).length} worker analyses:

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

// Extract from AI projects
const aiLearnings = aiProjectLearnings.projects.flatMap(project => [
  ...(project.patterns || []).map(p => ({ source: 'ai-project', project: project.name, type: 'pattern', content: p })),
  ...(project.decisions || []).map(d => ({ source: 'ai-project', project: project.name, type: 'decision', content: d })),
  ...(project.bestPractices || []).map(bp => ({ source: 'ai-project', project: project.name, type: 'bestPractice', content: bp })),
  ...(project.lessons || []).map(l => ({ source: 'ai-project', project: project.name, type: 'lesson', content: l }))
])

log(`Extracted ${skillLearnings.filter(Boolean).length} skill learnings, ${workflowLearnings.filter(Boolean).length} workflow learnings, ${aiLearnings.length} AI project learnings`)

phase('Categorize')

// Categorize all learnings by type
const categorized = await agent(`Categorize these learnings into memory types:

Skill Learnings:
${JSON.stringify(skillLearnings.filter(Boolean), null, 2)}

Workflow Learnings:
${JSON.stringify(workflowLearnings.filter(Boolean), null, 2)}

AI Project Learnings:
${JSON.stringify(aiLearnings, null, 2)}

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
  label: 'categorize',
  phase: 'Categorize',
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
