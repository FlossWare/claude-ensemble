#!/bin/bash

# AI Learn - Extract global learnings from skills and workflows
# Uses multi-model consensus to extract and categorize knowledge

SKILLS_DIR="$HOME/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills"
WORKFLOW="extract-learning"

echo "🧠 Extracting learnings from skills and workflows..."
echo ""

cd "$SKILLS_DIR" || exit 1

# Run the extract-learning workflow
echo "Running multi-model learning extraction..."
claude workflow run "$WORKFLOW" || {
  echo "❌ Learning extraction failed"
  exit 1
}

echo ""
echo "✅ Learning extraction complete!"
echo ""
echo "📚 Learnings stored in: $SKILLS_DIR/memory/"
echo "🔄 Commit and push to share with all sessions, arbiters, and workers"
