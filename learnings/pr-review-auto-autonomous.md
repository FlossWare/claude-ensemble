---
name: pr-review-auto-autonomous
description: "Fully autonomous PR review bot that auto-approves/rejects until no PRs left"
metadata:
  type: project
  priority: high
  originSessionId: cd831c80-3852-47b6-8899-f8cba2b22342
---

# PR Review Auto - Autonomous Bot

**Rule**: pr-review-auto is 100% autonomous - reviews all PRs and auto-approves/rejects with NO user interaction

**Why**: User requested "can we have a pr-review-auto that autonomously do pr-review until none are left and automatically accepts/rejects prs/mrs"

**How to apply**: Run `claude run pr-review-auto` and it handles everything automatically

## What It Does

**Fully autonomous PR review bot**:
1. Discovers all open PRs needing review
2. Reviews each with multi-AI consensus (opus/sonnet/haiku)
3. Analyzes breaking changes and impact
4. **Auto-approves** high-quality, safe PRs
5. **Auto-rejects** PRs with breaking changes or issues
6. Runs until all PRs reviewed (max 10 per run, configurable)
7. **Zero user interaction** - completely automated

## Auto-Approval Criteria (ALL must be true)

```javascript
✅ Quality score ≥ 90
✅ AI consensus ≥ 85%
✅ NO breaking changes
✅ ≤ 2 high-risk changes
✅ ≤ 50 files impacted
✅ AI decision = "approve"
```

## Auto-Reject Criteria (ANY triggers rejection)

```javascript
❌ Breaking changes detected
❌ Critical severity issues
❌ Quality score < 60
❌ Risk level = critical
❌ AI decision = "request_changes"
```

## Usage Examples

```bash
# Review all open PRs (auto-approve/reject)
claude run pr-review-auto

# Review max 5 PRs per run
claude run pr-review-auto --max 5

# Require quality ≥ 95 to approve
claude run pr-review-auto --quality 95
```

## Comparison: pr-review vs pr-review-auto

| Feature | pr-review | pr-review-auto |
|---------|-----------|----------------|
| Autonomy | User decides | Fully autonomous |
| Scope | Single PR or loop | All open PRs |
| Interaction | Manual approval | Zero interaction |
| Decision | User-based | Criteria-based |
| Use Case | Interactive | CI/CD, batch |

## Decision Flow

```
1. Discover PRs → 2. Impact Analysis → 3. Multi-AI Review
   ↓
4. Arbiter Decision → 5. Auto-Decision Logic:
   ↓
   • Breaking changes? → REJECT
   • Quality ≥ 90 + no breaking + consensus? → APPROVE
   • AI says request changes? → REJECT
   • Default → COMMENT
   ↓
6. Post + Approve/Reject automatically
```

## Safety Features

1. **Strict criteria**: Conservative thresholds (90+ quality)
2. **Breaking change detection**: Never approves breaking changes
3. **Multi-AI consensus**: 85%+ agreement required
4. **Full transparency**: Every decision documented in PR
5. **Fallback**: When uncertain, just comment (no action)

## Use Cases

- **CI/CD**: Auto-review PRs in pipeline
- **Scheduled**: Cron job for daily batch reviews
- **Manual**: Bulk-process all open PRs
- **Conservative**: High quality gates for critical repos

## Configuration

Edit `CONFIG` in `pr-review-auto.js`:

```javascript
const CONFIG = {
  workers: ['opus', 'sonnet', 'haiku'],
  arbiterModel: 'opus',
  
  autoApprove: {
    minQualityScore: 90,
    minConsensus: 85,
    maxBreakingChanges: 0,
    maxHighRiskChanges: 2,
  },
  
  autoReject: {
    hasBreakingChanges: true,
    hasCriticalIssues: true,
    lowQualityScore: 60,
  },
  
  maxPRsPerRun: 10,
}
```

## Files

- **pr-review-auto.js**: Main workflow (650 lines)
- **pr-review-auto.md**: Complete documentation

## Related

- [[pr-impact-analysis]] - Breaking change detection
- [[ai-attribution-tracking]] - Full AI transparency
- [[arbiter-worker-pattern]] - Multi-AI consensus
- [[automation-preferences]] - User prefers 100% automation
