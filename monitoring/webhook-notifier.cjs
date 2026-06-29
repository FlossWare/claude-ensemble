#!/usr/bin/env node
/**
 * Webhook Notifier for Critical Events
 *
 * Sends Slack/Discord alerts for:
 * 1. Critical drift detected (>20% drop)
 * 2. High disagreement task queued (CV >0.40)
 * 3. Circuit breaker opened (model disabled)
 * 4. Weekly consensus quality report
 *
 * Usage:
 *   const { notifyDrift, notifyDisagreement, notifyCircuitBreaker, sendWeeklyReport } = require('./webhook-notifier.cjs');
 *   await notifyDrift(driftAlert);
 *   await notifyDisagreement(disagreementData);
 *   await notifyCircuitBreaker(model, reason);
 *   await sendWeeklyReport();
 *
 * Configuration: monitoring/webhook-config.json
 *
 * Created: 2026-06-28
 */

const fs = require('fs');
const https = require('https');
const path = require('path');
const { URL } = require('url');

// Load configuration
const CONFIG_PATH = path.join(__dirname, 'webhook-config.json');
let config = {};

try {
  config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
} catch (err) {
  console.error('[WebhookNotifier] Failed to load config:', err.message);
  config = {
    webhooks: { slack: { enabled: false }, discord: { enabled: false } },
    thresholds: {},
    notifications: {},
    rate_limiting: { enabled: false }
  };
}

// Rate limiting cache
const RATE_LIMIT_CACHE_PATH = config.rate_limiting?.cache_file || '/tmp/webhook-rate-limit-cache.json';
let rateLimitCache = {};

function loadRateLimitCache() {
  try {
    if (fs.existsSync(RATE_LIMIT_CACHE_PATH)) {
      rateLimitCache = JSON.parse(fs.readFileSync(RATE_LIMIT_CACHE_PATH, 'utf8'));
    }
  } catch (err) {
    console.error('[WebhookNotifier] Failed to load rate limit cache:', err.message);
    rateLimitCache = {};
  }
}

function saveRateLimitCache() {
  try {
    fs.writeFileSync(RATE_LIMIT_CACHE_PATH, JSON.stringify(rateLimitCache, null, 2));
  } catch (err) {
    console.error('[WebhookNotifier] Failed to save rate limit cache:', err.message);
  }
}

/**
 * Check if notification should be rate limited
 *
 * @param {string} notificationType - Type of notification (e.g., 'critical_drift')
 * @returns {boolean} True if rate limited (should skip), false if allowed
 */
function isRateLimited(notificationType) {
  if (!config.rate_limiting?.enabled) {
    return false;
  }

  loadRateLimitCache();

  const now = Date.now();
  const notificationConfig = config.notifications?.[notificationType];

  if (!notificationConfig) {
    return false;
  }

  const rateLimitMinutes = notificationConfig.rate_limit_minutes || 60;
  const rateLimitMs = rateLimitMinutes * 60 * 1000;

  const cacheKey = `last_${notificationType}`;
  const lastSent = rateLimitCache[cacheKey];

  if (lastSent && (now - lastSent) < rateLimitMs) {
    const minutesRemaining = Math.ceil((rateLimitMs - (now - lastSent)) / 60000);
    console.log(`[WebhookNotifier] Rate limited: ${notificationType} (${minutesRemaining} min remaining)`);
    return true;
  }

  // Update cache
  rateLimitCache[cacheKey] = now;
  saveRateLimitCache();

  return false;
}

/**
 * Send webhook notification via HTTPS
 *
 * @param {string} url - Webhook URL
 * @param {object} payload - JSON payload
 * @returns {Promise<void>}
 */
function sendWebhook(url, payload) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);

    const options = {
      hostname: parsedUrl.hostname,
      port: parsedUrl.port || 443,
      path: parsedUrl.pathname + parsedUrl.search,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    };

    const req = https.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve();
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on('error', (err) => {
      reject(err);
    });

    req.write(JSON.stringify(payload));
    req.end();
  });
}

/**
 * Format message for Slack
 *
 * @param {object} data - Notification data
 * @param {string} template - Template name
 * @returns {object} Slack payload
 */
function formatSlackMessage(data, template) {
  const slackConfig = config.webhooks?.slack || {};

  const basePayload = {
    username: slackConfig.username || 'Claude Monitor',
    icon_emoji: slackConfig.icon_emoji || ':robot_face:',
  };

  if (slackConfig.channel) {
    basePayload.channel = slackConfig.channel;
  }

  switch (template) {
    case 'critical_drift':
      return {
        ...basePayload,
        attachments: [{
          color: 'danger',
          title: '🚨 Critical Model Drift Detected',
          fields: [
            { title: 'Model', value: data.model, short: true },
            { title: 'Task Type', value: data.task_type || 'all tasks', short: true },
            { title: 'Performance Drop', value: `${data.performance_drop_pct.toFixed(1)}%`, short: true },
            { title: 'Current Quality', value: data.current_7day_avg.toFixed(3), short: true },
            { title: 'Historical Quality', value: data.historical_30day_avg.toFixed(3), short: true },
            { title: 'Samples', value: `${data.current_sample_count}`, short: true },
          ],
          footer: 'Model Drift Detection',
          ts: Math.floor(Date.now() / 1000)
        }]
      };

    case 'high_disagreement':
      return {
        ...basePayload,
        attachments: [{
          color: 'warning',
          title: '⚠️  High Disagreement Detected',
          fields: [
            { title: 'Workflow', value: data.workflow_name, short: true },
            { title: 'Disagreement Score (CV)', value: data.disagreement_score.toFixed(3), short: true },
            { title: 'Task Description', value: data.task_description, short: false },
            { title: 'Votes', value: `${data.votes.length} models`, short: true },
            { title: 'Queue ID', value: `${data.queue_id}`, short: true },
            { title: 'Priority', value: `${data.priority}/10`, short: true },
          ],
          footer: 'Disagreement Detection',
          ts: Math.floor(Date.now() / 1000)
        }]
      };

    case 'circuit_breaker':
      return {
        ...basePayload,
        attachments: [{
          color: 'danger',
          title: '🔴 Circuit Breaker Opened',
          fields: [
            { title: 'Model', value: data.model, short: true },
            { title: 'State', value: data.state, short: true },
            { title: 'Reason', value: data.reason, short: false },
            { title: 'Consecutive Failures', value: `${data.consecutive_failures}`, short: true },
            { title: 'Next Retry', value: data.next_retry || 'N/A', short: true },
          ],
          footer: 'Circuit Breaker',
          ts: Math.floor(Date.now() / 1000)
        }]
      };

    case 'weekly_report':
      return {
        ...basePayload,
        attachments: [{
          color: 'good',
          title: '📊 Weekly Consensus Quality Report',
          fields: [
            { title: 'Date Range', value: `${data.start_date} to ${data.end_date}`, short: false },
            { title: 'Total Executions', value: `${data.total_executions}`, short: true },
            { title: 'Avg Quality Score', value: data.avg_quality.toFixed(3), short: true },
            { title: 'Avg Confidence', value: `${data.avg_confidence.toFixed(1)}%`, short: true },
            { title: 'Success Rate', value: `${data.success_rate.toFixed(1)}%`, short: true },
            { title: 'Top Model', value: `${data.top_model.name} (${data.top_model.quality.toFixed(3)})`, short: true },
            { title: 'Total Cost', value: `$${data.total_cost.toFixed(2)}`, short: true },
            { title: 'Drift Alerts', value: `${data.drift_alerts}`, short: true },
            { title: 'Disagreement Reviews', value: `${data.disagreement_reviews}`, short: true },
          ],
          footer: 'Weekly Report',
          ts: Math.floor(Date.now() / 1000)
        }]
      };

    default:
      return {
        ...basePayload,
        text: `Unknown template: ${template}`,
      };
  }
}

/**
 * Format message for Discord
 *
 * @param {object} data - Notification data
 * @param {string} template - Template name
 * @returns {object} Discord payload
 */
function formatDiscordMessage(data, template) {
  const discordConfig = config.webhooks?.discord || {};

  const basePayload = {
    username: discordConfig.username || 'Claude Monitor',
    avatar_url: discordConfig.avatar_url,
  };

  switch (template) {
    case 'critical_drift':
      return {
        ...basePayload,
        embeds: [{
          color: 15158332, // Red
          title: '🚨 Critical Model Drift Detected',
          fields: [
            { name: 'Model', value: data.model, inline: true },
            { name: 'Task Type', value: data.task_type || 'all tasks', inline: true },
            { name: 'Performance Drop', value: `${data.performance_drop_pct.toFixed(1)}%`, inline: true },
            { name: 'Current Quality', value: data.current_7day_avg.toFixed(3), inline: true },
            { name: 'Historical Quality', value: data.historical_30day_avg.toFixed(3), inline: true },
            { name: 'Samples', value: `${data.current_sample_count}`, inline: true },
          ],
          footer: { text: 'Model Drift Detection' },
          timestamp: new Date().toISOString()
        }]
      };

    case 'high_disagreement':
      return {
        ...basePayload,
        embeds: [{
          color: 16776960, // Yellow
          title: '⚠️  High Disagreement Detected',
          fields: [
            { name: 'Workflow', value: data.workflow_name, inline: true },
            { name: 'Disagreement Score (CV)', value: data.disagreement_score.toFixed(3), inline: true },
            { name: 'Task Description', value: data.task_description, inline: false },
            { name: 'Votes', value: `${data.votes.length} models`, inline: true },
            { name: 'Queue ID', value: `${data.queue_id}`, inline: true },
            { name: 'Priority', value: `${data.priority}/10`, inline: true },
          ],
          footer: { text: 'Disagreement Detection' },
          timestamp: new Date().toISOString()
        }]
      };

    case 'circuit_breaker':
      return {
        ...basePayload,
        embeds: [{
          color: 15158332, // Red
          title: '🔴 Circuit Breaker Opened',
          fields: [
            { name: 'Model', value: data.model, inline: true },
            { name: 'State', value: data.state, inline: true },
            { name: 'Reason', value: data.reason, inline: false },
            { name: 'Consecutive Failures', value: `${data.consecutive_failures}`, inline: true },
            { name: 'Next Retry', value: data.next_retry || 'N/A', inline: true },
          ],
          footer: { text: 'Circuit Breaker' },
          timestamp: new Date().toISOString()
        }]
      };

    case 'weekly_report':
      return {
        ...basePayload,
        embeds: [{
          color: 3066993, // Green
          title: '📊 Weekly Consensus Quality Report',
          fields: [
            { name: 'Date Range', value: `${data.start_date} to ${data.end_date}`, inline: false },
            { name: 'Total Executions', value: `${data.total_executions}`, inline: true },
            { name: 'Avg Quality Score', value: data.avg_quality.toFixed(3), inline: true },
            { name: 'Avg Confidence', value: `${data.avg_confidence.toFixed(1)}%`, inline: true },
            { name: 'Success Rate', value: `${data.success_rate.toFixed(1)}%`, inline: true },
            { name: 'Top Model', value: `${data.top_model.name} (${data.top_model.quality.toFixed(3)})`, inline: true },
            { name: 'Total Cost', value: `$${data.total_cost.toFixed(2)}`, inline: true },
            { name: 'Drift Alerts', value: `${data.drift_alerts}`, inline: true },
            { name: 'Disagreement Reviews', value: `${data.disagreement_reviews}`, inline: true },
          ],
          footer: { text: 'Weekly Report' },
          timestamp: new Date().toISOString()
        }]
      };

    default:
      return {
        ...basePayload,
        content: `Unknown template: ${template}`,
      };
  }
}

/**
 * Send notification to all enabled channels
 *
 * @param {object} data - Notification data
 * @param {string} notificationType - Notification type from config
 * @param {string} template - Template name
 * @returns {Promise<object>} Result object
 */
async function sendNotification(data, notificationType, template) {
  // Check rate limiting
  if (isRateLimited(notificationType)) {
    return {
      success: false,
      rate_limited: true,
      message: `Rate limited: ${notificationType}`
    };
  }

  const notificationConfig = config.notifications?.[notificationType];

  if (!notificationConfig || !notificationConfig.enabled) {
    console.log(`[WebhookNotifier] Notification disabled: ${notificationType}`);
    return {
      success: false,
      disabled: true,
      message: `Notification disabled: ${notificationType}`
    };
  }

  const channels = notificationConfig.channels || [];
  const results = [];

  for (const channel of channels) {
    const webhookConfig = config.webhooks?.[channel];

    if (!webhookConfig || !webhookConfig.enabled) {
      console.log(`[WebhookNotifier] Channel disabled: ${channel}`);
      continue;
    }

    try {
      let payload;
      if (channel === 'slack') {
        payload = formatSlackMessage(data, template);
      } else if (channel === 'discord') {
        payload = formatDiscordMessage(data, template);
      } else {
        console.warn(`[WebhookNotifier] Unknown channel: ${channel}`);
        continue;
      }

      await sendWebhook(webhookConfig.url, payload);
      console.log(`[WebhookNotifier] Sent ${notificationType} to ${channel}`);

      results.push({
        channel,
        success: true
      });
    } catch (err) {
      console.error(`[WebhookNotifier] Failed to send to ${channel}:`, err.message);
      results.push({
        channel,
        success: false,
        error: err.message
      });
    }
  }

  return {
    success: results.some(r => r.success),
    results,
    notification_type: notificationType
  };
}

/**
 * Notify about critical drift
 *
 * @param {object} driftAlert - Drift alert from drift-detector.cjs
 * @returns {Promise<object>} Result object
 */
async function notifyDrift(driftAlert) {
  const criticalThreshold = config.thresholds?.drift?.critical_drop_pct || 20;

  if (Math.abs(driftAlert.performance_drop_pct) >= criticalThreshold) {
    console.log(`[WebhookNotifier] Sending critical drift alert for ${driftAlert.model}`);
    return sendNotification(driftAlert, 'critical_drift', 'critical_drift');
  } else {
    console.log(`[WebhookNotifier] Drift below critical threshold (${Math.abs(driftAlert.performance_drop_pct).toFixed(1)}% < ${criticalThreshold}%)`);
    return {
      success: false,
      below_threshold: true,
      message: 'Drift below critical threshold'
    };
  }
}

/**
 * Notify about high disagreement
 *
 * @param {object} disagreementData - Disagreement data from disagreement-detector.cjs
 * @returns {Promise<object>} Result object
 */
async function notifyDisagreement(disagreementData) {
  const criticalCv = config.thresholds?.disagreement?.critical_cv || 0.40;

  if (disagreementData.disagreement_score >= criticalCv) {
    console.log(`[WebhookNotifier] Sending high disagreement alert (CV=${disagreementData.disagreement_score.toFixed(3)})`);
    return sendNotification(disagreementData, 'high_disagreement', 'high_disagreement');
  } else {
    console.log(`[WebhookNotifier] Disagreement below critical threshold (CV=${disagreementData.disagreement_score.toFixed(3)} < ${criticalCv})`);
    return {
      success: false,
      below_threshold: true,
      message: 'Disagreement below critical threshold'
    };
  }
}

/**
 * Notify about circuit breaker opened
 *
 * @param {string} model - Model name
 * @param {object} circuitState - Circuit breaker state
 * @returns {Promise<object>} Result object
 */
async function notifyCircuitBreaker(model, circuitState) {
  const data = {
    model,
    state: circuitState.state || 'open',
    reason: circuitState.reason || 'Too many consecutive failures',
    consecutive_failures: circuitState.consecutive_failures || 0,
    next_retry: circuitState.next_retry_at
      ? new Date(circuitState.next_retry_at).toLocaleString()
      : null
  };

  console.log(`[WebhookNotifier] Sending circuit breaker alert for ${model}`);
  return sendNotification(data, 'circuit_breaker_open', 'circuit_breaker');
}

/**
 * Send weekly consensus quality report
 *
 * @param {object} reportData - Report data (optional, will query if not provided)
 * @returns {Promise<object>} Result object
 */
async function sendWeeklyReport(reportData = null) {
  // If no report data provided, generate from database
  if (!reportData) {
    reportData = await generateWeeklyReport();
  }

  console.log('[WebhookNotifier] Sending weekly consensus quality report');
  return sendNotification(reportData, 'weekly_consensus_report', 'weekly_report');
}

/**
 * Generate weekly report from database
 *
 * @returns {Promise<object>} Report data
 */
async function generateWeeklyReport() {
  const { Pool } = require('pg');

  const pool = new Pool({
    host: process.env.PGHOST || 'aio-01',
    port: parseInt(process.env.PGPORT || '5433'),
    database: process.env.PGDATABASE || 'learning',
    user: process.env.PGUSER || process.env.USER,
    password: process.env.PGPASSWORD,
  });

  try {
    const endDate = new Date();
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - 7);

    // Query workflow executions
    const executionsQuery = `
      SELECT
        COUNT(*) as total_executions,
        AVG(
          CASE
            WHEN outcome = 'success' THEN 1.0
            ELSE 0.0
          END
        ) as success_rate,
        SUM(total_duration_ms) as total_duration_ms
      FROM workflow.executions
      WHERE created_at >= $1 AND created_at <= $2
    `;

    const executionsResult = await pool.query(executionsQuery, [startDate, endDate]);

    // Query worker results (use COALESCE for backwards compatibility)
    const workersQuery = `
      SELECT
        AVG(COALESCE(quality_score, confidence)) as avg_quality,
        AVG(confidence) as avg_confidence,
        SUM(cost_usd) as total_cost
      FROM workflow.worker_results
      WHERE created_at >= $1 AND created_at <= $2
    `;

    const workersResult = await pool.query(workersQuery, [startDate, endDate]);

    // Query top model (use COALESCE for backwards compatibility)
    const topModelQuery = `
      SELECT
        model,
        AVG(COALESCE(quality_score, confidence)) as avg_quality,
        COUNT(*) as count
      FROM workflow.worker_results
      WHERE created_at >= $1 AND created_at <= $2
        AND (quality_score IS NOT NULL OR confidence IS NOT NULL)
      GROUP BY model
      ORDER BY avg_quality DESC
      LIMIT 1
    `;

    const topModelResult = await pool.query(topModelQuery, [startDate, endDate]);

    // Query drift alerts
    const driftAlertsQuery = `
      SELECT COUNT(*) as drift_alerts
      FROM monitoring.drift_alerts
      WHERE detection_date >= $1 AND detection_date <= $2
    `;

    const driftAlertsResult = await pool.query(driftAlertsQuery, [startDate, endDate]);

    // Query disagreement reviews
    const disagreementQuery = `
      SELECT COUNT(*) as disagreement_reviews
      FROM workflow.human_review_queue
      WHERE created_at >= $1 AND created_at <= $2
        AND disagreement_level IN ('high', 'critical')
    `;

    const disagreementResult = await pool.query(disagreementQuery, [startDate, endDate]);

    await pool.end();

    const executions = executionsResult.rows[0];
    const workers = workersResult.rows[0];
    const topModel = topModelResult.rows[0] || { model: 'N/A', avg_quality: 0 };
    const driftAlerts = driftAlertsResult.rows[0];
    const disagreement = disagreementResult.rows[0];

    return {
      start_date: startDate.toISOString().split('T')[0],
      end_date: endDate.toISOString().split('T')[0],
      total_executions: parseInt(executions.total_executions) || 0,
      avg_quality: parseFloat(workers.avg_quality) || 0,
      avg_confidence: parseFloat(workers.avg_confidence) || 0,
      success_rate: parseFloat(executions.success_rate) * 100 || 0,
      top_model: {
        name: topModel.model,
        quality: parseFloat(topModel.avg_quality) || 0
      },
      total_cost: parseFloat(workers.total_cost) || 0,
      drift_alerts: parseInt(driftAlerts.drift_alerts) || 0,
      disagreement_reviews: parseInt(disagreement.disagreement_reviews) || 0,
    };
  } catch (err) {
    console.error('[WebhookNotifier] Failed to generate weekly report:', err.message);

    // Return dummy data if database unavailable
    return {
      start_date: new Date().toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
      total_executions: 0,
      avg_quality: 0,
      avg_confidence: 0,
      success_rate: 0,
      top_model: { name: 'N/A', quality: 0 },
      total_cost: 0,
      drift_alerts: 0,
      disagreement_reviews: 0,
      error: err.message
    };
  }
}

/**
 * Test webhook configuration
 *
 * @param {string} channel - Channel to test ('slack' or 'discord')
 * @returns {Promise<object>} Test result
 */
async function testWebhook(channel = 'slack') {
  const testData = {
    model: 'test-model',
    task_type: 'test',
    performance_drop_pct: -25.5,
    current_7day_avg: 0.65,
    historical_30day_avg: 0.87,
    current_sample_count: 42
  };

  console.log(`[WebhookNotifier] Testing ${channel} webhook...`);

  const webhookConfig = config.webhooks?.[channel];

  if (!webhookConfig || !webhookConfig.enabled) {
    return {
      success: false,
      error: `${channel} webhook not enabled in config`
    };
  }

  try {
    let payload;
    if (channel === 'slack') {
      payload = formatSlackMessage(testData, 'critical_drift');
      payload.text = '🧪 **TEST MESSAGE** - Webhook configuration is working!';
    } else if (channel === 'discord') {
      payload = formatDiscordMessage(testData, 'critical_drift');
      payload.embeds[0].title = '🧪 TEST MESSAGE - Webhook configuration is working!';
    }

    await sendWebhook(webhookConfig.url, payload);

    return {
      success: true,
      channel,
      message: 'Test webhook sent successfully'
    };
  } catch (err) {
    return {
      success: false,
      channel,
      error: err.message
    };
  }
}

// CLI interface
if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  (async () => {
    switch (command) {
      case 'test':
        const channel = args[1] || 'slack';
        const result = await testWebhook(channel);
        console.log(JSON.stringify(result, null, 2));
        break;

      case 'weekly-report':
        const reportResult = await sendWeeklyReport();
        console.log(JSON.stringify(reportResult, null, 2));
        break;

      default:
        console.log('Usage:');
        console.log('  node webhook-notifier.cjs test [slack|discord]');
        console.log('  node webhook-notifier.cjs weekly-report');
        process.exit(1);
    }
  })().catch(err => {
    console.error('Error:', err.message);
    process.exit(1);
  });
}

module.exports = {
  notifyDrift,
  notifyDisagreement,
  notifyCircuitBreaker,
  sendWeeklyReport,
  testWebhook,
  generateWeeklyReport,
};
