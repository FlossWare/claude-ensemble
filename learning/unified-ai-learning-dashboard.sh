#!/bin/bash

# Unified AI Learning Dashboard
#
# Combines all AI learning systems:
# - Perpetual Web Learner (general web research)
# - Perpetual AI Expert (deep 70-query research)
# - Disseminator Learner (knowledge dissemination)
# - Self-Improvement (meta-learning)

LEARNING_DIR="$HOME/.claude/learning"

clear
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  UNIFIED AI LEARNING DASHBOARD"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# 1. Perpetual AI Expert Status
echo "┌─────────────────────────────────────────────────────────────────────────────┐"
echo "│ PERPETUAL AI EXPERT (70-Query Deep Research)                               │"
echo "└─────────────────────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LEARNING_DIR/research/perpetual-ai-expert-state.json" ]; then
  STATE=$(cat "$LEARNING_DIR/research/perpetual-ai-expert-state.json")

  RUNS=$(echo "$STATE" | jq -r '.runCount // 0')
  QUERIES=$(echo "$STATE" | jq -r '.totalQueriesResearched // 0')
  PAPERS=$(echo "$STATE" | jq -r '.totalPapersRead // 0')
  IMPLS=$(echo "$STATE" | jq -r '.totalImplementationsFound // 0')
  UNDERSTOOD=$(echo "$STATE" | jq -r '.totalTechniquesUnderstood // 0')
  IMPLEMENTED=$(echo "$STATE" | jq -r '.totalTechniquesImplemented // 0')
  READY=$(echo "$STATE" | jq -r '.readyToImplement | length')
  LAST_RUN=$(echo "$STATE" | jq -r '.lastRun // "never"')

  echo "Runs:                 $RUNS"
  echo "Last run:             $LAST_RUN"
  echo "Queries researched:   $QUERIES / 70"
  echo "Papers read:          $PAPERS"
  echo "Implementations:      $IMPLS"
  echo "Techniques learned:   $UNDERSTOOD"
  echo "Implemented:          $IMPLEMENTED"
  echo "Ready to implement:   $READY"

  # Top expertise
  echo ""
  echo "Top expertise areas:"
  echo "$STATE" | jq -r '.expertiseLevel | to_entries | sort_by(-.value) | .[0:3] | .[] | "  \(.key): \((.value * 100 | floor))%"'
else
  echo "Status: NOT INITIALIZED"
  echo "Run: $LEARNING_DIR/setup-perpetual-ai-expert.sh"
fi

echo ""

# 2. Perpetual Web Learner Status
echo "┌─────────────────────────────────────────────────────────────────────────────┐"
echo "│ PERPETUAL WEB LEARNER (General Research)                                   │"
echo "└─────────────────────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LEARNING_DIR/research/perpetual-state.json" ]; then
  WEB_STATE=$(cat "$LEARNING_DIR/research/perpetual-state.json")

  WEB_RUNS=$(echo "$WEB_STATE" | jq -r '.runCount // 0')
  WEB_FINDINGS=$(echo "$WEB_STATE" | jq -r '.totalFindingsStored // 0')
  WEB_LAST=$(echo "$WEB_STATE" | jq -r '.lastRun // "never"')

  echo "Runs:          $WEB_RUNS"
  echo "Last run:      $WEB_LAST"
  echo "Findings:      $WEB_FINDINGS"

  # Latest synthesis
  LATEST_SYNTH=$(ls -t "$LEARNING_DIR/research"/web-synthesis-*.jsonl 2>/dev/null | head -1)
  if [ -n "$LATEST_SYNTH" ]; then
    COUNT=$(wc -l < "$LATEST_SYNTH")
    echo "Latest file:   $(basename $LATEST_SYNTH) ($COUNT items)"
  fi
else
  echo "Status: NOT INITIALIZED"
  echo "Run: $LEARNING_DIR/perpetual-web-learner.sh"
fi

echo ""

# 3. Knowledge Base Statistics
echo "┌─────────────────────────────────────────────────────────────────────────────┐"
echo "│ KNOWLEDGE BASE                                                              │"
echo "└─────────────────────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LEARNING_DIR/research/ai-expert-knowledge.jsonl" ]; then
  KB_LINES=$(wc -l < "$LEARNING_DIR/research/ai-expert-knowledge.jsonl")
  KB_PAPERS=$(grep -c '"type":"research_paper"' "$LEARNING_DIR/research/ai-expert-knowledge.jsonl" || echo 0)
  KB_IMPLS=$(grep -c '"type":"implementation"' "$LEARNING_DIR/research/ai-expert-knowledge.jsonl" || echo 0)

  echo "Total learnings:       $KB_LINES"
  echo "Research papers:       $KB_PAPERS"
  echo "Implementations:       $KB_IMPLS"
else
  echo "Knowledge base: EMPTY"
fi

# Vector database
if [ -f "$LEARNING_DIR/research/ai-expert-vectors.jsonl" ]; then
  VEC_COUNT=$(wc -l < "$LEARNING_DIR/research/ai-expert-vectors.jsonl")
  echo "Vector embeddings:     $VEC_COUNT"
fi

echo ""

# 4. Implementation Queue
echo "┌─────────────────────────────────────────────────────────────────────────────┐"
echo "│ IMPLEMENTATION QUEUE                                                        │"
echo "└─────────────────────────────────────────────────────────────────────────────┘"
echo ""

if [ -f "$LEARNING_DIR/research/ai-implementation-queue.jsonl" ]; then
  QUEUE_SIZE=$(wc -l < "$LEARNING_DIR/research/ai-implementation-queue.jsonl")
  echo "Techniques ready:  $QUEUE_SIZE"

  if [ "$QUEUE_SIZE" -gt 0 ]; then
    echo ""
    echo "Top 3 ready to implement:"
    head -3 "$LEARNING_DIR/research/ai-implementation-queue.jsonl" | while read -r line; do
      QUERY=$(echo "$line" | jq -r '.query')
      CONFIDENCE=$(echo "$line" | jq -r '.confidence * 100 | floor')
      echo "  • $QUERY (${CONFIDENCE}%)"
    done
  fi
else
  echo "Queue: EMPTY"
fi

echo ""

# 5. Recent Activity
echo "┌─────────────────────────────────────────────────────────────────────────────┐"
echo "│ RECENT ACTIVITY                                                             │"
echo "└─────────────────────────────────────────────────────────────────────────────┘"
echo ""

# Recent log entries
if [ -f "$LEARNING_DIR/logs/perpetual-ai-expert.log" ]; then
  echo "AI Expert (last 5 lines):"
  tail -5 "$LEARNING_DIR/logs/perpetual-ai-expert.log" | sed 's/^/  /'
  echo ""
fi

if [ -f "$LEARNING_DIR/logs/perpetual-web-learner.log" ]; then
  echo "Web Learner (last 5 lines):"
  tail -5 "$LEARNING_DIR/logs/perpetual-web-learner.log" | sed 's/^/  /'
  echo ""
fi

# 6. Actions
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  QUICK ACTIONS"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "AI Expert:"
echo "  Research:    $LEARNING_DIR/activate-perpetual-ai-expert.sh"
echo "  Deep dive:   $LEARNING_DIR/activate-perpetual-ai-expert.sh --deep-dive"
echo "  Status:      $LEARNING_DIR/activate-perpetual-ai-expert.sh --status"
echo "  Implement:   $LEARNING_DIR/activate-perpetual-ai-expert.sh --implement"
echo ""
echo "Web Learner:"
echo "  Research:    $LEARNING_DIR/perpetual-web-learner.sh"
echo "  Status:      node $LEARNING_DIR/perpetual-web-learner.js --status"
echo ""
echo "Monitoring:"
echo "  This dash:   $LEARNING_DIR/unified-ai-learning-dashboard.sh"
echo "  Watch mode:  watch -n 30 $LEARNING_DIR/unified-ai-learning-dashboard.sh"
echo ""
echo "Documentation:"
echo "  AI Expert:   $LEARNING_DIR/PERPETUAL_AI_EXPERT.md"
echo "  Web Learn:   $LEARNING_DIR/ACTIVE_LEARNING_README.md"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
