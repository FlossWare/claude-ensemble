---
name: ai-transparency-usage
description: "When user says \"ai-transparency\", use the ai-attribution module in chat or issue comments"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fe686aff-3d08-4a37-bf54-55ec516bd609
---

# AI Transparency Usage Directive

**Rule**: When the user says "ai-transparency", use the `shared/ai-attribution.js` module to provide full attribution.

**Why**: The user wants complete visibility into which AI models made what decisions, why alternatives were rejected, and consensus metrics.

**How to apply**: Apply in two contexts:

## Context 1: In Chat (Conversational)

When user wants to see AI attribution in the conversation, display it using the formatting functions:

```javascript
import { 
  formatThresholdAttributionMarkdown,
  formatAIAttribution 
} from './shared/ai-attribution.js'

// Show in chat
log(formatThresholdAttributionMarkdown(attribution))
```

**Display includes**:
- Worker AI that proposed the solution
- Confidence level
- Arbiter decision and reasoning
- Rejected proposals with reasons
- Consensus metrics (e.g., "2/3 models agree")

## Context 2: In Issue Comments (GitHub/GitLab)

When creating or commenting on issues, include the full attribution markdown:

```javascript
const attribution = createThresholdAttribution({
  workerModel: 'opus',
  confidence: 85,
  reasoning: finding.description,
  threshold: 70,
  allProposals: proposals,
  totalModels: 3
})

const markdown = formatThresholdAttributionMarkdown(attribution)

// Add to issue body or comment
gh issue create --title "..." --body "...\n\n${markdown}"
gh issue comment ${num} --body "${markdown}"
```

**Issue comment includes**:
- 🤖 AI Attribution header
- Worker AI (Finder) section
- Arbiter Decision section
- Multi-Model Consensus section
- Rejected Proposals section (with reasons)

## Implementation

**Available patterns**:
1. **Arbiter-based** - Multiple models propose, arbiter selects best (PR reviews)
2. **Threshold-based** - Multiple models propose, confidence threshold filters (code review, bug detection)

**Key principle**: ALWAYS capture ALL proposals, not just accepted ones. Users want to see what was considered and rejected.

## Examples

### Example 1: Code Review Finding in Chat
```
Found security issue: SQL injection vulnerability

🤖 AI Attribution:
- Worker: Opus (85% confidence)
- Decision: Accepted (meets 70% threshold)
- Consensus: 2/3 models agree
- Rejected: Sonnet (65%, below threshold), Haiku (50%, below threshold)
```

### Example 2: GitHub Issue with Attribution
```markdown
## Security Issue: SQL Injection in User Input

... issue description ...

## 🤖 AI Attribution

### Worker AI (Finder)
- **Model**: opus
- **Confidence**: 85%
- **Reasoning**: SQL injection vulnerability in user input handling

### Arbiter Decision
- **Decision**: accepted
- **Reason**: Confidence 85% meets threshold 70%

### Multi-Model Consensus
- **Models Reviewed**: 3
- **Models Agreed**: 2 / 3

### Rejected Proposals
1. **sonnet** (Confidence: 65%)
   - Reason: Confidence below threshold 70%
```

## Default Behavior

When user says "ai-transparency":
- ✅ **Always** show which models were involved
- ✅ **Always** show confidence levels
- ✅ **Always** show rejected proposals with reasons
- ✅ **Always** show consensus metrics
- ❌ **Never** hide which AI made the decision
- ❌ **Never** omit rejected alternatives

## Related

- [[ai-attribution-tracking]] - Full AI attribution tracking pattern
- [[arbiter-worker-pattern]] - Arbiter/worker multi-AI pattern
- Module: `~/.claude/repos/claude-global-skills/shared/ai-attribution.js`
- Guide: `~/.claude/repos/claude-global-skills/shared/AI-ATTRIBUTION-GUIDE.md`

---

**User directive**: "from now on, when I say ai-transparency, that is what i want you to do...if I want to know it in chat do it, if I want it in issue comments do it"

**Date**: 2026-06-05
