# Quick Start - Transparency Dashboard

Get the autonomous learning system transparency dashboard running in 2 minutes.

## TL;DR

```bash
# Start the CLI dashboard
./monitoring/start-dashboard.sh

# Or use npm script
npm run dashboard
```

That's it! You'll see:
- 🔴 **Live status** - What's happening now
- 🗺️ **Fleet activity** - Which AI on which server
- 🧠 **Decisions** - All autonomous decisions with rationale
- 📈 **Quality trends** - Learning progress over time
- 💰 **Cost tracking** - Real-time spend
- 🔍 **Issues** - Errors and failures

## What You'll See

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🟢 LIVE | Active: 3 executions | 2 workflows | 4 AI models | LIS: 87.3/100 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ 🗺️  Fleet Activity Map ─────────────┬─ ⚙️  Active Workflows ─────────────┐
│ Time     Model   Workflow    Status  │ Workflow       Count  Models        │
│ 10:23:15 opus    code-review ✅      │ code-review    5      opus,sonnet   │
│ 10:23:12 sonnet  code-solve  ⏳      │ code-solve     2      sonnet        │
│ 10:23:10 haiku   code-test   ✅      │ ai-consensus   1      all           │
└────────────────────────────────────────┴──────────────────────────────────────┘

┌─ 🧠 Learning Intelligence Score ─┬─ 🎯 Model Performance ─────────────────┐
│                                   │ opus:security     ████████████ 95     │
│            87.3%                  │ sonnet:code       ██████████   82     │
│         ████████                  │ haiku:test        ████████     71     │
│                                   │ gemini:research   ██████       64     │
└───────────────────────────────────┴───────────────────────────────────────┘

┌─ 📈 Quality Trend ────────────────┬─ 🧠 Autonomous Decisions ──────────────┐
│ 1.0 ┤                          ╭─ │ [10:23:15] opus - code-review:        │
│ 0.9 ┤                     ╭────╯  │   Selected for high-stakes security   │
│ 0.8 ┤              ╭──────╯       │ [10:23:12] sonnet - code-solve:       │
│ 0.7 ┤         ╭────╯              │   Cost-optimized choice for refactor  │
│ 0.6 ┤    ╭────╯                   │ [10:23:10] haiku - code-test:         │
│ 0.5 ┼────╯                        │   Speed-optimized for test generation │
└───────────────────────────────────┴───────────────────────────────────────┘

Press 'r' to refresh | 'h' for help | 'q' to quit
```

## First Time Setup

### 1. Install Dependencies

```bash
# Already in the project
npm install better-sqlite3 blessed blessed-contrib
```

### 2. Initialize Database (Auto)

The database auto-initializes on first use. No action needed!

**Location:** `~/.claude/learning/db/learning.db`

### 3. Run Dashboard

```bash
# Option 1: Direct script
./monitoring/start-dashboard.sh

# Option 2: npm script
npm run dashboard

# Option 3: Node directly
node monitoring/transparency-dashboard-cli.js
```

## What Gets Tracked

Every workflow that uses `learning-logger.js` appears here:

```javascript
// Example: This appears in the dashboard automatically
import { logExecution } from './shared/learning-logger.js';

logExecution({
  model: 'opus',
  workflow: 'code-review',
  task_type: 'security',
  quality_score: 0.92,
  confidence: 0.88,
  cost_usd: 0.0825,
  duration_ms: 3200,
  outcome: 'success',
  outcome_notes: 'Autonomous decision: Selected Opus for high-stakes security review',
});
```

**All autonomous workflows already integrated:**
- ✅ `ai-consensus` (all variants)
- ✅ `ai-performance-monitor`
- ✅ `ai-cost-tracker`
- ✅ `code-review-auto`
- ✅ `code-sdlc-auto`
- ✅ `ai-web-learn-*`
- ✅ All multi-AI workflows

## Views & Navigation

### Keyboard Shortcuts

- `r` - Refresh dashboard
- `h` or `?` - Show help
- `q` or `ESC` - Quit

### What Each Panel Shows

1. **Status Bar** (top)
   - Live activity: executions/min, active workflows, models
   - System health: LIS score, error count
   - Last update timestamp

2. **Fleet Activity Map** (top-left)
   - Recent executions (last 5 minutes)
   - Which AI model on which task
   - Success/failure status

3. **Active Workflows** (top-right)
   - Running workflows
   - Execution counts
   - Average duration

4. **Learning Intelligence Score** (middle-left)
   - 0-100 aggregate improvement metric
   - Combines quality, cost, speed, consistency

5. **Model Performance** (middle-center)
   - Quality scores by model
   - Sorted by performance

6. **Cost Distribution** (middle-right)
   - Spend by model
   - Real-time cost tracking

7. **Quality Trend** (bottom-left)
   - Quality over time
   - Shows learning progress

8. **Autonomous Decisions** (bottom-right)
   - Recent decisions with rationale
   - Why each choice was made

9. **Issue Tracker** (bottom)
   - Failures and errors
   - Recent issues

## Advanced Usage

### Custom Refresh Rate

```bash
# Refresh every 10 seconds (default: 5)
DASHBOARD_REFRESH=10 node monitoring/transparency-dashboard-cli.js
```

### Export Data

```bash
# Export current data to JSON
node monitoring/transparency-dashboard-cli.js --export data.json
```

### Query Database Directly

```bash
# Recent executions
sqlite3 ~/.claude/learning/db/learning.db \
  "SELECT * FROM execution_log ORDER BY timestamp DESC LIMIT 20;"

# Model performance
sqlite3 ~/.claude/learning/db/learning.db \
  "SELECT model, AVG(quality_score) as avg_quality FROM execution_log 
   WHERE quality_score IS NOT NULL GROUP BY model;"
```

## Grafana Alternative (Web UI)

Want a web-based dashboard instead?

```bash
# Show Grafana setup
./monitoring/start-dashboard.sh grafana

# Then import monitoring/autonomous-transparency-dashboard.json
```

**Grafana gives you:**
- ✅ Historical data (weeks/months)
- ✅ Interactive charts (zoom, filter)
- ✅ Alerts and notifications
- ✅ Multiple dashboards
- ✅ Remote access via browser

**CLI gives you:**
- ✅ Instant startup (no server needed)
- ✅ Low resource usage
- ✅ Terminal-friendly
- ✅ Fast refresh (1-5s)
- ✅ No setup required

**Best of both:** Run both! They share the same SQLite database.

## Troubleshooting

### "Database not found"

```bash
# Check database location
ls -lh ~/.claude/learning/db/learning.db

# If missing, it will auto-create on first workflow execution
# Or manually initialize:
mkdir -p ~/.claude/learning/db
sqlite3 ~/.claude/learning/db/learning.db < ~/.claude/learning/init-learning-db.sql
```

### "No data showing"

```bash
# Run a workflow to generate data
node ai-prompt.js "test prompt"

# Or run autonomous learning workflow
node ai-web-learn-production.js "test topic"

# Check data was logged
sqlite3 ~/.claude/learning/db/learning.db "SELECT COUNT(*) FROM execution_log;"
```

### "Module not found: blessed"

```bash
# Install dependencies
npm install better-sqlite3 blessed blessed-contrib
```

## Check Status

```bash
# View dashboard status
./monitoring/start-dashboard.sh status

# Output:
# Database Statistics:
#   Total executions: 1,234
#   Last hour: 45
#   Unique models: 6
#
# ✅ Grafana: Running
# ✅ Prometheus: Running
```

## Next Steps

1. ✅ **Start the dashboard** - See real-time activity
2. 🚀 **Run autonomous workflows** - Generate data
3. 📊 **Explore Grafana** - Web-based historical analysis
4. 🔔 **Set up alerts** - Get notified of issues
5. 📈 **Monitor learning** - Track improvement over time

---

**Questions?** See full docs: `monitoring/README-transparency-dashboard.md`

**Everything is transparent. Everything is visible. Everything is auditable.**
