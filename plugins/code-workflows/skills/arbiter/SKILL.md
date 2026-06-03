---
name: arbiter
description: This skill should be used when the user asks to "review decisions", "arbiter review", "multi-model decision", "track accuracy", or discusses using multiple AI models to make decisions and learn from outcomes.
version: 1.0.0
---

# Arbiter - Multi-Model Decision Making with Learning

Invoke multiple AI models as arbiters to review work, make decisions, and learn from accuracy over time.

## Usage

```bash
/arbiter review <issue-id>
/arbiter review-all
/arbiter stats
/arbiter learn <issue-id> <outcome>
/arbiter models
```

## Commands

### `/arbiter review <issue-id>`

Review a specific issue with multiple arbiter models.

**What it does:**
1. Loads issue from gitlab-issues/
2. Invokes configured arbiters (Opus, Gemini, etc.)
3. Collects their decisions and reasoning
4. Calculates consensus
5. Updates issue with arbiter attribution
6. Records decision for learning

### `/arbiter review-all`

Review all pending issues that lack arbiter decisions.

### `/arbiter stats`

Show arbiter accuracy statistics and learning metrics.

### `/arbiter learn <issue-id> <outcome>`

Record actual outcome for learning (correct/incorrect/partial).

### `/arbiter models`

List configured arbiter models and their accuracy stats.

## Features

- Multi-model decision making
- Consensus tracking
- Learning from outcomes
- Accuracy statistics per model
- Issue attribution

---

**Version**: 1.0  
**Created**: 2026-06-03
