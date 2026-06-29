/**
 * Notification Sender - Multi-channel notification system
 *
 * Sends notifications to:
 * - Slack (via webhooks)
 * - Email (via nodemailer or sendmail)
 * - GitHub issues (via gh CLI)
 * - Console/terminal
 *
 * Used by transparency logger to alert users of critical events.
 */

const { execSync } = require('child_process');
const fs = require('fs').promises;
const path = require('path');

/**
 * Configuration file location
 */
const CONFIG_FILE = path.join(process.env.HOME, '.claude', 'learning', 'notification-config.json');

/**
 * Default configuration structure
 */
const DEFAULT_CONFIG = {
  enabled: false,
  channels: {
    slack: {
      enabled: false,
      webhookUrl: null,
      severityFilter: ['critical', 'high'],
    },
    email: {
      enabled: false,
      to: null,
      from: 'fleet@localhost',
      severityFilter: ['critical', 'high'],
    },
    github: {
      enabled: false,
      createIssues: false,
      severityFilter: ['critical'],
    },
    console: {
      enabled: true,
      severityFilter: ['critical', 'high', 'medium'],
    },
  },
};

/**
 * Load notification configuration
 */
async function loadConfig() {
  try {
    const content = await fs.readFile(CONFIG_FILE, 'utf8');
    return { ...DEFAULT_CONFIG, ...JSON.parse(content) };
  } catch {
    return DEFAULT_CONFIG;
  }
}

/**
 * Save notification configuration
 */
async function saveConfig(config) {
  const dir = path.dirname(CONFIG_FILE);
  try {
    await fs.mkdir(dir, { recursive: true });
  } catch {
    // Directory already exists
  }

  await fs.writeFile(CONFIG_FILE, JSON.stringify(config, null, 2));
}

/**
 * Send notification to all configured channels
 *
 * @param {Object} event - Event object from transparency logger
 */
async function sendNotification(event) {
  const config = await loadConfig();

  if (!config.enabled) {
    return;
  }

  const promises = [];

  // Slack
  if (shouldNotify(config.channels.slack, event.severity)) {
    promises.push(sendSlack(config.channels.slack, event));
  }

  // Email
  if (shouldNotify(config.channels.email, event.severity)) {
    promises.push(sendEmail(config.channels.email, event));
  }

  // GitHub
  if (shouldNotify(config.channels.github, event.severity)) {
    promises.push(sendGitHub(config.channels.github, event));
  }

  // Console (always enabled by default)
  if (shouldNotify(config.channels.console, event.severity)) {
    sendConsole(event);
  }

  await Promise.allSettled(promises);
}

/**
 * Check if notification should be sent based on severity filter
 */
function shouldNotify(channelConfig, severity) {
  if (!channelConfig.enabled) {
    return false;
  }

  if (!channelConfig.severityFilter || channelConfig.severityFilter.length === 0) {
    return true;
  }

  return channelConfig.severityFilter.includes(severity);
}

/**
 * Send Slack notification
 */
async function sendSlack(config, event) {
  if (!config.webhookUrl) {
    return;
  }

  try {
    const payload = {
      text: formatSlackMessage(event),
      attachments: [
        {
          color: getSeverityColor(event.severity),
          fields: [
            {
              title: 'Type',
              value: event.type,
              short: true,
            },
            {
              title: 'Severity',
              value: event.severity.toUpperCase(),
              short: true,
            },
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

    // Add workflow link if available
    if (event.workflowRunId) {
      payload.attachments[0].fields.push({
        title: 'Workflow',
        value: event.workflowRunId,
        short: true,
      });
    }

    // Add issue link if available
    if (event.issueNumber && event.url) {
      payload.attachments[0].fields.push({
        title: 'Issue',
        value: `<${event.url}|#${event.issueNumber}>`,
        short: true,
      });
    }

    const payloadJson = JSON.stringify(payload).replace(/'/g, "'\\''");

    execSync(`curl -X POST -H 'Content-type: application/json' --data '${payloadJson}' '${config.webhookUrl}'`, {
      stdio: 'pipe',
      timeout: 5000,
    });

    console.log('✓ Sent Slack notification');
  } catch (error) {
    console.error(`✗ Failed to send Slack notification: ${error.message}`);
  }
}

/**
 * Send email notification
 */
async function sendEmail(config, event) {
  if (!config.to) {
    return;
  }

  try {
    const subject = `Fleet Alert [${event.severity.toUpperCase()}]: ${event.type}`;
    const body = formatEmailBody(event);

    // Use sendmail command (simple, no dependencies)
    const emailContent = `Subject: ${subject}\nFrom: ${config.from}\nTo: ${config.to}\n\n${body}`;

    execSync('sendmail -t', {
      input: emailContent,
      stdio: 'pipe',
      timeout: 5000,
    });

    console.log('✓ Sent email notification');
  } catch (error) {
    console.error(`✗ Failed to send email: ${error.message}`);
  }
}

/**
 * Send GitHub notification (create issue)
 */
async function sendGitHub(config, event) {
  if (!config.createIssues) {
    return;
  }

  try {
    // Check if gh CLI is available
    try {
      execSync('which gh', { stdio: 'ignore' });
    } catch {
      console.error('✗ GitHub CLI (gh) not available, skipping issue creation');
      return;
    }

    // Only create issues for bugs/validation failures
    if (!event.type.includes('bug') && !event.type.includes('validation_failed')) {
      return;
    }

    // Use the github-issue-integration module
    const { createValidationIssue } = require('./github-issue-integration.js');

    await createValidationIssue({
      title: `[Fleet Alert] ${event.description || event.title}`,
      body: formatGitHubIssueBody(event),
      severity: event.severity,
      workflowRunId: event.workflowRunId || 'unknown',
      failureDetails: event.metadata || {},
    });

    console.log('✓ Created GitHub issue');
  } catch (error) {
    console.error(`✗ Failed to create GitHub issue: ${error.message}`);
  }
}

/**
 * Send console notification
 */
function sendConsole(event) {
  const timestamp = new Date(event.timestamp).toLocaleTimeString();
  const icon = getSeverityIcon(event.severity);
  const message = event.description || event.title || event.type;

  console.log(`\n${icon} [${timestamp}] ${event.severity.toUpperCase()}: ${message}\n`);
}

/**
 * Format Slack message
 */
function formatSlackMessage(event) {
  const icon = getSeverityIcon(event.severity);
  const message = event.description || event.title || event.type;
  return `${icon} *Fleet Alert* [${event.severity.toUpperCase()}]: ${message}`;
}

/**
 * Format email body
 */
function formatEmailBody(event) {
  let body = `Fleet Transparency Alert\n`;
  body += `${'='.repeat(60)}\n\n`;

  body += `Type:        ${event.type}\n`;
  body += `Severity:    ${event.severity.toUpperCase()}\n`;
  body += `Timestamp:   ${event.timestamp}\n`;
  body += `Description: ${event.description || event.title || 'No description'}\n\n`;

  if (event.workflowRunId) {
    body += `Workflow:    ${event.workflowRunId}\n`;
  }

  if (event.issueNumber) {
    body += `Issue:       #${event.issueNumber}\n`;
    if (event.url) {
      body += `URL:         ${event.url}\n`;
    }
  }

  if (event.metadata && Object.keys(event.metadata).length > 0) {
    body += `\nMetadata:\n`;
    body += JSON.stringify(event.metadata, null, 2);
  }

  body += `\n\n${'='.repeat(60)}\n`;
  body += `View full transparency log: ~/.claude/learning/transparency.log\n`;

  return body;
}

/**
 * Format GitHub issue body
 */
function formatGitHubIssueBody(event) {
  let body = event.description || event.title || 'Fleet detected an issue';
  body += '\n\n';

  body += '## Event Details\n\n';
  body += `- **Type**: ${event.type}\n`;
  body += `- **Severity**: ${event.severity}\n`;
  body += `- **Timestamp**: ${event.timestamp}\n`;

  if (event.workflowRunId) {
    body += `- **Workflow**: \`${event.workflowRunId}\`\n`;
  }

  if (event.metadata && Object.keys(event.metadata).length > 0) {
    body += '\n## Metadata\n\n';
    body += '```json\n';
    body += JSON.stringify(event.metadata, null, 2);
    body += '\n```\n';
  }

  return body;
}

/**
 * Get color for severity level (Slack/etc)
 */
function getSeverityColor(severity) {
  switch (severity) {
    case 'critical':
      return 'danger';
    case 'high':
      return 'warning';
    case 'medium':
      return '#439FE0'; // Blue
    case 'low':
      return 'good';
    default:
      return '#808080'; // Gray
  }
}

/**
 * Get icon for severity level
 */
function getSeverityIcon(severity) {
  switch (severity) {
    case 'critical':
      return '🚨';
    case 'high':
      return '⚠️';
    case 'medium':
      return 'ℹ️';
    case 'low':
      return '•';
    default:
      return '•';
  }
}

/**
 * Configure notifications (interactive or programmatic)
 */
async function configure(options = {}) {
  const config = await loadConfig();

  // Enable/disable notifications
  if (options.enabled !== undefined) {
    config.enabled = options.enabled;
  }

  // Configure Slack
  if (options.slack) {
    config.channels.slack = { ...config.channels.slack, ...options.slack };
  }

  // Configure Email
  if (options.email) {
    config.channels.email = { ...config.channels.email, ...options.email };
  }

  // Configure GitHub
  if (options.github) {
    config.channels.github = { ...config.channels.github, ...options.github };
  }

  await saveConfig(config);
  console.log('✓ Notification configuration updated');

  return config;
}

/**
 * Get current configuration
 */
async function getConfig() {
  return await loadConfig();
}

module.exports = {
  sendNotification,
  configure,
  getConfig,
  loadConfig,
  saveConfig,
};
