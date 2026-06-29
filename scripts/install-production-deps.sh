#!/usr/bin/env bash
# Install production dependencies for web-learn workflows

set -euo pipefail

SKILLS_DIR="${HOME}/.claude/repos/claude-global-skills"

echo "Installing production dependencies for Claude Code workflows..."
echo ""

# Check if directory exists
if [ ! -d "$SKILLS_DIR" ]; then
    echo "Error: Skills directory not found: $SKILLS_DIR"
    exit 1
fi

cd "$SKILLS_DIR"

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "Error: Node.js not found"
    echo ""
    echo "Install Node.js (v18+):"
    echo "  - Ubuntu/Debian: sudo apt install nodejs npm"
    echo "  - Fedora/RHEL: sudo dnf install nodejs npm"
    echo "  - macOS: brew install node"
    echo "  - Or download from: https://nodejs.org/"
    exit 1
fi

# Check Node version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "Error: Node.js version 18+ required (found v$NODE_VERSION)"
    echo "Upgrade Node.js: https://nodejs.org/"
    exit 1
fi

echo "✓ Node.js $(node -v) found"
echo ""

# Install dependencies
echo "Installing npm packages..."
echo ""

npm install

echo ""
echo "✅ Installation complete!"
echo ""
echo "Installed packages:"
echo "  - chromadb: Persistent vector database"
echo "  - @xenova/transformers: Semantic embeddings (384-dim)"
echo ""
echo "Usage:"
echo "  /web-learn-production"
echo ""
echo "Example:"
echo '  {urls: ["https://docs.python.org/"], query: "How does async work?"}'
echo ""
