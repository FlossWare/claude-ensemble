---
name: session-learning-integration
description: "Learn from ALL user interactions - corrections, preferences, feedback - and feed back into decisions"
metadata: 
  node_type: memory
  type: feedback
  priority: critical
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# Session-Level Learning Integration

**Rule**: Learn from EVERY user interaction, not just arbiter/worker decisions.

**Why**: User feedback is the most valuable signal for improving AI decisions. When a user corrects us, prefers one approach over another, or provides feedback on outcomes, that's gold - capture it and use it to improve future decisions.

**How to apply**:

## Types of User Feedback to Capture

### 1. Corrections
**Signal**: User says "no, do it this way" or "that's wrong"

**Example**:
```
User: "No, don't use mocks in these tests - use real database"
Action: Save to memory as testing preference
Feed back: Include in future test plan proposals
```

**Capture Pattern**:
```javascript
// After user correction, save to memory
if (userCorrectedUs) {
  await saveToMemory({
    type: 'feedback',
    context: 'testing approach',
    correction: 'Use real database, not mocks',
    why: 'Past incident with mock/prod divergence',
    applies_to: ['code-test', 'test plan generation']
  })
}
```

### 2. Preferences
**Signal**: User says "I prefer X over Y"

**Example**:
```
User: "I prefer opus for code reviews over sonnet"
Action: Save as arbiter preference
Feed back: Use opus as arbiter for code-review workflows
```

**Capture Pattern**:
```javascript
if (userExpressedPreference) {
  await saveToMemory({
    type: 'user',
    preference: 'opus for code reviews',
    context: 'arbiter selection',
    applies_to: ['code-review']
  })
}
```

### 3. Outcome Feedback
**Signal**: User says "that worked great" or "that didn't work"

**Example**:
```
User: "That fix worked perfectly!"
Action: Update decision outcome to 'success'
Feed back: Reinforce that pattern in future decisions
```

**Capture Pattern**:
```javascript
if (userProvidedOutcome) {
  // Update the decision record
  await updateDecisionOutcome({
    decision_id: lastDecisionId,
    outcome: 'success',
    user_feedback: "That fix worked perfectly!"
  })
}
```

### 4. Task-Specific Patterns
**Signal**: User says "for X tasks, always do Y"

**Example**:
```
User: "For API tests, always check rate limiting"
Action: Save as project-specific testing pattern
Feed back: Include in test plan prompts for API projects
```

**Capture Pattern**:
```javascript
if (userDefinedPattern) {
  await saveToMemory({
    type: 'project',
    pattern: 'API tests must check rate limiting',
    context: 'test strategy',
    app_type: 'api',
    applies_to: ['code-test']
  })
}
```

## Integration Points

### After User Messages
1. **Parse user message** for correction/preference/feedback signals
2. **Classify feedback type** (correction, preference, outcome, pattern)
3. **Save to appropriate memory file** (feedback.md, user.md, project.md)
4. **Link to relevant decision** if applicable

### Before AI Decisions
1. **Load relevant memories** from auto-memory system
2. **Query learning database** for historical patterns
3. **Combine both** into worker/arbiter feedback
4. **Include in prompts** as context

## Memory Structure

### feedback.md - Corrections
```markdown
# Testing Approach

**Rule**: Use real database for integration tests, not mocks

**Why**: Past incident where mocked tests passed but prod migration failed

**How to apply**: In test plan generation, specify real DB for integration tests

**Applies to**: code-test, test strategy
```

### user.md - Preferences
```markdown
# Model Preferences

User prefers:
- opus for code reviews (most thorough)
- sonnet for test generation (good balance)
- Local models for quick iterations
```

### project.md - Task Patterns
```markdown
# API Testing Requirements

For API projects, test plans must include:
- Rate limiting checks
- Auth token validation
- Error response formatting
- Timeout handling

**Why**: Critical for production API reliability

**Applies to**: code-test when app_type=api
```

## Feedback Loop

```
┌──────────────────┐
│  User Interaction│
│  (correction/    │
│   preference/    │
│   feedback)      │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│  Parse & Classify│
│  Feedback Type   │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│ Save to Memory   │
│ + Learning DB    │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│  Load in Next    │
│  AI Decision     │
└──────────────────┘
```

## Implementation Checklist

- ✅ Learning system captures arbiter/worker decisions
- ✅ Workers get historical feedback before proposing
- ✅ Arbiters get patterns before deciding
- 📋 TODO: Parse user messages for feedback signals
- 📋 TODO: Auto-save user corrections to memory
- 📋 TODO: Link memory to learning database
- 📋 TODO: Load memory + learning in all workflows

## Example Integration

```javascript
// In code-test.js, before workers propose:

// 1. Load from learning database
const historicalFeedback = await getWorkerFeedback({
  workflow: 'code-test',
  task_type: 'test_plan',
  worker_model: 'opus'
})

// 2. Load from user memory
const userPreferences = await loadMemory('feedback.md', {
  context: 'testing',
  applies_to: 'code-test'
})

// 3. Combine both
const combinedFeedback = `
${historicalFeedback}

**User Preferences (from past interactions):**
${userPreferences}
`

// 4. Include in worker prompt
const prompt = testPlanPrompt + combinedFeedback
```

## Benefits

**Faster Learning**:
- Learn from one interaction, not 50 decisions
- User corrections immediately improve next decision
- No waiting for statistical patterns

**Personalized**:
- Learns user's specific preferences
- Adapts to project-specific patterns
- Respects user's past corrections

**Transparent**:
- User can see what was learned
- User can review/edit memory files
- Clear link between feedback and behavior

**Cumulative**:
- Learning database: statistical patterns
- Memory system: explicit user preferences
- Combined: best of both worlds

## Privacy

All learning stored locally:
- `~/.claude/learning/` - Decision patterns
- `~/.claude/memory/` - User preferences
- No external services
- User controls all data

## Metrics

Track improvement:
- Correction frequency (should decrease over time)
- User satisfaction signals (explicit feedback)
- Decision alignment with user preferences
- Memory utilization rate

## Next Steps

1. Parse user messages for feedback signals
2. Auto-detect corrections/preferences/outcomes
3. Save to appropriate memory files
4. Load and combine with learning database
5. Measure improvement over time

---

**Key Insight**: Don't just learn from AI decisions - learn from EVERY user interaction. That's where the real signal is.

**Impact**: Massive - turns every correction into permanent learning

**Priority**: Critical - this is the missing piece for true continuous learning
