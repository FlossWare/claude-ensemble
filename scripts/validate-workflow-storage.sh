#!/bin/bash
#
# Validate workflow storage integration
# Tests that ai-consensus-weighted properly logs to PostgreSQL
#

set -e

echo "======================================================================"
echo "WORKFLOW STORAGE VALIDATION"
echo "======================================================================"
echo ""

# Check before count
echo "Step 1: Check current execution count..."
BEFORE_COUNT=$(psql -h laptop-01 -U sfloess -d learning -t -c "SELECT COUNT(*) FROM workflows.executions;")
echo "  Current executions: $BEFORE_COUNT"
echo ""

# Note: Can't easily run the workflow from shell script
# The workflow needs to be invoked through Claude Code workflow runtime
echo "Step 2: Manual validation required"
echo ""
echo "To validate the integration, run a consensus workflow:"
echo ""
echo "  Via Claude Code:"
echo "  Ask Claude: 'Run ai-consensus-weighted with task=\"What is 2+2?\" and models=[\"haiku\"]'"
echo ""
echo "  Or via skill:"
echo "  /ai-consensus \"What is the capital of France?\""
echo ""

echo "Step 3: After running a workflow, verify storage:"
echo ""
echo "  psql -h laptop-01 -U sfloess -d learning -c \\"
echo "    \"SELECT workflow_name, task_description, outcome, total_workers "
echo "     FROM workflows.executions "
echo "     ORDER BY created_at DESC LIMIT 5;\""
echo ""

echo "Step 4: Check worker results:"
echo ""
echo "  psql -h laptop-01 -U sfloess -d learning -c \\"
echo "    \"SELECT e.workflow_name, w.model, w.confidence "
echo "     FROM workflows.worker_results w "
echo "     JOIN workflows.executions e ON w.workflow_execution_id = e.id "
echo "     ORDER BY w.created_at DESC LIMIT 10;\""
echo ""

echo "Step 5: Check arbiter decisions:"
echo ""
echo "  psql -h laptop-01 -U sfloess -d learning -c \\"
echo "    \"SELECT e.workflow_name, a.arbiter_model, a.confidence "
echo "     FROM workflows.arbiter_decisions a "
echo "     JOIN workflows.executions e ON a.workflow_execution_id = e.id "
echo "     ORDER BY a.created_at DESC LIMIT 5;\""
echo ""

echo "======================================================================"
echo "VALIDATION READY"
echo "======================================================================"
echo ""
echo "Integration is complete. Run a workflow to test."
