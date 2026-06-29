/**
 * Transparency Logger - Complete visibility into fleet operations
 *
 * Logs EVERYTHING the fleet does:
 * - Every bug found
 * - Every fix attempt
 * - Every validation result
 * - Every deployment
 * - Every learning session
 * - Every discovery
 *
 * Output channels:
 * - File logs (~/.claude/learning/transparency.log)
 * - Console output (human-readable)
 * - GitHub issues (bugs/blockers)
 * - Structured JSON (for dashboards)
 * - Slack/email notifications (optional)
 */

const fs = require('fs').promises;
const path = require('path');
const { execSync } = require('child_process');

/**
 * Configuration
 */
const CONFIG = {
  LOG_DIR: path.join(process.env.HOME, '.claude', 'learning'),
  LOG_FILE: 'transparency.log',
  JSON_LOG_FILE: 'transparency.json',
  STATE_FILE: 'transparency-state.json',

  // Console colors
  COLORS: {
    RESET: '\x1b[0m',
    RED: '\x1b[31m',
    GREEN: '\x1b[32m',
    YELLOW: '\x1b[33m',
    BLUE: '\x1b[34m',
    MAGENTA: '\x1b[35m',
    CYAN: '\x1b[36m',
    GRAY: '\x1b[90m',
  },

  // Event types
  EVENTS: {
    BUG_FOUND: 'bug_found',
    FIX_ATTEMPT: 'fix_attempt',
    FIX_SUCCESS: 'fix_success',
    FIX_FAILED: 'fix_failed',
    VALIDATION_STARTED: 'validation_started',
    VALIDATION_PASSED: 'validation_passed',
    VALIDATION_FAILED: 'validation_failed',
    DEPLOYMENT_STARTED: 'deployment_started',
    DEPLOYMENT_SUCCESS: 'deployment_success',
    DEPLOYMENT_FAILED: 'deployment_failed',
    LEARNING_STARTED: 'learning_started',
    LEARNING_COMPLETE: 'learning_complete',
    DISCOVERY: 'discovery',
    ISSUE_CREATED: 'issue_created',
    ISSUE_UPDATED: 'issue_updated',
    ISSUE_CLOSED: 'issue_closed',
  },

  // Severity levels
  SEVERITY: {
    CRITICAL: 'critical',
    HIGH: 'high',
    MEDIUM: 'medium',
    LOW: 'low',
    INFO: 'info',
  },
};

/**
 * Initialize logging system
 */
async function initialize() {
  try {
    await fs.mkdir(CONFIG.LOG_DIR, { recursive: true });

    // Create log files if they don't exist
    const logPath = path.join(CONFIG.LOG_DIR, CONFIG.LOG_FILE);
    const jsonLogPath = path.join(CONFIG.LOG_DIR, CONFIG.JSON_LOG_FILE);

    try {
      await fs.access(logPath);
    } catch {
      await fs.writeFile(logPath, `# Transparency Log - Initialized ${new Date().toISOString()}\n\n`);
    }

    try {
      await fs.access(jsonLogPath);
    } catch {
      await fs.writeFile(jsonLogPath, '[]');
    }

    return true;
  } catch (error) {
    console.error(`Failed to initialize transparency logger: ${error.message}`);
    return false;
  }
}

/**
 * Log an event to all channels
 */
async function log(eventType, data = {}) {
  await initialize();

  const event = {
    timestamp: new Date().toISOString(),
    type: eventType,
    severity: data.severity || CONFIG.SEVERITY.INFO,
    ...data,
  };

  // Log to file (human-readable)
  await logToFile(event);

  // Log to JSON (structured)
  await logToJSON(event);

  // Log to console
  logToConsole(event);

  // Update state (for dashboard queries)
  await updateState(event);

  return event;
}

/**
 * Log to human-readable file
 */
async function logToFile(event) {
  const logPath = path.join(CONFIG.LOG_DIR, CONFIG.LOG_FILE);

  let logEntry = `[${event.timestamp}] ${event.type.toUpperCase()}`;

  if (event.severity && event.severity !== CONFIG.SEVERITY.INFO) {
    logEntry += ` [${event.severity.toUpperCase()}]`;
  }

  logEntry += '\n';

  // Add details based on event type
  switch (event.type) {
    case CONFIG.EVENTS.BUG_FOUND:
      logEntry += `  Bug: ${event.description}\n`;
      logEntry += `  Location: ${event.location || 'unknown'}\n`;
      logEntry += `  Impact: ${event.impact || 'unknown'}\n`;
      if (event.issueNumber) {
        logEntry += `  Issue: #${event.issueNumber}\n`;
      }
      break;

    case CONFIG.EVENTS.FIX_ATTEMPT:
    case CONFIG.EVENTS.FIX_SUCCESS:
    case CONFIG.EVENTS.FIX_FAILED:
      logEntry += `  Fix: ${event.description}\n`;
      if (event.bugId) {
        logEntry += `  Bug ID: ${event.bugId}\n`;
      }
      if (event.commitSha) {
        logEntry += `  Commit: ${event.commitSha}\n`;
      }
      if (event.error) {
        logEntry += `  Error: ${event.error}\n`;
      }
      break;

    case CONFIG.EVENTS.VALIDATION_STARTED:
    case CONFIG.EVENTS.VALIDATION_PASSED:
    case CONFIG.EVENTS.VALIDATION_FAILED:
      logEntry += `  Validation: ${event.description}\n`;
      if (event.testCount) {
        logEntry += `  Tests: ${event.testCount}\n`;
      }
      if (event.failures) {
        logEntry += `  Failures: ${event.failures}\n`;
      }
      break;

    case CONFIG.EVENTS.DEPLOYMENT_STARTED:
    case CONFIG.EVENTS.DEPLOYMENT_SUCCESS:
    case CONFIG.EVENTS.DEPLOYMENT_FAILED:
      logEntry += `  Deployment: ${event.description}\n`;
      if (event.environment) {
        logEntry += `  Environment: ${event.environment}\n`;
      }
      if (event.version) {
        logEntry += `  Version: ${event.version}\n`;
      }
      break;

    case CONFIG.EVENTS.LEARNING_STARTED:
    case CONFIG.EVENTS.LEARNING_COMPLETE:
      logEntry += `  Learning: ${event.description}\n`;
      if (event.source) {
        logEntry += `  Source: ${event.source}\n`;
      }
      break;

    case CONFIG.EVENTS.DISCOVERY:
      logEntry += `  Discovery: ${event.description}\n`;
      if (event.details) {
        logEntry += `  Details: ${event.details}\n`;
      }
      break;

    case CONFIG.EVENTS.ISSUE_CREATED:
    case CONFIG.EVENTS.ISSUE_UPDATED:
    case CONFIG.EVENTS.ISSUE_CLOSED:
      logEntry += `  Issue #${event.issueNumber}: ${event.title}\n`;
      if (event.url) {
        logEntry += `  URL: ${event.url}\n`;
      }
      break;
  }

  // Add workflow context if present
  if (event.workflowRunId) {
    logEntry += `  Workflow: ${event.workflowRunId}\n`;
  }

  // Add metadata if present
  if (event.metadata && Object.keys(event.metadata).length > 0) {
    logEntry += `  Metadata: ${JSON.stringify(event.metadata)}\n`;
  }

  logEntry += '\n';

  await fs.appendFile(logPath, logEntry);
}

/**
 * Log to structured JSON file
 */
async function logToJSON(event) {
  const jsonLogPath = path.join(CONFIG.LOG_DIR, CONFIG.JSON_LOG_FILE);

  try {
    // Read existing logs
    const content = await fs.readFile(jsonLogPath, 'utf8');
    const logs = JSON.parse(content);

    // Append new event
    logs.push(event);

    // Keep only last 10000 events (prevent unbounded growth)
    if (logs.length > 10000) {
      logs.splice(0, logs.length - 10000);
    }

    // Write back
    await fs.writeFile(jsonLogPath, JSON.stringify(logs, null, 2));
  } catch (error) {
    console.error(`Failed to log to JSON: ${error.message}`);
  }
}

/**
 * Log to console with colors
 */
function logToConsole(event) {
  const { COLORS } = CONFIG;

  // Choose color based on event type and severity
  let color = COLORS.RESET;
  let icon = '•';

  switch (event.severity) {
    case CONFIG.SEVERITY.CRITICAL:
      color = COLORS.RED;
      icon = '✗';
      break;
    case CONFIG.SEVERITY.HIGH:
      color = COLORS.YELLOW;
      icon = '⚠';
      break;
    case CONFIG.SEVERITY.MEDIUM:
      color = COLORS.BLUE;
      icon = 'ℹ';
      break;
    case CONFIG.SEVERITY.LOW:
    case CONFIG.SEVERITY.INFO:
      color = COLORS.GRAY;
      icon = '•';
      break;
  }

  // Success events get green
  if (event.type.includes('success') || event.type.includes('passed') || event.type.includes('complete')) {
    color = COLORS.GREEN;
    icon = '✓';
  }

  const timestamp = new Date(event.timestamp).toLocaleTimeString();
  const message = event.description || event.title || event.type;

  console.log(`${COLORS.GRAY}[${timestamp}]${COLORS.RESET} ${color}${icon} ${message}${COLORS.RESET}`);
}

/**
 * Update state file (for dashboard queries)
 */
async function updateState(event) {
  const statePath = path.join(CONFIG.LOG_DIR, CONFIG.STATE_FILE);

  try {
    // Load existing state
    let state;
    try {
      const content = await fs.readFile(statePath, 'utf8');
      state = JSON.parse(content);
    } catch {
      state = {
        summary: {
          bugsFound: 0,
          bugsFixed: 0,
          bugsPending: 0,
          validationsPassed: 0,
          validationsFailed: 0,
          deploymentsSuccess: 0,
          deploymentsFailed: 0,
          learningSessionsComplete: 0,
          issuesCreated: 0,
          issuesClosed: 0,
        },
        lastUpdated: null,
        recentEvents: [],
      };
    }

    // Update summary based on event type
    switch (event.type) {
      case CONFIG.EVENTS.BUG_FOUND:
        state.summary.bugsFound++;
        state.summary.bugsPending++;
        break;
      case CONFIG.EVENTS.FIX_SUCCESS:
        state.summary.bugsFixed++;
        state.summary.bugsPending--;
        break;
      case CONFIG.EVENTS.VALIDATION_PASSED:
        state.summary.validationsPassed++;
        break;
      case CONFIG.EVENTS.VALIDATION_FAILED:
        state.summary.validationsFailed++;
        break;
      case CONFIG.EVENTS.DEPLOYMENT_SUCCESS:
        state.summary.deploymentsSuccess++;
        break;
      case CONFIG.EVENTS.DEPLOYMENT_FAILED:
        state.summary.deploymentsFailed++;
        break;
      case CONFIG.EVENTS.LEARNING_COMPLETE:
        state.summary.learningSessionsComplete++;
        break;
      case CONFIG.EVENTS.ISSUE_CREATED:
        state.summary.issuesCreated++;
        break;
      case CONFIG.EVENTS.ISSUE_CLOSED:
        state.summary.issuesClosed++;
        break;
    }

    // Update timestamp
    state.lastUpdated = event.timestamp;

    // Add to recent events (keep last 100)
    state.recentEvents.push({
      timestamp: event.timestamp,
      type: event.type,
      description: event.description || event.title || event.type,
    });

    if (state.recentEvents.length > 100) {
      state.recentEvents.splice(0, state.recentEvents.length - 100);
    }

    // Save state
    await fs.writeFile(statePath, JSON.stringify(state, null, 2));
  } catch (error) {
    console.error(`Failed to update state: ${error.message}`);
  }
}

/**
 * Get current state summary
 */
async function getState() {
  const statePath = path.join(CONFIG.LOG_DIR, CONFIG.STATE_FILE);

  try {
    const content = await fs.readFile(statePath, 'utf8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * Query recent events
 */
async function queryEvents(options = {}) {
  const {
    type = null,
    severity = null,
    limit = 100,
    since = null,
  } = options;

  const jsonLogPath = path.join(CONFIG.LOG_DIR, CONFIG.JSON_LOG_FILE);

  try {
    const content = await fs.readFile(jsonLogPath, 'utf8');
    let events = JSON.parse(content);

    // Filter by type
    if (type) {
      events = events.filter(e => e.type === type);
    }

    // Filter by severity
    if (severity) {
      events = events.filter(e => e.severity === severity);
    }

    // Filter by timestamp
    if (since) {
      const sinceDate = new Date(since);
      events = events.filter(e => new Date(e.timestamp) >= sinceDate);
    }

    // Apply limit
    events = events.slice(-limit);

    return events;
  } catch (error) {
    console.error(`Failed to query events: ${error.message}`);
    return [];
  }
}

/**
 * Send notification (Slack, email, etc.)
 */
async function sendNotification(event) {
  // Check if notifications are configured
  const notifyConfig = await loadNotificationConfig();

  if (!notifyConfig.enabled) {
    return;
  }

  // Only notify for critical/high severity events
  if (event.severity !== CONFIG.SEVERITY.CRITICAL && event.severity !== CONFIG.SEVERITY.HIGH) {
    return;
  }

  // Send to configured channels
  if (notifyConfig.slack && notifyConfig.slack.webhookUrl) {
    await sendSlackNotification(notifyConfig.slack.webhookUrl, event);
  }

  if (notifyConfig.email && notifyConfig.email.enabled) {
    await sendEmailNotification(notifyConfig.email, event);
  }
}

/**
 * Load notification configuration
 */
async function loadNotificationConfig() {
  const configPath = path.join(CONFIG.LOG_DIR, 'notification-config.json');

  try {
    const content = await fs.readFile(configPath, 'utf8');
    return JSON.parse(content);
  } catch {
    return { enabled: false };
  }
}

/**
 * Send Slack notification
 */
async function sendSlackNotification(webhookUrl, event) {
  try {
    const payload = {
      text: `*${event.type.toUpperCase()}* [${event.severity}]`,
      attachments: [
        {
          color: event.severity === CONFIG.SEVERITY.CRITICAL ? 'danger' : 'warning',
          fields: [
            {
              title: 'Description',
              value: event.description || event.title || 'No description',
              short: false,
            },
            {
              title: 'Timestamp',
              value: event.timestamp,
              short: true,
            },
          ],
        },
      ],
    };

    execSync(`curl -X POST -H 'Content-type: application/json' --data '${JSON.stringify(payload)}' ${webhookUrl}`, {
      stdio: 'ignore',
    });
  } catch (error) {
    console.error(`Failed to send Slack notification: ${error.message}`);
  }
}

/**
 * Send email notification
 */
async function sendEmailNotification(emailConfig, event) {
  // Placeholder - implement using nodemailer or similar
  console.log('Email notifications not yet implemented');
}

/**
 * Generate summary report
 */
async function generateSummary(since = null) {
  const state = await getState();
  const events = await queryEvents({ since, limit: 1000 });

  if (!state) {
    return 'No transparency data available yet.';
  }

  let report = '\n';
  report += '═══════════════════════════════════════════\n';
  report += '  FLEET TRANSPARENCY SUMMARY\n';
  report += '═══════════════════════════════════════════\n\n';

  report += `Last Updated: ${state.lastUpdated}\n\n`;

  report += 'BUGS:\n';
  report += `  Found:   ${state.summary.bugsFound}\n`;
  report += `  Fixed:   ${state.summary.bugsFixed}\n`;
  report += `  Pending: ${state.summary.bugsPending}\n\n`;

  report += 'VALIDATIONS:\n';
  report += `  Passed: ${state.summary.validationsPassed}\n`;
  report += `  Failed: ${state.summary.validationsFailed}\n\n`;

  report += 'DEPLOYMENTS:\n';
  report += `  Success: ${state.summary.deploymentsSuccess}\n`;
  report += `  Failed:  ${state.summary.deploymentsFailed}\n\n`;

  report += 'LEARNING:\n';
  report += `  Sessions Complete: ${state.summary.learningSessionsComplete}\n\n`;

  report += 'ISSUES:\n';
  report += `  Created: ${state.summary.issuesCreated}\n`;
  report += `  Closed:  ${state.summary.issuesClosed}\n`;
  report += `  Open:    ${state.summary.issuesCreated - state.summary.issuesClosed}\n\n`;

  report += 'RECENT EVENTS:\n';
  const recentCount = Math.min(10, state.recentEvents.length);
  for (let i = state.recentEvents.length - recentCount; i < state.recentEvents.length; i++) {
    const evt = state.recentEvents[i];
    const time = new Date(evt.timestamp).toLocaleTimeString();
    report += `  [${time}] ${evt.description}\n`;
  }

  report += '\n';
  report += '═══════════════════════════════════════════\n';

  return report;
}

module.exports = {
  CONFIG,
  initialize,
  log,
  getState,
  queryEvents,
  sendNotification,
  generateSummary,

  // Helper functions for common events
  logBugFound: async (data) => log(CONFIG.EVENTS.BUG_FOUND, { severity: CONFIG.SEVERITY.HIGH, ...data }),
  logFixAttempt: async (data) => log(CONFIG.EVENTS.FIX_ATTEMPT, data),
  logFixSuccess: async (data) => log(CONFIG.EVENTS.FIX_SUCCESS, { severity: CONFIG.SEVERITY.INFO, ...data }),
  logFixFailed: async (data) => log(CONFIG.EVENTS.FIX_FAILED, { severity: CONFIG.SEVERITY.HIGH, ...data }),
  logValidationStarted: async (data) => log(CONFIG.EVENTS.VALIDATION_STARTED, data),
  logValidationPassed: async (data) => log(CONFIG.EVENTS.VALIDATION_PASSED, { severity: CONFIG.SEVERITY.INFO, ...data }),
  logValidationFailed: async (data) => log(CONFIG.EVENTS.VALIDATION_FAILED, { severity: CONFIG.SEVERITY.HIGH, ...data }),
  logDeploymentStarted: async (data) => log(CONFIG.EVENTS.DEPLOYMENT_STARTED, data),
  logDeploymentSuccess: async (data) => log(CONFIG.EVENTS.DEPLOYMENT_SUCCESS, { severity: CONFIG.SEVERITY.INFO, ...data }),
  logDeploymentFailed: async (data) => log(CONFIG.EVENTS.DEPLOYMENT_FAILED, { severity: CONFIG.SEVERITY.CRITICAL, ...data }),
  logLearningStarted: async (data) => log(CONFIG.EVENTS.LEARNING_STARTED, data),
  logLearningComplete: async (data) => log(CONFIG.EVENTS.LEARNING_COMPLETE, data),
  logDiscovery: async (data) => log(CONFIG.EVENTS.DISCOVERY, data),
  logIssueCreated: async (data) => log(CONFIG.EVENTS.ISSUE_CREATED, { severity: CONFIG.SEVERITY.MEDIUM, ...data }),
  logIssueUpdated: async (data) => log(CONFIG.EVENTS.ISSUE_UPDATED, data),
  logIssueClosed: async (data) => log(CONFIG.EVENTS.ISSUE_CLOSED, { severity: CONFIG.SEVERITY.INFO, ...data }),
};
