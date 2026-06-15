#!/usr/bin/env node
/**
 * Prometheus Exporter for Fleet Transparency
 *
 * Exports transparency metrics in Prometheus format for Grafana dashboards.
 *
 * Metrics exposed:
 * - fleet_bugs_found_total
 * - fleet_bugs_fixed_total
 * - fleet_bugs_pending
 * - fleet_validations_passed
 * - fleet_validations_failed
 * - fleet_deployments_success
 * - fleet_deployments_failed
 * - fleet_learning_sessions_total
 * - fleet_issues_created
 * - fleet_issues_closed
 * - fleet_issues_open
 * - fleet_events_total
 *
 * Usage:
 *   node monitoring/prometheus-exporter.js
 *   # Starts HTTP server on port 9090
 *   # Metrics available at http://localhost:9090/metrics
 */

const http = require('http');
const fs = require('fs').promises;
const path = require('path');

const PORT = process.env.PROMETHEUS_PORT || 9090;
const STATE_FILE = path.join(process.env.HOME, '.claude', 'learning', 'transparency-state.json');
const JSON_LOG_FILE = path.join(process.env.HOME, '.claude', 'learning', 'transparency.json');

/**
 * Load transparency state
 */
async function loadState() {
  try {
    const content = await fs.readFile(STATE_FILE, 'utf8');
    return JSON.parse(content);
  } catch {
    return {
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
    };
  }
}

/**
 * Load event log for detailed metrics
 */
async function loadEvents() {
  try {
    const content = await fs.readFile(JSON_LOG_FILE, 'utf8');
    return JSON.parse(content);
  } catch {
    return [];
  }
}

/**
 * Calculate bug severity breakdown
 */
function calculateBugSeverity(events) {
  const severityCounts = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  };

  events.forEach(event => {
    if (event.type === 'bug_found' && event.severity) {
      severityCounts[event.severity] = (severityCounts[event.severity] || 0) + 1;
    }
  });

  return severityCounts;
}

/**
 * Calculate fix success rate
 */
function calculateFixRate(events) {
  let fixAttempts = 0;
  let fixSuccess = 0;
  let fixFailed = 0;

  events.forEach(event => {
    if (event.type === 'fix_attempt') fixAttempts++;
    if (event.type === 'fix_success') fixSuccess++;
    if (event.type === 'fix_failed') fixFailed++;
  });

  return { fixAttempts, fixSuccess, fixFailed };
}

/**
 * Generate Prometheus metrics
 */
async function generateMetrics() {
  const state = await loadState();
  const events = await loadEvents();
  const bugSeverity = calculateBugSeverity(events);
  const fixRate = calculateFixRate(events);

  let metrics = '';

  // Helper to add metric
  const addMetric = (name, help, type, value, labels = '') => {
    metrics += `# HELP ${name} ${help}\n`;
    metrics += `# TYPE ${name} ${type}\n`;
    metrics += `${name}${labels} ${value}\n`;
    metrics += '\n';
  };

  // Bug metrics
  addMetric('fleet_bugs_found_total', 'Total number of bugs found', 'counter', state.summary.bugsFound);
  addMetric('fleet_bugs_fixed_total', 'Total number of bugs fixed', 'counter', state.summary.bugsFixed);
  addMetric('fleet_bugs_pending', 'Number of bugs awaiting fix', 'gauge', state.summary.bugsPending);

  // Bug severity breakdown
  metrics += '# HELP fleet_bugs_by_severity Bugs by severity level\n';
  metrics += '# TYPE fleet_bugs_by_severity gauge\n';
  Object.entries(bugSeverity).forEach(([severity, count]) => {
    metrics += `fleet_bugs_by_severity{severity="${severity}"} ${count}\n`;
  });
  metrics += '\n';

  // Validation metrics
  addMetric('fleet_validations_passed', 'Number of validations passed', 'counter', state.summary.validationsPassed);
  addMetric('fleet_validations_failed', 'Number of validations failed', 'counter', state.summary.validationsFailed);

  // Deployment metrics
  addMetric('fleet_deployments_success', 'Successful deployments', 'counter', state.summary.deploymentsSuccess);
  addMetric('fleet_deployments_failed', 'Failed deployments', 'counter', state.summary.deploymentsFailed);

  // Learning metrics
  addMetric('fleet_learning_sessions_total', 'Total learning sessions completed', 'counter', state.summary.learningSessionsComplete);

  // Issue metrics
  addMetric('fleet_issues_created', 'Total issues created', 'counter', state.summary.issuesCreated);
  addMetric('fleet_issues_closed', 'Total issues closed', 'counter', state.summary.issuesClosed);
  addMetric('fleet_issues_open', 'Currently open issues', 'gauge', state.summary.issuesCreated - state.summary.issuesClosed);

  // Fix rate metrics
  addMetric('fleet_fix_attempts_total', 'Total fix attempts', 'counter', fixRate.fixAttempts);
  addMetric('fleet_fix_success_total', 'Successful fixes', 'counter', fixRate.fixSuccess);
  addMetric('fleet_fix_failed_total', 'Failed fixes', 'counter', fixRate.fixFailed);

  // Event count metrics
  addMetric('fleet_events_total', 'Total events logged', 'counter', events.length);

  return metrics;
}

/**
 * HTTP server to serve metrics
 */
async function startServer() {
  const server = http.createServer(async (req, res) => {
    if (req.url === '/metrics') {
      try {
        const metrics = await generateMetrics();
        res.writeHead(200, { 'Content-Type': 'text/plain; version=0.0.4' });
        res.end(metrics);
      } catch (error) {
        console.error('Error generating metrics:', error);
        res.writeHead(500, { 'Content-Type': 'text/plain' });
        res.end('Internal Server Error');
      }
    } else if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end('OK');
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found\n\nAvailable endpoints:\n  /metrics - Prometheus metrics\n  /health - Health check');
    }
  });

  server.listen(PORT, () => {
    console.log(`Fleet Transparency Prometheus Exporter running on http://localhost:${PORT}`);
    console.log(`Metrics available at http://localhost:${PORT}/metrics`);
    console.log('');
    console.log('Add this to your prometheus.yml:');
    console.log('');
    console.log('  - job_name: "fleet-transparency"');
    console.log(`    static_configs:`);
    console.log(`      - targets: ["localhost:${PORT}"]`);
    console.log('');
  });

  // Handle shutdown gracefully
  process.on('SIGTERM', () => {
    console.log('Received SIGTERM, shutting down...');
    server.close(() => {
      console.log('Server closed');
      process.exit(0);
    });
  });

  process.on('SIGINT', () => {
    console.log('Received SIGINT, shutting down...');
    server.close(() => {
      console.log('Server closed');
      process.exit(0);
    });
  });
}

// Start server if run directly
if (require.main === module) {
  startServer().catch(error => {
    console.error('Failed to start Prometheus exporter:', error);
    process.exit(1);
  });
}

module.exports = {
  generateMetrics,
  startServer,
};
