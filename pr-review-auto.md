# pr-review-auto - Autonomous PR Review Bot

**Fully automated PR review system that runs until no PRs are left**

## Overview

`pr-review-auto` is a **fully autonomous** PR review bot that:
- Discovers open PRs automatically
- Reviews each with multi-AI consensus
- Analyzes breaking changes and impact
- **Auto-approves** high-quality, safe PRs
- **Auto-rejects** PRs with breaking changes or critical issues
- Runs continuously until all PRs are reviewed
- **NO manual intervention required**

## Usage

### Basic (review all PRs)
```bash
claude run pr-review-auto
```

### With options
```bash
# Review max 5 PRs per run
claude run pr-review-auto --max 5

# Require quality ≥ 95 to auto-approve
claude run pr-review-auto --quality 95

# Both
claude run pr-review-auto --max 10 --quality 92
```

## How It Works

### Workflow Phases

1. **Setup**: Detect platform (GitHub/GitLab), sync with remote
2. **Discover PRs**: Find all open PRs needing review
3. **Fetch PR**: Get PR details, diff, changed files
4. **Impact Analysis**: Detect breaking changes, risk level
5. **Multi-Model Review**: Opus + Sonnet + Haiku review
6. **Arbiter Decision**: Opus makes final consensus decision
7. **Auto-Decision**: Apply approval criteria
8. **Post Results**: Comment + approve/reject automatically

### Auto-Approval Criteria

A PR is **auto-approved** when ALL conditions met:
- ✅ Quality score ≥ 90 (configurable)
- ✅ AI consensus ≥ 85%
- ✅ NO breaking changes
- ✅ ≤ 2 high-risk changes
- ✅ ≤ 50 files impacted
- ✅ AI decision = "approve"

### Auto-Reject Criteria

A PR is **auto-rejected** when ANY condition met:
- ❌ Breaking changes detected
- ❌ Critical severity issues found
- ❌ Quality score < 60
- ❌ Risk level = critical
- ❌ AI consensus = "request_changes"

### Default Behavior (COMMENT)

If neither approve nor reject criteria met:
- 💬 Post review comment
- 💬 No approval or rejection
- 💬 Provide feedback for manual review

## Configuration

Edit `CONFIG` object in `pr-review-auto.js`:

```javascript
const CONFIG = {
  workers: ['opus', 'sonnet', 'haiku'],
  arbiterModel: 'opus',

  autoApprove: {
    minQualityScore: 90,              // Require 90+ to approve
    minConsensus: 85,                 // 85%+ agreement
    maxBreakingChanges: 0,            // NO breaking changes
    maxHighRiskChanges: 2,            // Max 2 high-risk
    maxImpactedFiles: 50,             // Max 50 files
  },

  autoReject: {
    hasBreakingChanges: true,         // Reject if breaking
    hasCriticalIssues: true,          // Reject if critical
    lowQualityScore: 60,              // Reject if < 60
    highRiskLevel: 'critical',        // Reject if critical
  },

  maxPRsPerRun: 10,                   // Review 10/run
  stopWhenEmpty: true,                // Stop when done
}
```

## Example Output

```
═══════════════════════════════════════════════════════════
🤖 AUTONOMOUS PR REVIEW BOT
═══════════════════════════════════════════════════════════
Workers: opus, sonnet, haiku
Arbiter: opus
Auto-Approve: Quality ≥ 90, No breaking changes
Auto-Reject: Breaking changes, Critical issues, Quality < 60
Max PRs/run: 10
═══════════════════════════════════════════════════════════

🔧 Detecting platform...
✅ Platform: github (gh)

🔄 Syncing with remote...
✅ Up to date

📋 Finding open PRs needing review...
📊 Found 15 open PRs, 12 need review
🎯 Reviewing 10 PRs this run

═══════════════════════════════════════════════════════════
📝 PR #123
═══════════════════════════════════════════════════════════
📥 Fetching PR #123...
✅ "Add user authentication" by alice
   feature/auth → main
📊 5 files, +234/-12

🎯 Analyzing impact...
✅ Impact: low
   Breaking: 0
   High-risk: 0
   Impacted files: 8

🤖 Running 3-model review...
✅ 3 models completed review

⚖️ Arbiter deciding...
✅ Decision: approve
   Consensus: 95%

🤖 Determining auto-action...
🎯 Auto-Action: APPROVE
   Reasoning: High quality (92/100), 95% consensus, low risk

📝 Posting review...
✅ Comment posted
👍 Auto-approving PR...
✅ PR #123 APPROVED

═══════════════════════════════════════════════════════════
📝 PR #124
═══════════════════════════════════════════════════════════
📥 Fetching PR #124...
✅ "Remove old API endpoint" by bob
   refactor/api → main
📊 3 files, +45/-150

🎯 Analyzing impact...
✅ Impact: high
   Breaking: 2
   High-risk: 1
   Impacted files: 25

🤖 Running 3-model review...
✅ 3 models completed review

⚖️ Arbiter deciding...
✅ Decision: request_changes
   Consensus: 87%

🤖 Determining auto-action...
🎯 Auto-Action: REJECT
   Reasoning: Breaking changes detected: removeEndpoint, UserAPI

📝 Posting review...
✅ Comment posted
⚠️  Requesting changes...
✅ PR #124 REJECTED (changes requested)

═══════════════════════════════════════════════════════════
📊 AUTONOMOUS REVIEW SUMMARY
═══════════════════════════════════════════════════════════
Total PRs reviewed: 10
Auto-approved: 6
Changes requested: 3
Comment-only: 1

✅ PR #123: Add user authentication
   Action: APPROVE, Quality: 92/100, Risk: low
⚠️ PR #124: Remove old API endpoint
   Action: REJECT, Quality: 75/100, Risk: high
💬 PR #125: Update documentation
   Action: COMMENT, Quality: 85/100, Risk: low
...

ℹ️  2 more PRs remain - run again to continue
```

## PR Comment Format

```markdown
## 🤖 AUTONOMOUS PR REVIEW

**Quality Score**: 92/100
**AI Consensus**: approve (95% agreement)
**Impact Risk**: low
**Auto-Decision**: APPROVE

### Decision Reasoning
High quality (92/100), 95% consensus, low risk

### Impact Analysis
- **Breaking Changes**: 0
- **High-Risk Changes**: 0
- **Files Impacted**: 8
- **Missing Tests**: 1

### AI Reviews (3 models)

**opus** - approve (95/100, 90% confidence)
- Issues: 0 (0 critical)
  - ✅ Clean implementation
  - ✅ Good test coverage

**sonnet** - approve (90/100, 85% confidence)
- Issues: 1 (0 critical)
  - medium: Consider adding error handling for edge case
  - ✅ Well documented

**haiku** - approve (88/100, 80% confidence)
- Issues: 2 (0 critical)
  - low: Minor style inconsistency
  - ✅ Follows best practices

### Arbiter Decision (opus)
Strong consensus for approval. All models agree on high quality.
Minor suggestions can be addressed in follow-up PRs.

---

*Automated review by pr-review-auto workflow*
*Approval Criteria: Quality ≥ 90, Consensus ≥ 85%, No breaking changes*
```

## Decision Logic Flow

```
┌─────────────────┐
│   Fetch PR      │
│   + Diff        │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Impact Analysis │
│ (breaking/risk) │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Multi-AI Review │
│ (opus/sonnet/   │
│  haiku)         │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Arbiter Decision│
│ (opus consensus)│
└────────┬────────┘
         │
         v
┌─────────────────────────────────┐
│ Auto-Decision Logic             │
├─────────────────────────────────┤
│ IF breaking_changes > 0         │
│   → REJECT                      │
│                                 │
│ ELSE IF risk = critical         │
│   → REJECT                      │
│                                 │
│ ELSE IF quality < 60            │
│   → REJECT                      │
│                                 │
│ ELSE IF has critical issues     │
│   → REJECT                      │
│                                 │
│ ELSE IF quality ≥ 90 AND        │
│         consensus ≥ 85% AND     │
│         no breaking changes AND │
│         low/medium risk         │
│   → APPROVE                     │
│                                 │
│ ELSE IF AI says request_changes │
│   → REJECT                      │
│                                 │
│ ELSE                            │
│   → COMMENT (manual review)     │
└────────┬────────────────────────┘
         │
         v
┌─────────────────┐
│ Post Comment    │
│ + Approve/      │
│   Reject        │
└─────────────────┘
```

## Use Cases

### 1. Continuous Integration
Run as part of CI pipeline to auto-review all PRs:
```bash
# In CI config
- name: Auto-review PRs
  run: claude run pr-review-auto --max 20
```

### 2. Scheduled Reviews
Cron job to review PRs daily:
```bash
# In crontab
0 9 * * * cd /repo && claude run pr-review-auto
```

### 3. Manual Batch Review
Review all open PRs in one go:
```bash
claude run pr-review-auto
# Runs until all PRs reviewed
```

### 4. Conservative Mode
Higher quality threshold:
```bash
claude run pr-review-auto --quality 95
# Only approves exceptional PRs
```

## Comparison with pr-review

| Feature | pr-review | pr-review-auto |
|---------|-----------|----------------|
| **Autonomy** | User decides approve/reject | Fully autonomous |
| **Scope** | Single PR or loop | All open PRs |
| **Interaction** | Shows summary, waits for user | Zero interaction |
| **Decision** | Manual (based on AI + impact) | Auto (criteria-based) |
| **Use Case** | Interactive review | CI/CD, batch processing |
| **Safety** | User oversight | Strict criteria |

## Safety Features

1. **Strict Criteria**: Conservative auto-approve thresholds
2. **Breaking Change Detection**: Never approves breaking changes
3. **Multi-AI Consensus**: Requires 85%+ agreement
4. **Impact Analysis**: Risk assessment before approval
5. **Quality Gate**: 90+ quality score required
6. **Fallback to Comment**: When uncertain, just comment
7. **Full Transparency**: Every decision documented

## Limitations

1. **No Human Judgment**: Cannot assess business logic appropriateness
2. **False Positives**: May request changes on safe PRs if criteria strict
3. **False Negatives**: May approve PRs with subtle issues
4. **Rate Limits**: GitHub/GitLab API rate limits apply
5. **Context Window**: Large PRs truncated in review

## Best Practices

1. **Start Conservative**: Use default quality threshold (90)
2. **Monitor Results**: Check auto-approved PRs initially
3. **Tune Thresholds**: Adjust based on your team's needs
4. **Manual Override**: Can manually review comment-only PRs
5. **Regular Audits**: Spot-check auto-approved PRs
6. **Team Agreement**: Ensure team comfortable with automation

## Advanced Configuration

### Custom Workers
```javascript
workers: ['opus', 'sonnet', 'haiku', 'gemini']  // Add Gemini
```

### Stricter Approval
```javascript
autoApprove: {
  minQualityScore: 95,              // Higher threshold
  minConsensus: 95,                 // Require near-unanimous
  maxBreakingChanges: 0,
  maxHighRiskChanges: 0,            // Zero high-risk
  maxImpactedFiles: 10,             // Fewer files
  requireAllApprove: true,          // ALL models must approve
}
```

### More Lenient
```javascript
autoApprove: {
  minQualityScore: 80,              // Lower threshold
  minConsensus: 75,                 // Less agreement needed
  maxBreakingChanges: 0,            // Still no breaking
  maxHighRiskChanges: 5,            // More high-risk OK
  maxImpactedFiles: 100,            // More files OK
}
```

## Metrics

Track effectiveness:
- **Approval Rate**: % of PRs auto-approved
- **False Approvals**: PRs approved but later reverted
- **False Rejections**: Safe PRs rejected
- **Time Saved**: Hours not spent on manual review
- **Quality Impact**: Bug rate in approved PRs

## Future Enhancements

- [ ] Machine learning from approval/rejection outcomes
- [ ] Custom approval rules per repo/team
- [ ] Integration with external test results
- [ ] Slack/email notifications on decisions
- [ ] Weekly summary reports
- [ ] Auto-merge after approval (with safeguards)

## Troubleshooting

### No PRs reviewed
- Check: Are there open PRs?
- Check: Do PRs have "🤖 AUTONOMOUS PR REVIEW" comments already?
- Check: Are they draft PRs? (auto-skipped)

### Too many auto-approvals
- Increase `minQualityScore` (e.g., 95)
- Increase `minConsensus` (e.g., 95)
- Decrease `maxHighRiskChanges` (e.g., 0)

### Too many rejections
- Check if breaking changes common in your PRs
- Lower `minQualityScore` (e.g., 85)
- Adjust `maxImpactedFiles` higher

### Rate limit errors
- Reduce `maxPRsPerRun`
- Add delays between API calls
- Use authenticated API tokens

## Security Considerations

1. **Auto-approval risk**: Only use in repos with good test coverage
2. **Access control**: Ensure bot has appropriate permissions
3. **Audit trail**: All decisions logged in PR comments
4. **Override capability**: Humans can always override bot decisions
5. **Sensitive changes**: Consider requiring manual review for auth/security

## Contributing

To improve pr-review-auto:
1. Test on your repos
2. Tune thresholds for your team
3. Report false positives/negatives
4. Suggest new criteria
5. Add support for more platforms

---

**Status**: ✅ Ready for production use
**Autonomy Level**: 100% (zero user interaction)
**Safety**: High (conservative criteria, full transparency)
