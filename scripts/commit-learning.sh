#!/bin/bash
# Helper script to commit and push learning session results

if [ -z "$1" ]; then
    echo "Usage: ./scripts/commit-learning.sh \"Topic learned\""
    echo "Example: ./scripts/commit-learning.sh \"Rust ownership system\""
    exit 1
fi

TOPIC="$1"

# Check if in the right directory
if [ ! -d "memory" ]; then
    echo "Error: Must run from claude-global-skills root directory"
    exit 1
fi

# Show what changed
echo "📝 Changes in memory/:"
git status memory/ --short

# Add all memory changes
git add memory/

# Create commit
git commit -m "feat: Learned $TOPIC

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to remote
echo "🚀 Pushing to GitLab..."
git push

echo "✅ Learning session committed and pushed!"
echo "📚 View history: git log memory/"
