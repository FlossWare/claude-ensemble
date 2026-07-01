# Explainability Reporter Integration Guide

**Status:** ✅ WIRED  
**Issue:** #266  
**Date:** 2026-07-01

## Overview

The Explainability Reporter provides detailed breakdowns of multi-AI consensus decisions, showing:

1. **Weight components** - How each model's vote was weighted (tier × capability × confidence × history × calibration)
2. **Agreement analysis** - Majority coalition vs minority dissent
3. **Calibration adjustments** - Penalties applied for overconfident models
4. **Winner selection rationale** - Why the final answer won (highest weight, BFT filtering, tie-breaking, etc.)

## Integration Points

### 1. Direct Usage (Low-Level API)

```javascript
const { explain } = require('./shared/explainability-reporter.cjs');

// After getting voting result
const votingResult = await runWeightedVoting(votes, taskType, options);

// Generate explainability report
const explainResult = await explain(votingResult, {
  format: 'markdown',           // 'json' | 'markdown' | 'both'
  outputPath: '/tmp/report.md', // Optional file output
  workflowExecutionId: 'exec-123', // Optional PostgreSQL storage
});

console.log(explainResult.markdown);
```

### 2. Wrapper API (Recommended)

The easiest integration is via `weighted-voting-with-explain.cjs`:

```javascript
const { runWeightedVotingWithExplain } = require('./shared/weighted-voting-with-explain.cjs');

const result = await runWeightedVotingWithExplain(votes, taskType, {
  // Normal voting options
  strategy: 'weighted-average',
  minConfidence: 0.6,
  
  // Explainability options
  explain: true,                  // Enable explainability
  explainFormat: 'markdown',      // Output format
  explainOutputPath: '/tmp/report.md', // Optional file
});

// Access report
console.log(result.explainability.markdown);
```

### 3. Environment Variable Control

Enable explainability globally without code changes:

```bash
# Enable for all consensus decisions
export CONSENSUS_EXPLAIN=1

# Set output directory (default: /tmp/consensus-reports)
export CONSENSUS_EXPLAIN_DIR=/var/log/consensus-reports

# Set default format (default: markdown)
export CONSENSUS_EXPLAIN_FORMAT=both

# Run your workflow
node workflows/deep-research.mjs
```

### 4. CLI Tool

Generate reports from existing voting results:

```bash
# Demo with mock data
node shared/explain-consensus-cli.cjs --mock

# Explain from voting result JSON file
node shared/explain-consensus-cli.cjs --file /tmp/voting-result.json --format both

# Explain from PostgreSQL workflow execution
node shared/explain-consensus-cli.cjs --workflow-id exec-12345 --output /tmp/report.md
```

## Files Wired

### ✅ Already Integrated

1. **shared/weighted-voting-with-explain.cjs**
   - Wrapper around base weighted-voting.cjs
   - Adds optional explainability to any voting call
   - Used by: batch-consensus.cjs, consensus-cache.cjs

2. **shared/batch-consensus.cjs**
   - Batch processing API with explainability support
   - Options: `explain: true, explainFormat: 'markdown'`
   - Default: disabled (set `explain: true` to enable)

3. **shared/experiment-integration.cjs**
   - A/B testing framework for voting algorithms
   - Auto-generates explainability for first/last iteration
   - Used to debug voting algorithm changes

### ✅ Integration Helpers Created

4. **shared/explainability-integration-helper.cjs**
   - Environment variable checks
   - Wrapper functions for easy integration
   - Conditional logging utilities

5. **shared/explain-consensus-cli.cjs**
   - Standalone CLI tool for generating reports
   - Loads from: mock data, JSON files, PostgreSQL
   - Supports all output formats

6. **shared/EXPLAINABILITY-INTEGRATION.md** (this file)
   - Complete integration documentation
   - Usage examples for all patterns

## Usage Examples

### Example 1: Enable for Specific Workflow

```javascript
// In your workflow
const { runWeightedVotingWithExplain } = require('./shared/weighted-voting-with-explain.cjs');

export default async function({ args, phase, log, parallel }) {
  // ... worker execution ...
  
  const result = await runWeightedVotingWithExplain(workerResults, 'code_review', {
    explain: true,
    explainFormat: 'both',
    explainOutputPath: `/tmp/consensus-${Date.now()}`,
  });
  
  // Log report to console
  log('\n=== CONSENSUS EXPLAINABILITY ===');
  log(result.explainability.markdown);
}
```

### Example 2: Enable Globally via Environment

```bash
# In your shell or systemd service
export CONSENSUS_EXPLAIN=1
export CONSENSUS_EXPLAIN_DIR=/var/log/multi-ai-consensus
export CONSENSUS_EXPLAIN_FORMAT=markdown

# All consensus decisions will auto-generate reports
```

### Example 3: Conditional Explainability (Debug Mode)

```javascript
const { addExplainOptions } = require('./shared/explainability-integration-helper.cjs');

const votingOptions = addExplainOptions({
  strategy: 'weighted-average',
  minConfidence: 0.6,
}, {
  // Only explain if DEBUG_CONSENSUS=1
  explain: process.env.DEBUG_CONSENSUS === '1',
  explainFormat: 'markdown',
});

const result = await runWeightedVotingWithExplain(votes, taskType, votingOptions);
```

### Example 4: Store in PostgreSQL

```javascript
const result = await runWeightedVotingWithExplain(votes, taskType, {
  explain: true,
  context: {
    workflow_execution_id: 'exec-20260701-12345',
  },
});

// Report automatically stored in workflow.explainability_reports table
```

## Report Format

### Markdown Example

```markdown
# Multi-AI Consensus Explainability Report

## Summary
- **Winning Answer:** `{"recommendation":"approve"}`
- **Consensus Level:** strong (85.0%)
- **Total Weight:** 2.450
- **Supporting Votes:** 3

## Agreement Analysis
**Consensus Type:** strong_majority

### Majority Coalition (85.0%)
| Model | Weight | Confidence |
|-------|--------|------------|
| opus | 1.000 | 95% |
| sonnet | 0.900 | 90% |

## Weight Breakdown
**Formula:** `tier × capability × confidence × history × calibration`

### 1. opus
| Component | Value | Description |
|-----------|-------|-------------|
| tier_weight | 1.000 | Base model capability |
| capability_score | 0.950 | Task-specific strength |
| confidence | 0.920 | Self-reported confidence |
| historical_accuracy | 0.850 | Thompson Sampling avg |
| calibration_penalty | 1.000 | Overconfidence penalty |

**Calculation:**
- Before calibration: 0.7429
- After calibration: 0.7429
- Impact: no penalty

## Calibration Adjustments
**Models Penalized:** 1

| Model | Penalty | Reason | Impact |
|-------|---------|--------|--------|
| sonnet | 0.90× | overconfident (claimed 90%, actual 75%) | 10% reduction |

## Winner Selection Rationale
1. **HIGHEST TOTAL WEIGHT** - Winner had highest weight: 2.450
2. **BFT OUTLIER FILTERING** - 1 outlier excluded via MAD
```

### JSON Example

```json
{
  "status": "success",
  "summary": {
    "winning_answer": {"recommendation": "approve"},
    "consensus_level": "strong",
    "consensus_strength": "85.0%",
    "total_weight": "2.450",
    "vote_count": 3
  },
  "weight_breakdown": {
    "winner_votes": [
      {
        "model": "opus",
        "components": {
          "tier_weight": {"value": 1.0, "description": "..."},
          "capability_score": {"value": 0.95, "description": "..."},
          "confidence": {"value": 0.92, "description": "..."},
          "historical_accuracy": {"value": 0.85, "description": "..."},
          "calibration_penalty": {"value": 1.0, "description": "..."}
        },
        "calculation": {
          "formula": "tier × capability × confidence × history × calibration",
          "before_calibration": 0.7429,
          "after_calibration": 0.7429,
          "calibration_impact": "no penalty"
        },
        "final_weight": 1.0
      }
    ]
  },
  "agreement_analysis": {
    "consensus_type": "strong_majority",
    "majority": {
      "answer": {"recommendation": "approve"},
      "total_weight": 2.45,
      "percentage": "85.0"
    },
    "minorities": []
  },
  "calibration_adjustments": {
    "num_models_penalized": 0,
    "penalties_applied": []
  },
  "winner_selection": {
    "algorithm": "weighted_voting",
    "strategy": "weighted-average",
    "reasons": [
      {
        "type": "highest_total_weight",
        "description": "Winner had highest weight: 2.450"
      }
    ]
  }
}
```

## PostgreSQL Storage

Reports are automatically stored in `workflow.explainability_reports`:

```sql
-- Query recent explainability reports
SELECT
  workflow_execution_id,
  report->>'summary' as summary,
  report->'calibration_adjustments'->>'num_models_penalized' as penalties,
  created_at
FROM workflow.explainability_reports
ORDER BY created_at DESC
LIMIT 10;

-- Find decisions with high disagreement
SELECT
  workflow_execution_id,
  report->'agreement_analysis'->>'consensus_type' as consensus_type,
  report->'summary'->>'consensus_strength' as strength
FROM workflow.explainability_reports
WHERE (report->'agreement_analysis'->>'consensus_type') IN ('weak_majority', 'plurality')
ORDER BY created_at DESC;

-- Analyze calibration penalties over time
SELECT
  DATE(created_at) as date,
  AVG((report->'calibration_adjustments'->>'num_models_penalized')::int) as avg_penalties
FROM workflow.explainability_reports
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

## Testing

```bash
# Test basic functionality
node /tmp/test-explainability-integration.cjs

# Test CLI
node shared/explain-consensus-cli.cjs --mock
node shared/explain-consensus-cli.cjs --mock --format both --output /tmp/test-report

# Test environment variable control
CONSENSUS_EXPLAIN=1 node workflows/your-workflow.mjs
```

## Verification Steps

To verify explainability is working:

1. **Run CLI demo:**
   ```bash
   node shared/explain-consensus-cli.cjs --mock
   ```
   ✓ Should print detailed markdown report

2. **Test environment variable:**
   ```bash
   CONSENSUS_EXPLAIN=1 node -e "
     const { isExplainabilityEnabled } = require('./shared/explainability-integration-helper.cjs');
     console.log('Enabled:', isExplainabilityEnabled());
   "
   ```
   ✓ Should print: `Enabled: true`

3. **Test batch consensus with explain:**
   ```javascript
   const { batchConsensus } = require('./shared/batch-consensus.cjs');
   
   const results = await batchConsensus(
     ['What is 2+2?', 'What is the capital of France?'],
     {
       explain: true,
       explainFormat: 'markdown',
       workers: ['opus', 'sonnet', 'haiku'],
     }
   );
   
   console.log(results[0].explainability.markdown);
   ```
   ✓ Should show weight breakdown for first question

4. **Check PostgreSQL storage:**
   ```sql
   SELECT COUNT(*) FROM workflow.explainability_reports;
   ```
   ✓ Should show reports (if `workflowExecutionId` provided)

## Integration Checklist

- [x] Core reporter implemented (`explainability-reporter.cjs`)
- [x] Wrapper API created (`weighted-voting-with-explain.cjs`)
- [x] Integration helper utilities (`explainability-integration-helper.cjs`)
- [x] CLI tool (`explain-consensus-cli.cjs`)
- [x] Batch consensus integration (`batch-consensus.cjs`)
- [x] Experiment framework integration (`experiment-integration.cjs`)
- [x] Environment variable support
- [x] PostgreSQL storage schema
- [x] Documentation (this file)
- [x] Test suite (passing)

## Next Steps (Optional)

Future enhancements not required for initial integration:

1. **Grafana Dashboard**: Visualize calibration trends, consensus strength distribution
2. **Slack/Email Alerts**: Notify on high disagreement or calibration issues
3. **Web UI**: Interactive explainability viewer
4. **Export to PDF**: For formal audit trails
5. **Comparative Analysis**: Show explainability diff between two voting runs

## Summary

**What was wired:**
- Explainability reporter integrated into weighted-voting-with-explain.cjs
- Environment variable control via `CONSENSUS_EXPLAIN=1`
- CLI tool for generating reports from existing results
- Batch consensus now supports `explain: true` option
- Experiment framework auto-generates reports for A/B tests

**Where to use:**
- Any call to `runWeightedVotingWithExplain()`
- Batch processing via `batchConsensus()` with `explain: true`
- CLI via `explain-consensus-cli.cjs`
- Environment: `export CONSENSUS_EXPLAIN=1`

**How to verify:**
```bash
# Quick test
node shared/explain-consensus-cli.cjs --mock

# Full integration test
CONSENSUS_EXPLAIN=1 node workflows/deep-research.mjs
```
