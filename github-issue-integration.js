/**
 * GitHub Issue Integration Module
 *
 * Integrates validation workflow results with GitHub issues:
 * - Creates issues when fleet validation finds blockers/bugs
 * - Links issues to workflow run IDs
 * - Updates/closes issues when fleet fixes issues
 * - Tracks issue metadata in workflow state
 *
 * Usage:
 *   const { createValidationIssue, updateIssueWithFix, closeIssue } =
 *     require('./github-issue-integration.js');
 *
 * Examples:
 *   // Create issue for validation failure
 *   const issue = await createValidationIssue({
 *     title: 'Smoke test failed on deploy',
 *     body: 'App crashes on startup',
 *     severity: 'blocker',
 *     workflowRunId: 'workflow-123',
 *     failureDetails: { test: 'launch', error: 'Segfault' }
 *   });
 *
 *   // Update issue with fix details
 *   await updateIssueWithFix({
 *     issueNumber: 42,
 *     fixDetails: 'Applied patch...',
 *     commitShas: ['abc123', 'def456']
 *   });
 *
 *   // Close issue after validation passes
 *   await closeIssue({ issueNumber: 42 });
 */

const { execSync } = require('child_process');
const fs = require('fs').promises;
const path = require('path');

/**
 * Configuration for GitHub integration
 */
const CONFIG = {
  // GitHub CLI must be installed and authenticated
  GH_AVAILABLE: (() => {
    try {
      execSync('which gh', { stdio: 'ignore' });
      return true;
    } catch {
      return false;
    }
  })(),

  // Labels for validation issues
  LABELS: {
    BLOCKER: 'validation-blocker',
    BUG: 'validation-bug',
    FLAKY: 'validation-flaky',
    PERFORMANCE: 'validation-performance',
    SECURITY: 'validation-security',
    AUTO_CREATED: 'auto-created',
  },

  // State file for tracking created issues
  STATE_FILE: '.claude/workflow-issue-state.json',
};

/**
 * Load workflow state (tracking of created issues)
 */
async function loadWorkflowState() {
  try {
    const data = await fs.readFile(CONFIG.STATE_FILE, 'utf8');
    return JSON.parse(data);
  } catch {
    return { issues: [], workflows: {} };
  }
}

/**
 * Save workflow state
 */
async function saveWorkflowState(state) {
  const dir = path.dirname(CONFIG.STATE_FILE);
  try {
    await fs.mkdir(dir, { recursive: true });
  } catch {
    // Ignore if directory already exists
  }
  await fs.writeFile(CONFIG.STATE_FILE, JSON.stringify(state, null, 2));
}

/**
 * Execute gh CLI command with error handling
 */
function executeGh(args) {
  if (!CONFIG.GH_AVAILABLE) {
    throw new Error('GitHub CLI (gh) not available. Install with: brew install gh');
  }

  try {
    const result = execSync(`gh ${args}`, {
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe']
    });
    return result.trim();
  } catch (error) {
    throw new Error(`gh CLI error: ${error.message}`);
  }
}

/**
 * Detect current repository (owner/repo)
 */
function detectRepository() {
  try {
    const remoteUrl = execSync('git remote get-url origin', {
      encoding: 'utf8'
    }).trim();

    // Parse github.com:owner/repo.git or https://github.com/owner/repo.git
    const match = remoteUrl.match(/(?:git@github\.com:|https:\/\/github\.com\/)([^/]+)\/(.+?)(?:\.git)?$/);
    if (match) {
      return {
        owner: match[1],
        repo: match[2].replace(/\.git$/, ''),
        url: `https://github.com/${match[1]}/${match[2].replace(/\.git$/, '')}`
      };
    }
  } catch {
    // git command failed
  }

  throw new Error('Could not detect GitHub repository. Ensure you are in a git repo with a GitHub remote.');
}

/**
 * Create a GitHub issue for validation failure
 *
 * @param {Object} options - Issue options
 * @param {string} options.title - Issue title
 * @param {string} options.body - Issue body/description
 * @param {string} options.severity - Issue severity (blocker, bug, flaky, performance, security)
 * @param {string} options.workflowRunId - Link to workflow run for traceability
 * @param {Object} options.failureDetails - Details about the failure
 * @param {string[]} [options.labels] - Additional labels
 * @param {boolean} [options.dryRun] - Dry run mode (don't actually create)
 *
 * @returns {Object} Issue metadata { number, url, title, workflowRunId }
 */
async function createValidationIssue(options) {
  const {
    title,
    body,
    severity = 'bug',
    workflowRunId,
    failureDetails = {},
    labels = [],
    dryRun = false
  } = options;

  if (!title || !body) {
    throw new Error('createValidationIssue requires title and body');
  }

  // Build issue body with metadata
  const fullBody = buildIssueBody({
    description: body,
    severity,
    workflowRunId,
    failureDetails,
    createdBy: 'fleet-validation',
    timestamp: new Date().toISOString()
  });

  // Determine labels
  const issueLabels = [
    CONFIG.LABELS[severity.toUpperCase()] || CONFIG.LABELS.BUG,
    CONFIG.LABELS.AUTO_CREATED,
    ...labels
  ];

  if (dryRun) {
    console.log('[DRY RUN] Would create GitHub issue:');
    console.log(`  Title: ${title}`);
    console.log(`  Labels: ${issueLabels.join(', ')}`);
    console.log(`  Body length: ${fullBody.length} chars`);

    return {
      number: 0,
      url: 'https://github.com/... (dry run)',
      title,
      workflowRunId,
      isDryRun: true
    };
  }

  try {
    // Create the issue via GitHub CLI
    const args = [
      'issue create',
      `--title ${escapeArg(title)}`,
      `--body ${escapeArg(fullBody)}`,
      `--label ${issueLabels.map(l => `"${l}"`).join(',')}`
    ].join(' ');

    const output = executeGh(args);

    // Extract issue number from output (e.g., "https://github.com/owner/repo/issues/42")
    const match = output.match(/\/issues\/(\d+)/);
    if (!match) {
      throw new Error(`Could not parse issue number from: ${output}`);
    }

    const issueNumber = parseInt(match[1], 10);
    const repo = detectRepository();
    const issueUrl = `${repo.url}/issues/${issueNumber}`;

    // Track in workflow state
    const state = await loadWorkflowState();
    state.issues.push({
      number: issueNumber,
      url: issueUrl,
      title,
      severity,
      workflowRunId,
      createdAt: new Date().toISOString(),
      status: 'open',
      linkedCommits: []
    });

    if (!state.workflows[workflowRunId]) {
      state.workflows[workflowRunId] = {
        issues: [issueNumber],
        status: 'in-progress',
        createdAt: new Date().toISOString()
      };
    } else {
      state.workflows[workflowRunId].issues.push(issueNumber);
    }

    await saveWorkflowState(state);

    console.log(`✓ Created issue #${issueNumber}: ${issueUrl}`);

    return {
      number: issueNumber,
      url: issueUrl,
      title,
      severity,
      workflowRunId
    };
  } catch (error) {
    console.error(`✗ Failed to create GitHub issue: ${error.message}`);
    throw error;
  }
}

/**
 * Update issue with fix details and mark related commits
 *
 * @param {Object} options - Update options
 * @param {number} options.issueNumber - GitHub issue number
 * @param {string} options.fixDetails - Description of the fix
 * @param {string[]} options.commitShas - Array of commit SHAs that fix the issue
 * @param {boolean} [options.dryRun] - Dry run mode
 *
 * @returns {Object} Update result { issueNumber, comment }
 */
async function updateIssueWithFix(options) {
  const {
    issueNumber,
    fixDetails,
    commitShas = [],
    dryRun = false
  } = options;

  if (!issueNumber || !fixDetails) {
    throw new Error('updateIssueWithFix requires issueNumber and fixDetails');
  }

  const comment = buildFixComment({
    fixDetails,
    commitShas,
    appliedBy: 'fleet-validation',
    timestamp: new Date().toISOString()
  });

  if (dryRun) {
    console.log(`[DRY RUN] Would add comment to issue #${issueNumber}`);
    console.log(`Comment length: ${comment.length} chars`);
    return {
      issueNumber,
      comment,
      isDryRun: true
    };
  }

  try {
    const args = [
      'issue comment',
      issueNumber,
      `--body ${escapeArg(comment)}`
    ].join(' ');

    const output = executeGh(args);
    console.log(`✓ Added fix comment to issue #${issueNumber}`);

    // Update workflow state
    const state = await loadWorkflowState();
    const issueEntry = state.issues.find(i => i.number === issueNumber);
    if (issueEntry) {
      issueEntry.linkedCommits.push(...commitShas);
      issueEntry.lastFixedAt = new Date().toISOString();
    }
    await saveWorkflowState(state);

    return {
      issueNumber,
      comment,
      output
    };
  } catch (error) {
    console.error(`✗ Failed to add comment to issue #${issueNumber}: ${error.message}`);
    throw error;
  }
}

/**
 * Close GitHub issue after fix validation
 *
 * @param {Object} options - Close options
 * @param {number} options.issueNumber - GitHub issue number
 * @param {string} [options.reason] - Reason for closing
 * @param {boolean} [options.dryRun] - Dry run mode
 *
 * @returns {Object} Close result { issueNumber, url }
 */
async function closeIssue(options) {
  const {
    issueNumber,
    reason = 'Fixed by fleet validation',
    dryRun = false
  } = options;

  if (!issueNumber) {
    throw new Error('closeIssue requires issueNumber');
  }

  if (dryRun) {
    console.log(`[DRY RUN] Would close issue #${issueNumber} with reason: ${reason}`);
    return {
      issueNumber,
      isDryRun: true
    };
  }

  try {
    const args = [
      'issue close',
      issueNumber,
      `--comment ${escapeArg(reason)}`
    ].join(' ');

    const output = executeGh(args);
    console.log(`✓ Closed issue #${issueNumber}`);

    // Update workflow state
    const state = await loadWorkflowState();
    const issueEntry = state.issues.find(i => i.number === issueNumber);
    if (issueEntry) {
      issueEntry.status = 'closed';
      issueEntry.closedAt = new Date().toISOString();
    }
    await saveWorkflowState(state);

    const repo = detectRepository();
    return {
      issueNumber,
      url: `${repo.url}/issues/${issueNumber}`,
      closed: true
    };
  } catch (error) {
    console.error(`✗ Failed to close issue #${issueNumber}: ${error.message}`);
    throw error;
  }
}

/**
 * Link issue to workflow run (add comment with workflow URL)
 *
 * @param {Object} options - Link options
 * @param {number} options.issueNumber - GitHub issue number
 * @param {string} options.workflowRunId - Workflow run identifier
 * @param {string} [options.workflowUrl] - Full URL to workflow run
 * @param {boolean} [options.dryRun] - Dry run mode
 */
async function linkIssueToWorkflow(options) {
  const {
    issueNumber,
    workflowRunId,
    workflowUrl,
    dryRun = false
  } = options;

  if (!issueNumber || !workflowRunId) {
    throw new Error('linkIssueToWorkflow requires issueNumber and workflowRunId');
  }

  const comment = `🔗 Linked to workflow run: \`${workflowRunId}\`${workflowUrl ? `\n${workflowUrl}` : ''}`;

  if (dryRun) {
    console.log(`[DRY RUN] Would link issue #${issueNumber} to workflow ${workflowRunId}`);
    return { issueNumber, workflowRunId, isDryRun: true };
  }

  try {
    const args = [
      'issue comment',
      issueNumber,
      `--body ${escapeArg(comment)}`
    ].join(' ');

    executeGh(args);
    console.log(`✓ Linked issue #${issueNumber} to workflow ${workflowRunId}`);

    return { issueNumber, workflowRunId };
  } catch (error) {
    console.error(`✗ Failed to link issue #${issueNumber}: ${error.message}`);
    throw error;
  }
}

/**
 * Get workflow state (issues created/tracked)
 */
async function getWorkflowState(workflowRunId = null) {
  const state = await loadWorkflowState();

  if (workflowRunId) {
    return state.workflows[workflowRunId] || { issues: [] };
  }

  return state;
}

/**
 * Build issue body with metadata
 */
function buildIssueBody(options) {
  const {
    description,
    severity,
    workflowRunId,
    failureDetails = {},
    createdBy,
    timestamp
  } = options;

  let body = description + '\n\n';

  body += `## Metadata\n`;
  body += `- **Severity**: ${severity}\n`;
  body += `- **Created by**: ${createdBy}\n`;
  body += `- **Timestamp**: ${timestamp}\n`;
  body += `- **Workflow Run ID**: \`${workflowRunId}\`\n\n`;

  if (Object.keys(failureDetails).length > 0) {
    body += `## Failure Details\n`;
    body += '```json\n';
    body += JSON.stringify(failureDetails, null, 2) + '\n';
    body += '```\n\n';
  }

  body += `_This issue was automatically created by the fleet validation workflow._`;

  return body;
}

/**
 * Build fix comment
 */
function buildFixComment(options) {
  const {
    fixDetails,
    commitShas = [],
    appliedBy,
    timestamp
  } = options;

  let comment = `## Fix Applied\n\n`;
  comment += fixDetails + '\n\n';

  if (commitShas.length > 0) {
    comment += `### Related Commits\n`;
    commitShas.forEach(sha => {
      comment += `- \`${sha}\`\n`;
    });
    comment += '\n';
  }

  comment += `**Applied by**: ${appliedBy}\n`;
  comment += `**Timestamp**: ${timestamp}\n`;

  return comment;
}

/**
 * Escape argument for shell execution
 */
function escapeArg(str) {
  // Use double quotes and escape backslashes and double quotes
  return '"' + str.replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
}

module.exports = {
  createValidationIssue,
  updateIssueWithFix,
  closeIssue,
  linkIssueToWorkflow,
  getWorkflowState,
  detectRepository,
  CONFIG,
  // Exported for testing
  buildIssueBody,
  buildFixComment
};
