# Multi-AI Consensus Pattern

**Standard pattern for all workflows**: Every phase should use multi-AI workers (opus/sonnet/haiku) + arbiter synthesis.

## Pattern Template

```javascript
// PHASE X: <Phase Name> with multi-AI consensus
phase('<Phase Name>')

log('🤖 Multi-AI <task> (opus/sonnet/haiku)...')

const workers = await parallel([
  () => agent(`[OPUS] <task description>

<context>

Task:
1. <step 1>
2. <step 2>
3. <step 3>

Return structured data.`, {
    label: 'opus-<task>',
    model: 'opus',
    schema: {
      type: 'object',
      properties: {
        model: { type: 'string' },
        // ... task-specific fields
      }
    }
  }),

  () => agent(`[SONNET] <task description>

<context>

Task:
1. <step 1>
2. <step 2>
3. <step 3>

Return structured data.`, {
    label: 'sonnet-<task>',
    model: 'sonnet',
    schema: {
      type: 'object',
      properties: {
        model: { type: 'string' },
        // ... task-specific fields
      }
    }
  }),

  () => agent(`[HAIKU] <task description>

<context>

Task:
1. <step 1>
2. <step 2>
3. <step 3>

Return structured data.`, {
    label: 'haiku-<task>',
    model: 'haiku',
    schema: {
      type: 'object',
      properties: {
        model: { type: 'string' },
        // ... task-specific fields
      }
    }
  }),
])

const validWorkers = workers.filter(Boolean)
log(`✅ ${validWorkers.length}/3 workers completed`)

log('⚖️  Arbiter synthesizing best answer...')

const synthesis = await agent(`[ARBITER] Review ${validWorkers.length} worker responses.

Worker Responses:
${validWorkers.map((w, i) => `
Worker ${i + 1} (${w.model || 'unknown'}):
<format worker output>
`).join('\n')}

Task:
1. Select the BEST answer
2. Explain why you chose it
3. Rate confidence (0-100)
4. Synthesize final result

Return structured decision.`, {
  label: 'arbiter-<task>',
  schema: {
    type: 'object',
    properties: {
      winning_worker: { type: 'string' },
      why_selected: { type: 'string' },
      confidence: { type: 'number' },
      result: {
        // ... final synthesized result matching worker schema
      }
    }
  }
})

log(`✅ Winner: ${synthesis.winning_worker} (confidence: ${synthesis.confidence}%)`)

const result = synthesis.result
```

## When to Use

**✅ USE in every phase that:**
- Makes a decision
- Analyzes data
- Rates quality
- Discovers information
- Validates results
- Synthesizes findings

**❌ DON'T USE for:**
- Pure mechanical operations (reading a file, listing files)
- Operations where multi-AI adds no value (running a shell command)
- Steps where speed matters more than quality

## Examples

### File Discovery
```javascript
const fileDiscovery = await parallel([
  () => agent(`[OPUS] List all memory files...`, { model: 'opus', schema }),
  () => agent(`[SONNET] List all memory files...`, { model: 'sonnet', schema }),
  () => agent(`[HAIKU] List all memory files...`, { model: 'haiku', schema }),
])
const arbiter = await agent(`[ARBITER] Select most complete list...`)
```

### Code Analysis
```javascript
const analysis = await parallel([
  () => agent(`[OPUS] Analyze code for bugs...`, { model: 'opus', schema }),
  () => agent(`[SONNET] Analyze code for bugs...`, { model: 'sonnet', schema }),
  () => agent(`[HAIKU] Analyze code for bugs...`, { model: 'haiku', schema }),
])
const arbiter = await agent(`[ARBITER] Select most thorough analysis...`)
```

### Quality Rating
```javascript
const ratings = await parallel([
  () => agent(`[OPUS] Rate search quality...`, { model: 'opus', schema }),
  () => agent(`[SONNET] Rate search quality...`, { model: 'sonnet', schema }),
  () => agent(`[HAIKU] Rate search quality...`, { model: 'haiku', schema }),
])
const arbiter = await agent(`[ARBITER] Synthesize consensus rating...`)
```

## Benefits

1. **Higher Accuracy** - Multiple models catch what one misses
2. **Reduced False Positives** - Consensus filters noise
3. **Better Coverage** - Different models notice different patterns
4. **Confidence Scoring** - Arbiter rates quality of synthesis
5. **Diverse Perspectives** - Opus (creative), Sonnet (balanced), Haiku (fast/precise)

## Cost vs Quality

- **3 workers + 1 arbiter** = 4x cost but much higher quality
- Use for **critical decisions** (security, bugs, breaking changes)
- Use for **final validation** (release readiness, production deployment)
- Skip for **development iteration** (draft PRs, WIP code review)

## Standard Workflow Structure

Every workflow should follow this pattern:

```
Phase 1: Gather (multi-AI workers + arbiter)
Phase 2: Analyze (multi-AI workers + arbiter)
Phase 3: Decide (multi-AI workers + arbiter)
Phase 4: Verify (multi-AI workers + arbiter)
```

**NOT:**
```
Phase 1: Gather (single agent)
Phase 2: Analyze (single agent)
Phase 3: Multi-AI decision
```

Every meaningful step gets multi-AI treatment.
