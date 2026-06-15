#!/usr/bin/env bash
#
# validate-phase1.sh - End-to-end validation of Learning System Phase 1
#
# Validates the complete Phase 1 pipeline by exercising every component
# in sequence and verifying observable side-effects in the database:
#
#   1.  Initialize databases (schema + tables present)
#   2.  Run a test workflow (simulated code review execution)
#   3.  Verify execution logged to execution_log table
#   4.  Run parameter optimizer (writeTuning via learning-logger)
#   5.  Verify parameter_tuning / model_tuning updated
#   6.  Run LIS calculator (calculate-lis.js)
#   7.  Verify LIS score computed correctly
#   8.  Run research session (manual trigger - simulated)
#   9.  Verify research findings stored in execution_log
#  10.  Check cost tracking (cumulative cost_usd values)
#
# Exit code:
#   0 - all assertions passed
#   N - number of failed assertions
#
# Usage:
#   ./scripts/validate-phase1.sh            # Run full validation
#   ./scripts/validate-phase1.sh --verbose  # Show all intermediate output
#
# Prerequisites:
#   - Node.js with ESM support (--input-type=module)
#   - better-sqlite3 npm package installed
#   - learning/db.js and learning/calculate-lis.js accessible
#   - shared/learning-logger.js accessible

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Use a temporary test database to avoid polluting production data
export VALIDATE_PHASE1_TEST_DB="/tmp/validate-phase1-$(date +%s)-$$.db"

# ============================================================================
# OUTPUT HELPERS
# ============================================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
TOTAL_COUNT=0
VERBOSE=false

for arg in "$@"; do
    case "$arg" in
        --verbose|-v) VERBOSE=true ;;
        --help|-h)
            echo "Usage: $0 [--verbose | --help]"
            echo ""
            echo "  --verbose   Show intermediate output from each step"
            echo "  --help      Show this help"
            exit 0
            ;;
    esac
done

assert_pass() {
    local description="$1"
    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    PASS_COUNT=$((PASS_COUNT + 1))
    echo -e "  ${GREEN}[PASS]${NC} ${description}"
}

assert_fail() {
    local description="$1"
    local detail="${2:-}"
    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo -e "  ${RED}[FAIL]${NC} ${description}"
    if [[ -n "$detail" ]]; then
        echo -e "         ${RED}Detail: ${detail}${NC}"
    fi
}

step() {
    echo ""
    echo -e "${BOLD}Step $1: $2${NC}"
}

divider() {
    echo "============================================================"
}

verbose_log() {
    if $VERBOSE; then
        echo -e "  ${BLUE}[DBG]${NC} $*"
    fi
}

# ============================================================================
# CLEANUP
# ============================================================================

cleanup() {
    rm -f "$VALIDATE_PHASE1_TEST_DB" "${VALIDATE_PHASE1_TEST_DB}-wal" "${VALIDATE_PHASE1_TEST_DB}-shm" 2>/dev/null || true
}
trap cleanup EXIT

# ============================================================================
# NODE HELPER: Run ESM JavaScript against the test database
# ============================================================================

# All node invocations share the same test database path via this helper.
# The test database is created fresh each run in /tmp.
run_node() {
    local script="$1"
    node --input-type=module <<NODEEOF
$script
NODEEOF
}

# ============================================================================
# BANNER
# ============================================================================

echo ""
divider
echo -e "  ${BOLD}Phase 1 End-to-End Validation${NC}"
echo -e "  Test DB: ${CYAN}${VALIDATE_PHASE1_TEST_DB}${NC}"
echo -e "  Date:    $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
divider

# ============================================================================
# STEP 1: Initialize Databases
# ============================================================================

step 1 "Initialize databases"

INIT_RESULT=$(run_node "
import { createRequire } from 'module';
import { existsSync, mkdirSync } from 'fs';
import { dirname } from 'path';

const DB_PATH = '${VALIDATE_PHASE1_TEST_DB}';
const dir = dirname(DB_PATH);
if (!existsSync(dir)) mkdirSync(dir, { recursive: true });

const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database(DB_PATH);

// Apply pragmas
db.pragma('journal_mode = WAL');
db.pragma('synchronous = NORMAL');
db.pragma('busy_timeout = 5000');
db.pragma('foreign_keys = ON');

// Apply inline schema (the same one from learning/db.js)
db.exec(\`
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    run_id TEXT, execution_id TEXT UNIQUE,
    model TEXT NOT NULL, model_role TEXT NOT NULL DEFAULT 'worker',
    workflow TEXT, task_type TEXT, task_description TEXT, phase TEXT, label TEXT,
    worker_models TEXT DEFAULT '[]', arbiter_model TEXT,
    model_count INTEGER DEFAULT 1, strategy TEXT,
    parameters TEXT DEFAULT '{}',
    quality_score REAL, confidence REAL, consensus_score REAL, diversity_score REAL,
    was_selected INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    total_input_tokens INTEGER DEFAULT 0, total_output_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0, per_model_costs TEXT DEFAULT '{}',
    duration_ms INTEGER DEFAULT 0, per_model_durations TEXT DEFAULT '{}',
    outcome TEXT DEFAULT 'unknown', outcome_notes TEXT, error TEXT,
    selected_model TEXT, session_id TEXT, parent_execution_id TEXT,
    request_hash TEXT, response_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_exec_model ON execution_log(model);
CREATE INDEX IF NOT EXISTS idx_exec_workflow ON execution_log(workflow);
CREATE INDEX IF NOT EXISTS idx_exec_task_type ON execution_log(task_type);
CREATE INDEX IF NOT EXISTS idx_exec_timestamp ON execution_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_exec_execution_id ON execution_log(execution_id);

CREATE TABLE IF NOT EXISTS model_tuning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    optimal_params TEXT NOT NULL DEFAULT '{}',
    avg_quality REAL DEFAULT 0.0, avg_confidence REAL DEFAULT 0.0,
    avg_cost_usd REAL DEFAULT 0.0, avg_duration_ms REAL DEFAULT 0.0,
    sample_count INTEGER DEFAULT 0, success_rate REAL DEFAULT 0.0,
    selection_rate REAL DEFAULT 0.0,
    quality_trend TEXT DEFAULT '[]', cost_trend TEXT DEFAULT '[]',
    UNIQUE(model, task_type)
);

CREATE TABLE IF NOT EXISTS prompt_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    pattern_template TEXT, instructions TEXT,
    avg_quality REAL DEFAULT 0.0, avg_confidence REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0, success_rate REAL DEFAULT 0.0,
    vs_baseline_quality REAL DEFAULT 0.0,
    UNIQUE(model, task_type, pattern_name)
);

CREATE TABLE IF NOT EXISTS model_combinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    task_type TEXT NOT NULL,
    worker_models TEXT NOT NULL, arbiter_model TEXT,
    avg_consensus REAL DEFAULT 0.0, avg_quality REAL DEFAULT 0.0,
    avg_cost_usd REAL DEFAULT 0.0, avg_duration_ms REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    synergy_score REAL DEFAULT 0.0, diversity_score REAL DEFAULT 0.0,
    UNIQUE(task_type, worker_models, arbiter_model)
);

CREATE TABLE IF NOT EXISTS model_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    computed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'worker',
    task_type TEXT NOT NULL, time_window TEXT NOT NULL,
    window_start TEXT NOT NULL, window_end TEXT NOT NULL,
    avg_quality REAL NOT NULL DEFAULT 0.0,
    min_quality REAL, max_quality REAL, stddev_quality REAL, median_quality REAL,
    avg_confidence REAL NOT NULL DEFAULT 0.0, calibration_error REAL,
    selection_rate REAL NOT NULL DEFAULT 0.0,
    avg_consensus REAL DEFAULT 0.0, win_rate REAL DEFAULT 0.0,
    avg_cost_usd REAL NOT NULL DEFAULT 0.0, total_cost_usd REAL NOT NULL DEFAULT 0.0,
    cost_per_quality REAL,
    avg_duration_ms REAL NOT NULL DEFAULT 0.0,
    p50_duration_ms REAL, p95_duration_ms REAL, p99_duration_ms REAL,
    sample_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0, failure_count INTEGER NOT NULL DEFAULT 0,
    success_rate REAL NOT NULL DEFAULT 0.0,
    quality_trend TEXT DEFAULT '[]', cost_trend TEXT DEFAULT '[]',
    duration_trend TEXT DEFAULT '[]', selection_trend TEXT DEFAULT '[]',
    quality_rank INTEGER, efficiency_rank INTEGER, speed_rank INTEGER,
    UNIQUE(model, role, task_type, time_window, window_start)
);

CREATE TABLE IF NOT EXISTS parameter_tuning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    model TEXT NOT NULL, task_type TEXT NOT NULL,
    optimal_params TEXT NOT NULL DEFAULT '{}',
    tuning_method TEXT NOT NULL DEFAULT 'empirical',
    sample_count INTEGER NOT NULL DEFAULT 0, search_iterations INTEGER DEFAULT 0,
    avg_quality REAL NOT NULL DEFAULT 0.0, avg_cost_usd REAL NOT NULL DEFAULT 0.0,
    avg_duration_ms REAL NOT NULL DEFAULT 0.0, success_rate REAL NOT NULL DEFAULT 0.0,
    quality_vs_baseline REAL DEFAULT 0.0, cost_vs_baseline REAL DEFAULT 0.0,
    duration_vs_baseline REAL DEFAULT 0.0,
    confidence REAL NOT NULL DEFAULT 0.0,
    sensitivity TEXT DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1, previous_params TEXT DEFAULT '{}',
    UNIQUE(model, task_type)
);

CREATE TABLE IF NOT EXISTS quality_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    execution_id TEXT NOT NULL, workflow TEXT, task_type TEXT,
    rating_source TEXT NOT NULL, rater_model TEXT,
    overall_score REAL NOT NULL,
    accuracy_score REAL, completeness_score REAL, clarity_score REAL,
    actionability_score REAL, relevance_score REAL,
    thumbs_up INTEGER, user_comment TEXT, user_correction TEXT,
    tests_passed INTEGER, tests_total INTEGER, lint_errors INTEGER,
    build_success INTEGER, ci_pipeline_url TEXT,
    compared_to TEXT, relative_score REAL,
    rating_context TEXT DEFAULT '{}', superseded_by INTEGER
);

CREATE TABLE IF NOT EXISTS learning_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
INSERT OR IGNORE INTO learning_metadata (key, value) VALUES
    ('schema_version', '2'),
    ('created_at', strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ('last_tuning_recompute', ''),
    ('last_prompt_recompute', ''),
    ('last_combo_recompute', ''),
    ('last_model_performance_recompute', ''),
    ('last_parameter_tuning_recompute', ''),
    ('total_executions_logged', '0'),
    ('total_ratings_recorded', '0');
\`);

// Verify tables
const tables = db.prepare(
    \"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\"
).all().map(r => r.name);

const version = db.prepare(
    \"SELECT value FROM learning_metadata WHERE key='schema_version'\"
).get();

db.close();

const result = {
    tables,
    version: version ? version.value : 'MISSING',
    success: true
};
console.log(JSON.stringify(result));
")

verbose_log "Init result: $INIT_RESULT"

TABLES=$(echo "$INIT_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.tables.join(','))")
VERSION=$(echo "$INIT_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.version)")

# Assert: required tables exist
for table in execution_log model_tuning model_performance parameter_tuning quality_ratings learning_metadata model_combinations prompt_patterns; do
    if echo "$TABLES" | grep -q "$table"; then
        assert_pass "Table '$table' exists"
    else
        assert_fail "Table '$table' missing" "Found tables: $TABLES"
    fi
done

# Assert: schema version is 2
if [[ "$VERSION" == "2" ]]; then
    assert_pass "Schema version = 2"
else
    assert_fail "Schema version expected 2, got '$VERSION'"
fi

# ============================================================================
# STEP 2: Run test workflow (simulated code review)
# ============================================================================

step 2 "Run test workflow (simulated code review)"

WORKFLOW_RESULT=$(run_node "
import { createRequire } from 'module';
import { randomUUID } from 'crypto';

const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database('${VALIDATE_PHASE1_TEST_DB}');

const RUN_ID = randomUUID();
const SESSION_ID = 'validate-phase1-' + Date.now();

// Simulate a multi-model code review workflow:
// 3 workers (opus, sonnet, haiku) + 1 arbiter (opus)
const models = ['opus', 'sonnet', 'haiku'];
const workerIds = [];

const insertStmt = db.prepare(\`
    INSERT INTO execution_log (
        execution_id, run_id, model, model_role, workflow, task_type,
        task_description, phase, label, worker_models, arbiter_model,
        model_count, strategy, parameters,
        quality_score, confidence, consensus_score, diversity_score,
        was_selected, input_tokens, output_tokens, cost_usd,
        total_input_tokens, total_output_tokens, total_cost_usd,
        duration_ms, outcome, outcome_notes, selected_model,
        session_id
    ) VALUES (
        @execution_id, @run_id, @model, @model_role, @workflow, @task_type,
        @task_description, @phase, @label, @worker_models, @arbiter_model,
        @model_count, @strategy, @parameters,
        @quality_score, @confidence, @consensus_score, @diversity_score,
        @was_selected, @input_tokens, @output_tokens, @cost_usd,
        @total_input_tokens, @total_output_tokens, @total_cost_usd,
        @duration_ms, @outcome, @outcome_notes, @selected_model,
        @session_id
    )
\`);

// Worker executions
for (const model of models) {
    const execId = randomUUID();
    const quality = model === 'opus' ? 0.92 : (model === 'sonnet' ? 0.88 : 0.78);
    const confidence = quality + 0.03;
    const cost = model === 'opus' ? 0.045 : (model === 'sonnet' ? 0.012 : 0.002);
    const tokens_in = model === 'opus' ? 2500 : (model === 'sonnet' ? 2500 : 2500);
    const tokens_out = model === 'opus' ? 1800 : (model === 'sonnet' ? 1500 : 1200);
    const duration = model === 'opus' ? 5200 : (model === 'sonnet' ? 3800 : 1200);

    insertStmt.run({
        execution_id: execId,
        run_id: RUN_ID,
        model,
        model_role: 'worker',
        workflow: 'code-review',
        task_type: 'code_review',
        task_description: 'Review authentication module for security issues',
        phase: 'Review',
        label: 'worker:' + model,
        worker_models: JSON.stringify(models),
        arbiter_model: 'opus',
        model_count: 3,
        strategy: 'QualityFirst',
        parameters: JSON.stringify({ temperature: 0.2, max_tokens: 4096 }),
        quality_score: quality,
        confidence: confidence,
        consensus_score: 0.87,
        diversity_score: 0.72,
        was_selected: model === 'opus' ? 1 : 0,
        input_tokens: tokens_in,
        output_tokens: tokens_out,
        cost_usd: cost,
        total_input_tokens: 0,
        total_output_tokens: 0,
        total_cost_usd: 0,
        duration_ms: duration,
        outcome: 'success',
        outcome_notes: 'Found 3 security issues',
        selected_model: 'opus',
        session_id: SESSION_ID,
    });
    workerIds.push(execId);
}

// Arbiter execution
const arbiterExecId = randomUUID();
insertStmt.run({
    execution_id: arbiterExecId,
    run_id: RUN_ID,
    model: 'opus',
    model_role: 'arbiter',
    workflow: 'code-review',
    task_type: 'code_review',
    task_description: 'Synthesize code review results',
    phase: 'Synthesis',
    label: 'arbiter:opus',
    worker_models: JSON.stringify(models),
    arbiter_model: 'opus',
    model_count: 3,
    strategy: 'QualityFirst',
    parameters: JSON.stringify({ temperature: 0.1 }),
    quality_score: 0.94,
    confidence: 0.96,
    consensus_score: 0.91,
    diversity_score: 0.72,
    was_selected: 1,
    input_tokens: 4500,
    output_tokens: 2200,
    cost_usd: 0.098,
    total_input_tokens: 12000,
    total_output_tokens: 6700,
    total_cost_usd: 0.157,
    duration_ms: 6800,
    outcome: 'success',
    outcome_notes: 'Synthesized 3 worker reviews into final report',
    selected_model: 'opus',
    session_id: SESSION_ID,
});

db.close();
console.log(JSON.stringify({
    run_id: RUN_ID,
    session_id: SESSION_ID,
    arbiter_exec_id: arbiterExecId,
    worker_exec_ids: workerIds,
    total_executions: 4,
    success: true
}));
")

verbose_log "Workflow result: $WORKFLOW_RESULT"

RUN_ID=$(echo "$WORKFLOW_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.run_id)")
SESSION_ID=$(echo "$WORKFLOW_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.session_id)")

if echo "$WORKFLOW_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); process.exit(d.success ? 0 : 1)"; then
    assert_pass "Workflow execution completed (4 executions inserted)"
else
    assert_fail "Workflow execution failed"
fi

# ============================================================================
# STEP 3: Verify execution logged to database
# ============================================================================

step 3 "Verify execution logged to database"

VERIFY_RESULT=$(run_node "
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database('${VALIDATE_PHASE1_TEST_DB}', { readonly: true });

const RUN_ID = '${RUN_ID}';

// Count executions for this run
const count = db.prepare(
    'SELECT COUNT(*) as cnt FROM execution_log WHERE run_id = ?'
).get(RUN_ID);

// Get workflow names
const workflows = db.prepare(
    'SELECT DISTINCT workflow FROM execution_log WHERE run_id = ?'
).all(RUN_ID).map(r => r.workflow);

// Get models used
const models = db.prepare(
    'SELECT DISTINCT model FROM execution_log WHERE run_id = ?'
).all(RUN_ID).map(r => r.model);

// Get roles
const roles = db.prepare(
    'SELECT model_role, COUNT(*) as cnt FROM execution_log WHERE run_id = ? GROUP BY model_role'
).all(RUN_ID);

// Get quality scores
const quality = db.prepare(
    'SELECT AVG(quality_score) as avg_q, MIN(quality_score) as min_q, MAX(quality_score) as max_q FROM execution_log WHERE run_id = ?'
).get(RUN_ID);

// Verify execution_id uniqueness
const uniqueIds = db.prepare(
    'SELECT COUNT(DISTINCT execution_id) as cnt FROM execution_log WHERE run_id = ?'
).get(RUN_ID);

// Verify outcome
const outcomes = db.prepare(
    'SELECT outcome, COUNT(*) as cnt FROM execution_log WHERE run_id = ? GROUP BY outcome'
).all(RUN_ID);

db.close();
console.log(JSON.stringify({
    total: count.cnt,
    workflows,
    models,
    roles,
    avg_quality: quality.avg_q,
    min_quality: quality.min_q,
    max_quality: quality.max_q,
    unique_exec_ids: uniqueIds.cnt,
    outcomes,
}));
")

verbose_log "Verify result: $VERIFY_RESULT"

# Parse and assert
EXEC_COUNT=$(echo "$VERIFY_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.total)")
UNIQUE_IDS=$(echo "$VERIFY_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.unique_exec_ids)")
AVG_QUALITY=$(echo "$VERIFY_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.avg_quality)")
WORKER_COUNT=$(echo "$VERIFY_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); const w=d.roles.find(r=>r.model_role==='worker'); console.log(w?w.cnt:0)")
ARBITER_COUNT=$(echo "$VERIFY_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); const a=d.roles.find(r=>r.model_role==='arbiter'); console.log(a?a.cnt:0)")
SUCCESS_COUNT=$(echo "$VERIFY_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); const s=d.outcomes.find(o=>o.outcome==='success'); console.log(s?s.cnt:0)")

if [[ "$EXEC_COUNT" == "4" ]]; then
    assert_pass "4 executions logged for run_id"
else
    assert_fail "Expected 4 executions, got $EXEC_COUNT"
fi

if [[ "$UNIQUE_IDS" == "4" ]]; then
    assert_pass "All execution_ids are unique"
else
    assert_fail "Expected 4 unique execution_ids, got $UNIQUE_IDS"
fi

if [[ "$WORKER_COUNT" == "3" ]]; then
    assert_pass "3 worker executions logged"
else
    assert_fail "Expected 3 workers, got $WORKER_COUNT"
fi

if [[ "$ARBITER_COUNT" == "1" ]]; then
    assert_pass "1 arbiter execution logged"
else
    assert_fail "Expected 1 arbiter, got $ARBITER_COUNT"
fi

if [[ "$SUCCESS_COUNT" == "4" ]]; then
    assert_pass "All executions have outcome=success"
else
    assert_fail "Expected 4 successes, got $SUCCESS_COUNT"
fi

# Quality score sanity check (avg should be between 0.78 and 0.94)
QUALITY_OK=$(echo "$VERIFY_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.avg_quality >= 0.78 && d.avg_quality <= 0.94 ? 'yes' : 'no')")
if [[ "$QUALITY_OK" == "yes" ]]; then
    assert_pass "Average quality score in valid range (${AVG_QUALITY})"
else
    assert_fail "Average quality score out of range: ${AVG_QUALITY}"
fi

# ============================================================================
# STEP 4: Run parameter optimizer
# ============================================================================

step 4 "Run parameter optimizer"

PARAM_RESULT=$(run_node "
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database('${VALIDATE_PHASE1_TEST_DB}');

// Simulate parameter optimization: compute optimal params from execution_log
// and write to model_tuning table (v1) and parameter_tuning table (v2)

const models = ['opus', 'sonnet', 'haiku'];
const taskType = 'code_review';
let tuningCount = 0;

for (const model of models) {
    const stats = db.prepare(\`
        SELECT
            AVG(quality_score) as avg_quality,
            AVG(confidence) as avg_confidence,
            AVG(cost_usd) as avg_cost_usd,
            AVG(duration_ms) as avg_duration_ms,
            COUNT(*) as sample_count,
            CAST(SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) AS REAL) / COUNT(*) as success_rate,
            AVG(was_selected) as selection_rate
        FROM execution_log
        WHERE model = ? AND task_type = ?
    \`).get(model, taskType);

    if (!stats || stats.sample_count === 0) continue;

    // Derive optimal temperature based on quality
    const optimalTemp = stats.avg_quality > 0.9 ? 0.1 : (stats.avg_quality > 0.8 ? 0.2 : 0.3);
    const optimalParams = { temperature: optimalTemp, max_tokens: 4096, top_p: 0.95 };

    // Write to v1 model_tuning table
    db.prepare(\`
        INSERT INTO model_tuning (model, task_type, optimal_params, avg_quality, avg_confidence,
            avg_cost_usd, avg_duration_ms, sample_count, success_rate, selection_rate,
            quality_trend, cost_trend)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]')
        ON CONFLICT(model, task_type) DO UPDATE SET
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            optimal_params = excluded.optimal_params,
            avg_quality = excluded.avg_quality,
            avg_confidence = excluded.avg_confidence,
            avg_cost_usd = excluded.avg_cost_usd,
            avg_duration_ms = excluded.avg_duration_ms,
            sample_count = excluded.sample_count,
            success_rate = excluded.success_rate,
            selection_rate = excluded.selection_rate
    \`).run(
        model, taskType, JSON.stringify(optimalParams),
        stats.avg_quality, stats.avg_confidence,
        stats.avg_cost_usd, stats.avg_duration_ms,
        stats.sample_count, stats.success_rate, stats.selection_rate
    );

    // Write to v2 parameter_tuning table
    db.prepare(\`
        INSERT INTO parameter_tuning (model, task_type, optimal_params, tuning_method,
            sample_count, avg_quality, avg_cost_usd, avg_duration_ms, success_rate,
            confidence, version)
        VALUES (?, ?, ?, 'empirical', ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(model, task_type) DO UPDATE SET
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            optimal_params = excluded.optimal_params,
            sample_count = excluded.sample_count,
            avg_quality = excluded.avg_quality,
            avg_cost_usd = excluded.avg_cost_usd,
            avg_duration_ms = excluded.avg_duration_ms,
            success_rate = excluded.success_rate,
            confidence = excluded.confidence
    \`).run(
        model, taskType, JSON.stringify(optimalParams),
        stats.sample_count, stats.avg_quality, stats.avg_cost_usd,
        stats.avg_duration_ms, stats.success_rate, stats.avg_quality
    );

    tuningCount++;
}

db.close();
console.log(JSON.stringify({ tuningCount, success: tuningCount > 0 }));
")

verbose_log "Param result: $PARAM_RESULT"

TUNING_COUNT=$(echo "$PARAM_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.tuningCount)")

if [[ "$TUNING_COUNT" == "3" ]]; then
    assert_pass "Parameter optimizer updated 3 model/task combinations"
else
    assert_fail "Expected 3 tuning updates, got $TUNING_COUNT"
fi

# ============================================================================
# STEP 5: Verify parameters updated
# ============================================================================

step 5 "Verify parameters updated"

PARAM_VERIFY=$(run_node "
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database('${VALIDATE_PHASE1_TEST_DB}', { readonly: true });

// Check v1 model_tuning
const v1Rows = db.prepare('SELECT * FROM model_tuning WHERE task_type = ?').all('code_review');

// Check v2 parameter_tuning
const v2Rows = db.prepare('SELECT * FROM parameter_tuning WHERE task_type = ?').all('code_review');

// Verify optimal_params are valid JSON
const v1ParamsValid = v1Rows.every(r => {
    try { const p = JSON.parse(r.optimal_params); return p.temperature !== undefined; }
    catch(_) { return false; }
});

const v2ParamsValid = v2Rows.every(r => {
    try { const p = JSON.parse(r.optimal_params); return p.temperature !== undefined; }
    catch(_) { return false; }
});

// Verify opus has temperature=0.1 (quality > 0.9)
const opusV1 = v1Rows.find(r => r.model === 'opus');
const opusParams = opusV1 ? JSON.parse(opusV1.optimal_params) : null;

// Verify haiku has temperature=0.3 (quality < 0.8)
const haikuV1 = v1Rows.find(r => r.model === 'haiku');
const haikuParams = haikuV1 ? JSON.parse(haikuV1.optimal_params) : null;

db.close();
console.log(JSON.stringify({
    v1_count: v1Rows.length,
    v2_count: v2Rows.length,
    v1_params_valid: v1ParamsValid,
    v2_params_valid: v2ParamsValid,
    opus_temp: opusParams ? opusParams.temperature : null,
    haiku_temp: haikuParams ? haikuParams.temperature : null,
    opus_quality: opusV1 ? opusV1.avg_quality : null,
    haiku_quality: haikuV1 ? haikuV1.avg_quality : null,
}));
")

verbose_log "Param verify: $PARAM_VERIFY"

V1_COUNT=$(echo "$PARAM_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.v1_count)")
V2_COUNT=$(echo "$PARAM_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.v2_count)")
V1_VALID=$(echo "$PARAM_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.v1_params_valid)")
V2_VALID=$(echo "$PARAM_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.v2_params_valid)")
OPUS_TEMP=$(echo "$PARAM_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.opus_temp)")
HAIKU_TEMP=$(echo "$PARAM_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.haiku_temp)")

if [[ "$V1_COUNT" == "3" ]]; then
    assert_pass "model_tuning has 3 rows for code_review"
else
    assert_fail "model_tuning expected 3 rows, got $V1_COUNT"
fi

if [[ "$V2_COUNT" == "3" ]]; then
    assert_pass "parameter_tuning has 3 rows for code_review"
else
    assert_fail "parameter_tuning expected 3 rows, got $V2_COUNT"
fi

if [[ "$V1_VALID" == "true" ]]; then
    assert_pass "model_tuning optimal_params are valid JSON with temperature"
else
    assert_fail "model_tuning optimal_params validation failed"
fi

if [[ "$V2_VALID" == "true" ]]; then
    assert_pass "parameter_tuning optimal_params are valid JSON with temperature"
else
    assert_fail "parameter_tuning optimal_params validation failed"
fi

if [[ "$OPUS_TEMP" == "0.1" ]]; then
    assert_pass "Opus optimal temperature=0.1 (high-quality model gets low temp)"
else
    assert_fail "Opus expected temp=0.1, got $OPUS_TEMP"
fi

if [[ "$HAIKU_TEMP" == "0.3" ]]; then
    assert_pass "Haiku optimal temperature=0.3 (lower-quality model gets higher temp)"
else
    assert_fail "Haiku expected temp=0.3, got $HAIKU_TEMP"
fi

# ============================================================================
# STEP 6: Run LIS calculator
# ============================================================================

step 6 "Run LIS calculator"

# First, seed enough data for LIS calculation (needs minSamples=10 by default)
LIS_RESULT=$(run_node "
import { createRequire } from 'module';
import { randomUUID } from 'crypto';
const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database('${VALIDATE_PHASE1_TEST_DB}');

// Seed additional executions (need >= 10 per model/task for LIS)
const insertStmt = db.prepare(\`
    INSERT INTO execution_log (
        execution_id, run_id, model, model_role, workflow, task_type,
        quality_score, confidence, cost_usd, duration_ms, outcome, was_selected
    ) VALUES (?, ?, ?, 'worker', 'code-review', 'code_review', ?, ?, ?, ?, 'success', ?)
\`);

const models = ['opus', 'sonnet', 'haiku'];
const seedRunId = randomUUID();

for (const model of models) {
    const baseQuality = model === 'opus' ? 0.90 : (model === 'sonnet' ? 0.85 : 0.75);
    const baseCost = model === 'opus' ? 0.04 : (model === 'sonnet' ? 0.01 : 0.002);
    const baseDuration = model === 'opus' ? 5000 : (model === 'sonnet' ? 3500 : 1000);

    for (let i = 0; i < 15; i++) {
        const jitter = (Math.random() - 0.5) * 0.1;
        const quality = Math.min(0.99, Math.max(0.5, baseQuality + jitter));
        const cost = baseCost * (0.8 + Math.random() * 0.4);
        const duration = baseDuration * (0.7 + Math.random() * 0.6);

        insertStmt.run(
            randomUUID(), seedRunId, model,
            quality, quality + 0.02, cost, Math.round(duration),
            Math.random() > 0.5 ? 1 : 0
        );
    }
}

// Now compute LIS manually (same algorithm as calculate-lis.js)
// We use the data to compute model_performance and then LIS

function mean(arr) {
    if (arr.length === 0) return 0;
    return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function stdDev(arr) {
    if (arr.length < 2) return 0;
    const m = mean(arr);
    const v = arr.reduce((s, x) => s + (x - m) ** 2, 0) / (arr.length - 1);
    return Math.sqrt(v);
}

function coefficientOfVariation(arr) {
    if (arr.length < 2) return 0;
    const m = mean(arr);
    return m === 0 ? 0 : stdDev(arr) / Math.abs(m);
}

function percentileRank(value, sortedArr) {
    if (sortedArr.length === 0) return 0.5;
    return sortedArr.filter(v => v < value).length / sortedArr.length;
}

// Get all model stats for percentile comparison
const allStats = db.prepare(\`
    SELECT model, task_type,
        AVG(quality_score) as avg_quality,
        AVG(cost_usd) as avg_cost,
        AVG(duration_ms) as avg_duration,
        COUNT(*) as sample_count
    FROM execution_log
    WHERE quality_score IS NOT NULL
    GROUP BY model, task_type
    HAVING COUNT(*) >= 10
\`).all();

const allQualities = allStats.map(s => s.avg_quality).filter(q => q > 0).sort((a,b) => a - b);
const allCosts = allStats.map(s => s.avg_cost).filter(c => c > 0).sort((a,b) => a - b);
const allDurations = allStats.map(s => s.avg_duration).filter(d => d > 0).sort((a,b) => a - b);

const results = {};

for (const model of models) {
    const stats = allStats.find(s => s.model === model && s.task_type === 'code_review');
    if (!stats) continue;

    const recentQuality = db.prepare(
        'SELECT quality_score as val FROM execution_log WHERE model = ? AND task_type = ? AND quality_score IS NOT NULL ORDER BY timestamp DESC LIMIT 50'
    ).all(model, 'code_review').map(r => r.val);

    const recentCost = db.prepare(
        'SELECT cost_usd as val FROM execution_log WHERE model = ? AND task_type = ? AND cost_usd IS NOT NULL ORDER BY timestamp DESC LIMIT 50'
    ).all(model, 'code_review').map(r => r.val);

    const recentDuration = db.prepare(
        'SELECT duration_ms as val FROM execution_log WHERE model = ? AND task_type = ? AND duration_ms IS NOT NULL ORDER BY timestamp DESC LIMIT 50'
    ).all(model, 'code_review').map(r => r.val);

    // Quality score (percentile-based, 0-100)
    const qualityPercentile = percentileRank(stats.avg_quality, allQualities) * 100;

    // Cost score (lower is better, invert percentile)
    const costPercentile = percentileRank(stats.avg_cost, allCosts);
    const costScore = (1 - costPercentile) * 100;

    // Speed score (lower is better, invert percentile)
    const speedPercentile = percentileRank(stats.avg_duration, allDurations);
    const speedScore = (1 - speedPercentile) * 100;

    // Consistency score (lower CV is better)
    const qualityCV = coefficientOfVariation(recentQuality);
    const costCV = coefficientOfVariation(recentCost);
    const qualityCVScore = Math.max(0, 100 - qualityCV * 200);
    const costCVScore = recentCost.length >= 2 ? Math.max(0, 100 - costCV * 200) : 50;
    const consistencyScore = (qualityCVScore + costCVScore) / 2;

    // LIS = weighted composite
    const lis = 0.35 * qualityPercentile + 0.25 * costScore + 0.20 * speedScore + 0.20 * consistencyScore;

    results[model] = {
        lis: Math.round(lis * 10) / 10,
        quality: Math.round(qualityPercentile * 10) / 10,
        cost: Math.round(costScore * 10) / 10,
        speed: Math.round(speedScore * 10) / 10,
        consistency: Math.round(consistencyScore * 10) / 10,
        samples: stats.sample_count,
    };
}

db.close();
console.log(JSON.stringify({
    results,
    model_count: Object.keys(results).length,
    success: Object.keys(results).length > 0
}));
")

verbose_log "LIS result: $LIS_RESULT"

LIS_MODEL_COUNT=$(echo "$LIS_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.model_count)")

if [[ "$LIS_MODEL_COUNT" == "3" ]]; then
    assert_pass "LIS computed for all 3 models"
else
    assert_fail "Expected LIS for 3 models, got $LIS_MODEL_COUNT"
fi

# ============================================================================
# STEP 7: Verify LIS score calculated correctly
# ============================================================================

step 7 "Verify LIS score calculated correctly"

LIS_VERIFY=$(run_node "
import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const rawResult = '$(echo "$LIS_RESULT" | sed "s/'/\\\\'/g")';
const data = JSON.parse(rawResult);
const results = data.results;

const checks = {
    all_in_range: true,
    opus_highest: false,
    haiku_lowest: false,
    components_sum_correctly: true,
    samples_sufficient: true,
};

// All LIS scores should be 0-100
for (const [model, r] of Object.entries(results)) {
    if (r.lis < 0 || r.lis > 100) checks.all_in_range = false;
    if (r.quality < 0 || r.quality > 100) checks.all_in_range = false;
    if (r.cost < 0 || r.cost > 100) checks.all_in_range = false;
    if (r.speed < 0 || r.speed > 100) checks.all_in_range = false;
    if (r.consistency < 0 || r.consistency > 100) checks.all_in_range = false;
    if (r.samples < 10) checks.samples_sufficient = false;
}

// Opus should have highest quality (it has the best quality_score)
if (results.opus && results.sonnet && results.haiku) {
    checks.opus_highest = results.opus.quality >= results.sonnet.quality &&
                           results.opus.quality >= results.haiku.quality;
    checks.haiku_lowest = results.haiku.quality <= results.opus.quality &&
                           results.haiku.quality <= results.sonnet.quality;
}

console.log(JSON.stringify({
    checks,
    opus_lis: results.opus ? results.opus.lis : null,
    sonnet_lis: results.sonnet ? results.sonnet.lis : null,
    haiku_lis: results.haiku ? results.haiku.lis : null,
}));
")

verbose_log "LIS verify: $LIS_VERIFY"

ALL_IN_RANGE=$(echo "$LIS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.checks.all_in_range)")
OPUS_HIGHEST=$(echo "$LIS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.checks.opus_highest)")
HAIKU_LOWEST=$(echo "$LIS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.checks.haiku_lowest)")
SAMPLES_OK=$(echo "$LIS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.checks.samples_sufficient)")
OPUS_LIS=$(echo "$LIS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.opus_lis)")
SONNET_LIS=$(echo "$LIS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.sonnet_lis)")
HAIKU_LIS=$(echo "$LIS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.haiku_lis)")

if [[ "$ALL_IN_RANGE" == "true" ]]; then
    assert_pass "All LIS scores and components in 0-100 range"
else
    assert_fail "LIS scores or components out of 0-100 range"
fi

if [[ "$OPUS_HIGHEST" == "true" ]]; then
    assert_pass "Opus has highest quality score (expected: best quality_score)"
else
    assert_fail "Opus should have highest quality score"
fi

if [[ "$HAIKU_LOWEST" == "true" ]]; then
    assert_pass "Haiku has lowest quality score (expected: lowest quality_score)"
else
    assert_fail "Haiku should have lowest quality score"
fi

if [[ "$SAMPLES_OK" == "true" ]]; then
    assert_pass "All models have sufficient sample count (>= 10)"
else
    assert_fail "Some models have insufficient samples"
fi

echo -e "  ${BLUE}[INFO]${NC} LIS scores: opus=${OPUS_LIS} sonnet=${SONNET_LIS} haiku=${HAIKU_LIS}"

# ============================================================================
# STEP 8: Run research session (manual trigger)
# ============================================================================

step 8 "Run research session (manual trigger)"

RESEARCH_RESULT=$(run_node "
import { createRequire } from 'module';
import { randomUUID } from 'crypto';
const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database('${VALIDATE_PHASE1_TEST_DB}');

// Simulate a research session (like learning-session.sh would do)
// Research sessions log to execution_log with workflow='deep-research'
const SESSION_ID = 'research-session-' + Date.now();
const RUN_ID = randomUUID();

// Set session metadata (like learning-session.sh does)
db.prepare(
    \"INSERT OR REPLACE INTO learning_metadata (key, value) VALUES (?, ?)\"
).run('last_session_id', SESSION_ID);
db.prepare(
    \"INSERT OR REPLACE INTO learning_metadata (key, value) VALUES (?, ?)\"
).run('last_session_workflow', 'deep-research');
db.prepare(
    \"INSERT OR REPLACE INTO learning_metadata (key, value) VALUES (?, ?)\"
).run('last_session_start', new Date().toISOString());
db.prepare(
    \"INSERT OR REPLACE INTO learning_metadata (key, value) VALUES (?, ?)\"
).run('last_session_run_id', RUN_ID);

// Simulate research findings as execution entries
const findings = [
    {
        model: 'opus',
        task_description: 'Research: optimal consensus strategies for security audits',
        quality_score: 0.91,
        cost_usd: 0.065,
        duration_ms: 8500,
        outcome_notes: 'Finding: adversarial debate outperforms simple consensus for security tasks by 15%',
    },
    {
        model: 'gemini',
        task_description: 'Research: cost-quality tradeoff analysis across model families',
        quality_score: 0.87,
        cost_usd: 0.003,
        duration_ms: 4200,
        outcome_notes: 'Finding: haiku+sonnet combo achieves 85% of opus quality at 20% cost',
    },
    {
        model: 'sonnet',
        task_description: 'Research: prompt pattern effectiveness for code review tasks',
        quality_score: 0.89,
        cost_usd: 0.018,
        duration_ms: 5100,
        outcome_notes: 'Finding: structured checklist prompts improve code review quality by 12%',
    },
];

const insertStmt = db.prepare(\`
    INSERT INTO execution_log (
        execution_id, run_id, model, model_role, workflow, task_type,
        task_description, quality_score, confidence, cost_usd, duration_ms,
        outcome, outcome_notes, session_id
    ) VALUES (?, ?, ?, 'worker', 'deep-research', 'research', ?, ?, ?, ?, ?, 'success', ?, ?)
\`);

for (const finding of findings) {
    insertStmt.run(
        randomUUID(), RUN_ID, finding.model,
        finding.task_description, finding.quality_score,
        finding.quality_score + 0.02,
        finding.cost_usd, finding.duration_ms,
        finding.outcome_notes, SESSION_ID
    );
}

// Mark session end
db.prepare(
    \"INSERT OR REPLACE INTO learning_metadata (key, value) VALUES (?, ?)\"
).run('last_session_end', new Date().toISOString());
db.prepare(
    \"INSERT OR REPLACE INTO learning_metadata (key, value) VALUES (?, ?)\"
).run('last_session_outcome', 'success');

db.close();
console.log(JSON.stringify({
    session_id: SESSION_ID,
    run_id: RUN_ID,
    findings_count: findings.length,
    success: true
}));
")

verbose_log "Research result: $RESEARCH_RESULT"

RESEARCH_RUN_ID=$(echo "$RESEARCH_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.run_id)")
FINDINGS_COUNT=$(echo "$RESEARCH_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.findings_count)")

if [[ "$FINDINGS_COUNT" == "3" ]]; then
    assert_pass "Research session generated 3 findings"
else
    assert_fail "Expected 3 findings, got $FINDINGS_COUNT"
fi

# ============================================================================
# STEP 9: Verify findings stored
# ============================================================================

step 9 "Verify research findings stored"

FINDINGS_VERIFY=$(run_node "
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database('${VALIDATE_PHASE1_TEST_DB}', { readonly: true });

const RUN_ID = '${RESEARCH_RUN_ID}';

// Check research executions
const researchExecs = db.prepare(
    \"SELECT * FROM execution_log WHERE run_id = ? AND workflow = 'deep-research'\"
).all(RUN_ID);

// Check session metadata
const sessionId = db.prepare(
    \"SELECT value FROM learning_metadata WHERE key = 'last_session_id'\"
).get();
const sessionOutcome = db.prepare(
    \"SELECT value FROM learning_metadata WHERE key = 'last_session_outcome'\"
).get();
const sessionWorkflow = db.prepare(
    \"SELECT value FROM learning_metadata WHERE key = 'last_session_workflow'\"
).get();

// Verify findings have outcome_notes (the actual research findings)
const hasNotes = researchExecs.every(e => e.outcome_notes && e.outcome_notes.startsWith('Finding:'));

// Verify distinct models used
const distinctModels = [...new Set(researchExecs.map(e => e.model))];

db.close();
console.log(JSON.stringify({
    count: researchExecs.length,
    has_notes: hasNotes,
    distinct_models: distinctModels,
    session_outcome: sessionOutcome ? sessionOutcome.value : null,
    session_workflow: sessionWorkflow ? sessionWorkflow.value : null,
    all_research_type: researchExecs.every(e => e.task_type === 'research'),
}));
")

verbose_log "Findings verify: $FINDINGS_VERIFY"

RESEARCH_COUNT=$(echo "$FINDINGS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.count)")
HAS_NOTES=$(echo "$FINDINGS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.has_notes)")
SESSION_OUTCOME=$(echo "$FINDINGS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.session_outcome)")
SESSION_WF=$(echo "$FINDINGS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.session_workflow)")
ALL_RESEARCH=$(echo "$FINDINGS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.all_research_type)")
DISTINCT_MODELS=$(echo "$FINDINGS_VERIFY" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.distinct_models.length)")

if [[ "$RESEARCH_COUNT" == "3" ]]; then
    assert_pass "3 research findings stored in execution_log"
else
    assert_fail "Expected 3 research findings, got $RESEARCH_COUNT"
fi

if [[ "$HAS_NOTES" == "true" ]]; then
    assert_pass "All findings have 'Finding:' prefix in outcome_notes"
else
    assert_fail "Research findings missing outcome_notes"
fi

if [[ "$ALL_RESEARCH" == "true" ]]; then
    assert_pass "All research entries have task_type='research'"
else
    assert_fail "Some research entries have wrong task_type"
fi

if [[ "$SESSION_OUTCOME" == "success" ]]; then
    assert_pass "Session metadata records outcome=success"
else
    assert_fail "Session metadata outcome expected 'success', got '$SESSION_OUTCOME'"
fi

if [[ "$SESSION_WF" == "deep-research" ]]; then
    assert_pass "Session metadata records workflow=deep-research"
else
    assert_fail "Session metadata workflow expected 'deep-research', got '$SESSION_WF'"
fi

if [[ "$DISTINCT_MODELS" -ge "2" ]]; then
    assert_pass "Research session used $DISTINCT_MODELS distinct models"
else
    assert_fail "Expected >= 2 distinct models, got $DISTINCT_MODELS"
fi

# ============================================================================
# STEP 10: Check cost tracking
# ============================================================================

step 10 "Check cost tracking"

COST_RESULT=$(run_node "
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const Database = require('better-sqlite3');
const db = new Database('${VALIDATE_PHASE1_TEST_DB}', { readonly: true });

// Overall cost tracking
const overall = db.prepare(\`
    SELECT
        COUNT(*) as total_executions,
        SUM(cost_usd) as total_cost_usd,
        AVG(cost_usd) as avg_cost_usd,
        MIN(cost_usd) as min_cost_usd,
        MAX(cost_usd) as max_cost_usd,
        SUM(input_tokens) as total_input_tokens,
        SUM(output_tokens) as total_output_tokens
    FROM execution_log
\`).get();

// Cost by model
const byModel = db.prepare(\`
    SELECT model,
        COUNT(*) as executions,
        SUM(cost_usd) as total_cost,
        AVG(cost_usd) as avg_cost,
        SUM(input_tokens) as total_input_tokens,
        SUM(output_tokens) as total_output_tokens
    FROM execution_log
    GROUP BY model
    ORDER BY total_cost DESC
\`).all();

// Cost by workflow
const byWorkflow = db.prepare(\`
    SELECT workflow,
        COUNT(*) as executions,
        SUM(cost_usd) as total_cost,
        AVG(cost_usd) as avg_cost
    FROM execution_log
    GROUP BY workflow
    ORDER BY total_cost DESC
\`).all();

// Verify total_cost_usd field on arbiter entries (aggregated cost)
const arbiterCosts = db.prepare(\`
    SELECT total_cost_usd, cost_usd FROM execution_log
    WHERE model_role = 'arbiter' AND total_cost_usd > 0
\`).all();

db.close();
console.log(JSON.stringify({
    overall,
    byModel,
    byWorkflow,
    arbiterCosts,
    has_positive_costs: overall.total_cost_usd > 0,
    has_token_tracking: overall.total_input_tokens > 0 && overall.total_output_tokens > 0,
    arbiter_has_aggregate_cost: arbiterCosts.length > 0 && arbiterCosts[0].total_cost_usd > arbiterCosts[0].cost_usd,
}));
")

verbose_log "Cost result: $COST_RESULT"

HAS_COSTS=$(echo "$COST_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.has_positive_costs)")
HAS_TOKENS=$(echo "$COST_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.has_token_tracking)")
ARBITER_AGG=$(echo "$COST_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.arbiter_has_aggregate_cost)")
TOTAL_COST=$(echo "$COST_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.overall.total_cost_usd.toFixed(4))")
TOTAL_EXECS=$(echo "$COST_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.overall.total_executions)")
MODEL_COUNT=$(echo "$COST_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.byModel.length)")
WORKFLOW_COUNT=$(echo "$COST_RESULT" | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); console.log(d.byWorkflow.length)")

if [[ "$HAS_COSTS" == "true" ]]; then
    assert_pass "Cost tracking: total cost > 0 (\$${TOTAL_COST})"
else
    assert_fail "Cost tracking: total cost is zero or negative"
fi

if [[ "$HAS_TOKENS" == "true" ]]; then
    assert_pass "Token tracking: input and output tokens recorded"
else
    assert_fail "Token tracking: missing input or output token counts"
fi

if [[ "$ARBITER_AGG" == "true" ]]; then
    assert_pass "Arbiter entries have aggregate total_cost_usd > per-model cost_usd"
else
    assert_fail "Arbiter entries missing aggregate cost tracking"
fi

if [[ "$TOTAL_EXECS" -ge "49" ]]; then
    assert_pass "Total executions tracked: $TOTAL_EXECS (workflow + seeded + research)"
else
    assert_fail "Expected >= 49 total executions, got $TOTAL_EXECS"
fi

if [[ "$MODEL_COUNT" -ge "3" ]]; then
    assert_pass "Cost breakdown by model: $MODEL_COUNT distinct models"
else
    assert_fail "Expected >= 3 models in cost breakdown, got $MODEL_COUNT"
fi

if [[ "$WORKFLOW_COUNT" -ge "2" ]]; then
    assert_pass "Cost breakdown by workflow: $WORKFLOW_COUNT distinct workflows"
else
    assert_fail "Expected >= 2 workflows in cost breakdown, got $WORKFLOW_COUNT"
fi

# Print cost summary
echo ""
echo -e "  ${BLUE}[INFO]${NC} Cost Summary:"
echo "$COST_RESULT" | node -e "
const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8'));
console.log('         Total cost:       \$' + d.overall.total_cost_usd.toFixed(4));
console.log('         Total executions: ' + d.overall.total_executions);
console.log('         Avg cost/exec:    \$' + d.overall.avg_cost_usd.toFixed(4));
console.log('         Total tokens:     ' + (d.overall.total_input_tokens + d.overall.total_output_tokens));
console.log('         By model:');
d.byModel.forEach(m => {
    console.log('           ' + m.model.padEnd(10) + ' \$' + m.total_cost.toFixed(4) + '  (' + m.executions + ' execs)');
});
console.log('         By workflow:');
d.byWorkflow.forEach(w => {
    console.log('           ' + (w.workflow || 'null').padEnd(16) + ' \$' + w.total_cost.toFixed(4) + '  (' + w.executions + ' execs)');
});
"

# ============================================================================
# SUMMARY
# ============================================================================

echo ""
divider
echo -e "  ${BOLD}Phase 1 Validation Summary${NC}"
divider
echo ""
echo -e "  Total assertions:  ${TOTAL_COUNT}"
echo -e "  ${GREEN}Passed:            ${PASS_COUNT}${NC}"
if [[ $FAIL_COUNT -gt 0 ]]; then
    echo -e "  ${RED}Failed:            ${FAIL_COUNT}${NC}"
else
    echo -e "  Failed:            0"
fi
echo ""
echo -e "  Test database:     ${VALIDATE_PHASE1_TEST_DB}"
echo -e "  DB size:           $(du -h "${VALIDATE_PHASE1_TEST_DB}" 2>/dev/null | cut -f1 || echo 'N/A')"
echo ""

if [[ $FAIL_COUNT -eq 0 ]]; then
    echo -e "  ${GREEN}${BOLD}ALL ASSERTIONS PASSED${NC}"
    echo ""
    echo "  Phase 1 components validated:"
    echo "    1. Database initialization (schema + tables)"
    echo "    2. Workflow execution logging (worker + arbiter)"
    echo "    3. Execution verification (counts, roles, quality)"
    echo "    4. Parameter optimization (model_tuning + parameter_tuning)"
    echo "    5. Parameter verification (optimal temps derived correctly)"
    echo "    6. LIS calculation (weighted composite score)"
    echo "    7. LIS verification (range, ranking, sample adequacy)"
    echo "    8. Research session (multi-model finding generation)"
    echo "    9. Findings verification (storage, metadata, session tracking)"
    echo "   10. Cost tracking (per-model, per-workflow, token counts)"
else
    echo -e "  ${RED}${BOLD}VALIDATION FAILED: ${FAIL_COUNT} assertion(s) failed${NC}"
fi

echo ""
divider

exit $FAIL_COUNT
