---
name: ai-attribution-tracking
description: Full AI attribution tracking in code review - worker models, arbiter decisions, rejected proposals
metadata: 
  node_type: memory
  type: project
  originSessionId: current
---

# AI Attribution Tracking in Code Review

**Rule**: All code review findings must include **complete AI attribution** showing which models proposed what, which were accepted/rejected, and why.

**Why**: Provides full transparency into the AI decision-making process. Users can see not just what was found, but how consensus was reached and what alternative proposals were considered.

**How to apply**: Every finding stored in `allFindings` includes an `ai_attribution` object with full traceability.

## Attribution Structure

Each finding includes:

```javascript
{
  // Standard finding data
  severity: 'critical',
  description: '...',
  file: 'foo.js',
  confidence: 85,
  
  // Worker AI that found it
  worker_model: 'opus',
  
  // Full AI Attribution
  ai_attribution: {
    total_models_reviewed: 3,
    
    // The AI that found this issue
    worker_ai: {
      model: 'opus',
      confidence: 85,
      reasoning: 'SQL injection vulnerability...'
    },
    
    // Arbiter's decision
    arbiter: {
      decision: 'accepted',
      reason: 'Confidence 85% meets threshold 70%',
      timestamp: '2026-06-04T...'
    },
    
    // Models that disagreed or had lower confidence
    rejected_proposals: [
      {
        model: 'sonnet',
        confidence: 65,
        reason: 'Confidence 65% below threshold 70%',
        description: 'Potential SQL injection...'
      },
      {
        model: 'haiku',
        confidence: 50,
        reason: 'Confidence 50% below threshold 70%',
        description: 'Possible vulnerability...'
      }
    ],
    
    // Consensus stats
    consensus: {
      models_agreed: 1,
      models_total: 3
    }
  }
}
```

## GitHub Issue Format

Issues created include all attribution details:

```markdown
## 🤖 AI Attribution

### Worker AI (Finder)
- **Model**: opus
- **Confidence**: 85%
- **Reasoning**: SQL injection vulnerability in user input handling

### Arbiter Decision
- **Decision**: accepted
- **Reason**: Confidence 85% meets threshold 70%
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

## Benefits

✅ **Full transparency** - see exactly which AIs proposed what  
✅ **Traceable decisions** - understand why findings were accepted/rejected  
✅ **Quality insights** - see consensus levels and model agreement  
✅ **Audit trail** - complete record of AI decision-making process  
✅ **Learning tool** - understand how different models evaluate code  

## Implementation

### Phase 1: Multi-Model Review
Three models (Opus, Sonnet, Haiku) review each commit in rotation:
- Each model finds issues independently
- All proposals captured (accepted and rejected)

### Phase 2: Arbiter Decision
Confidence threshold (default 70%) determines acceptance:
- Above threshold → accepted
- Below threshold → rejected with reason

### Phase 3: Consensus Tracking
Track which models agreed:
- Total models reviewed
- Models that found the same issue
- Models that missed it or disagreed

### Phase 4: Issue Creation
GitHub/GitLab issues include:
- Primary finding from worker AI
- Arbiter's acceptance reasoning
- All rejected proposals with reasons
- Consensus statistics

## Reusable System

**Location**: `~/.claude/repos/claude-global-skills/shared/ai-attribution.js`

**Documentation**: `~/.claude/repos/claude-global-skills/shared/AI-ATTRIBUTION-GUIDE.md`

**Two patterns available**:
1. **Arbiter-based**: Arbiter selects best proposal (PR reviews)
2. **Threshold-based**: Confidence filtering (code review, security scans)

**Usage**:
- **Skills/Commands**: `import { ... } from './shared/ai-attribution.js'`
- **Workflows**: Copy inline functions (can't use imports with scriptPath)
- **Any project**: Reference canonical implementation

## Integration

To add AI attribution to any workflow:

1. Choose pattern (arbiter vs threshold)
2. Collect proposals from multiple models
3. Tag as accepted/rejected
4. Call `createThresholdAttribution()` or `formatAIAttribution()`
5. Add markdown to issues/comments

See `AI-ATTRIBUTION-GUIDE.md` for complete examples.

## Related Memories
- [[code-skills-autonomous]] - Autonomous workflow patterns
- [[workflow-registration-filter]] - Workflow registration rules

---

**Date**: 2026-06-04
**Context**: Created reusable AI attribution system for all workflows
**Status**: Production ready ✅
**Location**: `shared/ai-attribution.js` + `shared/AI-ATTRIBUTION-GUIDE.md`
