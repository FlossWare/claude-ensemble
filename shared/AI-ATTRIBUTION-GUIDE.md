# AI Attribution & Transparency Guide

Complete guide to implementing AI attribution across workflows, skills, and commands.

## Overview

AI attribution provides **full transparency** into multi-AI decision-making by tracking:
- **Worker AIs**: Which models proposed what
- **Arbiter decisions**: How proposals were accepted/rejected  
- **Rejected proposals**: What was considered but declined
- **Consensus metrics**: How many models agreed

## Two Attribution Patterns

### Pattern 1: Arbiter-Based (Best-of-N)

**Use when**: Arbiter selects the single best proposal from multiple models

**Used in**: PR reviews, code improvements, complex decision-making

**Example**:
```javascript
// Multiple models review independently
const reviews = {
  opus: await agent('Review PR', {model: 'opus', schema}),
  sonnet: await agent('Review PR', {model: 'sonnet', schema}),
  haiku: await agent('Review PR', {model: 'haiku', schema})
}

// Arbiter chooses best
const arbiterDecision = await agent('Pick best review', {
  model: 'opus',
  schema: arbiterSchema
})

// Format attribution
const attribution = formatAIAttribution(reviews, arbiterDecision)
```

### Pattern 2: Threshold-Based (Confidence Filtering)

**Use when**: Accept all proposals above a confidence threshold

**Used in**: Code review, security scanning, issue detection

**Example**:
```javascript
// Multiple models review independently
const allProposals = []
const models = ['opus', 'sonnet', 'haiku']

const reviews = await parallel(models.map(model =>
  () => agent('Find bugs', {model, schema})
))

// Tag proposals
reviews.forEach((review, idx) => {
  review.issues?.forEach(issue => {
    allProposals.push({
      model: models[idx],
      finding: issue,
      accepted: issue.confidence >= THRESHOLD,
      rejection_reason: issue.confidence < THRESHOLD 
        ? `Confidence ${issue.confidence}% below threshold ${THRESHOLD}%`
        : null
    })
  })
})

// Create attribution for each accepted finding
allProposals.filter(p => p.accepted).forEach(proposal => {
  const attribution = createThresholdAttribution({
    workerModel: proposal.model,
    confidence: proposal.finding.confidence,
    reasoning: proposal.finding.description,
    threshold: THRESHOLD,
    allProposals: allProposals, // Include rejected for comparison
    totalModels: models.length
  })

  // Add to findings
  findings.push({
    ...proposal.finding,
    ai_attribution: attribution
  })
})
```

## Available Functions

### Arbiter-Based Functions

```javascript
// From shared/ai-attribution.js
import {
  formatAIAttribution,      // Full markdown with arbiter decision
  formatShortAttribution,    // One-line summary
  formatInlineComment,       // Inline code comment format
  formatPRComment           // PR review comment format
} from './shared/ai-attribution.js'
```

### Threshold-Based Functions

```javascript
// From shared/ai-attribution.js
import {
  createThresholdAttribution,          // Create attribution object
  formatThresholdAttributionMarkdown,  // Full markdown format
  formatThresholdAttributionSimple     // One-line summary
} from './shared/ai-attribution.js'
```

### For Workflows (No Imports)

Copy the inline version from `shared/ai-attribution.js`:

```javascript
// Copy this into your workflow file
function createThresholdAttribution({workerModel, confidence, reasoning, threshold = 70, allProposals = [], totalModels = 1}) {
  // ... (see inline code in ai-attribution.js)
}

function formatThresholdAttributionMarkdown(attribution, options = {}) {
  // ... (see inline code in ai-attribution.js)
}
```

## Output Examples

### Threshold-Based Attribution

```markdown
## 🤖 AI Attribution

### Worker AI (Finder)
- **Model**: opus
- **Confidence**: 85%
- **Reasoning**: SQL injection vulnerability in user input handling

### Arbiter Decision
- **Decision**: accepted
- **Reason**: Confidence 85% meets threshold 70%
- **Threshold**: 70%
- **Timestamp**: 2026-06-04T18:22:15.123Z

### Multi-Model Consensus
- **Models Reviewed**: 3
- **Models Agreed**: 1 / 3

### Rejected Proposals

The following proposals were reviewed but declined:

1. **sonnet** (Confidence: 65%)
   - **Reason for Rejection**: Confidence 65% below threshold 70%
   - **Description**: Potential SQL injection in query builder

2. **haiku** (Confidence: 50%)
   - **Reason for Rejection**: Confidence 50% below threshold 70%
   - **Description**: Possible vulnerability in database calls
```

### Arbiter-Based Attribution

```markdown
## 🤖 AI Attribution

**Multi-Model Consensus Review**

### Reviewer Models
- **Opus**: Real Issue (Confidence: 92%)
- **Sonnet**: Real Issue (Confidence: 88%)
- **Haiku**: False Positive (Confidence: 45%)

### Arbiter Decision
- **Final Decision**: real_issue
- **Consensus Score**: 67% agreement
- **Best Analysis**: opus
- **Reasoning**: SQL injection confirmed in user input validation

### Rejected Models
- **haiku**: Low confidence (45%) and contradicts majority consensus
```

## Integration Guide

### Step 1: Choose Pattern

- **Arbiter-based**: When you need the single best answer
- **Threshold-based**: When you want all high-confidence findings

### Step 2: Collect Proposals

```javascript
// Run models in parallel
const models = ['opus', 'sonnet', 'haiku']
const reviews = await parallel(models.map(model =>
  () => agent(prompt, {model, schema})
))
```

### Step 3: Create Attribution

**For threshold-based**:
```javascript
const attribution = createThresholdAttribution({
  workerModel: 'opus',
  confidence: 85,
  reasoning: finding.description,
  threshold: 70,
  allProposals: taggedProposals,
  totalModels: 3
})
```

**For arbiter-based**:
```javascript
const arbiterDecision = await agent('Pick best', {schema})
const attribution = formatAIAttribution(reviews, arbiterDecision)
```

### Step 4: Add to Issues/Comments

```javascript
const markdown = formatThresholdAttributionMarkdown(attribution)

// Add to GitHub issue
await agent(`
Execute:
gh issue create --title "..." --body "..." 
gh issue comment \${issue_number} --body "${markdown}"
`)
```

## Data Structure

### Threshold-Based Attribution Object

```javascript
{
  total_models_reviewed: 3,
  
  worker_ai: {
    model: 'opus',
    confidence: 85,
    reasoning: 'SQL injection vulnerability...'
  },
  
  arbiter: {
    decision: 'accepted',
    reason: 'Confidence 85% meets threshold 70%',
    threshold: 70,
    timestamp: '2026-06-04T18:22:15.123Z'
  },
  
  rejected_proposals: [
    {
      model: 'sonnet',
      confidence: 65,
      reason: 'Confidence 65% below threshold 70%',
      description: 'Potential SQL injection...'
    }
  ],
  
  consensus: {
    models_agreed: 1,
    models_total: 3
  }
}
```

## Best Practices

1. **Always capture ALL proposals** - not just accepted ones
2. **Include rejection reasons** - explain why proposals were declined
3. **Track timestamps** - know when decisions were made
4. **Show consensus stats** - how many models agreed?
5. **Link to source** - which commit/file/line?
6. **Version the schema** - AI attribution evolves

## Usage in Workflows

### code-review Workflow

Uses threshold-based attribution:
- 3 models review each commit (rotating: Opus, Sonnet, Haiku)
- Findings above 70% confidence → accepted
- Below 70% → rejected with reason
- All captured in `ai_attribution` object

### pr-review Workflow

Uses arbiter-based attribution:
- 3-4 models review PR independently
- Arbiter (Opus) selects best review
- Shows all model opinions + arbiter reasoning

### code-solve Workflow

Uses threshold-based attribution:
- Multiple models propose fixes
- Confidence threshold filters proposals
- Attribution shows accepted fix + rejected alternatives

## Migration Guide

### From No Attribution → Threshold-Based

**Before**:
```javascript
const issues = await agent('Find bugs', {schema})
allFindings.push(...issues)
```

**After**:
```javascript
const models = ['opus', 'sonnet', 'haiku']
const reviews = await parallel(models.map(m => 
  () => agent('Find bugs', {model: m, schema})
))

// Tag proposals
const proposals = []
reviews.forEach((review, idx) => {
  review.issues?.forEach(issue => {
    proposals.push({
      model: models[idx],
      finding: issue,
      accepted: issue.confidence >= THRESHOLD,
      rejection_reason: issue.confidence < THRESHOLD 
        ? `Below threshold` : null
    })
  })
})

// Add attribution
proposals.filter(p => p.accepted).forEach(p => {
  allFindings.push({
    ...p.finding,
    ai_attribution: createThresholdAttribution({
      workerModel: p.model,
      confidence: p.finding.confidence,
      reasoning: p.finding.description,
      threshold: THRESHOLD,
      allProposals: proposals,
      totalModels: models.length
    })
  })
})
```

## Sharing Across Projects

### Option 1: Import (for skills/commands)

```javascript
import { formatThresholdAttributionMarkdown } from '../shared/ai-attribution.js'
```

### Option 2: Inline (for workflows)

Copy the inline code block from `shared/ai-attribution.js`

### Option 3: Reference File

Point to the canonical implementation:
```javascript
// See ~/.claude/repos/claude-global-skills/shared/ai-attribution.js
// for the reference implementation
```

## See Also

- `shared/ai-attribution.js` - Reference implementation
- `code-review.js` - Example of threshold-based attribution
- `pr-review.js` - Example of arbiter-based attribution
- `consensus-engine.js` - Advanced consensus algorithms

---

**Status**: Production ready ✅  
**Version**: 2.0 (threshold-based + arbiter-based)  
**Last Updated**: 2026-06-04
