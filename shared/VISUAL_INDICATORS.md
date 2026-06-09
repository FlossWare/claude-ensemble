# Visual Indicators Prototype

Testing skills-ai visual concepts for .claude.

## Features

### Colored Output for Multi-AI
Each model gets a distinct color for easy visual tracking:
- 🔵 **Blue**: Claude Opus
- 🔷 **Cyan**: Claude Sonnet  
- 🟣 **Purple**: GPT-4o
- 🟡 **Yellow**: Gemini
- 🟢 **Green**: Haiku

### Progress Indicators
- Worker status (analyzing → complete)
- Arbiter synthesis progress
- Consensus quality visualization
- Phase transitions

### Model Comparison Tables
Side-by-side comparison of worker findings for consensus evaluation.

## Usage

```bash
source shared/visual-indicators.sh

# Headers
header "Multi-AI Consensus"
phase "Worker Analysis"

# Workers
worker_start 0 "claude-opus-4"
worker_complete 0 "claude-opus-4"

# Arbiter
arbiter_start "claude-opus-4"
arbiter_complete

# Quality
consensus_quality 0.87  # High/Medium/Low based on score

# Status
success "Analysis complete!"
error "Something failed"
warning "Check this"
info "FYI message"
```

## Demo

Run the demo to see it in action:

```bash
./skills/demo-consensus.sh
```

## How It Helps Learning

**Visual feedback benefits:**

1. **Transparency** - See which models are working
2. **Progress tracking** - Know what phase we're in
3. **Quality awareness** - Consensus score shows confidence
4. **Model diversity** - Colors show we're using different models
5. **Debugging** - Easier to spot which worker failed

**Learning example:**

Without visuals:
```
Running multi-model workflow...
Done.
```

With visuals:
```
🤖 Worker 0: claude-opus-4 analyzing...
✓ Worker 0: claude-opus-4 complete
🤖 Worker 1: claude-sonnet-4 analyzing...
✓ Worker 1: claude-sonnet-4 complete
🧠 Arbiter: claude-opus-4 synthesizing consensus...
🎯 Consensus reached!
🎯 High consensus (0.87)
```

You can SEE:
- Three different workers analyzed
- Arbiter synthesized consensus
- High-quality agreement (0.87)

This builds **trust** and **understanding** of how multi-AI works.

## Concepts from skills-ai

- Colored model indicators
- Progress visualization
- Consensus quality display
- Interactive feedback
- Professional CLI design

All proven concepts flow back to FlossWare skills-ai.
