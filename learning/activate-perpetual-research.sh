#!/bin/bash
# Activate perpetual AI research - become expert at everything

echo "🔬 ACTIVATING PERPETUAL AI RESEARCH"
echo "======================================"
echo ""
echo "Mission: Become expert at everything"
echo "Scope: All AI - most complex papers, techniques, implementations"
echo "Strategy: Investigate, learn, do"
echo ""

# Use existing web research infrastructure
RESEARCH_DIR="$HOME/.claude/learning/research"
cd "$RESEARCH_DIR" || exit 1

# Run comprehensive research session
echo "🚀 Launching comprehensive AI research..."
echo ""

node research-session.js \
  --topics-file="../research-topics.json" \
  --depth=comprehensive \
  --complexity=embrace-most-complex \
  --output=perpetual-ai-research.jsonl \
  --perpetual=true

echo ""
echo "✅ Research session complete"
echo "📊 Check findings: tail -20 $RESEARCH_DIR/perpetual-ai-research.jsonl"
echo ""
