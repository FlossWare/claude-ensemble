---
name: arbiter
description: Multi-model arbiter system with learning - review decisions, track accuracy, improve over time
tags: [decision-making, multi-model, learning, quality-assurance]
---

# Arbiter Skill - Multi-Model Decision Making with Learning

Invoke multiple AI models as arbiters to review work, make decisions, and learn from accuracy over time.

## Usage

```
/arbiter review <issue-id>
/arbiter review-all
/arbiter stats
/arbiter learn <issue-id> <outcome>
/arbiter models
```

## Commands

### `/arbiter review <issue-id>`

Review a specific issue with multiple arbiter models.

**Example:**
```
/arbiter review 011
```

**What it does:**
1. Loads issue from gitlab-issues/
2. Invokes configured arbiters (Opus, Gemini, etc.)
3. Collects their decisions and reasoning
4. Calculates consensus
5. Updates issue with arbiter attribution
6. Records decision for learning

**Output:**
- Arbiter decisions with reasoning
- Consensus percentage
- Recommended action
- Updated issue file with attribution

### `/arbiter review-all`

Review all pending issues that lack arbiter decisions.

**Example:**
```
/arbiter review-all
```

**What it does:**
1. Finds all issues with `arbiter::pending` status
2. Reviews each with all configured arbiters
3. Updates all issues with attributions
4. Generates summary report

**Output:**
- Summary of all arbiter decisions
- Consensus statistics
- Issues ready to ship
- Issues needing human review

### `/arbiter stats`

Show arbiter performance statistics and learning data.

**Example:**
```
/arbiter stats
```

**What it does:**
1. Loads historical arbiter decisions
2. Calculates accuracy per model
3. Shows learning trends
4. Identifies model strengths/weaknesses

**Output:**
- Accuracy per model (overall and by category)
- False positive rates
- Consensus rates
- Model improvement over time
- Recommendations for model selection

### `/arbiter learn <issue-id> <outcome>`

Record the actual outcome of an issue to improve future decisions.

**Example:**
```
/arbiter learn 010 false-positive
/arbiter learn 011 confirmed
```

**What it does:**
1. Records actual outcome for the issue
2. Compares to arbiter predictions
3. Updates model accuracy scores
4. Adjusts confidence weights
5. Generates learning report

**Outcomes:**
- `confirmed` - Issue was real (arbiter was correct if they approved)
- `false-positive` - Issue was not real (arbiter was wrong if they approved)
- `fixed` - Issue was fixed (confirms it was real)
- `wont-fix` - Issue acknowledged but won't fix (confirms it was real)
- `invalid` - Issue was invalid/duplicate (similar to false-positive)

### `/arbiter models`

Show available arbiter models and their current performance.

**Example:**
```
/arbiter models
```

**Output:**
- List of available arbiter models
- Current accuracy scores
- Specializations (what each model is good at)
- Recommended use cases

## Configuration

Configuration is stored in `.claude/arbiter-config.json`:

```json
{
  "arbiters": {
    "opus": {
      "enabled": true,
      "model": "claude-opus-4",
      "confidence_weight": 1.0,
      "specializations": ["code-analysis", "critical-issues"]
    },
    "gemini": {
      "enabled": true,
      "model": "gemini-pro",
      "confidence_weight": 1.0,
      "specializations": ["verification", "comprehensive-review"]
    },
    "sonnet": {
      "enabled": false,
      "model": "claude-sonnet-4.5",
      "confidence_weight": 1.0,
      "specializations": ["balanced-review"]
    }
  },
  "learning": {
    "enabled": true,
    "history_file": ".claude/arbiter-history.jsonl",
    "min_decisions_for_weight": 10,
    "weight_adjustment_rate": 0.1
  },
  "consensus": {
    "min_arbiters": 2,
    "approval_threshold": 0.5,
    "high_confidence_threshold": 0.8
  }
}
```

## Learning System

The arbiter system learns from outcomes and improves over time:

### 1. Accuracy Tracking

Every arbiter decision is recorded with:
- Model name
- Issue ID
- Decision (APPROVE/REJECT)
- Reasoning
- Confidence level
- Timestamp

When outcome is known:
- Actual result (confirmed/false-positive)
- Comparison to prediction
- Accuracy updated

### 2. Confidence Weighting

Models that are more accurate get higher weights:

```
weight = base_weight * (accuracy_rate / average_accuracy)
```

Example:
- Opus: 90% accuracy → weight 1.2
- Gemini: 75% accuracy → weight 1.0
- Sonnet: 60% accuracy → weight 0.8

### 3. Specialization Detection

System tracks which models are good at what:

- Opus might be better at TypeScript errors (95% accuracy)
- Gemini might be better at UX issues (90% accuracy)
- Models automatically weighted higher for their specialties

### 4. Consensus Calculation with Learning

Instead of simple majority:

```
consensus_score = sum(decision * weight * confidence) / sum(weights)
```

Better models have more influence on final decision.

### 5. Continuous Improvement

As more outcomes are recorded:
- Accuracy rates update
- Weights adjust
- Specializations refine
- Recommendations improve

## Data Files

### `.claude/arbiter-history.jsonl`

Historical decisions for learning:

```jsonl
{"issue": "010", "arbiter": "opus", "decision": "APPROVE", "confidence": "HIGH", "outcome": "false-positive", "timestamp": "2026-06-01T14:00:00Z"}
{"issue": "011", "arbiter": "opus", "decision": "APPROVE", "confidence": "HIGH", "outcome": "confirmed", "timestamp": "2026-06-01T14:00:00Z"}
{"issue": "011", "arbiter": "gemini", "decision": "APPROVE", "confidence": "HIGH", "outcome": "confirmed", "timestamp": "2026-06-02T10:00:00Z"}
```

### `.claude/arbiter-stats.json`

Aggregated statistics:

```json
{
  "opus": {
    "total_decisions": 50,
    "correct": 45,
    "accuracy": 0.90,
    "by_category": {
      "typescript-errors": {"decisions": 10, "accuracy": 0.95},
      "form-validation": {"decisions": 8, "accuracy": 0.875}
    },
    "false_positives": 3,
    "false_negatives": 2,
    "current_weight": 1.2
  },
  "gemini": {
    "total_decisions": 48,
    "correct": 36,
    "accuracy": 0.75,
    "by_category": {
      "ux-issues": {"decisions": 12, "accuracy": 0.90},
      "accessibility": {"decisions": 10, "accuracy": 0.80}
    },
    "false_positives": 8,
    "false_negatives": 4,
    "current_weight": 1.0
  }
}
```

## Examples

### Example 1: Review Issue 011

```
User: /arbiter review 011

System:
🎯 Arbiter Review: Issue 011 (RoleExecution broken)

Invoking arbiters: Opus 4.6, Gemini

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Opus 4.6 (weight: 1.2, TypeScript specialist)
Decision: APPROVE
Confidence: HIGH
Reasoning: "22 TypeScript errors confirmed through compilation.
            Legitimate critical issue - code is non-functional."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Gemini (weight: 1.0)
Decision: APPROVE
Confidence: HIGH  
Reasoning: "Component cannot possibly work. Objective proof
            from compilation errors."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CONSENSUS: APPROVE
  - Agreement: 2/2 arbiters (100%)
  - Weighted score: 1.0 (unanimous high confidence)
  - Recommendation: Ship to GitLab

📝 Updated: gitlab-issues/ui-tests-with-arbiter/011_opus_UI-002_critical_WITH_ARBITER.md

📊 Next: Record outcome with `/arbiter learn 011 <outcome>` after verification
```

### Example 2: Record Learning

```
User: /arbiter learn 011 confirmed

System:
📚 Learning Update: Issue 011

Outcome: CONFIRMED (issue was real)

Arbiter Performance:
✅ Opus 4.6: CORRECT (predicted APPROVE, was correct)
   - Accuracy: 44/49 → 45/50 (90.0%)
   - Weight: 1.2 → 1.2 (no change, already high)
   
✅ Gemini: CORRECT (predicted APPROVE, was correct)
   - Accuracy: 35/47 → 36/48 (75.0%)
   - Weight: 1.0 → 1.0 (no change)

Category Update: TypeScript-errors
  - Opus accuracy in this category: 10/10 → 10/10 (100%)
  - Gemini accuracy in this category: 7/9 → 7/9 (77.8%)

💡 Insight: Opus remains the most reliable arbiter for TypeScript
            compilation issues. Consider weighting Opus higher for
            similar issues in the future.

📈 Learning data saved to .claude/arbiter-history.jsonl
```

### Example 3: Show Statistics

```
User: /arbiter stats

System:
📊 Arbiter Performance Statistics

╔══════════════════════════════════════════════════════════════╗
║                    Overall Accuracy                          ║
╚══════════════════════════════════════════════════════════════╝

Opus 4.6:     ████████████████████░ 90% (45/50 correct)
Gemini:       ███████████████░░░░░ 75% (36/48 correct)
Sonnet 4.5:   ██████████████░░░░░░ 70% (28/40 correct)

╔══════════════════════════════════════════════════════════════╗
║                    By Category                               ║
╚══════════════════════════════════════════════════════════════╝

TypeScript Errors:
  Opus:    ████████████████████ 100% (10/10)  🌟 Specialist
  Gemini:  ███████████████░░░░░  77% (7/9)
  Sonnet:  ████████████░░░░░░░░  60% (6/10)

UX Issues:
  Gemini:  ██████████████████░░  90% (9/10)   🌟 Specialist
  Opus:    ████████████████░░░░  80% (8/10)
  Sonnet:  ██████████████████░░  90% (9/10)   🌟 Specialist

Form Validation:
  Opus:    █████████████████░░░  87% (7/8)
  Gemini:  ████████████████░░░░  80% (8/10)
  Sonnet:  ███████████░░░░░░░░░  55% (6/11)

╔══════════════════════════════════════════════════════════════╗
║                    False Positive Rates                      ║
╚══════════════════════════════════════════════════════════════╝

Opus:    6% (3/50)   ⭐ Best
Gemini:  17% (8/48)
Sonnet:  25% (10/40) ⚠️  High

╔══════════════════════════════════════════════════════════════╗
║                    Current Weights                           ║
╚══════════════════════════════════════════════════════════════╝

Opus 4.6:    1.2  (above average accuracy)
Gemini:      1.0  (average accuracy)
Sonnet 4.5:  0.8  (below average accuracy)

╔══════════════════════════════════════════════════════════════╗
║                    Recommendations                           ║
╚══════════════════════════════════════════════════════════════╝

✅ For TypeScript/compilation issues: Prefer Opus (100% accuracy)
✅ For UX/accessibility issues: Prefer Gemini or Sonnet (90% accuracy)
✅ For form validation: Prefer Opus or Gemini (>80% accuracy)
⚠️  Sonnet shows high false positive rate - recommend verification

📈 Trend: All models improving over time (5% accuracy gain over last 20 decisions)

Next: Continue recording outcomes with `/arbiter learn` to improve weights
```

### Example 4: Review All Pending

```
User: /arbiter review-all

System:
🔍 Reviewing all pending issues...

Found 16 issues with arbiter::pending status

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Processing in parallel (2 arbiters × 16 issues = 32 agent calls)...

⏱️  Estimated time: ~8 minutes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Progress bar showing completion]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Review Complete!

Results:
  - 12 issues: APPROVE (both arbiters agree)
  - 2 issues: SPLIT DECISION (arbiters disagree)
  - 2 issues: REJECT (both arbiters say false positive)

Updated files:
  - 16 issues in gitlab-issues/ui-tests-with-arbiter/
  - All issues now have full arbiter attribution
  - Labels updated (arbiter::approved::2-of-2, etc.)

Next steps:
  1. Review split decisions manually (issues 014, 019)
  2. Ship 12 approved issues to GitLab
  3. Remove 2 rejected issues (false positives)
  4. Record outcomes with `/arbiter learn` as they are verified
```

## Benefits

### 1. Automated Quality Assurance
- Multiple independent reviews
- Catch false positives before GitLab
- Consistent decision making

### 2. Transparency
- Every decision shows reasoning
- Clear audit trail
- Human always makes final call

### 3. Continuous Learning
- Models improve over time
- Specialize in their strengths
- False positive rates decrease

### 4. Efficient Workflow
- Review 16 issues in parallel
- Generate attribution automatically
- No manual coordination needed

### 5. Data-Driven Decisions
- Statistics show which models to trust
- Evidence-based recommendations
- Track improvement trends

## Technical Implementation

The skill is implemented as:

1. **Skill definition**: This file (.claude/skills/arbiter.md)
2. **Core logic**: `.claude/arbiter/arbiter_skill.py`
3. **Learning engine**: `.claude/arbiter/learning.py`
4. **Stats tracker**: `.claude/arbiter/stats.py`
5. **Configuration**: `.claude/arbiter-config.json`
6. **History database**: `.claude/arbiter-history.jsonl`

## Integration with Existing System

This skill builds on the arbiter attribution system already implemented:

- Uses existing ARBITER_ATTRIBUTION.md for documentation
- Reads/writes to gitlab-issues/ui-tests-with-arbiter/
- Leverages add_arbiter_attribution.py for formatting
- Extends with learning and automation

## Future Enhancements

1. **Active Learning**: System suggests which issues to verify next for maximum learning
2. **Model Ensembles**: Combine multiple models' strengths
3. **Confidence Calibration**: Adjust confidence scores based on accuracy
4. **Auto-verification**: Automatically verify objective issues (compilation errors)
5. **Cross-project Learning**: Share learnings across projects
6. **Human Feedback**: Learn from human corrections

---

**Start using**: `/arbiter review <issue-id>` to review any issue with multiple AI arbiters

**Enable learning**: `/arbiter learn <issue-id> <outcome>` after verifying each issue

**Track progress**: `/arbiter stats` to see how models improve over time
