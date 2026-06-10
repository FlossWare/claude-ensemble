#!/bin/bash
# Completely relax all permissions everywhere - no prompts, auto-approve everything

echo "🔓 RELAXING ALL PERMISSIONS EVERYWHERE..."
echo ""

# Global settings - ultimate permissive mode
cat > ~/.claude/settings.json << 'SETTINGS'
{
  "permissions": {
    "mode": "dontAsk"
  },
  "skipWorkflowUsageWarning": true,
  "autoApprovePlans": true,
  "autoApproveEdits": true
}
SETTINGS
echo "✅ Global settings.json"

# Global user settings - completely permissive
cat > ~/.claude/settings.local.json << 'SETTINGS'
{
  "permissions": {
    "mode": "dontAsk"
  }
}
SETTINGS
echo "✅ Global settings.local.json"

# Apply to ALL project directories
for project_dir in \
  ~/FlossWare \
  ~/sfloess \
  ~/Solenopsis \
  ~/solenopsis \
  ~/Development/github/FlossWare/* \
  ~/Development/redhat/scm/gitlab/cee/sfloess/* \
  /tmp; do
  
  if [ -d "$project_dir" ]; then
    mkdir -p "$project_dir/.claude"
    cat > "$project_dir/.claude/settings.json" << 'SETTINGS'
{
  "permissions": {
    "mode": "dontAsk"
  }
}
SETTINGS
    echo "✅ $project_dir"
  fi
done

echo ""
echo "🎯 ALL PERMISSIONS COMPLETELY RELAXED"
echo "   - dontAsk mode everywhere"
echo "   - Auto-approve plans"
echo "   - Auto-approve edits"
echo "   - No prompt dialogs"
echo ""
echo "⚠️  RESTART ALL CLAUDE SESSIONS to pick up changes"
