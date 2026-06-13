// Fleet-aware agent wrapper with graceful fallback
let _agent;
try {
  const { createFleetAgent } = await import('../fleet-agent-wrapper.js');
  _agent = (process.env.FLEET_DISPATCHER === 'true') ? createFleetAgent(agent) : agent;
} catch (e) {
  _agent = agent; // Graceful fallback if wrapper unavailable
}

export const meta = {
  name: 'knowledge-ingest',
  description: 'Universal knowledge ingestion - learn from any doc format',
  phases: [
    { title: 'Detect', detail: 'Detect format and structure' },
    { title: 'Extract', detail: 'Multi-AI fact extraction' },
    { title: 'Chunk', detail: 'Semantic chunking' },
    { title: 'Store', detail: 'Store in global memory' }
  ]
}

// Borrow concepts from knowledge-ai:
// - Universal format support (PDF, MD, HTML, code docs)
// - Multi-AI consensus extraction
// - Semantic chunking
// - Vector-friendly storage

// Input: args.source (file path or URL)
// Output: knowledge stored in memory/

const SOURCE = args?.source
if (!SOURCE) {
  throw new Error('Missing required arg: source (file path or URL)')
}

phase('Detect')

// Detect format and extract structure
const detected = await _agent(`Analyze source: ${SOURCE}

Detect:
- Format (PDF, Markdown, HTML, code, plain text)
- Structure (headers, sections, code blocks)
- Domain (programming, docs, tutorial, API reference)
- Language (if code)

Read the file and analyze its structure.`, {
  label: 'detect-format',
  schema: {
    type: 'object',
    properties: {
      format: { type: 'string', enum: ['pdf', 'markdown', 'html', 'code', 'text', 'unknown'] },
      structure: {
        type: 'object',
        properties: {
          hasHeaders: { type: 'boolean' },
          hasSections: { type: 'boolean' },
          hasCodeBlocks: { type: 'boolean' },
          hasLists: { type: 'boolean' }
        }
      },
      domain: { type: 'string' },
      language: { type: 'string' },
      totalLines: { type: 'number' }
    },
    required: ['format', 'structure', 'domain']
  }
})

log(`Detected: ${detected.format} (${detected.domain}), ${detected.totalLines} lines`)

phase('Extract')

// Multi-AI fact extraction with consensus - all models for maximum coverage
const MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']

// Each worker extracts facts independently
const extracted = await parallel(
  MODELS.map(model => () =>
    agent(`As ${model}, extract knowledge from: ${SOURCE}

Extract:
- Key concepts and definitions
- Relationships between concepts
- Best practices and patterns
- Code examples (if applicable)
- References and citations

Format each fact as:
- concept: name of concept
- definition: clear explanation
- context: where/when to use it
- examples: concrete examples

Extract ONLY high-value, non-obvious facts.`, {
      label: `extract:${model}`,
      phase: 'Extract',
      model: model,
      schema: {
        type: 'object',
        properties: {
          facts: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                concept: { type: 'string' },
                definition: { type: 'string' },
                context: { type: 'string' },
                examples: { type: 'array', items: { type: 'string' } }
              },
              required: ['concept', 'definition']
            }
          }
        },
        required: ['facts']
      }
    })
  )
)

// Arbiter validates and synthesizes consensus facts
const consensus = await _agent(`As arbiter, synthesize consensus from ${extracted.filter(Boolean).length} worker extractions:

${JSON.stringify(extracted.filter(Boolean), null, 2)}

For each fact:
- Validate accuracy (is it correct?)
- Check agreement (2+ workers agree?)
- Assess value (is it non-obvious and useful?)

Return ONLY high-consensus, high-value facts.`, {
  label: 'arbiter-consensus',
  phase: 'Extract',
  model: 'opus',
  schema: {
    type: 'object',
    properties: {
      consensusFacts: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            concept: { type: 'string' },
            definition: { type: 'string' },
            context: { type: 'string' },
            examples: { type: 'array', items: { type: 'string' } },
            agreementCount: { type: 'number' },
            confidence: { type: 'string', enum: ['high', 'medium', 'low'] }
          },
          required: ['concept', 'definition', 'agreementCount']
        }
      }
    },
    required: ['consensusFacts']
  }
})

log(`Extracted ${consensus.consensusFacts.length} consensus facts`)

phase('Chunk')

// Semantic chunking - group related facts into coherent chunks
const chunked = await _agent(`Organize these ${consensus.consensusFacts.length} facts into semantic chunks:

${JSON.stringify(consensus.consensusFacts, null, 2)}

Create chunks that:
- Group related concepts together
- Maintain coherent context
- Are sized for retrieval (500-1000 chars each)
- Preserve relationships between facts

Each chunk should have:
- title: descriptive name
- content: markdown-formatted knowledge
- concepts: list of concept names in this chunk
- domain: topic area`, {
  label: 'semantic-chunk',
  phase: 'Chunk',
  schema: {
    type: 'object',
    properties: {
      chunks: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            title: { type: 'string' },
            content: { type: 'string' },
            concepts: { type: 'array', items: { type: 'string' } },
            domain: { type: 'string' }
          },
          required: ['title', 'content', 'concepts', 'domain']
        }
      }
    },
    required: ['chunks']
  }
})

log(`Created ${chunked.chunks.length} semantic chunks`)

phase('Store')

// Store chunks as memory files (vector-friendly)
const stored = await pipeline(
  chunked.chunks,
  chunk => agent(`Store this knowledge chunk in global memory:

Title: ${chunk.title}
Domain: ${chunk.domain}
Concepts: ${chunk.concepts.join(', ')}

Content:
${chunk.content}

Create memory file:
- Name: knowledge-${chunk.domain}-${chunk.title.toLowerCase().replace(/\s+/g, '-')}.md
- Type: technical
- Include frontmatter with concepts array
- Format content as markdown

Update memory/MEMORY.md index.`, {
    label: `store:${chunk.title}`,
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

log(`Stored ${successful} chunks, ${failed} failed`)

return {
  source: SOURCE,
  format: detected.format,
  domain: detected.domain,
  factsExtracted: consensus.consensusFacts.length,
  chunksCreated: chunked.chunks.length,
  chunksStored: successful,
  failed: failed,
  summary: `Ingested ${SOURCE} (${detected.format}): extracted ${consensus.consensusFacts.length} facts, stored ${successful} chunks in global memory`
}
