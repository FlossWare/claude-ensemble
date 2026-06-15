#!/usr/bin/env node
/**
 * Enhanced workflow status display - shows hosts being used
 */

const fs = require('fs');
const path = require('path');

/**
 * Extract host assignments from workflow transcripts
 */
function getWorkflowHosts(workflowRunId) {
  const transcriptDir = path.join(
    process.env.HOME,
    '.claude/projects/-home-sfloess/39a38f09-c545-4579-9ac1-6c31a694eba2/subagents/workflows',
    workflowRunId
  );

  if (!fs.existsSync(transcriptDir)) {
    return [];
  }

  const hosts = new Set();

  // Read agent transcripts to find host assignments
  const files = fs.readdirSync(transcriptDir);
  for (const file of files) {
    if (file.endsWith('.jsonl')) {
      try {
        const content = fs.readFileSync(path.join(transcriptDir, file), 'utf8');
        const lines = content.split('\n').filter(Boolean);

        for (const line of lines) {
          const entry = JSON.parse(line);

          // Check for host mentions in prompts or tool calls
          if (entry.content) {
            const hostMatches = entry.content.match(/server-0[123]|aio-01|pi-0[12]/g);
            if (hostMatches) {
              hostMatches.forEach(h => hosts.add(h));
            }
          }
        }
      } catch (err) {
        // Skip invalid files
      }
    }
  }

  return Array.from(hosts);
}

/**
 * Get active workflows with host info
 */
function getActiveWorkflows() {
  const workflowsDir = path.join(
    process.env.HOME,
    '.claude/projects/-home-sfloess/39a38f09-c545-4579-9ac1-6c31a694eba2/subagents/workflows'
  );

  if (!fs.existsSync(workflowsDir)) {
    return [];
  }

  const workflows = [];
  const dirs = fs.readdirSync(workflowsDir);

  for (const dir of dirs) {
    if (dir.startsWith('wf_')) {
      const scriptPath = path.join(workflowsDir, dir, '../../../workflows/scripts');
      const scriptFiles = fs.existsSync(scriptPath) ? fs.readdirSync(scriptPath) : [];

      // Find matching script
      const scriptFile = scriptFiles.find(f => f.includes(dir));
      if (scriptFile) {
        try {
          const scriptContent = fs.readFileSync(path.join(scriptPath, scriptFile), 'utf8');
          const metaMatch = scriptContent.match(/export const meta = \{[^}]+name:\s*['"]([^'"]+)['"]/);
          const descMatch = scriptContent.match(/description:\s*['"]([^'"]+)['"]/);

          if (metaMatch) {
            workflows.push({
              runId: dir,
              name: metaMatch[1],
              description: descMatch ? descMatch[1] : 'No description',
              hosts: getWorkflowHosts(dir)
            });
          }
        } catch (err) {
          // Skip invalid workflows
        }
      }
    }
  }

  return workflows;
}

/**
 * Display enhanced status
 */
function displayStatus() {
  const workflows = getActiveWorkflows();

  console.log('\n🚀 ACTIVE WORKFLOWS\n');

  if (workflows.length === 0) {
    console.log('No active workflows');
    return;
  }

  workflows.forEach(wf => {
    console.log(`📊 ${wf.name} (${wf.runId})`);
    console.log(`   ${wf.description}`);

    if (wf.hosts.length > 0) {
      console.log(`   🖥️  Hosts: ${wf.hosts.join(', ')}`);
    } else {
      console.log(`   🖥️  Hosts: Determining...`);
    }

    console.log('');
  });

  // Summary
  const allHosts = new Set();
  workflows.forEach(wf => wf.hosts.forEach(h => allHosts.add(h)));

  console.log(`\n📈 Summary: ${workflows.length} workflows using ${allHosts.size} hosts`);
  if (allHosts.size > 0) {
    console.log(`   Active hosts: ${Array.from(allHosts).join(', ')}`);
  }
}

// CLI
if (require.main === module) {
  displayStatus();
}

module.exports = {
  getWorkflowHosts,
  getActiveWorkflows,
  displayStatus
};
