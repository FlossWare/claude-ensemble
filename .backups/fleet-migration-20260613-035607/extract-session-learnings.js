export const meta = {
  name: 'extract-session-learnings',
  description: 'Extract learnings from all Claude Code session transcripts',
  phases: [
    { title: 'Discover', detail: 'Find all session transcripts' },
    { title: 'Analyze', detail: 'Extract patterns from user interactions' },
    { title: 'Consensus', detail: 'Multi-model synthesis of learnings' },
    { title: 'Store', detail: 'Save to global memory' }
  ]
}

// === FLEET DISPATCHER INTEGRATION (inline - no imports needed) ===
const FLEET_DISPATCHER = 'http://pi-02:3004';
const FLEET_ENABLED = true; // Set to false to disable fleet telemetry

async function _dispatchAgent(model, prompt, jobType) {
  if (!FLEET_ENABLED) return null;
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
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    return null;
  }
}

async function _completeAgent(jobId, server, success, duration, jobType, model, error) {
  if (!FLEET_ENABLED) return;
  try {
    await fetch(`${FLEET_DISPATCHER}/agent/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, server, success, duration, job_type: jobType, model, error }),
    });
  } catch (e) {}
}

const _agent = async (prompt, opts = {}) => {
  const model = opts.model || 'sonnet';
  const jobType = 'agent'; // Can enhance with job type inference
  const dispatch = await _dispatchAgent(model, prompt, jobType);
  if (!dispatch) return agent(prompt, opts);
  
  const start = Date.now();
  try {
    const result = await agent(prompt, opts);
    _completeAgent(dispatch.job_id, dispatch.server, true, (Date.now()-start)/1000, jobType, model).catch(()=>{});
    return result;
  } catch (error) {
    _completeAgent(dispatch.job_id, dispatch.server, false, (Date.now()-start)/1000, jobType, model, error.message).catch(()=>{});
    throw error;
  }
};
// === END FLEET DISPATCHER INTEGRATION ===


// Extract learnings from session transcripts (.jsonl files)
// Identify:
// - User preferences and corrections
// - Successful patterns that worked
// - Failed approaches and why
// - Domain knowledge shared by user
// - Project context and constraints

phase('Discover')

// Find all session transcript files
const transcripts = await _agent(`Find all session transcript files:

Search ~/.claude/projects/*/*.jsonl

Return list of transcript files with:
- path
- project (from directory name)
- size (to prioritize recent/large sessions)

Limit to 50 most recent or largest files.`, {
  label: 'find-transcripts',
  schema: {
    type: 'object',
    properties: {
      transcripts: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            path: { type: 'string' },
            project: { type: 'string' },
            sizeKB: { type: 'number' }
          },
          required: ['path', 'project']
        }
      }
    },
    required: ['transcripts']
  }
})

log(`Found ${transcripts.transcripts.length} session transcripts`)

phase('Analyze')

// Analyze transcripts in batches using pipeline (not parallel - avoid barrier)
const BATCH_SIZE = 5
const batches = []
for (let i = 0; i < transcripts.transcripts.length; i += BATCH_SIZE) {
  batches.push(transcripts.transcripts.slice(i, i + BATCH_SIZE))
}

const analyzed = await pipeline(
  batches.slice(0, 10), // Process first 10 batches (50 transcripts max)
  batch => parallel(batch.map(transcript => () =>
    agent(`Analyze session transcript: ${transcript.path}

Extract learnings:
1. **User Corrections** - When user said "no not that", "don't do X", "stop"
2. **User Confirmations** - When user said "yes exactly", "perfect", "that's right"
3. **Successful Patterns** - Approaches that worked well
4. **Failed Patterns** - Approaches that failed (and why)
5. **User Preferences** - How user likes to work, communicate style
6. **Domain Knowledge** - Technical facts or context user shared
7. **Project Constraints** - Deadlines, requirements, restrictions

For each learning, note:
- Type (correction, confirmation, pattern, preference, knowledge, constraint)
- Context (what was happening)
- Lesson (what to remember)

Only extract NON-OBVIOUS learnings. Skip generic or already-known patterns.`, {
      label: `analyze:${transcript.project}`,
      phase: 'Analyze',
      schema: {
        type: 'object',
        properties: {
          learnings: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                type: { type: 'string', enum: ['correction', 'confirmation', 'pattern', 'preference', 'knowledge', 'constraint'] },
                context: { type: 'string' },
                lesson: { type: 'string' }
              },
              required: ['type', 'context', 'lesson']
            }
          }
        },
        required: ['learnings']
      }
    })
  ))
)

// Flatten all learnings
const allLearnings = analyzed.flat().filter(Boolean).flatMap(a => a.learnings || [])

log(`Extracted ${allLearnings.length} raw learnings from sessions`)

phase('Consensus')

// Use multi-model consensus to validate and synthesize learnings
const MODELS = ['claude-opus-4', 'claude-sonnet-4', 'gpt-4o']

// Group similar learnings
const grouped = await _agent(`Group these ${allLearnings.length} learnings by similarity:

${JSON.stringify(allLearnings.slice(0, 200), null, 2)}

Group similar/duplicate learnings together.
For each group:
- Provide synthesized learning (merge duplicates)
- Indicate confidence (high/medium/low)
- Indicate importance (critical/important/nice-to-have)

Skip low-confidence or trivial learnings.`, {
  label: 'group-learnings',
  phase: 'Consensus',
  schema: {
    type: 'object',
    properties: {
      groups: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            synthesized: { type: 'string' },
            type: { type: 'string' },
            confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
            importance: { type: 'string', enum: ['critical', 'important', 'nice-to-have'] },
            count: { type: 'number' }
          },
          required: ['synthesized', 'type', 'confidence', 'importance']
        }
      }
    },
    required: ['groups']
  }
})

// Multi-model validation
const validated = await parallel(
  MODELS.map((model, idx) => () =>
    agent(`As ${model}, review these grouped learnings and validate:

${JSON.stringify(grouped.groups.filter(g => g.confidence === 'high' || g.importance === 'critical'), null, 2)}

For each learning:
- Is it accurate?
- Is it actionable?
- Is it non-obvious?
- Should it be stored in global memory?

Return only learnings that pass validation.`, {
      label: `validate:${model}`,
      phase: 'Consensus',
      model: model.includes('claude') ? model.split('-')[1] : 'sonnet',
      schema: {
        type: 'object',
        properties: {
          validated: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                learning: { type: 'string' },
                type: { type: 'string' },
                reason: { type: 'string' }
              },
              required: ['learning', 'type', 'reason']
            }
          }
        },
        required: ['validated']
      }
    })
  )
)

// Arbiter synthesizes consensus
const consensus = await _agent(`As arbiter, synthesize consensus from ${validated.filter(Boolean).length} model validations:

${JSON.stringify(validated.filter(Boolean), null, 2)}

Identify learnings with majority agreement (2+ models).
For each consensus learning:
- Synthesized lesson
- Memory type (feedback, user, project, reference, technical)
- Why it matters
- How to apply it

Return ONLY high-consensus, high-value learnings.`, {
  label: 'arbiter-synthesis',
  phase: 'Consensus',
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      consensusLearnings: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            lesson: { type: 'string' },
            memoryType: { type: 'string', enum: ['feedback', 'user', 'project', 'reference', 'technical'] },
            why: { type: 'string' },
            howToApply: { type: 'string' },
            agreementCount: { type: 'number' }
          },
          required: ['lesson', 'memoryType', 'why', 'howToApply']
        }
      }
    },
    required: ['consensusLearnings']
  }
})

log(`Consensus: ${consensus.consensusLearnings.length} validated learnings`)

phase('Store')

// Store each consensus learning to global memory
const stored = await pipeline(
  consensus.consensusLearnings,
  learning => agent(`Save this learning to global memory:

Type: ${learning.memoryType}
Lesson: ${learning.lesson}
Why: ${learning.why}
How to Apply: ${learning.howToApply}

Generate:
- kebab-case name (unique slug)
- one-line description
- full markdown content with frontmatter

Create memory file and update MEMORY.md index.`, {
    label: `store:${learning.memoryType}`,
    phase: 'Store',
    schema: {
      type: 'object',
      properties: {
        stored: { type: 'boolean' },
        name: { type: 'string' },
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
  transcriptsAnalyzed: analyzed.flat().filter(Boolean).length,
  rawLearnings: allLearnings.length,
  consensusLearnings: consensus.consensusLearnings.length,
  stored: successful,
  failed: failed,
  summary: `Analyzed ${analyzed.flat().filter(Boolean).length} sessions, extracted ${consensus.consensusLearnings.length} consensus learnings, stored ${successful} to global memory`
}
