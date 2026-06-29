# Workflow Logging Best Practices

Add these log() patterns to your workflows so users can see real-time status.

## Essential Log Points

### 1. Phase Transitions
```javascript
phase('Worker Execution')
log('Starting worker execution phase')
```

### 2. Worker Spawning
```javascript
const workers = ['opus', 'sonnet', 'haiku']
log(`Spawning ${workers.length} workers: ${workers.join(', ')}`)

const results = await parallel(workers.map(model => () => {
  log(`  → ${model}: starting task`)
  return agent(prompt, { model, label: `worker-${model}` })
}))
```

### 3. Waiting for Results
```javascript
log('Waiting for worker responses...')
const results = await parallel(...)
log(`Received ${results.filter(Boolean).length}/${results.length} responses`)
```

### 4. Arbiter Analysis
```javascript
phase('Arbiter Synthesis')
log(`Arbiter (${arbiter}) analyzing ${results.length} worker responses`)

const synthesis = await agent(arbiterPrompt, { 
  model: arbiter,
  label: 'arbiter-synthesis'
})

log(`Arbiter consensus: ${synthesis.confidence}% confidence`)
```

### 5. Decision Points
```javascript
if (confidence >= threshold) {
  log(`✓ Confidence threshold met: ${confidence}% >= ${threshold}%`)
} else {
  log(`✗ Below threshold: ${confidence}% < ${threshold}%, triggering refinement`)
}
```

### 6. Loops and Iterations
```javascript
for (let round = 1; round <= maxRounds; round++) {
  log(`--- Refinement round ${round}/${maxRounds} ---`)
  
  // ... work ...
  
  log(`Round ${round} complete: ${improved}/${total} workers improved`)
}
```

### 7. Budget and Cost
```javascript
const budget = await workflow('ai-cost-tracker', { action: 'getRemainingBudget' })
log(`Budget remaining: $${budget.remaining.toFixed(2)}`)
```

### 8. Error Handling
```javascript
try {
  const result = await agent(...)
} catch (error) {
  log(`⚠ Worker failed: ${error}`)
  return null
}
```

## Example: Enhanced Consensus Workflow

```javascript
export const meta = {
  name: 'ai-consensus-example',
  description: 'Example with comprehensive logging',
  phases: [
    { title: 'Setup', detail: 'Select models and prepare' },
    { title: 'Workers', detail: 'Parallel worker execution' },
    { title: 'Arbiter', detail: 'Synthesize consensus' }
  ]
}

phase('Setup')
log('Starting consensus workflow')

const arbiter = await workflow('get-next-arbiter')
log(`Selected arbiter: ${arbiter}`)

const workers = ['opus', 'sonnet', 'haiku']
log(`Selected ${workers.length} workers: ${workers.join(', ')}`)

phase('Workers')
log('Spawning workers in parallel...')

const results = await parallel(workers.map((model, i) => () => {
  log(`  → Worker ${i+1}/${workers.length} (${model}): starting`)
  
  const result = agent(task, { 
    model, 
    label: `worker-${model}`,
    schema: RESPONSE_SCHEMA
  })
  
  return result.then(r => {
    log(`  ✓ Worker ${i+1} (${model}): completed (confidence: ${r.confidence}%)`)
    return r
  })
}))

const validResults = results.filter(Boolean)
log(`Workers complete: ${validResults.length}/${workers.length} succeeded`)

phase('Arbiter')
log(`Arbiter (${arbiter}) analyzing ${validResults.length} responses`)

const synthesis = await agent(arbiterPrompt, {
  model: arbiter,
  label: 'arbiter-synthesis',
  schema: SYNTHESIS_SCHEMA
})

log(`Arbiter synthesis complete: ${synthesis.confidence}% confidence`)

if (synthesis.confidence >= 70) {
  log('✓ High confidence consensus achieved')
} else {
  log('⚠ Low confidence - consider refinement')
}

await workflow('update-arbiter-state', { arbiter, workflow_name: 'ai-consensus-example' })
log('Arbiter state updated')

return synthesis
```

## Benefits

1. **User Visibility**: Users see what's happening in real-time
2. **Debugging**: Easy to spot where workflows get stuck
3. **Progress Tracking**: Know how far along a workflow is
4. **Performance**: See which workers are slow
5. **Transparency**: Understand AI decision-making

## When to Log

- **Always**: Phase changes, worker spawning, major decisions
- **Often**: Loop iterations, budget checks, model selection
- **Sometimes**: Individual worker completions, intermediate results
- **Rarely**: Low-level calculations, internal state changes

## What NOT to Log

- ❌ Sensitive data (API keys, passwords)
- ❌ Extremely verbose data dumps
- ❌ Every line of code execution
- ❌ Internal implementation details users don't care about

Focus on **what the user needs to understand what's happening**.
