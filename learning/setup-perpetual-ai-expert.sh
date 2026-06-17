#!/bin/bash

# Perpetual AI Expert System - Setup Script
#
# Sets up everything needed for autonomous, perpetual AI research

set -e

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  PERPETUAL AI EXPERT SYSTEM - SETUP"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

LEARNING_DIR="$HOME/.claude/learning"
RESEARCH_DIR="$LEARNING_DIR/research"
IMPL_DIR="$HOME/Development/ai-implementations"

# 1. Create directory structure
echo "📁 Creating directory structure..."
mkdir -p "$RESEARCH_DIR"
mkdir -p "$RESEARCH_DIR/sessions"
mkdir -p "$LEARNING_DIR/logs"
mkdir -p "$LEARNING_DIR/db"
mkdir -p "$IMPL_DIR"

# Create category directories for implementations
categories=(
  "advanced-reasoning"
  "multi-agent-orchestration"
  "meta-learning-automl"
  "efficient-inference"
  "rag-knowledge-systems"
  "training-fine-tuning"
  "mathematical-foundations"
  "systems-infrastructure"
  "evaluation-robustness"
  "domain-specific-ai"
)

for category in "${categories[@]}"; do
  mkdir -p "$IMPL_DIR/$category"
done

echo "✓ Directory structure created"
echo ""

# 2. Check dependencies
echo "🔍 Checking dependencies..."

# Node.js
if ! command -v node &> /dev/null; then
  echo "❌ Node.js not found. Please install Node.js 18+."
  exit 1
fi

node_version=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$node_version" -lt 18 ]; then
  echo "❌ Node.js version 18+ required. Current: $(node -v)"
  exit 1
fi
echo "✓ Node.js $(node -v)"

# Python (for implementations)
if ! command -v python3 &> /dev/null; then
  echo "⚠️  Python3 not found. Implementations will require Python."
else
  echo "✓ Python $(python3 --version)"
fi

# SQLite (for learning.db)
if ! command -v sqlite3 &> /dev/null; then
  echo "⚠️  SQLite3 not found. Installing..."
  if command -v apt-get &> /dev/null; then
    sudo apt-get update && sudo apt-get install -y sqlite3
  elif command -v dnf &> /dev/null; then
    sudo dnf install -y sqlite
  else
    echo "❌ Cannot install SQLite. Please install manually."
    exit 1
  fi
fi
echo "✓ SQLite $(sqlite3 --version)"

echo ""

# 3. Initialize databases
echo "🗄️  Initializing databases..."

cd "$LEARNING_DIR"

if [ ! -f "$LEARNING_DIR/db/learning.db" ]; then
  echo "Creating learning.db..."
  if [ -f "$LEARNING_DIR/init-learning-db.sql" ]; then
    sqlite3 "$LEARNING_DIR/db/learning.db" < "$LEARNING_DIR/init-learning-db.sql"
    echo "✓ learning.db created"
  else
    echo "⚠️  init-learning-db.sql not found, skipping"
  fi
else
  echo "✓ learning.db exists"
fi

echo ""

# 4. Create initial state file
echo "📊 Initializing state..."

STATE_FILE="$RESEARCH_DIR/perpetual-ai-expert-state.json"
if [ ! -f "$STATE_FILE" ]; then
  cat > "$STATE_FILE" <<'EOF'
{
  "version": 1,
  "created": "$(date -Iseconds)",
  "runCount": 0,
  "lastRun": null,
  "totalQueriesResearched": 0,
  "totalPapersRead": 0,
  "totalImplementationsFound": 0,
  "totalTechniquesUnderstood": 0,
  "totalTechniquesImplemented": 0,
  "categoryProgress": {},
  "queryEffectiveness": {},
  "thompsonState": {},
  "recentQueries": [],
  "readyToImplement": [],
  "implementationHistory": [],
  "deepLearnings": [],
  "expertiseLevel": {}
}
EOF
  echo "✓ State file created"
else
  echo "✓ State file exists"
fi

echo ""

# 5. Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x "$LEARNING_DIR/perpetual-ai-expert.js"
chmod +x "$LEARNING_DIR/perpetual-ai-expert-status.js"
chmod +x "$LEARNING_DIR/ai-implementation-generator.js"
chmod +x "$LEARNING_DIR/activate-perpetual-ai-expert.sh"
chmod +x "$LEARNING_DIR/setup-perpetual-ai-expert.sh"
echo "✓ Scripts are executable"
echo ""

# 6. Test basic functionality
echo "🧪 Testing basic functionality..."

echo "  Testing status script..."
if node "$LEARNING_DIR/perpetual-ai-expert-status.js" --help > /dev/null 2>&1; then
  echo "  ✓ Status script works"
else
  echo "  ❌ Status script failed"
  exit 1
fi

echo "  Testing implementation generator..."
if node "$LEARNING_DIR/ai-implementation-generator.js" --help > /dev/null 2>&1; then
  echo "  ✓ Implementation generator works"
else
  echo "  ❌ Implementation generator failed"
  exit 1
fi

echo "  Testing main research engine..."
if node "$LEARNING_DIR/perpetual-ai-expert.js" --help > /dev/null 2>&1; then
  echo "  ✓ Research engine works"
else
  echo "  ❌ Research engine failed"
  exit 1
fi

echo ""

# 7. Optional: Install systemd timer
echo "⏰ Systemd Timer Setup (optional)"
echo ""
echo "To run research automatically every 6 hours:"
echo ""
echo "  sudo cp $LEARNING_DIR/perpetual-ai-expert.service /etc/systemd/system/"
echo "  sudo cp $LEARNING_DIR/perpetual-ai-expert.timer /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable perpetual-ai-expert.timer"
echo "  sudo systemctl start perpetual-ai-expert.timer"
echo ""
echo "Check status: sudo systemctl status perpetual-ai-expert.timer"
echo ""

# 8. Summary
echo "════════════════════════════════════════════════════════════════════════════════"
echo "  SETUP COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Directory Structure:"
echo "  Research:         $RESEARCH_DIR"
echo "  Implementations:  $IMPL_DIR"
echo "  Logs:             $LEARNING_DIR/logs"
echo "  Database:         $LEARNING_DIR/db/learning.db"
echo ""
echo "Scripts:"
echo "  Main:             $LEARNING_DIR/activate-perpetual-ai-expert.sh"
echo "  Status:           $LEARNING_DIR/perpetual-ai-expert-status.js"
echo "  Implement:        $LEARNING_DIR/ai-implementation-generator.js"
echo ""
echo "Next Steps:"
echo ""
echo "1. Run initial deep research:"
echo "   $LEARNING_DIR/activate-perpetual-ai-expert.sh --deep-dive"
echo ""
echo "2. Check status:"
echo "   $LEARNING_DIR/activate-perpetual-ai-expert.sh --status"
echo ""
echo "3. Generate implementations:"
echo "   $LEARNING_DIR/activate-perpetual-ai-expert.sh --implement"
echo ""
echo "4. Set up continuous operation (optional):"
echo "   # See systemd timer instructions above"
echo ""
echo "Documentation: $LEARNING_DIR/PERPETUAL_AI_EXPERT.md"
echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Mission: Become expert at EVERYTHING in AI"
echo "Strategy: Investigate → Learn → DO"
echo "Status: READY"
echo ""
