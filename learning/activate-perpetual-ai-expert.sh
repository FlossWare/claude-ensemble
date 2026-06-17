#!/bin/bash

# Perpetual AI Expert System - Activation Script
#
# Mission: Become expert at EVERYTHING in AI
# Strategy: Investigate → Learn → DO
# Scope: All 70 queries across 10 categories, deepest complexity

set -e

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  PERPETUAL AI EXPERT SYSTEM - ACTIVATION"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Mission:   Become expert at EVERYTHING in AI"
echo "Strategy:  Investigate → Learn → DO"
echo "Scope:     70 queries across 10 categories"
echo "Depth:     Embrace most complex papers, deepest math"
echo ""
echo "Research Categories:"
echo "  1. Advanced Reasoning (CoT, ToT, process supervision)"
echo "  2. Multi-Agent Orchestration (debate, swarm, hierarchical)"
echo "  3. Meta-Learning & AutoML (MAML, NAS, continual learning)"
echo "  4. Efficient Inference (speculative decoding, quantization, MoE)"
echo "  5. RAG & Knowledge (ColBERT, dense retrieval, knowledge graphs)"
echo "  6. Training & Fine-tuning (LoRA, RLHF, DPO, constitutional AI)"
echo "  7. Mathematical Foundations (transformers, attention, optimization)"
echo "  8. Systems & Infrastructure (distributed training, inference)"
echo "  9. Evaluation & Robustness (benchmarks, adversarial, calibration)"
echo " 10. Domain-Specific AI (code, math, science, medical, legal)"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

LEARNING_DIR="$HOME/.claude/learning"
RESEARCH_DIR="$LEARNING_DIR/research"

# Ensure directories exist
mkdir -p "$RESEARCH_DIR"
mkdir -p "$LEARNING_DIR/logs"
mkdir -p "$HOME/Development/ai-implementations"

cd "$LEARNING_DIR"

# Parse arguments
MODE="normal"
DRY_RUN=""

for arg in "$@"; do
  case $arg in
    --deep-dive)
      MODE="deep-dive"
      ;;
    --dry-run)
      DRY_RUN="--dry-run"
      ;;
    --status)
      MODE="status"
      ;;
    --implement)
      MODE="implement"
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --deep-dive     Deep research mode (15 queries instead of 5)"
      echo "  --dry-run       Preview mode (no actual research)"
      echo "  --status        Show current status and expertise levels"
      echo "  --implement     Generate code for ready techniques"
      echo "  --help          Show this help"
      echo ""
      echo "Modes:"
      echo "  normal          Run 5 queries using Thompson Sampling (default)"
      echo "  deep-dive       Run 15 queries for comprehensive learning"
      echo "  status          Display dashboard with expertise levels"
      echo "  implement       Generate implementations for ready techniques"
      echo ""
      exit 0
      ;;
  esac
done

# Execute based on mode
case "$MODE" in
  status)
    echo "📊 DISPLAYING STATUS..."
    echo ""
    node perpetual-ai-expert-status.js
    ;;

  implement)
    echo "🔨 GENERATING IMPLEMENTATIONS..."
    echo ""
    node ai-implementation-generator.js
    ;;

  deep-dive)
    echo "🔬 STARTING DEEP DIVE RESEARCH (15 queries)..."
    echo ""
    node perpetual-ai-expert.js --deep-dive $DRY_RUN
    ;;

  normal)
    echo "🔬 STARTING RESEARCH (5 queries)..."
    echo ""
    node perpetual-ai-expert.js $DRY_RUN
    ;;
esac

# Show status after research
if [ "$MODE" = "normal" ] || [ "$MODE" = "deep-dive" ]; then
  if [ -z "$DRY_RUN" ]; then
    echo ""
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo "  RESEARCH COMPLETE - STATUS SUMMARY"
    echo "════════════════════════════════════════════════════════════════════════════════"
    echo ""
    node perpetual-ai-expert-status.js --coverage
    echo ""
    echo "Full status: $0 --status"
    echo "Implement:   $0 --implement"
    echo ""
  fi
fi

echo "✅ Complete."
echo ""
