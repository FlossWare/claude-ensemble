#!/usr/bin/env bash
#
# test-lis-dashboard.sh - Test LIS dashboard with sample data
#
# Creates sample execution data if needed, then displays the dashboard

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Testing LIS Dashboard..."
echo

# ============================================================================
# CREATE SAMPLE DATA IF NEEDED
# ============================================================================

node --input-type=module <<'EOF'
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = process.env.REPO_ROOT || join(__dirname, '..');

const dbPath = join(REPO_ROOT, 'learning', 'db.js');
const { getDb, logExecution, getExecutionCount } = await import(dbPath);

const db = getDb();
if (!db) {
  console.error('❌ Database not available');
  process.exit(1);
}

const existingCount = getExecutionCount();
console.log(`Current executions: ${existingCount}`);

if (existingCount < 20) {
  console.log('Creating sample data for testing...\n');

  const models = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'];
  const tasks = ['code_review', 'code_solve', 'consensus', 'web_learn'];
  const roles = ['worker', 'arbiter'];

  // Generate 50 sample executions with realistic patterns
  for (let i = 0; i < 50; i++) {
    const model = models[Math.floor(Math.random() * models.length)];
    const task = tasks[Math.floor(Math.random() * tasks.length)];
    const role = Math.random() > 0.3 ? 'worker' : 'arbiter';

    // Simulate quality improvement over time
    const timeProgress = i / 50;
    const baseQuality = 0.70 + (timeProgress * 0.15) + (Math.random() * 0.10);
    const quality = Math.min(0.99, Math.max(0.50, baseQuality));

    // Simulate cost reduction over time
    const baseCost = 0.005 - (timeProgress * 0.002) + (Math.random() * 0.001);
    const cost = Math.max(0.0001, baseCost);

    // Simulate speed improvement over time
    const baseDuration = 5000 - (timeProgress * 1000) + (Math.random() * 1000);
    const duration = Math.max(500, baseDuration);

    const confidence = quality + (Math.random() * 0.1 - 0.05);
    const outcome = Math.random() > 0.1 ? 'success' : 'failed';

    // Create timestamp spread across last 30 days
    const timestamp = new Date();
    timestamp.setDate(timestamp.getDate() - Math.floor(Math.random() * 30));

    logExecution({
      model,
      model_role: role,
      task_type: task,
      quality_score: quality,
      confidence: Math.min(0.99, Math.max(0.01, confidence)),
      cost_usd: cost,
      duration_ms: Math.round(duration),
      outcome,
      was_selected: role === 'arbiter' ? null : (Math.random() > 0.5 ? 1 : 0),
      consensus_score: role === 'arbiter' ? null : (0.7 + Math.random() * 0.25),
      timestamp: timestamp.toISOString()
    });
  }

  console.log('✓ Created 50 sample executions\n');
} else {
  console.log('✓ Sufficient data already exists\n');
}

EOF

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Test 1: Standard Dashboard View"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

"$SCRIPT_DIR/learning-dashboard.sh"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Test 2: Compact View"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

"$SCRIPT_DIR/learning-dashboard.sh" --compact

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Test 3: 7-Day Trend"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

"$SCRIPT_DIR/learning-dashboard.sh" --days 7 --compact

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Test 4: JSON Export"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

EXPORT_FILE="/tmp/lis-dashboard-test.json"
"$SCRIPT_DIR/learning-dashboard.sh" --json --export "$EXPORT_FILE" > /dev/null 2>&1

if [[ -f "$EXPORT_FILE" ]]; then
  echo "✓ JSON export successful"
  echo "  File: $EXPORT_FILE"
  echo "  Size: $(wc -c < "$EXPORT_FILE") bytes"
  echo
  echo "Sample data:"
  head -20 "$EXPORT_FILE"
  echo "..."
  rm "$EXPORT_FILE"
else
  echo "✗ JSON export failed"
fi

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  All Tests Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
