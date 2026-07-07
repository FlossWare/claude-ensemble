#!/usr/bin/env node
/**
 * Fleet Health Predictor - AI-based predictive server failure detection
 *
 * GitLab Issue: #108
 * Purpose: Prevent fleet worker failures by predicting degradation from Prometheus metrics
 *
 * Analyzes:
 * - CPU temperature trends (hwmon sensors)
 * - Memory leak patterns (increasing RSS over time)
 * - Disk I/O saturation (iowait spikes)
 * - Load average trends (sustained high load)
 *
 * Models:
 * - Haiku: Fast metric analysis (time-series anomaly detection)
 * - Sonnet: Validation of predictions (cross-check against historical patterns)
 * - Opus: Migration decisions (critical: move jobs before failure)
 *
 * Triggers:
 * - Every 5 minutes (cron)
 * - Immediate when metrics exceed 80% of circuit breaker threshold
 *
 * Target: Prevent 80% of unexpected failures, zero jobs lost
 * Threshold: 70% degradation probability → mark server degraded
 */

import { execSync } from 'child_process';
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import os from 'os';

const require = createRequire(import.meta.url);
const { executeRemoteLLMTask } = require('../shared/fleet-utils.js');

// Configuration
const PROMETHEUS_URL = process.env.PROMETHEUS_URL || 'http://pi-02:9090';
const LOOKBACK_HOURS = 7 * 24; // 7 days of history
const PREDICTION_THRESHOLD = 0.70; // 70% probability → mark degraded
const CIRCUIT_BREAKER_THRESHOLDS = {
  cpu_usage: 90,        // % (80% trigger = 72%)
  memory_usage: 95,     // % (80% trigger = 76%)
  load_avg_per_core: 3.0, // (80% trigger = 2.4)
  disk_iowait: 50,      // % (80% trigger = 40%)
  cpu_temp: 85          // °C (80% trigger = 68°C)
};

// Database connection
const DB_CONFIG = {
  host: process.env.POSTGRES_HOST || 'aio-01',
  port: parseInt(process.env.POSTGRES_PORT || '5433', 10),
  database: 'learning',
  user: 'claude'
};

/**
 * Query Prometheus for metric over time range
 */
async function queryPrometheus(query, startTime, endTime, step = '5m') {
  const params = new URLSearchParams({
    query,
    start: startTime.toISOString(),
    end: endTime.toISOString(),
    step
  });

  const url = `${PROMETHEUS_URL}/api/v1/query_range?${params}`;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    if (data.status !== 'success') {
      throw new Error(`Prometheus error: ${data.error || 'unknown'}`);
    }
    return data.data.result;
  } catch (error) {
    console.error(`Prometheus query failed: ${error.message}`);
    return [];
  }
}

/**
 * Collect time-series metrics for all fleet workers
 */
async function collectMetrics() {
  const endTime = new Date();
  const startTime = new Date(endTime.getTime() - LOOKBACK_HOURS * 3600 * 1000);

  console.log(`Collecting metrics from ${startTime.toISOString()} to ${endTime.toISOString()}`);

  const queries = {
    // CPU usage per node (from node_exporter)
    cpu_usage: 'avg by (instance) (rate(node_cpu_seconds_total{mode!="idle"}[5m])) * 100',

    // Memory usage per node
    memory_usage: '100 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100)',

    // Load average (1m) per node
    load_avg: 'node_load1',

    // CPU cores per node (for normalization)
    cpu_cores: 'count by (instance) (node_cpu_seconds_total{mode="idle"})',

    // Disk I/O wait percentage
    iowait: 'rate(node_cpu_seconds_total{mode="iowait"}[5m]) * 100',

    // CPU temperature (hwmon sensors)
    cpu_temp: 'node_hwmon_temp_celsius',

    // Memory RSS growth (detect leaks)
    memory_rss: 'node_memory_Active_bytes',

    // Disk usage percentage
    disk_usage: '(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100'
  };

  const results = {};

  for (const [metricName, query] of Object.entries(queries)) {
    console.log(`  Querying ${metricName}...`);
    const data = await queryPrometheus(query, startTime, endTime);
    results[metricName] = data;
  }

  return results;
}

/**
 * Analyze metrics with Haiku for anomaly detection
 */
async function analyzeWithHaiku(metrics, hostname) {
  const prompt = `
Analyze the following 7-day time-series metrics for server "${hostname}" and detect anomalies or degradation patterns.

Metrics provided:
- CPU usage (%) over 7 days
- Memory usage (%) over 7 days
- Load average (1m) over 7 days
- Disk I/O wait (%) over 7 days
- CPU temperature (°C) over 7 days
- Memory RSS (bytes) over 7 days

Circuit breaker thresholds (immediate failure):
- CPU usage: ${CIRCUIT_BREAKER_THRESHOLDS.cpu_usage}%
- Memory usage: ${CIRCUIT_BREAKER_THRESHOLDS.memory_usage}%
- Load avg/core: ${CIRCUIT_BREAKER_THRESHOLDS.load_avg_per_core}
- Disk I/O wait: ${CIRCUIT_BREAKER_THRESHOLDS.disk_iowait}%
- CPU temp: ${CIRCUIT_BREAKER_THRESHOLDS.cpu_temp}°C

Data (JSON):
${JSON.stringify(metrics, null, 2)}

Analyze for:
1. Sustained upward trends (memory leaks, temperature creep)
2. Increasing variance (instability)
3. Periodic spikes becoming more frequent
4. Metrics approaching circuit breaker thresholds

Return JSON format:
{
  "degradation_probability": 0.0-1.0,
  "primary_risk": "memory_leak|cpu_thermal|disk_saturation|load_spike|none",
  "time_to_failure_hours": <estimate or null>,
  "evidence": ["observation 1", "observation 2", ...],
  "recommendation": "migrate_jobs|monitor|no_action"
}
`;

  const result = await executeRemoteLLMTask({
    task: prompt,
    model: 'haiku',
    maxTokens: 2048
  });

  try {
    // Extract JSON from response (may be wrapped in markdown)
    const jsonMatch = result.output.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('No JSON found in response');
    }
    return JSON.parse(jsonMatch[0]);
  } catch (error) {
    console.error(`Failed to parse Haiku response: ${error.message}`);
    console.error('Raw output:', result.output);
    return {
      degradation_probability: 0.0,
      primary_risk: 'none',
      time_to_failure_hours: null,
      evidence: ['Parse error - analysis unavailable'],
      recommendation: 'monitor'
    };
  }
}

/**
 * Validate predictions with Sonnet (cross-check against historical patterns)
 */
async function validateWithSonnet(haikuAnalysis, metrics, hostname) {
  const prompt = `
You are validating a predictive health analysis for server "${hostname}".

Haiku's analysis:
${JSON.stringify(haikuAnalysis, null, 2)}

7-day metric history:
${JSON.stringify(metrics, null, 2)}

Your task:
1. Cross-check Haiku's findings against the raw data
2. Identify false positives (normal variance misidentified as degradation)
3. Identify missed patterns (Haiku missed subtle trends)
4. Validate the degradation probability (0.0-1.0)

Return JSON:
{
  "validated_probability": 0.0-1.0,
  "agreement": "agree|disagree_higher|disagree_lower",
  "false_positives": ["pattern 1", ...],
  "missed_patterns": ["pattern 1", ...],
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}
`;

  const result = await executeRemoteLLMTask({
    task: prompt,
    model: 'sonnet',
    maxTokens: 2048
  });

  try {
    const jsonMatch = result.output.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('No JSON found in response');
    }
    return JSON.parse(jsonMatch[0]);
  } catch (error) {
    console.error(`Failed to parse Sonnet response: ${error.message}`);
    return {
      validated_probability: haikuAnalysis.degradation_probability,
      agreement: 'agree',
      false_positives: [],
      missed_patterns: [],
      confidence: 0.5,
      reasoning: 'Parse error - defaulting to Haiku analysis'
    };
  }
}

/**
 * Make migration decision with Opus (critical decisions only)
 */
async function decideMigrationWithOpus(analysis, validation, hostname, activeJobs) {
  if (validation.validated_probability < PREDICTION_THRESHOLD) {
    return {
      action: 'none',
      reasoning: 'Degradation probability below threshold'
    };
  }

  const prompt = `
CRITICAL DECISION REQUIRED

Server: ${hostname}
Active jobs: ${activeJobs}
Degradation probability: ${(validation.validated_probability * 100).toFixed(1)}%

Haiku analysis:
${JSON.stringify(analysis, null, 2)}

Sonnet validation:
${JSON.stringify(validation, null, 2)}

Your task:
Decide whether to migrate jobs from this server BEFORE failure occurs.

Considerations:
- Migration disrupts running jobs (cost: 5-10 minutes)
- Server failure loses ALL jobs (cost: job restart + reputation damage)
- False positive: wasted migration effort
- False negative: catastrophic job loss

Target: Prevent 80% of failures, zero jobs lost

Return JSON:
{
  "action": "migrate_immediately|schedule_migration|monitor_closely|no_action",
  "urgency": "critical|high|medium|low",
  "migration_window_hours": <number or null>,
  "target_servers": ["server-01", "server-02", ...],
  "reasoning": "detailed justification"
}
`;

  const result = await executeRemoteLLMTask({
    task: prompt,
    model: 'opus',
    maxTokens: 3072
  });

  try {
    const jsonMatch = result.output.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('No JSON found in response');
    }
    return JSON.parse(jsonMatch[0]);
  } catch (error) {
    console.error(`Failed to parse Opus response: ${error.message}`);
    return {
      action: 'monitor_closely',
      urgency: 'medium',
      migration_window_hours: null,
      target_servers: [],
      reasoning: 'Parse error - defaulting to safe monitoring'
    };
  }
}

/**
 * Store prediction results to PostgreSQL
 */
async function storePrediction(hostname, analysis, validation, decision) {
  const psycopg2 = require('psycopg2');

  let conn;
  try {
    conn = psycopg2.connect({
      ...DB_CONFIG,
      connect_timeout: 5
    });

    const cursor = conn.cursor();

    // Create table if not exists
    cursor.execute(`
      CREATE TABLE IF NOT EXISTS monitoring.health_predictions (
        id SERIAL PRIMARY KEY,
        hostname TEXT NOT NULL,
        degradation_probability REAL NOT NULL,
        primary_risk TEXT,
        time_to_failure_hours REAL,
        validated_probability REAL,
        validation_confidence REAL,
        decision_action TEXT,
        decision_urgency TEXT,
        evidence JSONB,
        reasoning TEXT,
        predicted_at TIMESTAMP DEFAULT NOW(),
        INDEX idx_hostname_predicted (hostname, predicted_at DESC)
      )
    `);

    // Insert prediction
    cursor.execute(`
      INSERT INTO monitoring.health_predictions
      (hostname, degradation_probability, primary_risk, time_to_failure_hours,
       validated_probability, validation_confidence, decision_action, decision_urgency,
       evidence, reasoning)
      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    `, [
      hostname,
      analysis.degradation_probability,
      analysis.primary_risk,
      analysis.time_to_failure_hours,
      validation.validated_probability,
      validation.confidence,
      decision.action,
      decision.urgency,
      JSON.stringify({
        haiku_evidence: analysis.evidence,
        sonnet_reasoning: validation.reasoning,
        opus_reasoning: decision.reasoning
      }),
      decision.reasoning
    ]);

    conn.commit();
    cursor.close();
    conn.close();
  } catch (error) {
    console.error(`Failed to store prediction: ${error.message}`);
    if (conn) {
      conn.rollback();
      conn.close();
    }
  }
}

/**
 * Get active jobs count for a server (from fleet registry)
 */
async function getActiveJobs(hostname) {
  const psycopg2 = require('psycopg2');

  let conn;
  try {
    conn = psycopg2.connect({
      ...DB_CONFIG,
      connect_timeout: 5
    });

    const cursor = conn.cursor();
    cursor.execute(`
      SELECT COUNT(*)
      FROM fleet.jobs
      WHERE assigned_worker = %s
        AND status IN ('running', 'pending')
    `, [hostname]);

    const result = cursor.fetchone();
    cursor.close();
    conn.close();

    return result ? result[0] : 0;
  } catch (error) {
    console.error(`Failed to get active jobs: ${error.message}`);
    if (conn) {
      conn.close();
    }
    return 0;
  }
}

/**
 * Extract metrics for a specific hostname from Prometheus results
 */
function extractHostMetrics(allMetrics, hostname) {
  const hostMetrics = {};

  for (const [metricName, results] of Object.entries(allMetrics)) {
    // Find results matching this hostname (instance label)
    const matching = results.filter(r => {
      const instance = r.metric.instance || '';
      return instance.includes(hostname) || instance === hostname;
    });

    if (matching.length > 0) {
      // Take first match (should only be one)
      hostMetrics[metricName] = matching[0].values.map(v => ({
        timestamp: v[0],
        value: parseFloat(v[1])
      }));
    } else {
      hostMetrics[metricName] = [];
    }
  }

  return hostMetrics;
}

/**
 * Check if metrics exceed 80% of circuit breaker thresholds
 */
function checkImmediateTrigger(metrics) {
  const latest = {};

  for (const [metricName, values] of Object.entries(metrics)) {
    if (values.length > 0) {
      latest[metricName] = values[values.length - 1].value;
    }
  }

  const triggers = [];

  if (latest.cpu_usage && latest.cpu_usage > CIRCUIT_BREAKER_THRESHOLDS.cpu_usage * 0.8) {
    triggers.push(`cpu_usage: ${latest.cpu_usage.toFixed(1)}% > ${CIRCUIT_BREAKER_THRESHOLDS.cpu_usage * 0.8}%`);
  }

  if (latest.memory_usage && latest.memory_usage > CIRCUIT_BREAKER_THRESHOLDS.memory_usage * 0.8) {
    triggers.push(`memory_usage: ${latest.memory_usage.toFixed(1)}% > ${CIRCUIT_BREAKER_THRESHOLDS.memory_usage * 0.8}%`);
  }

  if (latest.load_avg && latest.cpu_cores) {
    const loadPerCore = latest.load_avg / latest.cpu_cores;
    if (loadPerCore > CIRCUIT_BREAKER_THRESHOLDS.load_avg_per_core * 0.8) {
      triggers.push(`load_avg/core: ${loadPerCore.toFixed(2)} > ${CIRCUIT_BREAKER_THRESHOLDS.load_avg_per_core * 0.8}`);
    }
  }

  if (latest.iowait && latest.iowait > CIRCUIT_BREAKER_THRESHOLDS.disk_iowait * 0.8) {
    triggers.push(`iowait: ${latest.iowait.toFixed(1)}% > ${CIRCUIT_BREAKER_THRESHOLDS.disk_iowait * 0.8}%`);
  }

  if (latest.cpu_temp && latest.cpu_temp > CIRCUIT_BREAKER_THRESHOLDS.cpu_temp * 0.8) {
    triggers.push(`cpu_temp: ${latest.cpu_temp.toFixed(1)}°C > ${CIRCUIT_BREAKER_THRESHOLDS.cpu_temp * 0.8}°C`);
  }

  return triggers;
}

/**
 * Main prediction workflow
 */
async function predictHealth(hostname) {
  console.log(`\n${'='.repeat(60)}`);
  console.log(`Predicting health for: ${hostname}`);
  console.log('='.repeat(60));

  // Step 1: Collect metrics
  const allMetrics = await collectMetrics();
  const hostMetrics = extractHostMetrics(allMetrics, hostname);

  // Check for immediate triggers
  const triggers = checkImmediateTrigger(hostMetrics);
  if (triggers.length > 0) {
    console.log('\n⚠️  IMMEDIATE TRIGGER DETECTED:');
    triggers.forEach(t => console.log(`  - ${t}`));
  }

  // Step 2: Analyze with Haiku (fast anomaly detection)
  console.log('\n[1/3] Analyzing with Haiku...');
  const analysis = await analyzeWithHaiku(hostMetrics, hostname);
  console.log(`  Degradation probability: ${(analysis.degradation_probability * 100).toFixed(1)}%`);
  console.log(`  Primary risk: ${analysis.primary_risk}`);
  console.log(`  Recommendation: ${analysis.recommendation}`);

  // Step 3: Validate with Sonnet (cross-check)
  console.log('\n[2/3] Validating with Sonnet...');
  const validation = await validateWithSonnet(analysis, hostMetrics, hostname);
  console.log(`  Validated probability: ${(validation.validated_probability * 100).toFixed(1)}%`);
  console.log(`  Agreement: ${validation.agreement}`);
  console.log(`  Confidence: ${(validation.confidence * 100).toFixed(1)}%`);

  // Step 4: Migration decision with Opus (if needed)
  console.log('\n[3/3] Decision with Opus...');
  const activeJobs = await getActiveJobs(hostname);
  const decision = await decideMigrationWithOpus(analysis, validation, hostname, activeJobs);
  console.log(`  Action: ${decision.action}`);
  console.log(`  Urgency: ${decision.urgency}`);
  if (decision.migration_window_hours) {
    console.log(`  Migration window: ${decision.migration_window_hours}h`);
  }

  // Step 5: Store prediction
  await storePrediction(hostname, analysis, validation, decision);

  console.log('\n✅ Prediction complete');

  return {
    hostname,
    degradation_probability: validation.validated_probability,
    primary_risk: analysis.primary_risk,
    action: decision.action,
    urgency: decision.urgency,
    triggers: triggers.length > 0 ? triggers : null
  };
}

/**
 * Get all active fleet workers
 */
async function getFleetWorkers() {
  const psycopg2 = require('psycopg2');

  let conn;
  try {
    conn = psycopg2.connect({
      ...DB_CONFIG,
      connect_timeout: 5
    });

    const cursor = conn.cursor();
    cursor.execute(`
      SELECT hostname
      FROM fleet.workers
      WHERE status IN ('active', 'degraded')
        AND last_heartbeat > NOW() - INTERVAL '10 minutes'
      ORDER BY hostname
    `);

    const workers = cursor.fetchall().map(row => row[0]);
    cursor.close();
    conn.close();

    return workers;
  } catch (error) {
    console.error(`Failed to get fleet workers: ${error.message}`);
    if (conn) {
      conn.close();
    }

    // Fallback to static list
    return [
      'server-01',
      'server-02',
      'server-03',
      'laptop-01',
      'pi-01',
      'pi-02',
      'desktop-ap',
      'server-ap'
    ];
  }
}

/**
 * CLI entry point
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Fleet Health Predictor - AI-based predictive server failure detection

Usage:
  node tools/fleet-health-predictor.js [OPTIONS]

Options:
  --hostname <name>   Predict health for specific server
  --all               Predict health for all fleet workers (default)
  --threshold <0-1>   Set degradation probability threshold (default: 0.70)
  --help              Show this help

Examples:
  node tools/fleet-health-predictor.js --hostname server-01
  node tools/fleet-health-predictor.js --all
  node tools/fleet-health-predictor.js --hostname laptop-01 --threshold 0.60

Environment:
  PROMETHEUS_URL      Prometheus server URL (default: http://pi-02:9090)
  POSTGRES_HOST       PostgreSQL host (default: aio-01)
  POSTGRES_PORT       PostgreSQL port (default: 5433)

Cron setup (every 5 minutes):
  */5 * * * * cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills && node tools/fleet-health-predictor.js --all >> /var/log/fleet-health-predictor.log 2>&1
`);
    process.exit(0);
  }

  // Parse arguments
  let targetHostname = null;
  let allWorkers = true;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--hostname') {
      targetHostname = args[++i];
      allWorkers = false;
    } else if (args[i] === '--all') {
      allWorkers = true;
    } else if (args[i] === '--threshold') {
      const threshold = parseFloat(args[++i]);
      if (threshold >= 0 && threshold <= 1) {
        PREDICTION_THRESHOLD = threshold;
      }
    }
  }

  console.log('='.repeat(60));
  console.log('FLEET HEALTH PREDICTOR');
  console.log('='.repeat(60));
  console.log(`Prometheus: ${PROMETHEUS_URL}`);
  console.log(`Lookback: ${LOOKBACK_HOURS / 24} days`);
  console.log(`Threshold: ${(PREDICTION_THRESHOLD * 100).toFixed(0)}% degradation probability`);
  console.log('='.repeat(60));

  let results = [];

  if (allWorkers) {
    const workers = await getFleetWorkers();
    console.log(`\nAnalyzing ${workers.length} workers: ${workers.join(', ')}\n`);

    for (const worker of workers) {
      try {
        const result = await predictHealth(worker);
        results.push(result);
      } catch (error) {
        console.error(`\n❌ Failed to predict health for ${worker}: ${error.message}\n`);
      }
    }
  } else if (targetHostname) {
    const result = await predictHealth(targetHostname);
    results.push(result);
  } else {
    console.error('Error: No hostname specified and --all not set');
    process.exit(1);
  }

  // Summary
  console.log('\n' + '='.repeat(60));
  console.log('SUMMARY');
  console.log('='.repeat(60));

  const degraded = results.filter(r => r.degradation_probability >= PREDICTION_THRESHOLD);
  const criticalActions = results.filter(r => r.urgency === 'critical');

  console.log(`Total analyzed: ${results.length}`);
  console.log(`Degraded (>=${(PREDICTION_THRESHOLD * 100).toFixed(0)}%): ${degraded.length}`);
  console.log(`Critical actions required: ${criticalActions.length}`);

  if (degraded.length > 0) {
    console.log('\nDegraded servers:');
    degraded.forEach(r => {
      console.log(`  - ${r.hostname}: ${(r.degradation_probability * 100).toFixed(1)}% (${r.primary_risk}) → ${r.action}`);
    });
  }

  if (criticalActions.length > 0) {
    console.log('\n⚠️  CRITICAL ACTIONS REQUIRED:');
    criticalActions.forEach(r => {
      console.log(`  - ${r.hostname}: ${r.action} (${r.urgency})`);
    });
  }

  console.log('\n✅ Fleet health prediction complete');
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error(`Fatal error: ${error.message}`);
    process.exit(1);
  });
}

// Exports for integration
export {
  predictHealth,
  collectMetrics,
  analyzeWithHaiku,
  validateWithSonnet,
  decideMigrationWithOpus,
  checkImmediateTrigger
};
