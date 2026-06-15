---
name: feedback_always_hybrid
description: ALWAYS use hybrid multi-AI (Anthropic + local models) for all decisions. Never Anthropic-only.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eef2a5e9-6453-4f04-a320-06ec8386a952
---

# ALWAYS Use Hybrid Multi-AI

**Rule:** ALWAYS use hybrid Anthropic + local models for multi-AI consensus. Never use Anthropic-only.

**Why:** 
- Empirically proven: Hybrid review found MORE bugs than Anthropic-only (4 confirmed + 1 NEW critical bug)
- Local models caught infinite loop risk that Opus/Sonnet/Haiku missed
- Model diversity = different architectures catch different bug classes
- Red Hat compliant (local models approved for proprietary code)
- Cost efficient (50% free models vs 100% paid)
- [[reference_multi_ai_quality_comparison]]: Hybrid FREE+PAID = 95-98% quality (best ROI)

**How to apply:**

### Default Pattern (6-model consensus)
```javascript
// Finders: 2 diverse models
parallel([
  () => agent(prompt, { model: 'sonnet' }),
  () => agent(prompt, { agentType: 'general-purpose' })  // Local
])

// Verifiers: 6-vote hybrid
parallel([
  () => agent(verifyPrompt, { model: 'opus' }),     // Anthropic
  () => agent(verifyPrompt, { model: 'sonnet' }),   // Anthropic
  () => agent(verifyPrompt, { model: 'haiku' }),    // Anthropic
  () => agent(verifyPrompt, { agentType: 'general-purpose' }), // Local 1
  () => agent(verifyPrompt, { agentType: 'general-purpose' }), // Local 2
  () => agent(verifyPrompt, { agentType: 'general-purpose' })  // Local 3
])
```

### Available Local Models
- phi3.5:latest, phi3.5:3.8b (Microsoft Phi - strong reasoning)
- mathstral:7b (Math/code specialist)
- wizardlm2:7b (General reasoning)
- zephyr:7b (Instruction following)
- starcoder2:7b (Code understanding)
- gemma3:4b (Fast iteration)

### When to Use What
- **Code review:** 3 Anthropic + 3 local (proven best)
- **Design decisions:** 3 Anthropic + 3 local
- **Bug finding:** Mix local (starcoder2/phi3.5) + Anthropic
- **Quick checks:** 1 Anthropic + 1 local minimum

### Evidence
**harness_cli review (2026-06-15):**
- Anthropic-only: 4 findings confirmed (3-vote max)
- Hybrid (3+3): 4 findings confirmed PLUS 1 NEW critical bug (6-vote unanimous on 2 findings)
- Winner: Hybrid found 25% more bugs

### Never Do This Again
- ❌ Anthropic-only multi-AI (violated [[feedback_always_multi_ai]])
- ❌ Solo review without fleet consensus
- ❌ Forgetting local models exist

### Always Do This
- ✅ Hybrid Anthropic + local for ALL multi-AI decisions
- ✅ Use agentType: 'general-purpose' for local models
- ✅ Aim for 6-vote consensus (3+3) on important decisions
- ✅ Red Hat compliant by default
