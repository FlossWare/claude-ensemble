---
name: chatgpt-coarchitect
description: ChatGPT as co-architect for evaluation framework design and anti-self-referential safeguards
metadata: 
  node_type: memory
  type: reference
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# ChatGPT Co-Architect Role

**Context:** 2026-06-14 session revealed self-referential bias risks in multi-model orchestration system.

**ChatGPT's Contribution:**
1. **Accurate Diagnosis:** Identified system as "orchestration not AI invention"
2. **Framework Design:** Two-layer evaluation architecture to prevent feedback loop collapse
3. **Evaluation Harness:** Adversarial prompt template for independent evaluation
4. **Warning Systems:** Flagged risks (self-confirming logic, circular validation, metric overfitting)

## Evaluation Harness Prompt

**Location:** `~/.claude/self/evaluation-harness.mjs`

**Key Principles:**
- Assume system is wrong until proven otherwise
- Don't trust majority vote by default
- Don't accept internal metrics as truth
- Flag self-confirming logic explicitly

**5 Evaluation Dimensions:**
1. Correctness (factually/logically valid?)
2. Robustness (handles edge cases?)
3. Generalization (holds outside this system?)
4. Bias Resistance (tailored to please evaluator?)
5. Reproducibility (another system would agree?)

## Two-Layer Architecture

**Layer 1:** Fast internal arbiters (6-model consensus, ~30s)
**Layer 2:** Adversarial independent evaluators (ChatGPT harness)
**Layer 3:** Periodic external baseline tests (user validation)

## Why This Matters

**User directive:** "let's use chatgpt as a coarchitect"

**Prevents:**
- Feedback loop collapse (system grading its own homework)
- Model convergence (diversity loss)
- Metric overfitting (high internal scores, low external quality)
- Self-referential optimization (confident but wrong)

**How to Apply:**
- For major architectural decisions, consult ChatGPT (independent perspective)
- For evaluation design, use ChatGPT's adversarial framework
- For quality validation, apply Layer 2 evaluation (not just Layer 1 consensus)
- For system claims, verify externally (user testing, objective metrics)

**Related:**
- [[feedback_always_multi_ai]] - Multi-model consensus (Layer 1)
- [[feedback_always_review]] - External validation requirement
- [[reference_multi_ai_providers]] - Available models for diversity
