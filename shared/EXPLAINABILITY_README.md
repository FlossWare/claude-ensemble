# Explainability Reporter for Multi-AI Consensus

**Created:** 2026-06-28  
**Purpose:** Show why a specific model won consensus by breaking down voting weights and decision rationale

## Overview

The explainability reporter provides transparency into weighted voting decisions by generating detailed reports that explain:

1. **Weight Breakdown** - How each model's final weight was calculated (tier × capability × confidence × history × calibration)
2. **Agreement Analysis** - Which models agreed/disagreed and why
3. **Calibration Adjustments** - Penalties applied for confidence/accuracy mismatch
4. **Winner Selection** - Rationale for why the winner was selected

## Files

- **`explainability-reporter.cjs`** - Core explainability module
- **`weighted-voting-with-explain.cjs`** - Wrapper that adds explainability to weighted voting
- **`test-explainability-reporter.cjs`** - Unit tests (10 scenarios)
- **`test-explainability-examples.cjs`** - Example scenarios demonstrating usage

## Quick Start

### Basic Usage

```javascript
const { runWeightedVotingWithExplain } = require('./weighted-voting-with-explain.cjs');

const result = await runWeightedVotingWithExplain(votes, 'code_review', {
  explain: true,
  explainFormat: 'markdown',  // or 'json', 'both'
  explainOutputPath: '/tmp/explain-report.md',
});

console.log(result.explainability.markdown);
```

### Integration with Existing Workflows

```javascript
const { explain } = require('./explainability-reporter.cjs');

// After running weighted voting
const votingResult = await runWeightedVoting(votes, 'security_audit', options);

// Generate explainability report
const explainResult = await explain(votingResult.voting_result, {
  format: 'markdown',
  outputPath: '/tmp/security-audit-explainability.md',
  workflowExecutionId: 'wf-123',
});
```

## Output Formats

### Markdown (Human-Readable)

Generated reports include:

- **Summary** - Winning answer, consensus level, total weight
- **Agreement Analysis** - Majority coalition vs minority opinions
- **Weight Breakdown** - Component-by-component weight calculation for each vote
- **Calibration Adjustments** - Penalties applied to "lying" models
- **Winner Selection Rationale** - Explanation of why winner was chosen
- **Metadata** - Task type, vote counts, BFT status

### JSON (Machine-Readable)

Same structure as Markdown, but in JSON format for programmatic access:

```json
{
  "status": "success",
  "summary": {
    "winning_answer": "LGTM",
    "consensus_level": "strong",
    "consensus_strength": "90.0%",
    "total_weight": "4.500",
    "vote_count": 5
  },
  "weight_breakdown": { ... },
  "agreement_analysis": { ... },
  "calibration_adjustments": { ... },
  "winner_selection": { ... }
}
```

## Example Scenarios

Run the example scenarios to see reports for:

1. **Strong Consensus** (90% agreement)
2. **Controversial Decision** (52% vs 48%)
3. **Outlier Filtering** (BFT-MAD excluded faulty models)

```bash
node shared/test-explainability-examples.cjs
```

Reports written to:
- `/tmp/explainability-scenario1-strong-consensus.md`
- `/tmp/explainability-scenario2-controversial.md`
- `/tmp/explainability-scenario3-outliers.md`

## Testing

Run unit tests to verify all functionality:

```bash
node shared/test-explainability-reporter.cjs
```

**Test Coverage:**
- Weight breakdown calculation
- Weight breakdown with calibration penalty
- Agreement analysis (strong consensus)
- Agreement analysis (controversial)
- Winner selection rationale (basic)
- Winner selection rationale (BFT outliers)
- Report generation (full)
- Markdown formatting
- JSON formatting
- Error handling

All tests pass (10/10).

## API Reference

### Core Functions

#### `explain(votingResult, options)`

Generate comprehensive explainability report.

**Parameters:**
- `votingResult` - Result from weighted voting
- `options.format` - Output format: 'json', 'markdown', 'both' (default: 'json')
- `options.outputPath` - Optional file path to write report
- `options.workflowExecutionId` - Workflow ID for PostgreSQL storage
- `options.votingOptions` - Original voting options (for context)

**Returns:** `{ report, markdown?, json?, file_path? }`

#### `generateReport(votingResult, options)`

Generate explainability report object (no formatting).

**Returns:** Report object with summary, weight breakdown, agreement analysis, etc.

#### `formatAsMarkdown(report)`

Format report as Markdown string.

#### `formatAsJSON(report)`

Format report as JSON string.

### Helper Functions

#### `generateWeightBreakdown(vote)`

Generate weight breakdown for a single vote.

#### `analyzeAgreement(votingResult)`

Analyze which models agreed/disagreed.

#### `explainWinnerSelection(votingResult, options)`

Explain why the winner was selected.

## Storage

Explainability reports can be stored in PostgreSQL for long-term analysis:

```sql
CREATE TABLE workflow.explainability_reports (
  id SERIAL PRIMARY KEY,
  workflow_execution_id TEXT NOT NULL,
  voting_result_id INTEGER REFERENCES workflow.weighted_votes(id),
  report JSONB NOT NULL,
  format TEXT DEFAULT 'json',
  created_at TIMESTAMP DEFAULT NOW()
);
```

Storage is automatic when `workflowExecutionId` is provided:

```javascript
await explain(votingResult, {
  workflowExecutionId: 'wf-123',  // Auto-stores to PostgreSQL
});
```

## Integration Points

### With Weighted Voting

The explainability reporter is designed to work seamlessly with the weighted voting system:

```javascript
const { runWeightedVotingWithExplain } = require('./weighted-voting-with-explain.cjs');

const result = await runWeightedVotingWithExplain(votes, taskType, {
  explain: true,
  explainFormat: 'both',
});

// Access both voting result and explainability
console.log(result.voting_result);
console.log(result.explainability);
```

### With Disagreement Detection

Combine with disagreement detection for human review workflows:

```javascript
const result = await runWeightedVotingWithExplain(votes, taskType, {
  withDisagreementDetection: true,
  explain: true,
  context: {
    workflow_execution_id: 'wf-123',
    workflow_name: 'deep-research',
    task_description: 'Analyze firmware security',
  },
});

if (result.needs_human_review) {
  console.log('High disagreement detected!');
  console.log('Explainability report:', result.explainability.file_path);
}
```

## Example Report Structure

```markdown
# Multi-AI Consensus Explainability Report

## Summary
- Winning Answer: "LGTM - code looks good"
- Consensus Level: strong (90.0%)
- Total Weight: 4.500
- Supporting Votes: 5

## Agreement Analysis
**Consensus Type:** strong_majority

### Majority Coalition (90.0%)
| Model | Weight | Confidence |
|-------|--------|------------|
| opus | 0.950 | 90% |
| sonnet | 0.850 | 85% |
| haiku | 0.700 | 80% |
| fable | 0.920 | 88% |
| gpt-4o | 0.880 | 87% |

## Weight Breakdown
**Formula:** `tier × capability × confidence × history × calibration`

### 1. opus
| Component | Value | Description |
|-----------|-------|-------------|
| tier_weight | 1.000 | Base model capability |
| capability_score | 0.950 | Task-specific strength |
| confidence | 0.900 | Model confidence |
| historical_accuracy | 0.850 | Thompson Sampling avg |
| calibration_penalty | 1.000 | No penalty |

**Calculation:**
- Before calibration: 0.7268
- After calibration: 0.7268
- Impact: no penalty

[... similar breakdown for other models ...]

## Calibration Adjustments
✓ No penalties applied - all models well-calibrated

## Winner Selection Rationale
**Algorithm:** weighted_voting
**Strategy:** weighted-average

1. HIGHEST TOTAL WEIGHT
   Winner had highest total weight: 4.500
   Supporting votes: 5

## Metadata
- Task type: code_review
- Total votes: 6
- Filtered votes: 6
- Discarded votes: 0
- BFT enabled: No
```

## Notes

- Graceful degradation: If PostgreSQL unavailable, reports still generate (no storage)
- BFT-aware: Automatically includes outlier filtering analysis when MAD strategy used
- Sybil-aware: Shows vote flooding detection and family diversity normalization
- Calibration-aware: Highlights models with confidence/accuracy mismatch penalties

## Future Enhancements

Potential improvements:

1. **Visualization** - Generate charts/graphs for weight distributions
2. **Comparison Mode** - Compare explainability reports across multiple workflows
3. **Model Performance Trends** - Track model calibration over time
4. **Confidence Calibration Curves** - Plot expected vs observed accuracy
5. **Interactive Reports** - Web UI for exploring explainability data
