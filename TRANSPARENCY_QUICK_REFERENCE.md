# Transparency System - Quick Reference

**One-page guide to fleet transparency.**

## 🎯 Philosophy

**NOTHING IS HIDDEN.** Every bug, fix, validation, deployment — all logged and visible.

## 📊 View Status

```bash
# Quick summary
./scripts/transparency.sh

# Live activity stream
./scripts/transparency.sh --tail

# Recent events
./scripts/transparency.sh --events

# Bug tracking
./scripts/transparency.sh --bugs

# JSON output
./scripts/transparency.sh --json
```

## 📝 Log Events (In Workflows)

```javascript
const {
  logBugFound,
  logFixAttempt,
  logFixSuccess,
  logValidationPassed,
  logDeploymentSuccess,
} = require('../shared/transparency-logger.js');

// Bug found
await logBugFound({
  description: 'Null pointer in auth.js',
  location: 'src/auth.js:42',
  severity: 'high',
  workflowRunId: 'workflow-123'
});

// Fix attempt
await logFixAttempt({
  description: 'Adding null check',
  bugId: 'bug-001',
  workflowRunId: 'workflow-123'
});

// Fix success
await logFixSuccess({
  description: 'Fix applied',
  commitSha: 'abc123',
  workflowRunId: 'workflow-123'
});

// Validation passed
await logValidationPassed({
  description: 'All tests passed',
  testCount: 50,
  workflowRunId: 'workflow-123'
});

// Deployment success
await logDeploymentSuccess({
  description: 'Deployed to production',
  version: '2.3.1',
  environment: 'production',
  workflowRunId: 'workflow-123'
});
```

## 🔔 Configure Notifications

```javascript
const { configure } = require('../shared/notification-sender.js');

// Enable Slack
await configure({
  enabled: true,
  slack: {
    enabled: true,
    webhookUrl: 'https://hooks.slack.com/services/YOUR/WEBHOOK',
    severityFilter: ['critical', 'high']
  }
});

// Enable Email
await configure({
  enabled: true,
  email: {
    enabled: true,
    to: 'you@example.com',
    severityFilter: ['critical']
  }
});

// Enable GitHub Issues
await configure({
  enabled: true,
  github: {
    enabled: true,
    createIssues: true,
    severityFilter: ['critical']
  }
});
```

## 📈 Enable Grafana Dashboard

```bash
# 1. Start Prometheus exporter
node monitoring/prometheus-exporter.js &

# 2. Add to prometheus.yml:
#    - job_name: 'fleet-transparency'
#      static_configs:
#        - targets: ['localhost:9090']

# 3. Import to Grafana:
#    monitoring/transparency-dashboard.json
```

## 🔍 Query State

```javascript
const { getState, queryEvents } = require('../shared/transparency-logger.js');

// Get summary
const state = await getState();
console.log(`Bugs pending: ${state.summary.bugsPending}`);

// Query critical events
const critical = await queryEvents({
  severity: 'critical',
  limit: 10
});

// Query recent bugs
const bugs = await queryEvents({
  type: 'bug_found',
  since: '2026-06-01T00:00:00Z'
});
```

## 📂 File Locations

```
~/.claude/learning/
├── transparency.log           # Human-readable log
├── transparency.json          # Structured events
├── transparency-state.json    # Current state
└── notification-config.json   # Notification settings
```

## 🎚️ Severity Levels

- `critical` → 🚨 Immediate notification (system down, security)
- `high` → ⚠️ Notification (major bugs, failures)
- `medium` → ℹ️ Logged only (minor issues)
- `low` → • Logged only (cosmetic)
- `info` → • Logged only (status updates)

## 📋 Event Types

**Bug Tracking**: `bug_found`, `fix_attempt`, `fix_success`, `fix_failed`  
**Validation**: `validation_started`, `validation_passed`, `validation_failed`  
**Deployment**: `deployment_started`, `deployment_success`, `deployment_failed`  
**Learning**: `learning_started`, `learning_complete`  
**Discovery**: `discovery`  
**Issues**: `issue_created`, `issue_updated`, `issue_closed`

## 🚀 Quick Start

```bash
# 1. Use in workflow (automatic logging)
const { logBugFound } = require('../shared/transparency-logger.js');
await logBugFound({ description: 'Bug!', severity: 'high' });

# 2. View status
./scripts/transparency.sh

# 3. (Optional) Configure notifications
# 4. (Optional) Enable Grafana dashboard
```

## 📚 Full Documentation

`/home/sflooss/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/docs/TRANSPARENCY_SYSTEM.md`

**NOTHING IS HIDDEN. USER IN CONTROL.**
