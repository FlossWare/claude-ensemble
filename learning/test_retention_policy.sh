#!/bin/bash
# Test Retention Policy Implementation
# Verifies all components are working correctly

set -e

echo "======================================"
echo "Retention Policy Implementation Test"
echo "======================================"
echo ""

# Test 1: Check database schema
echo "Test 1: Database schema..."
if psql -h aio-01 -U postgres -d learning -c "\d learning.workflow_completions" > /dev/null 2>&1; then
    echo "✓ workflow_completions table exists"
else
    echo "✗ FAIL: workflow_completions table missing"
    echo "  Run: psql -h aio-01 -U postgres -d learning < /home/sfloess/.claude/learning/schema_workflow_completions.sql"
    exit 1
fi

# Test 2: Check cleanup function
echo "Test 2: Cleanup function..."
if psql -h aio-01 -U postgres -d learning -c "SELECT * FROM learning.cleanup_old_workflow_embeddings(90)" > /dev/null 2>&1; then
    echo "✓ cleanup_old_workflow_embeddings function exists"
else
    echo "✗ FAIL: cleanup function missing"
    echo "  Run: psql -h aio-01 -U postgres -d learning < /home/sfloess/.claude/learning/cleanup_workflow_embeddings.sql"
    exit 1
fi

# Test 3: Check sentence-transformers
echo "Test 3: sentence-transformers installation..."
if python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-mpnet-base-v2')" > /dev/null 2>&1; then
    echo "✓ sentence-transformers installed (all-mpnet-base-v2)"
else
    echo "✗ FAIL: sentence-transformers not installed"
    echo "  Run: bash /home/sfloess/.claude/learning/install_embeddings.sh"
    exit 1
fi

# Test 4: Check backup script integration
echo "Test 4: Backup script integration..."
if grep -q "cleanup_old_workflow_embeddings" /home/sfloess/bin/backup-learning-db.sh; then
    echo "✓ Retention cleanup integrated in backup script"
else
    echo "✗ FAIL: Backup script not updated"
    echo "  Check: /home/sfloess/bin/backup-learning-db.sh"
    exit 1
fi

# Test 5: Test JavaScript integration
echo "Test 5: JavaScript modules..."
if node -e "const { getWorkflowTracker } = require('/home/sfloess/.claude/learning/workflow-completion-tracker.js'); console.log('OK')" > /dev/null 2>&1; then
    echo "✓ workflow-completion-tracker.js module loads"
else
    echo "✗ FAIL: JavaScript module errors"
    echo "  Check: /home/sfloess/.claude/learning/workflow-completion-tracker.js"
    exit 1
fi

# Test 6: Test CLI tool
echo "Test 6: CLI tool..."
if node /home/sfloess/.claude/learning/retention-cli.js > /dev/null 2>&1; then
    echo "✓ retention-cli.js works"
else
    echo "✗ FAIL: CLI tool errors"
    echo "  Check: /home/sfloess/.claude/learning/retention-cli.js"
    exit 1
fi

# Test 7: Test embedding generation (quick)
echo "Test 7: Embedding generation..."
EMBEDDING_TEST=$(python3 -c "
from sentence_transformers import SentenceTransformer
import json
model = SentenceTransformer('all-mpnet-base-v2')
embedding = model.encode('test query').tolist()
print(len(embedding))
" 2>&1)

if [ "$EMBEDDING_TEST" = "768" ]; then
    echo "✓ Embedding generation works (768-dim)"
else
    echo "✗ FAIL: Embedding generation failed"
    echo "  Output: $EMBEDDING_TEST"
    exit 1
fi

# Summary
echo ""
echo "======================================"
echo "All Tests Passed!"
echo "======================================"
echo ""
echo "Next Steps:"
echo "1. Run manual cleanup test:"
echo "   psql -h aio-01 -U postgres -d learning -c \"SELECT * FROM learning.cleanup_old_workflow_embeddings(90);\""
echo ""
echo "2. Test workflow tracking:"
echo "   node /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/workflows/deep-research-with-tracking.mjs \"test query\""
echo ""
echo "3. Check statistics:"
echo "   node /home/sfloess/.claude/learning/retention-cli.js stats"
echo ""
echo "4. Verify backup runs daily at 3 AM:"
echo "   crontab -l | grep backup-learning-db.sh"
echo ""
