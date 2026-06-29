#!/bin/bash
# Fix permissions for autonomous workflows - USE DONTASK MODE

echo "Setting dontAsk mode for all Claude sessions/projects..."

# Global settings
cat > ~/.claude/settings.json << 'SETTINGS'
{
  "permissions": {
    "mode": "dontAsk"
  },
  "skipWorkflowUsageWarning": true
}
SETTINGS

cat > ~/.claude/settings.local.json << 'SETTINGS'
{
  "permissions": {
    "mode": "dontAsk"
  }
}
SETTINGS

echo "✅ Fixed global settings"

# Project settings  
for project_dir in ~/FlossWare ~/sfloess ~/Solenopsis ~/solenopsis ~/Development/github/FlossWare/*; do
  if [ -d "$project_dir" ]; then
    mkdir -p "$project_dir/.claude"
    cat > "$project_dir/.claude/settings.json" << 'SETTINGS'
{
  "permissions": {
    "mode": "dontAsk"
  }
}
SETTINGS
    echo "✅ Fixed: $project_dir"
  fi
done

echo ""
echo "🎯 ALL PERMISSIONS SET TO DONTASK MODE"
echo "⚠️  Restart all Claude sessions to pick up changes"
