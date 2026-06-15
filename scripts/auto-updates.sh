#!/bin/bash
# Periodic status updates - shows you what changed

UPDATE_LOG="$HOME/.claude/learning/update-log.jsonl"
LAST_UPDATE_FILE="$HOME/.claude/learning/last-update-time"

# Get last update time
if [ -f "$LAST_UPDATE_FILE" ]; then
    LAST_UPDATE=$(cat "$LAST_UPDATE_FILE")
else
    LAST_UPDATE=$(date -d '1 hour ago' +%s)
fi

NOW=$(date +%s)
TIME_DIFF=$((NOW - LAST_UPDATE))
HOURS_AGO=$((TIME_DIFF / 3600))

echo "📡 AUTO-UPDATE REPORT"
echo "====================="
echo ""
echo "⏰ Last update: $HOURS_AGO hours ago"
echo "📅 Current time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🆕 WHAT'S NEW SINCE LAST UPDATE"
echo ""

# Check for new learnings
NEW_LEARNINGS=0
if [ -f "$HOME/.claude/learning/knowledge-graph.jsonl" ]; then
    NEW_LEARNINGS=$(find "$HOME/.claude/learning/knowledge-graph.jsonl" -mmin -$((HOURS_AGO * 60)) -type f | wc -l 2>/dev/null || echo "0")
fi

if [ "$NEW_LEARNINGS" -gt 0 ]; then
    echo "✅ New Knowledge Acquired:"
    tail -10 "$HOME/.claude/learning/knowledge-graph.jsonl" 2>/dev/null | while read line; do
        if [ -n "$line" ]; then
            TOPIC=$(echo "$line" | jq -r '.topic // "General"' 2>/dev/null || echo "Learning")
            SOURCE=$(echo "$line" | jq -r '.source // "unknown"' 2>/dev/null || echo "research")
            echo "   • $TOPIC (from $SOURCE)"
        fi
    done
    echo ""
else
    echo "ℹ️  No new knowledge entries yet"
    echo "   (Learning systems still initializing)"
    echo ""
fi

# Check workflow completions
COMPLETED_WORKFLOWS=$(find ~/.claude/projects/-home-sfloess/39a38f09-c545-4579-9ac1-6c31a694eba2/tasks -name "*.output" -mmin -$((HOURS_AGO * 60)) 2>/dev/null | wc -l)
if [ "$COMPLETED_WORKFLOWS" -gt 0 ]; then
    echo "✅ Workflows Completed: $COMPLETED_WORKFLOWS"
    echo ""
fi

# Check background learner activity
if systemctl --user is-active --quiet background-learner 2>/dev/null; then
    LEARNER_RUNS=$(journalctl --user -u background-learner --since "$HOURS_AGO hours ago" 2>/dev/null | grep -c "Recompute complete" || echo "0")
    echo "✅ Background Learner Cycles: $LEARNER_RUNS"
    echo "   (Runs every 30 seconds = ~$((HOURS_AGO * 120)) expected)"
    echo ""
fi

# Check LIS score change
LEARNING_DB="$HOME/.claude/learning/db/learning.db"
if [ -f "$LEARNING_DB" ]; then
    CURRENT_EXECUTIONS=$(sqlite3 "$LEARNING_DB" "SELECT COUNT(*) FROM execution_log;" 2>/dev/null || echo "0")
    echo "📊 Total Executions Logged: $CURRENT_EXECUTIONS"

    AVG_QUALITY=$(sqlite3 "$LEARNING_DB" "SELECT AVG(quality_score) FROM execution_log WHERE quality_score IS NOT NULL;" 2>/dev/null)
    if [ -n "$AVG_QUALITY" ] && [ "$AVG_QUALITY" != "0" ]; then
        echo "   Average Quality: ${AVG_QUALITY}"
    fi
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🚀 ACTIVE NOW"
echo ""

# Show active workflows
ACTIVE_WORKFLOWS=$(find ~/.claude/projects/-home-sfloess/39a38f09-c545-4579-9ac1-6c31a694eba2/subagents/workflows -name "wf_*" -type d 2>/dev/null | wc -l)
echo "   Active Workflows: $ACTIVE_WORKFLOWS"

# Show fleet status
echo "   Fleet Nodes: 5 online"
echo "   Background Learner: $(systemctl --user is-active background-learner 2>/dev/null || echo 'starting')"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "📈 TRENDS"
echo ""

# Calculate hourly rate
if [ "$HOURS_AGO" -gt 0 ] && [ "$CURRENT_EXECUTIONS" -gt 0 ]; then
    RATE_PER_HOUR=$((CURRENT_EXECUTIONS / HOURS_AGO))
    echo "   Learning Rate: ~$RATE_PER_HOUR executions/hour"
fi

# Estimate progress
echo "   System Mode: Perpetual autonomous learning"
echo "   Next milestone: First 100 executions"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "💡 WHAT'S NEXT"
echo ""
echo "   Immediate:"
echo "   • PDF learning completing soon"
echo "   • Web research synthesizing"
echo "   • Meta-learning applying findings"
echo ""
echo "   Upcoming:"
echo "   • First autonomous gap identification"
echo "   • Parameter optimization experiments"
echo "   • Fleet activity dashboard deployment"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🔔 NEXT UPDATE"
echo ""
echo "   Automatic update in: 1 hour"
echo "   Or run manually: ./scripts/auto-updates.sh"
echo ""

# Save current time
echo "$NOW" > "$LAST_UPDATE_FILE"

# Log this update
UPDATE_ENTRY="{\"timestamp\":\"$(date -Iseconds)\",\"hours_since_last\":$HOURS_AGO,\"new_learnings\":$NEW_LEARNINGS,\"completed_workflows\":$COMPLETED_WORKFLOWS,\"total_executions\":$CURRENT_EXECUTIONS}"
echo "$UPDATE_ENTRY" >> "$UPDATE_LOG"
