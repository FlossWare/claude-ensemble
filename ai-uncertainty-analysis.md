# Uncertainty Quantification Analysis

Decomposes decision uncertainty into **epistemic** (model disagreement) and **aleatoric** (task ambiguity) components, enabling informed risk assessment and decision-making.

## Overview

Uncertainty Quantification (UQ) is essential for high-stakes decision-making. This workflow separates two distinct sources of uncertainty:

1. **Epistemic Uncertainty** — Model disagreement, reducible through more/better models or information
2. **Aleatoric Uncertainty** — Inherent task ambiguity, irreducible without task refinement

By quantifying both, you can:
- Identify whether uncertainty stems from model limitations or task ambiguity
- Decide whether to gather more context (epistemic) or clarify the task (aleatoric)
- Assess whether a decision is reliable enough to act on
- Detect when models are hedging due to unclear requirements

## When to Use

- **High-stakes classification** — "Is this a tumor?" Epistemic + aleatoric quantification reveals confidence
- **Policy/decision analysis** — "Should we approve this loan?" Disagree­ment signals need for clarification
- **Scientific claims** — "What does this study conclude?" Hedging detection reveals caveats
- **Risk assessment** — Aggregate uncertainty score guides confidence in the decision
- **Model selection** — Disagreement patterns reveal which models understand the task
- **Task refinement** — Aleatoric signals show where to ask clarifying questions

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `task` | string | *required* | The question or decision to analyze |
| `context` | string | `''` | Additional context provided to all workers |
| `schema` | object | `{ answer: string, confidence: number }` | JSON Schema defining the answer structure |
| `models` | string[] | task-router selection | Worker model names (e.g., `['opus', 'sonnet', 'haiku']`) |
| `budget` | string | `'medium'` | Budget tier passed to task router when models not specified |

Both camelCase and snake_case parameter names are accepted.

## How It Works

```
Parallel Worker Execution
  ↓
Worker Responses with Confidence + Caveats
  ↓
Split Analysis:
  ├─ Epistemic: String similarity → pairwise disagreement → agreement score
  │  └─ Identifies conflicting model pairs, variance magnitude
  │
  └─ Aleatoric: Hedging pattern detection → ambiguity signals → task clarity
     └─ Detects hedging keywords, variance in confidence, contingency language
  ↓
Aggregate Uncertainty (0-100)
  ├─ Decision Reliability (low/medium/high)
  ├─ Risk Level (low/medium/high)
  └─ Recommendations (actionable guidance)
```

### Phase Details

1. **Get Arbiter** — Selects the arbiter model via rotation (same as other consensus workflows)
2. **Workers** — All models execute in parallel. Each produces a structured answer with confidence, reasoning, and caveats
3. **Epistemic Analysis** — Computes pairwise string similarity, derives agreement score and disagreement patterns
4. **Aleatoric Analysis** — Detects hedging keywords (might, may, uncertain, etc.), computes average hedging score, identifies ambiguity signals
5. **Synthesis** — Combines epistemic + aleatoric into aggregate uncertainty score, determines reliability and recommendations
6. **Update State** — Records arbiter rotation

## Return Value

```javascript
{
  status: 'success',
  
  uncertainty_report: {
    task_summary: '...',
    timestamp: '2026-06-10T...',
    
    epistemic: {
      type: 'inter_model_variance',
      model_count: 3,
      agreement_score: 65,              // 0-100: consensus strength
      variance_magnitude: 35,            // normalized pairwise disagreement
      consensus_strength: 'medium',      // low/medium/high
      disagreement_patterns: [
        {
          pattern: 'high_variance',
          description: 'Models produce significantly different answers',
          severity: 'moderate'
        }
      ],
      conflicting_models: [
        {
          pair: ['opus', 'haiku'],
          disagreement_level: 58,
          confidence_gap: 20
        }
      ]
    },
    
    aleatoric: {
      type: 'intra_model_hedging',
      hedging_indicators: [
        {
          model: 'opus',
          score: 42,                     // 0-100 hedging prevalence
          indicators: [
            { category: 'possibility', count: 3, examples: ['might', 'could'] }
          ]
        }
      ],
      total_hedging_score: 48,           // average hedging across models
      ambiguity_signals: [
        {
          signal: 'hedging_variance',
          description: 'Models have different confidence levels',
          confidence: 45
        }
      ],
      task_clarity: 'medium',            // low/medium/high
      uncertain_terms: ['might', 'perhaps', 'possibly']
    },
    
    aggregate: {
      total_uncertainty: 56,             // combined epistemic + aleatoric
      decision_reliability: 'medium',    // low/medium/high
      risk_level: 'medium',              // low/medium/high
      recommendation: 'Moderate uncertainty...'
    },
    
    worker_details: {
      count: 3,
      responses: [
        {
          model: 'opus',
          confidence: 78,
          reasoning: '...',
          caveats: ['Assumes standard image quality']
        }
      ],
      avg_confidence: 72,
      confidence_range: { min: 65, max: 85 }
    },
    
    model_specific: {
      opus: {
        confidence: 78,
        hedging_score: 35,
        reasoning: '...',
        caveats: [...]
      }
    }
  },
  
  workers: [...],                        // raw worker responses
  execution_id: 'uncertainty_1718...'
}
```

## Examples

### Basic usage: Classify with uncertainty quantification

```javascript
const result = await workflow('ai-uncertainty-analysis', {
  task: 'Is this image a cat or a dog?',
  context: imageBase64Data,
})

console.log(`Total Uncertainty: ${result.uncertainty_report.aggregate.total_uncertainty}%`)
console.log(`Decision Reliability: ${result.uncertainty_report.aggregate.decision_reliability}`)
console.log(`Recommendation: ${result.uncertainty_report.aggregate.recommendation}`)
```

### High-stakes decision with strict schema

```javascript
const result = await workflow('ai-uncertainty-analysis', {
  task: 'Should we approve this credit application?',
  context: applicantProfile,
  schema: {
    type: 'object',
    properties: {
      decision: { type: 'string', enum: ['approve', 'deny', 'review'] },
      confidence: { type: 'number', minimum: 0, maximum: 100 },
      reasoning: { type: 'string' }
    }
  },
  models: ['opus', 'sonnet'],            // strict pair for high-stakes decisions
})

if (result.uncertainty_report.aggregate.total_uncertainty > 70) {
  console.log('TOO RISKY: Manual review required')
  console.log(`Main issue: ${
    result.uncertainty_report.aggregate.decision_reliability === 'low'
      ? 'Models disagree significantly'
      : 'Task is ambiguous'
  }`)
}
```

### Medical diagnosis with focus on aleatoric signals

```javascript
const result = await workflow('ai-uncertainty-analysis', {
  task: 'What is the differential diagnosis for this patient?',
  context: patientData,
  budget: 'high',                        // use best models for medical analysis
})

const aleatoric = result.uncertainty_report.aleatoric
console.log(`Task Clarity: ${aleatoric.task_clarity}`)
if (aleatoric.total_hedging_score > 60) {
  console.log('CAUTION: Diagnosis inherently uncertain—consider additional tests')
  console.log(`Ambiguity signals: ${aleatoric.ambiguity_signals.map(s => s.signal).join(', ')}`)
}
```

### Debugging model disagreement

```javascript
const result = await workflow('ai-uncertainty-analysis', {
  task: 'What is the main argument of this paper?',
  context: paperText,
  models: ['opus', 'sonnet', 'haiku'],   // explicit models to debug
})

const epistemic = result.uncertainty_report.epistemic
console.log(`Agreement Score: ${epistemic.agreement_score}%`)

if (epistemic.conflicting_models.length > 0) {
  console.log('Top disagreements:')
  epistemic.conflicting_models.forEach(pair => {
    console.log(`  ${pair.pair.join(' vs ')}: ${pair.disagreement_level}%`)
  })
}
```

## Understanding the Report

### Epistemic Uncertainty

Measures how much models agree on the answer.

- **agreement_score** — Percentage consensus (higher = more aligned)
- **variance_magnitude** — Average pairwise string-based disagreement (0-100)
- **consensus_strength** — Qualitative assessment: low (< 40%) / medium (40–70%) / high (> 70%)
- **conflicting_models** — The model pairs with largest disagreement
- **disagreement_patterns** — High-level patterns like "high_variance"

**Interpretation:**
- High epistemic uncertainty → Some models fundamentally understand the task differently
  - Action: Add more context, clarify task requirements, use different model families
- Low epistemic uncertainty → Models are aligned
  - Action: Trust the consensus; differences are likely due to randomness

### Aleatoric Uncertainty

Measures task ambiguity through hedging patterns.

- **hedging_indicators** — Per-model hedging keywords found (might, may, could, uncertain, etc.)
- **total_hedging_score** — Average hedging prevalence (0-100)
- **ambiguity_signals** — Detected patterns like "high_hedging_prevalence" or "hedging_variance"
- **task_clarity** — Qualitative: low / medium / high
- **uncertain_terms** — Actual words found that indicate uncertainty

**Interpretation:**
- High aleatoric uncertainty → Task is inherently ambiguous or unclear
  - Action: Rephrase the question, provide more context, break into simpler sub-questions
- Low aleatoric uncertainty → Task is clear; models hedge due to genuine epistemic limits
  - Action: Focus on gathering more data, not task refinement

### Aggregate Uncertainty

Combined score balancing both sources.

- **total_uncertainty** — Average of epistemic variance + aleatoric hedging (0-100)
- **decision_reliability** — Can you act on the result? (low / medium / high)
- **risk_level** — How risky is it to act? (low / medium / high)
- **recommendation** — Specific actionable guidance

**Decision Table:**

| Total Uncertainty | Reliability | Risk | Action |
|---|---|---|---|
| 0–30% | High | Low | Proceed with confidence |
| 30–70% | Medium | Medium | Document assumptions; flag uncertain areas |
| 70–100% | Low | High | Request clarification; gather more context; consider alternatives |

## Hedging Detection Details

The workflow scans responses for these uncertainty indicators:

| Category | Keywords/Patterns | Weight | Interpretation |
|---|---|---|---|
| **possibility** | might, may, could, possibly, perhaps, probably | 0.6 | Conditional/uncertain |
| **mitigation** | somewhat, relatively, fairly, rather, quite | 0.5 | Weakening language |
| **observation** | seems, appears, suggests, indicates, tends to | 0.7 | Inference over fact |
| **explicit_uncertainty** | uncertain, ambiguous, unclear, difficult to determine | 0.9 | Direct uncertainty signal |
| **opinion** | in my opinion, i think, arguably, debatable | 0.8 | Subjective framing |
| **contingency** | depends on, varies, can vary, contingent | 0.8 | Conditional answers |
| **caveats** | with caveats, caveat, exception, unless, except | 0.7 | Limitations noted |
| **interrogative** | ? at end/start of sentence | 0.9 | Question marks signal doubt |

Hedging score = (match_count / word_count) * 100, capped at 100%.

## String Similarity Algorithm

Epistemic agreement uses **Levenshtein distance** (edit distance):

1. Serialize each worker's answer to JSON
2. Compute edit distance between all pairs
3. Normalize: similarity = (max_length - distance) / max_length
4. Disagreement = 1 - similarity
5. Average disagreement over all pairs = variance magnitude
6. Agreement score = (1 - avg_disagreement) * 100

This captures *structural* differences in answers, not just semantic equivalence. JSON serialization ensures consistent comparison of complex objects.

## Cost Considerations

- **Workers:** N parallel calls (default 3 models)
- **Analysis:** Single-pass computational (no extra LLM calls)
- **Total:** ~3 LLM calls per run (same as basic consensus)

Cost is proportional to model choice:
- Budget `low` → cheaper models, faster analysis
- Budget `medium` → balanced models
- Budget `high` → most capable models, best uncertainty estimates

## Integration Examples

### Pre-decision uncertainty check

```javascript
const result = await workflow('ai-uncertainty-analysis', {
  task: 'Is this email phishing?',
  context: emailContent,
})

if (result.uncertainty_report.aggregate.total_uncertainty > 60) {
  // Route to human review
  await routeToHumanReview(emailContent, result)
} else if (result.uncertainty_report.aggregate.total_uncertainty > 40) {
  // Apply with flagging
  flagEmailForMonitoring(emailContent)
  markAsPhishing(emailContent)
} else {
  // Auto-action
  blockAndDelete(emailContent)
}
```

### Diagnosis confidence reporting

```javascript
const result = await workflow('ai-uncertainty-analysis', {
  task: 'Diagnose this patient condition',
  context: patientSymptoms,
  budget: 'high',
})

const report = result.uncertainty_report
const diagnosis = report.worker_details.responses[0]

console.log(`DIAGNOSIS: ${diagnosis.reasoning}`)
console.log(`Confidence: ${diagnosis.confidence}%`)
console.log(`Model Agreement: ${report.epistemic.agreement_score}%`)
console.log(`Task Clarity: ${report.aleatoric.task_clarity}`)

if (report.aleatoric.ambiguity_signals.length > 0) {
  console.log(`Caveats: ${report.aleatoric.ambiguity_signals.map(s => s.description).join('; ')}`)
}
```

### Adversarial testing via disagreement

```javascript
// Use disagreement to find edge cases
const result = await workflow('ai-uncertainty-analysis', {
  task: 'Rate sentiment of: "This product works, but..."',
  context: '',
  models: ['opus', 'sonnet', 'haiku'],
})

if (result.uncertainty_report.epistemic.agreement_score < 50) {
  console.log('⚠️  EDGE CASE: Models disagree on this input')
  console.log('Likely reason: task ambiguity or conflicting signals')
  
  // Use disagreement as signal for adversarial training dataset
  return { edge_case: true, analysis: result }
}
```

## Files

- `~/.claude/repos/claude-global-skills/ai-uncertainty-analysis.js` — Main workflow
- `~/.claude/repos/claude-global-skills/ai-uncertainty-analysis.md` — This documentation

## Dependencies

- `ai-task-router` — For dynamic model selection
- `get-next-arbiter` — For arbiter rotation
- `update-arbiter-state` — For tracking arbiter usage
- `agent()` — LLM invocation primitive
- `parallel()` — Parallel execution primitive

## Related Workflows

- **ai-consensus** — Basic multi-model consensus (no uncertainty quantification)
- **ai-consensus-weighted** — Confidence-weighted consensus
- **ai-consensus-refinement** — Iterative refinement with confidence thresholds
- **ai-consensus-debate** — Adversarial debate for robust analysis

---

**Version**: 1.0  
**Created**: 2026-06-10  
**Dependencies**: ai-task-router, get-next-arbiter, update-arbiter-state
