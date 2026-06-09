#!/bin/bash
# Demo: Multi-AI Consensus with Visual Indicators
# Tests visual-indicators.sh concepts from skills-ai

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../shared/visual-indicators.sh"

# Demo multi-AI consensus with visual feedback
header "Multi-AI Consensus Demo"

info "This demo shows visual indicators for multi-model workflows"
echo ""

# Phase 1: Workers analyze
phase "Worker Analysis"

sleep 0.5
worker_start 0 "claude-opus-4"
sleep 1
worker_complete 0 "claude-opus-4"

sleep 0.5
worker_start 1 "claude-sonnet-4"
sleep 1
worker_complete 1 "claude-sonnet-4"

sleep 0.5
worker_start 2 "gpt-4o"
sleep 1
worker_complete 2 "gpt-4o"

# Phase 2: Arbiter synthesis
phase "Arbiter Synthesis"

sleep 0.5
arbiter_start "claude-opus-4"
sleep 1.5
arbiter_complete

# Show comparison
model_comparison
model_row "Opus" "High confidence finding" "$BLUE"
model_row "Sonnet" "High confidence finding" "$CYAN"
model_row "GPT-4o" "Medium confidence finding" "$PURPLE"
model_comparison_end

# Show consensus quality
echo ""
consensus_quality 0.87

# Summary
summary_box "Results Summary" \
  "Workers analyzed: 3" \
  "Consensus reached: Yes" \
  "Quality score: 0.87" \
  "Confidence: High"

success "Consensus demo complete!"
