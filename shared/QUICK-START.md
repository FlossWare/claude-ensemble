# Quick Start: Building Workflows with Arbiter/Worker Pattern

**Use this guide to quickly create new workflows using our validated patterns.**

## 🚀 Quick Start (5 minutes)

### 1. Copy the Template
```bash
cp workflows/TEMPLATE-arbiter-worker.js workflows/your-workflow.js
```

### 2. Update Meta
```javascript
export const meta = {
  name: 'your-workflow',
  description: 'What this workflow does',
  phases: [
    { title: 'Phase 1', detail: 'What happens', model: 'opus' },
    { title: 'Phase 2', detail: 'What happens', model: 'sonnet' }
  ]
}
```

### 3. Configure Workers & Arbiters
```javascript
const WORKER_MODELS = ['opus', 'sonnet', 'haiku']
const PHASE1_ARBITER = 'opus'
const PHASE2_ARBITER = 'sonnet'  // DIFFERENT from phase 1!
```

### 4. Add Your Logic
Replace the template's analysis/proposal logic with your workflow's purpose.

### 5. Test
```bash
# Test locally first
claude-code workflow run workflows/your-workflow.js

# Check for prompts - should be ZERO!
```

## 📋 Copy-Paste Snippets

### No Bash Instruction (Copy into prompts)
```javascript
const NO_BASH_INSTRUCTION = `
IMPORTANT: Use the Read tool to analyze files, NOT Bash commands.
- Don't use sed, grep, cat, wc, or other shell commands
- Use Read tool for file content
- Analyze in your reasoning, return structured data
`.trim()

// Use in agent prompts:
const result = await agent(`Your task.

${NO_BASH_INSTRUCTION}

Return results.`, { schema })
```

### Progress Logging Pattern
```javascript
// BEFORE parallel operation
log(`🔄 ${count} workers ${action} in parallel...`)

// DURING (with labels)
const results = await parallel(items.map(item =>
  () => agent('Task', {
    label: `${model} ${description}`,  // Shows in /workflows UI
    model, schema
  })
))

// AFTER
log(`✅ Received ${results.filter(Boolean).length}/${items.length} results`)
```

### Role Swap Helper (Copy into workflow)
```javascript
async function validateWithRoleSwap(decision, selectedProposal, arbiterModel, workerModels, context) {
  const newWorker = arbiterModel
  const selectedIndex = decision.selected_index
  const newArbiters = workerModels.filter((_, idx) => idx !== selectedIndex)

  log(`🔄 Role swap: ${arbiterModel} → worker, ${newArbiters.join(', ')} → arbiters`)

  const workerReview = await agent(`Review as skeptic.

${NO_BASH_INSTRUCTION}

Proposal: ${JSON.stringify(selectedProposal, null, 2)}

Find issues.`, {
    label: `${newWorker} Skeptical Review`,
    model: newWorker,
    schema: {
      type: 'object',
      properties: {
        approved: { type: 'boolean' },
        concerns: { type: 'array', items: { type: 'string' } },
        confidence: { type: 'number', minimum: 0, maximum: 100 }
      }
    }
  })

  log(`${workerReview.approved ? '✅' : '⚠️'} Worker: ${workerReview.approved ? 'APPROVED' : 'CONCERNS'}`)

  log(`🗳️  ${newArbiters.length} arbiters voting...`)

  const arbiterVotes = await parallel(newArbiters.map(model =>
    () => agent(`Vote: approve or reject?

${NO_BASH_INSTRUCTION}

Proposal: ${JSON.stringify(selectedProposal, null, 2)}
Worker review: ${JSON.stringify(workerReview, null, 2)}

Vote.`, {
      label: `${model} Vote`,
      model: model,
      schema: {
        type: 'object',
        properties: {
          vote: { type: 'string', enum: ['approve', 'reject'] },
          reasoning: { type: 'string' }
        }
      }
    })
  ))

  const approvals = arbiterVotes.filter(Boolean).filter(v => v.vote === 'approve').length
  const rejections = arbiterVotes.filter(Boolean).length - approvals

  log(`✅ Votes: ${approvals} approve, ${rejections} reject`)

  return {
    consensus: workerReview.approved && approvals > rejections,
    worker_review: workerReview,
    arbiter_votes: arbiterVotes.filter(Boolean),
    approvals,
    rejections
  }
}
```

## ✅ Checklist Before Running

- [ ] Different arbiters for different phases
- [ ] `NO_BASH_INSTRUCTION` in all agent prompts
- [ ] Progress logging before/after parallel operations
- [ ] Descriptive labels on agent calls
- [ ] Role swap validation included
- [ ] Schemas for all agent calls
- [ ] No export syntax in inline functions
- [ ] Tested locally first

## 🎯 Pattern Quick Reference

### When to Use What

**Use `parallel()` for**:
- ✅ Solve/refactor phases (workers propose independently)
- ✅ Multiple workers analyzing same item
- ✅ Independent tasks

**Use `pipeline()` for**:
- ✅ Multi-stage dependent operations per item
- ✅ Sequential processing where later stages need earlier results
- ✅ Each item goes through multiple phases

**Different Arbiters**:
- ✅ Review phase: Arbiter A
- ✅ Solve phase: Arbiter B (MUST be different!)
- ✅ Verify phase: Arbiter C (MUST be different!)

**Role Swap**:
- ✅ After every arbiter selection
- ✅ Arbiter becomes skeptical worker
- ✅ Workers become voting arbiters
- ✅ Consensus = worker approved AND majority arbiters approve

## 🚫 Common Mistakes

### ❌ DON'T: Same Arbiter for Review and Solve
```javascript
// BAD
const REVIEW_ARBITER = 'opus'
const SOLVE_ARBITER = 'opus'  // ❌ SAME!
```

### ✅ DO: Different Arbiters
```javascript
// GOOD
const REVIEW_ARBITER = 'opus'
const SOLVE_ARBITER = 'sonnet'  // ✅ DIFFERENT!
```

### ❌ DON'T: Bash Commands in Prompts
```javascript
// BAD
await agent(`Execute: sed -n '1,10p' file.js`)
```

### ✅ DO: Read Tool
```javascript
// GOOD
await agent(`Read file.js lines 1-10.

${NO_BASH_INSTRUCTION}

Return content.`, { schema })
```

### ❌ DON'T: Silent Parallel Operations
```javascript
// BAD
const results = await parallel(items.map(i => () => agent('Task', {})))
```

### ✅ DO: Log Before/After
```javascript
// GOOD
log(`🔄 ${items.length} workers processing...`)
const results = await parallel(items.map(i =>
  () => agent('Task', { label: `${model} ${i}` })
))
log(`✅ Received ${results.filter(Boolean).length}/${items.length}`)
```

## 📚 Full Documentation

- **Template**: `workflows/TEMPLATE-arbiter-worker.js`
- **Instructions**: `shared/inline/instructions.js`
- **Pattern Guide**: Memory file `arbiter-worker-pattern.md`
- **Progress Logging**: `shared/PROGRESS-LOGGING-PATTERN.md`
- **No Bash Rule**: Memory file `no-bash-in-workflows.md`

## 🎓 Examples

See these workflows for real implementations:
- `workflows/refactor-all-workflows.js` - Multi-workflow refactoring
- `workflows/refactor-iterate.js` - Iterative refinement
- `code-solve.js` - Arbiter-based fix selection
- `code-review.js` - Multi-phase review workflow

## ⚡ Pro Tips

1. **Start simple**: Copy template, modify minimally, test
2. **Log everything**: Users want visibility
3. **Different arbiters**: Never reuse same arbiter for review+solve
4. **Role swap always**: It catches bugs arbiters miss
5. **No Bash**: Use Read tool, avoid prompts
6. **Test locally**: Run once before committing
7. **Schemas always**: Structured output prevents parse errors
8. **Labels matter**: They show in `/workflows` UI

## 🆘 Troubleshooting

**Getting permission prompts?**
→ Add `NO_BASH_INSTRUCTION` to agent prompts

**Workflow not iterating?**
→ Check role swap returns `consensus: boolean`

**Same arbiter error?**
→ Use different arbiters for each phase

**Export syntax error?**
→ Remove `export` from inline functions

**No progress visibility?**
→ Add log() before/after parallel operations

---

**Ready to build?** Copy the template and start coding! 🚀
