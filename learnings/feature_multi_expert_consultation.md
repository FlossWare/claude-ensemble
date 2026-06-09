---
name: multi-expert-consultation
description: Multi-expert consultation feature - ask multiple related experts and synthesize their answers
metadata: 
  node_type: memory
  type: project
  originSessionId: 50760802-b2be-4756-b141-b1ad4f67c15f
---

# Multi-Expert Consultation Feature

When declining an expert suggestion in the CLI, users can now consult ALL related experts instead of just using one.

**Why:** User asked "if we don't use an expert (type N), can it still search across all the experts for an answer? Or choose the right one to ask?" - wanted democratic knowledge gathering across multiple experts.

**How to apply:** When discussing expert system capabilities, mention that users can get multi-expert consensus on questions by typing 'c' at the expert suggestion prompt.

## User Flow

```
💡 Expert suggestion: This looks like a python question
   Expert: python-expert

   Use python-expert? (y/enter=yes, c=consult all experts, n=no): c
   
   🔍 Consulting multiple experts...
   Experts: python, software-engineering, performance
   
   💭 Asking python expert...
   💭 Asking software-engineering expert...
   💭 Asking performance expert...
   
   ============================================================
   📚 Multi-Expert Consultation Results:
   ============================================================
   
   1. PYTHON EXPERT:
   [Answer from python expert]
   
   ------------------------------------------------------------
   
   2. SOFTWARE-ENGINEERING EXPERT:
   [Answer from software-engineering expert]
   
   ------------------------------------------------------------
   
   3. PERFORMANCE EXPERT:
   [Answer from performance expert]
   
   ============================================================
   🎯 SYNTHESIS:
   ============================================================
   
   [AI synthesizes all answers into one comprehensive response]
   
   ⏱️  Multi-expert consultation time: 12.3s
```

## Implementation Details

**File:** `cli/ai-cli.py`
**Method:** `_consult_multiple_experts(message, primary_expert)`

### Features

1. **Related Domain Discovery**
   - Automatically finds experts related to primary expert's domain
   - E.g., netbsd → bsd, unix, freebsd, openbsd
   - E.g., python → software-engineering, performance
   - Limits to 3 experts max (fast, focused)

2. **Parallel Consultation**
   - Asks all experts concurrently
   - 60s timeout per expert (skips if too slow)
   - Graceful degradation if expert errors

3. **Answer Display**
   - Side-by-side comparison of all expert answers
   - Clear visual separation
   - Expert domain labeled

4. **AI Synthesis**
   - Uses current AI provider to synthesize
   - Highlights where experts agree
   - Notes unique insights from each
   - Creates comprehensive combined answer

5. **Performance Tracking**
   - Shows cook time for multi-expert consultation
   - Helps users understand cost/benefit

## Related Domains Configured

```python
related_domains = {
    'netbsd': ['bsd', 'unix', 'freebsd', 'openbsd'],
    'fedora': ['rhel', 'linux'],
    'debian': ['ubuntu', 'linux'],
    'ubuntu': ['debian', 'linux'],
    'python': ['software-engineering', 'performance'],
    'java': ['software-engineering', 'performance'],
    'docker': ['podman', 'kubernetes'],
    'kubernetes': ['docker', 'podman'],
}
```

## Use Cases

1. **Comprehensive Answers**
   - Get multiple perspectives on complex questions
   - Cross-domain expertise (e.g., Python + Performance)
   
2. **Quality Verification**
   - Multiple experts validate each other
   - Catches domain-specific nuances
   
3. **Learning**
   - See how different experts approach same problem
   - Understand trade-offs between approaches

## Benefits

- **Democratic Knowledge** - No single expert bias
- **Comprehensive** - Multiple angles on same question
- **Fast** - Parallel execution
- **Smart Synthesis** - AI combines best parts
- **Optional** - Users choose when they want it (y=single, c=multiple, n=none)

This makes Universal AI's expert system even more powerful by enabling panel-of-experts consultation!
