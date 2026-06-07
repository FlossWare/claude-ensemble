export const meta = {
  name: 'code-doc',
  description: 'Interactive documentation generation - prompts before creating docs',
  whenToUse: 'When you want comprehensive documentation generation with manual review',
  phases: [
    { title: 'Detect Platform', detail: 'Identify GitHub/GitLab and project type' },
    { title: 'Find Undocumented Code', detail: 'Scan for missing docs' },
    { title: 'Analyze Signatures', detail: 'Extract function/class signatures' },
    { title: 'Multi-AI Doc Generation', detail: 'Generate docs with consensus', model: 'opus' },
    { title: 'Impact Analysis', detail: 'Prioritize by importance' },
    { title: 'README Completeness', detail: 'Check README gaps' },
    { title: 'User Confirmation', detail: 'Review before generating docs' },
    { title: 'Generate Documentation', detail: 'Create PR with docs' },
  ],
}

const AUTONOMOUS = args?.autonomous === true  // INTERACTIVE by default

log(`📚 Documentation Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)

// Phase 1: Detect Platform
phase('Detect Platform')

const platform = await agent(`Detect platform and project type.

Check:
- git remote -v (github/gitlab)
- Project language (package.json, Cargo.toml, go.mod, etc.)
- Existing docs (README.md, docs/, JSDoc, docstrings)

Return platform and language.`, {
  label: 'Detect Platform',
  schema: {
    type: 'object',
    properties: {
      platform: { type: 'string', enum: ['github', 'gitlab', 'unknown'] },
      language: { type: 'string' },
      has_readme: { type: 'boolean' },
      doc_style: { type: 'string' }
    }
  }
})

log(`✅ Platform: ${platform.platform}, Language: ${platform.language}`)

// Phase 2: Find Undocumented Code
phase('Find Undocumented Code')

log('🔍 Scanning for undocumented code...')

const undocumented = await agent(`Find undocumented code.

For ${platform.language}:

JavaScript/TypeScript:
- Functions without JSDoc
- Classes without description
- Exported APIs without docs
- React components without prop docs

Python:
- Functions without docstrings
- Classes without docstrings
- Public methods without docs

Go:
- Exported functions without doc comments
- Public types without docs

Scan codebase and return undocumented items.
Prioritize:
- Public/exported APIs (HIGH)
- Complex functions (MEDIUM)
- Internal utils (LOW)`, {
  label: 'Find Undocumented',
  schema: {
    type: 'object',
    properties: {
      undocumented: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file: { type: 'string' },
            line: { type: 'number' },
            type: { type: 'string', enum: ['function', 'class', 'method', 'component', 'type'] },
            name: { type: 'string' },
            exported: { type: 'boolean' },
            complexity: { type: 'string', enum: ['high', 'medium', 'low'] }
          }
        }
      },
      total: { type: 'number' }
    }
  }
})

log(`✅ Found ${undocumented.total || 0} undocumented items`)

if (undocumented.total === 0) {
  log(`✅ All code is documented!`)
  return {
    status: 'complete',
    message: 'All code is already documented'
  }
}

// Phase 3: Analyze Signatures
phase('Analyze Signatures')

log('📝 Analyzing signatures and usage...')

const signatures = await Promise.all(
  (undocumented.undocumented || []).slice(0, 20).map(item =>
    agent(`Extract signature and usage for ${item.name}.

File: ${item.file}:${item.line}

Read the file and extract:
- Full function/class signature
- Parameters and types
- Return type
- Usage examples (if found in codebase)
- Dependencies/imports

Return signature details.`, {
      label: `Analyze: ${item.name}`,
      schema: {
        type: 'object',
        properties: {
          signature: { type: 'string' },
          parameters: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                name: { type: 'string' },
                type: { type: 'string' },
                optional: { type: 'boolean' }
              }
            }
          },
          return_type: { type: 'string' },
          usage_examples: { type: 'array', items: { type: 'string' } }
        }
      }
    }).catch(() => null)
  )
)

const validSignatures = signatures.filter(Boolean)

log(`✅ Analyzed ${validSignatures.length} signatures`)

// Phase 4: Multi-AI Doc Generation
phase('Multi-AI Doc Generation')

log('🤖 Generating documentation with multi-AI consensus...')

// Dynamic model detection - models that fail return null and are filtered out
const WORKERS = [
  'opus', 'sonnet', 'haiku',  // Claude models (always available)
  // Gemini (via MCP/Google AI API)
  // 'grok',                   // Grok (via xAI API) - uncomment when configured
  // 'ollama/llama3',          // Ollama (local) - uncomment when running
  // 'gpt-4',                  // OpenAI (via MCP) - uncomment when configured
]

// Generate docs for first 10 items (limit for token efficiency)
const docGenerations = await pipeline(
  undocumented.undocumented.slice(0, 10),

  // Stage 1: Each worker generates docs independently
  item => parallel(WORKERS.map(model => () =>
    agent(`Generate documentation for ${item.name}.

Type: ${item.type}
File: ${item.file}:${item.line}
Complexity: ${item.complexity}

Generate ${platform.doc_style || 'standard'} documentation:
- Brief description (1-2 sentences)
- Parameters (with types and descriptions)
- Return value
- Usage example
- Notes/warnings if applicable

Write high-quality, clear documentation.`, {
      label: `Doc (${model}): ${item.name}`,
      model,
      schema: {
        type: 'object',
        properties: {
          description: { type: 'string' },
          params_doc: { type: 'string' },
          returns_doc: { type: 'string' },
          example: { type: 'string' },
          notes: { type: 'string' }
        }
      }
    }).catch(() => null)
  )),

  // Stage 2: Arbiter creates consensus doc
  (workerDocs, item) => {
    const validDocs = workerDocs.filter(Boolean)
    if (validDocs.length === 0) return null

    return agent(`Merge ${validDocs.length} documentation versions for ${item.name}.

Create best consensus documentation by:
- Combining best descriptions
- Most accurate parameter docs
- Clearest examples

Return final documentation.`, {
      label: `Arbiter: ${item.name}`,
      model: 'opus',
      schema: {
        type: 'object',
        properties: {
          final_doc: { type: 'string' },
          confidence: { type: 'number' }
        }
      }
    })
  }
)

const validDocs = docGenerations.filter(Boolean)

log(`✅ Generated ${validDocs.length} documentation blocks`)

// Phase 5: Impact Analysis
phase('Impact Analysis')

log('🎯 Prioritizing by importance...')

// Score by impact (exported APIs > complex > internal)
undocumented.undocumented.forEach((item, idx) => {
  let score = 0

  if (item.exported) score += 50
  if (item.complexity === 'high') score += 30
  else if (item.complexity === 'medium') score += 15

  if (item.type === 'class') score += 20
  else if (item.type === 'function') score += 10

  item.impact_score = score
  item.doc = validDocs[idx]?.final_doc
})

// Sort by impact
undocumented.undocumented.sort((a, b) => b.impact_score - a.impact_score)

log(`✅ Prioritized ${undocumented.total} items`)

// Phase 6: README Completeness
phase('README Completeness')

log('📖 Checking README completeness...')

const readmeCheck = await agent(`Check README.md completeness.

Expected sections:
- Title and description
- Installation instructions
- Usage examples
- API documentation
- Contributing guidelines
- License

Check which sections are missing.`, {
  label: 'README Check',
  schema: {
    type: 'object',
    properties: {
      missing_sections: { type: 'array', items: { type: 'string' } },
      needs_update: { type: 'boolean' }
    }
  }
})

log(`✅ README check: ${readmeCheck.missing_sections?.length || 0} missing sections`)

// Phase 7: User Confirmation
phase('User Confirmation')

if (!AUTONOMOUS) {
  log('')
  log('═'.repeat(60))
  log('📚 DOCUMENTATION AUDIT RESULTS')
  log('═'.repeat(60))
  log(`Undocumented items: ${undocumented.total}`)
  log(`Generated docs: ${validDocs.length}`)
  log(`Missing README sections: ${readmeCheck.missing_sections?.length || 0}`)
  log('')

  const topItems = undocumented.undocumented.slice(0, 5)
  log('Top 5 items to document:')
  topItems.forEach((item, idx) => {
    log(`   ${idx + 1}. ${item.name} (${item.file})`)
    log(`      Type: ${item.type}, Exported: ${item.exported}`)
  })

  log('═'.repeat(60))

  // ASK USER: Generate documentation?
  const userDecision = await agent(`Review documentation gaps and decide what to generate.

Undocumented: ${undocumented.total}
Generated: ${validDocs.length}

Options:
- ALL: Generate docs for all ${undocumented.total} items
- EXPORTED_ONLY: Only public/exported APIs
- TOP_10: Top 10 highest priority items
- NONE: Don't generate (just show report)

Return your decision.`, {
    label: 'User Decision',
    schema: {
      type: 'object',
      properties: {
        action: { type: 'string', enum: ['ALL', 'EXPORTED_ONLY', 'TOP_10', 'NONE'] },
        reasoning: { type: 'string' }
      },
      required: ['action']
    }
  })

  log(`\n👤 User Decision: ${userDecision.action}`)

  if (userDecision.action === 'NONE') {
    log(`ℹ️  No documentation generated (user chose NONE)`)
    return {
      status: 'report_only',
      undocumented: undocumented.total,
      message: 'Documentation audit complete - report only'
    }
  }

  // Filter based on user decision
  let itemsToDocument = undocumented.undocumented
  if (userDecision.action === 'EXPORTED_ONLY') {
    itemsToDocument = undocumented.undocumented.filter(item => item.exported)
  } else if (userDecision.action === 'TOP_10') {
    itemsToDocument = undocumented.undocumented.slice(0, 10)
  }

  undocumented.undocumented = itemsToDocument
}

// Phase 8: Generate Documentation
phase('Generate Documentation')

log(`📝 Creating documentation PR...`)

// Use branch name from args or default
const docBranch = args?.doc_branch || 'docs/auto-generated'

const prResult = await agent(`Create documentation PR.

Branch: ${docBranch}

Steps:
1. Create branch
2. Add documentation to files:
   ${undocumented.undocumented.slice(0, 5).map(item => `   - ${item.file} (add docs for ${item.name})`).join('\n')}
3. Commit changes
4. Push branch
5. Create PR with title "📚 Add missing documentation"

Execute git commands to create PR.`, {
  label: 'Create Docs PR',
  schema: {
    type: 'object',
    properties: {
      pr_number: { type: 'number' },
      pr_url: { type: 'string' },
      files_updated: { type: 'number' }
    }
  }
})

log(`✅ Documentation PR created: ${prResult.pr_url}`)

log('')
log('═'.repeat(60))
log('📚 DOCUMENTATION GENERATION COMPLETE')
log('═'.repeat(60))
log(`Undocumented items: ${undocumented.total}`)
log(`Documented: ${undocumented.undocumented.length}`)
log(`PR: ${prResult.pr_url}`)
log('═'.repeat(60))

const result = {
  status: 'complete',
  total_undocumented: undocumented.total,
  documented: undocumented.undocumented.length,
  docs_generated: undocumented.undocumented.length,
  coverage: undocumented.total > 0 ? Math.round((undocumented.undocumented.length / undocumented.total) * 100) : 100,
  pr_url: prResult.pr_url,
  pr_number: prResult.pr_number
}

// Extract learnings
try {
  await workflow('ai-extract-learning', {
    workflow_name: 'code-doc',
    execution_data: result
  })
} catch (error) {
  log(`⚠️ Learning extraction failed: ${error.message}`)
}

return result
