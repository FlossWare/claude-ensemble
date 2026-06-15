---
name: terminology-correction
description: Corrected misleading "deep learning" terminology to accurate "system audit" terminology
metadata:
  type: feedback
---

**Rule:** Never use "deep learning" terminology for multi-AI analysis workflows.

**Why:** "Deep learning" has a specific technical meaning (neural networks with multiple layers, gradient descent, backpropagation, training). Using it for research/analysis workflows is misleading and contradicts the core principle that this system is orchestration over pre-trained models, not a learning system.

**Correct terminology:**
- ✅ **System audit** - Multi-AI examination of architecture/quality
- ✅ **Deep research** - Comprehensive multi-source investigation
- ✅ **Multi-AI analysis** - Consensus-based examination
- ✅ **Self-introspection** - System analyzing its own structure
- ✅ **Comprehensive review** - Thorough examination with diverse perspectives

**Incorrect terminology:**
- ❌ **Deep learning** - Implies neural network training
- ❌ **Self-learning** - Implies autonomous model improvement
- ❌ **Learning workflow** - Implies training or fine-tuning
- ❌ **Training pipeline** - Implies gradient descent/backprop

**How to apply:**

When creating workflows that analyze codebases or systems:
1. Name them `*-audit`, `*-analysis`, `*-review`, or `*-research`
2. Describe them as "multi-AI consensus examination" not "learning"
3. Emphasize diverse perspectives (6 models catching different issues)
4. Avoid ML terminology unless actually doing ML (training, fine-tuning, etc.)

**Example correction:**
- Before: `deep-self-learn` - "Multi-AI consensus deep learning about the system"
- After: `multi-ai-system-audit` - "Multi-AI consensus audit of system architecture"

**Context:** The CLAUDE.md explicitly states this is NOT a learning system:
```
What This System IS NOT:
- ✗ Learning system (no model training, no weight updates)
- ✗ Self-improving AI (same model capabilities throughout)
```

All improvements are from routing efficiency, task decomposition, and retry logic - NOT model intelligence gains.
