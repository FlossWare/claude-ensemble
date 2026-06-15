# Fleet Transparency System

Complete visibility into everything the autonomous fleet does.

## 🎯 Philosophy

**NOTHING IS HIDDEN.**

Every bug found, every fix attempt, every validation, every deployment, every learning session, every discovery — all logged, all visible, all queryable.

## 📊 What User Sees (Without Looking)

When notifications are configured:

- **Slack**: "Fleet found 3 critical bugs, auto-fixing..."
- **Email**: "Fleet deployed v2.3.1 successfully, all validations passed"
- **Later**: "Fleet fixed all 3 bugs, deployed, validated"

## 🔍 What User Can Check (Optional)

### Quick Status Check

```bash
./scripts/transparency.sh
```

Shows real-time summary:
- Bugs found/fixed/pending
- Validation pass/fail rate
- Deployment success/failure
- Learning sessions
- GitHub issues open/closed

### Live Activity Stream

```bash
./scripts/transparency.sh --tail
```

Real-time log with color-coded events:
- 🔴 Critical events (bugs, failures)
- 🟡 Warnings (retries, degraded performance)
- 🟢 Success (fixes, deployments, validations)

### Recent Events

```bash
./scripts/transparency.sh --events
```

Last 20 events across all categories.

### Bug Tracking

```bash
./scripts/transparency.sh --bugs
```

Detailed bug discovery and fix status.

### JSON Output (for scripts/integrations)

```bash
./scripts/transparency.sh --json
```

Machine-readable state for custom dashboards.

## 📈 Grafana Dashboard

Visual real-time monitoring:

1. **Start Prometheus exporter**:
   ```bash
   node monitoring/prometheus-exporter.js
   ```

2. **Configure Prometheus** (add to `prometheus.yml`):
   ```yaml
   scrape_configs:
     - job_name: "fleet-transparency"
       static_configs:
         - targets: ["localhost:9090"]
   ```

3. **Import dashboard** to Grafana:
   ```bash
   monitoring/transparency-dashboard.json
   ```

### Dashboard Panels

- Real-time fleet status (bugs pending, validations failed)
- Bug discovery & fix rate over time
- Validation success rate gauge
- Recent events timeline
- Deployment success/failure pie chart
- Learning sessions counter
- GitHub issues status bar
- Bug severity breakdown table
- Fix attempt success rate
- Alerts & notifications

## 📁 File Locations

All transparency data stored in `~/.claude/learning/`:

- `transparency.log` - Human-readable log
- `transparency.json` - Structured event log (JSON array)
- `transparency-state.json` - Current state summary
- `notification-config.json` - Notification settings

## 🔔 Notifications

### Configure Slack

```javascript
const { configure } = require('./shared/notification-sender.js');

await configure({
  enabled: true,
  slack: {
    enabled: true,
    webhookUrl: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
    severityFilter: ['critical', 'high']
  }
});
```

### Configure Email

```javascript
await configure({
  enabled: true,
  email: {
    enabled: true,
    to: 'you@example.com',
    from: 'fleet@localhost',
    severityFilter: ['critical', 'high']
  }
});
```

### Configure GitHub Issues

```javascript
await configure({
  enabled: true,
  github: {
    enabled: true,
    createIssues: true,
    severityFilter: ['critical']
  }
});
```

## 🔧 Usage in Workflows

### Log Events

```javascript
const {
  logBugFound,
  logFixAttempt,
  logFixSuccess,
  logValidationPassed,
  logDeploymentSuccess,
} = require('../shared/transparency-logger.js');

// When bug found
await logBugFound({
  description: 'Null pointer dereference in auth.js',
  location: 'src/auth.js:42',
  impact: 'Login broken for all users',
  severity: 'critical',
  workflowRunId: 'workflow-123',
  metadata: {
    stackTrace: '...',
    affectedUsers: 1250
  }
});

// When attempting fix
await logFixAttempt({
  description: 'Adding null check before access',
  bugId: 'bug-001',
  workflowRunId: 'workflow-123'
});

// When fix succeeds
await logFixSuccess({
  description: 'Null check added, tests passing',
  bugId: 'bug-001',
  commitSha: 'abc123',
  workflowRunId: 'workflow-123'
});

// When validation passes
await logValidationPassed({
  description: 'Smoke tests passed',
  testCount: 15,
  workflowRunId: 'workflow-123'
});

// When deployment succeeds
await logDeploymentSuccess({
  description: 'Deployed to production',
  environment: 'production',
  version: '2.3.1',
  workflowRunId: 'workflow-123'
});
```

### Query State

```javascript
const { getState, queryEvents } = require('../shared/transparency-logger.js');

// Get current summary
const state = await getState();
console.log(`Bugs pending: ${state.summary.bugsPending}`);

// Query recent bugs
const recentBugs = await queryEvents({
  type: 'bug_found',
  limit: 10,
  since: '2026-06-01T00:00:00Z'
});

// Query critical events
const criticalEvents = await queryEvents({
  severity: 'critical',
  limit: 20
});
```

## 📋 Event Types

### Bug Tracking
- `bug_found` - New bug discovered
- `fix_attempt` - Attempting to fix bug
- `fix_success` - Fix successful
- `fix_failed` - Fix failed

### Validation
- `validation_started` - Validation suite started
- `validation_passed` - All validations passed
- `validation_failed` - Validation failures detected

### Deployment
- `deployment_started` - Deployment initiated
- `deployment_success` - Deployment successful
- `deployment_failed` - Deployment failed

### Learning
- `learning_started` - Learning session started
- `learning_complete` - Learning extracted and stored

### Discovery
- `discovery` - New insight/pattern discovered

### GitHub Issues
- `issue_created` - GitHub issue created
- `issue_updated` - GitHub issue updated
- `issue_closed` - GitHub issue closed

## 🎚️ Severity Levels

- `critical` - System down, data loss, security breach
- `high` - Major functionality broken, urgent fix needed
- `medium` - Minor functionality issues, fix soon
- `low` - Cosmetic issues, technical debt
- `info` - Informational events, status updates

## 🔐 Privacy & Security

- All logs stored locally in `~/.claude/learning/`
- No data sent to external services without explicit configuration
- Notification webhooks only used when configured
- GitHub integration respects repository permissions
- Sensitive data filtered from logs (credentials, tokens)

## 🚀 Quick Start

1. **Enable transparency logging** (automatic in all workflows)

2. **View status**:
   ```bash
   ./scripts/transparency.sh
   ```

3. **Optional: Configure notifications**:
   ```javascript
   const { configure } = require('./shared/notification-sender.js');
   await configure({
     enabled: true,
     slack: { enabled: true, webhookUrl: '...' }
   });
   ```

4. **Optional: Start Prometheus exporter**:
   ```bash
   node monitoring/prometheus-exporter.js &
   ```

5. **Optional: Import Grafana dashboard**:
   - Open Grafana
   - Import `monitoring/transparency-dashboard.json`

## 📊 Example Output

### CLI Summary

```
═══════════════════════════════════════════
  FLEET TRANSPARENCY SUMMARY
═══════════════════════════════════════════

Last Updated: 2026-06-13T10:30:45.123Z

BUGS:
  Found:   12
  Fixed:   10
  Pending: 2

VALIDATIONS:
  Passed: 45
  Failed: 3

DEPLOYMENTS:
  Success: 8
  Failed:  1

LEARNING:
  Sessions Complete: 15

ISSUES:
  Created: 5
  Closed:  3
  Open:    2

RECENT EVENTS:
  [10:30:45] Fixed null pointer in auth.js
  [10:28:12] Validation passed: smoke tests
  [10:25:33] Deployed v2.3.1 to production
  [10:20:15] Bug found: memory leak in worker
  [10:15:00] Learning complete: REST API patterns
```

### Log Entry Example

```
[2026-06-13T10:30:45.123Z] BUG_FOUND [HIGH]
  Bug: Null pointer dereference in auth.js
  Location: src/auth.js:42
  Impact: Login broken for all users
  Issue: #123
  Workflow: workflow-123

[2026-06-13T10:30:50.456Z] FIX_ATTEMPT
  Fix: Adding null check before access
  Bug ID: bug-001
  Workflow: workflow-123

[2026-06-13T10:31:15.789Z] FIX_SUCCESS
  Fix: Null check added, tests passing
  Bug ID: bug-001
  Commit: abc123def456
  Workflow: workflow-123

[2026-06-13T10:32:00.012Z] VALIDATION_PASSED
  Validation: Smoke tests passed
  Tests: 15
  Workflow: workflow-123

[2026-06-13T10:35:00.000Z] DEPLOYMENT_SUCCESS
  Deployment: Deployed to production
  Environment: production
  Version: 2.3.1
  Workflow: workflow-123
```

## 🎯 Design Principles

1. **Log Everything** - No hidden operations
2. **Multiple Channels** - CLI, files, dashboards, notifications
3. **Optional Visibility** - User can check anytime, or ignore
4. **Real-time Updates** - Live streaming of events
5. **Queryable History** - Full event log with filters
6. **Integration Friendly** - JSON output, Prometheus metrics
7. **Privacy First** - Local by default, opt-in for external services

## 🔗 Related Documentation

- [GitHub Issue Integration](./GITHUB_ISSUE_INTEGRATION_GUIDE.md)
- [Grafana Dashboard Guide](../monitoring/DASHBOARD_GUIDE.md)
- [Notification Configuration](./NOTIFICATION_CONFIG.md)
- [Metrics & Observability](./METRICS_AND_OBSERVABILITY.md)
