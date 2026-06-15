#!/usr/bin/env node
/**
 * Offline Issue Queue - Stores issues when GitHub unavailable, syncs later
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const QUEUE_FILE = path.join(process.env.HOME, '.claude/learning/issue-queue.jsonl');
const QUEUE_DIR = path.dirname(QUEUE_FILE);

// Ensure directory exists
if (!fs.existsSync(QUEUE_DIR)) {
  fs.mkdirSync(QUEUE_DIR, { recursive: true });
}

/**
 * Try to create GitHub issue, queue if fails
 */
function createIssue({ title, body, labels = [], priority = 'normal' }) {
  const issue = {
    action: 'create',
    title,
    body,
    labels: [...labels, 'auto-generated'],
    priority,
    timestamp: new Date().toISOString(),
    attempts: 0
  };

  try {
    // Try to create issue immediately
    const labelsArg = issue.labels.join(',');
    const result = execSync(
      `gh issue create --title "${title}" --body "${body}" --label "${labelsArg}"`,
      { encoding: 'utf8', timeout: 5000 }
    );

    const match = result.match(/#(\d+)/);
    if (match) {
      console.log(`✅ Created issue #${match[1]}: ${title}`);
      return { success: true, issueNumber: parseInt(match[1]) };
    }
  } catch (err) {
    console.warn(`⚠️ GitHub unavailable, queuing issue: ${title}`);
    console.warn(`   Reason: ${err.message}`);

    // Queue for later
    queueIssue(issue);
    return { success: false, queued: true };
  }
}

/**
 * Try to close GitHub issue, queue if fails
 */
function closeIssue({ issueNumber, fixDescription, commits = [] }) {
  const issue = {
    action: 'close',
    issueNumber,
    comment: `**Auto-Fixed by Fleet**\n\n${fixDescription}\n\nCommits:\n${commits.map(c => `- ${c}`).join('\n')}`,
    timestamp: new Date().toISOString(),
    attempts: 0
  };

  try {
    // Add comment
    execSync(
      `gh issue comment ${issueNumber} --body "${issue.comment}"`,
      { encoding: 'utf8', timeout: 5000 }
    );

    // Close issue
    execSync(
      `gh issue close ${issueNumber}`,
      { encoding: 'utf8', timeout: 5000 }
    );

    console.log(`✅ Closed issue #${issueNumber}`);
    return { success: true };
  } catch (err) {
    console.warn(`⚠️ GitHub unavailable, queuing close for #${issueNumber}`);
    console.warn(`   Reason: ${err.message}`);

    // Queue for later
    queueIssue(issue);
    return { success: false, queued: true };
  }
}

/**
 * Queue issue to file
 */
function queueIssue(issue) {
  fs.appendFileSync(QUEUE_FILE, JSON.stringify(issue) + '\n');
}

/**
 * Process queued issues (run periodically)
 */
function processQueue() {
  if (!fs.existsSync(QUEUE_FILE)) {
    console.log('No queued issues');
    return { processed: 0, failed: 0 };
  }

  const lines = fs.readFileSync(QUEUE_FILE, 'utf8').split('\n').filter(Boolean);
  const remaining = [];
  let processed = 0;
  let failed = 0;

  console.log(`Processing ${lines.length} queued issues...`);

  for (const line of lines) {
    const issue = JSON.parse(line);
    issue.attempts++;

    try {
      if (issue.action === 'create') {
        const labelsArg = issue.labels.join(',');
        execSync(
          `gh issue create --title "${issue.title}" --body "${issue.body}" --label "${labelsArg}"`,
          { encoding: 'utf8', timeout: 5000 }
        );
        console.log(`✅ Created queued issue: ${issue.title}`);
        processed++;
      } else if (issue.action === 'close') {
        execSync(
          `gh issue comment ${issue.issueNumber} --body "${issue.comment}"`,
          { encoding: 'utf8', timeout: 5000 }
        );
        execSync(
          `gh issue close ${issue.issueNumber}`,
          { encoding: 'utf8', timeout: 5000 }
        );
        console.log(`✅ Closed queued issue #${issue.issueNumber}`);
        processed++;
      }
    } catch (err) {
      console.warn(`⚠️ Still can't process issue (attempt ${issue.attempts}): ${err.message}`);

      // Keep in queue if attempts < 10
      if (issue.attempts < 10) {
        remaining.push(issue);
      } else {
        console.error(`❌ Giving up on issue after 10 attempts: ${issue.title || issue.issueNumber}`);
        failed++;
      }
    }
  }

  // Rewrite queue with remaining items
  if (remaining.length > 0) {
    fs.writeFileSync(QUEUE_FILE, remaining.map(i => JSON.stringify(i)).join('\n') + '\n');
  } else {
    fs.unlinkSync(QUEUE_FILE);
  }

  return { processed, failed, remaining: remaining.length };
}

/**
 * Get queue status
 */
function getQueueStatus() {
  if (!fs.existsSync(QUEUE_FILE)) {
    return { count: 0, items: [] };
  }

  const lines = fs.readFileSync(QUEUE_FILE, 'utf8').split('\n').filter(Boolean);
  const items = lines.map(line => JSON.parse(line));

  return {
    count: items.length,
    items: items.map(i => ({
      action: i.action,
      title: i.title || `#${i.issueNumber}`,
      attempts: i.attempts,
      timestamp: i.timestamp
    }))
  };
}

module.exports = {
  createIssue,
  closeIssue,
  processQueue,
  getQueueStatus
};

// CLI
if (require.main === module) {
  const command = process.argv[2];

  if (command === 'process') {
    const result = processQueue();
    console.log(`\n📊 Queue processed: ${result.processed} succeeded, ${result.failed} failed, ${result.remaining} remaining`);
  } else if (command === 'status') {
    const status = getQueueStatus();
    console.log(`\n📊 Queue status: ${status.count} items`);
    status.items.forEach(item => {
      console.log(`  ${item.action}: ${item.title} (${item.attempts} attempts, ${item.timestamp})`);
    });
  } else {
    console.log('Usage: issue-queue.js [process|status]');
    console.log('  process - Try to sync queued issues to GitHub');
    console.log('  status  - Show queued issues');
  }
}
