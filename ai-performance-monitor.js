export const meta = {
  name: 'ai-performance-monitor',
  description: 'Track accuracy, latency, cost over time with dashboards, metrics, and anomaly alerts',
  whenToUse: 'When you need to monitor AI model performance, detect degradation, generate performance reports, and analyze trends across workflows',
  phases: [
    { title: 'Init', detail: 'Load performance config and historical data' },
    { title: 'Track', detail: 'Record metrics: accuracy, latency, cost, tokens' },
    { title: 'Analyze', detail: 'Compute statistics, detect anomalies, identify trends' },
    { title: 'Report', detail: 'Generate dashboards, alerts, and comprehensive reports' },
  ],
}

// ============================================================================
// USAGE:
//
// --- Record a performance observation ---
// const result = await workflow('ai-performance-monitor', {
//   action: 'track',
//   model: 'opus',
//   workflow_id: 'code-review-run-42',
//   task_type: 'code-review',
//   latency_ms: 2500,
//   input_tokens: 1500,
//   output_tokens: 800,
//   cost_usd: 0.0825,
//   accuracy: 0.95,          // 0-1, if applicable
//   success: true,           // was the task successful?
//   metadata: { severity: 'high' },
// })
//
// --- Get current performance metrics for a model ---
// const metrics = await workflow('ai-performance-monitor', {
//   action: 'getMetrics',
//   model: 'opus',           // optional filter by model
//   time_window_hours: 24,   // optional, default 24
// })
//
// --- Generate a performance dashboard ---
// const dashboard = await workflow('ai-performance-monitor', {
//   action: 'getDashboard',
//   include_charts: true,
// })
//
// --- Generate a comprehensive report ---
// const report = await workflow('ai-performance-monitor', {
//   action: 'generateReport',
//   model: 'opus',           // optional
//   time_window_hours: 168,  // 1 week
// })
//
// --- Check for performance anomalies ---
// const anomalies = await workflow('ai-performance-monitor', {
//   action: 'detectAnomalies',
//   model: 'opus',
// })
//
// --- Get performance trends ---
// const trends = await workflow('ai-performance-monitor', {
//   action: 'getTrends',
//   model: 'opus',
//   metrics: ['latency', 'accuracy', 'cost'],
//   time_window_hours: 168,
// })
//
// --- Compare model performance ---
// const comparison = await workflow('ai-performance-monitor', {
//   action: 'compareModels',
//   models: ['opus', 'sonnet', 'haiku'],
//   time_window_hours: 24,
// })
//
// --- Reset all performance data ---
// const reset = await workflow('ai-performance-monitor', { action: 'reset' })
// ============================================================================

import fs from 'fs'
import path from 'path'

// ============================================================================
// CONFIGURATION
// ============================================================================

const DEFAULT_CONFIG = {
  data_dir: '~/.claude/repos/claude-global-skills/memory',
  data_file: 'performance-data.json',
  anomaly_detection: {
    enabled: true,
    std_dev_threshold: 2.5,        // trigger alert if > 2.5 std devs from mean
    min_samples_for_baseline: 10,  // need at least 10 samples to compute baseline
    metrics: ['latency_ms', 'cost_usd', 'accuracy'],
  },
  alerts: {
    enabled: true,
    latency_warning_ms: 5000,
    cost_warning_usd: 0.50,
    accuracy_warning: 0.70,        // warn if accuracy < 70%
    error_rate_warning: 0.10,      // warn if error rate > 10%
  },
  time_windows: {
    default_hours: 24,
    min_hours: 1,
    max_hours: 720,                // 30 days
  },
}

// ============================================================================
// DATA STRUCTURE
// ============================================================================

function createPerformanceRecord(args = {}) {
  return {
    timestamp: new Date().toISOString(),
    session_id: args.session_id || generateSessionId(),
    model: args.model || 'unknown',
    workflow_id: args.workflow_id || null,
    task_type: args.task_type || null,
    latency_ms: args.latency_ms || 0,
    input_tokens: args.input_tokens || 0,
    output_tokens: args.output_tokens || 0,
    cost_usd: args.cost_usd || 0,
    accuracy: args.accuracy !== undefined ? args.accuracy : null,
    success: args.success !== undefined ? args.success : true,
    error: args.error || null,
    metadata: args.metadata || {},
  }
}

function createPerformanceData() {
  return {
    version: '1.0',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    session_id: generateSessionId(),
    records: [],
    model_stats: {},      // cached stats per model
    last_analysis: null,
  }
}

function generateSessionId() {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

// ============================================================================
// FILE I/O
// ============================================================================

function loadPerformanceData() {
  try {
    ensureDataDir()
    const dataPath = path.join(DEFAULT_CONFIG.data_dir, DEFAULT_CONFIG.data_file)

    if (fs.existsSync(dataPath)) {
      const raw = fs.readFileSync(dataPath, 'utf-8')
      const data = JSON.parse(raw)
      return data
    }
  } catch (err) {
    console.warn(`Failed to load performance data: ${err.message}`)
  }

  return createPerformanceData()
}

function savePerformanceData(data) {
  try {
    ensureDataDir()
    const dataPath = path.join(DEFAULT_CONFIG.data_dir, DEFAULT_CONFIG.data_file)
    data.updated_at = new Date().toISOString()
    fs.writeFileSync(dataPath, JSON.stringify(data, null, 2), 'utf-8')
    return true
  } catch (err) {
    console.error(`Failed to save performance data: ${err.message}`)
    return false
  }
}

function ensureDataDir() {
  if (!fs.existsSync(DEFAULT_CONFIG.data_dir)) {
    fs.mkdirSync(DEFAULT_CONFIG.data_dir, { recursive: true })
  }
}

// ============================================================================
// ACTIONS
// ============================================================================

async function handleTrack(args) {
  const data = loadPerformanceData()
  const record = createPerformanceRecord(args)

  data.records.push(record)
  savePerformanceData(data)

  // Check for alerts
  const alerts = checkAlertsForRecord(record, data)

  return {
    recorded: true,
    timestamp: record.timestamp,
    alerts: alerts,
    total_records: data.records.length,
  }
}

async function handleGetMetrics(args) {
  const data = loadPerformanceData()
  const model = args.model
  const timeWindowHours = args.time_window_hours || DEFAULT_CONFIG.time_windows.default_hours

  // Filter records by model and time window
  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000)
  const relevantRecords = data.records.filter((r) => {
    const recordTime = new Date(r.timestamp)
    const modelMatch = !model || r.model === model
    return modelMatch && recordTime >= cutoffTime
  })

  if (relevantRecords.length === 0) {
    return {
      model: model || 'all',
      time_window_hours: timeWindowHours,
      record_count: 0,
      metrics: null,
    }
  }

  const metrics = computeMetrics(relevantRecords)

  return {
    model: model || 'all',
    time_window_hours: timeWindowHours,
    record_count: relevantRecords.length,
    metrics: metrics,
    observation_period: {
      start: relevantRecords[0].timestamp,
      end: relevantRecords[relevantRecords.length - 1].timestamp,
    },
  }
}

async function handleGetDashboard(args) {
  const data = loadPerformanceData()
  const includeCharts = args.include_charts !== false

  // Get metrics for all models
  const models = [...new Set(data.records.map((r) => r.model))]
  const dashboardData = {}

  for (const model of models) {
    const modelRecords = data.records.filter((r) => r.model === model)
    if (modelRecords.length > 0) {
      dashboardData[model] = {
        record_count: modelRecords.length,
        metrics: computeMetrics(modelRecords),
        recent_anomalies: detectAnomaliesForModel(modelRecords, model),
      }
    }
  }

  // Compute overall dashboard
  const overallMetrics = computeMetrics(data.records)

  const dashboard = {
    timestamp: new Date().toISOString(),
    summary: {
      total_records: data.records.length,
      unique_models: models.length,
      unique_workflows: [...new Set(data.records.map((r) => r.workflow_id).filter(Boolean))].length,
      unique_tasks: [...new Set(data.records.map((r) => r.task_type).filter(Boolean))].length,
    },
    overall_metrics: overallMetrics,
    by_model: dashboardData,
    system_health: computeSystemHealth(data.records),
  }

  if (includeCharts) {
    dashboard.charts = {
      latency_over_time: generateTimeSeriesChart(data.records, 'latency_ms', 20),
      cost_over_time: generateTimeSeriesChart(data.records, 'cost_usd', 20),
      accuracy_over_time: generateTimeSeriesChart(data.records, 'accuracy', 20),
      model_distribution: generateModelDistribution(data.records),
    }
  }

  return dashboard
}

async function handleGenerateReport(args) {
  const data = loadPerformanceData()
  const model = args.model
  const timeWindowHours = args.time_window_hours || DEFAULT_CONFIG.time_windows.default_hours

  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000)
  const relevantRecords = data.records.filter((r) => {
    const recordTime = new Date(r.timestamp)
    const modelMatch = !model || r.model === model
    return modelMatch && recordTime >= cutoffTime
  })

  const metrics = computeMetrics(relevantRecords)
  const anomalies = detectAnomaliesForModel(relevantRecords, model || 'all')
  const trends = analyzeTrends(relevantRecords)

  const report = {
    title: `Performance Report${model ? ` - ${model}` : ''}`,
    generated_at: new Date().toISOString(),
    analysis_period: {
      hours: timeWindowHours,
      start: relevantRecords[0]?.timestamp || null,
      end: relevantRecords[relevantRecords.length - 1]?.timestamp || null,
      record_count: relevantRecords.length,
    },
    executive_summary: generateExecutiveSummary(metrics, anomalies, trends),
    detailed_metrics: metrics,
    anomalies: anomalies,
    trends: trends,
    recommendations: generateRecommendations(metrics, anomalies, trends),
    tables: {
      by_workflow: generateWorkflowTable(relevantRecords),
      by_task_type: generateTaskTypeTable(relevantRecords),
      by_model: generateModelTable(relevantRecords),
      recent_records: relevantRecords.slice(-20),
    },
  }

  return report
}

async function handleDetectAnomalies(args) {
  const data = loadPerformanceData()
  const model = args.model

  const relevantRecords = model
    ? data.records.filter((r) => r.model === model)
    : data.records

  const anomalies = detectAnomaliesForModel(relevantRecords, model || 'all')

  return {
    model: model || 'all',
    anomaly_count: anomalies.length,
    anomalies: anomalies,
    alert_threshold: `${DEFAULT_CONFIG.anomaly_detection.std_dev_threshold} σ`,
    confidence: anomalies.length > 0 ? 'high' : 'medium',
  }
}

async function handleGetTrends(args) {
  const data = loadPerformanceData()
  const model = args.model
  const timeWindowHours = args.time_window_hours || DEFAULT_CONFIG.time_windows.default_hours
  const metricsList = args.metrics || ['latency_ms', 'cost_usd', 'accuracy']

  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000)
  const relevantRecords = data.records.filter((r) => {
    const recordTime = new Date(r.timestamp)
    const modelMatch = !model || r.model === model
    return modelMatch && recordTime >= cutoffTime
  })

  const trends = analyzeTrends(relevantRecords)

  return {
    model: model || 'all',
    time_window_hours: timeWindowHours,
    observation_count: relevantRecords.length,
    metrics_analyzed: metricsList,
    trends: trends,
  }
}

async function handleCompareModels(args) {
  const data = loadPerformanceData()
  const modelsToCompare = args.models || [...new Set(data.records.map((r) => r.model))]
  const timeWindowHours = args.time_window_hours || DEFAULT_CONFIG.time_windows.default_hours

  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000)

  const comparison = {
    timestamp: new Date().toISOString(),
    time_window_hours: timeWindowHours,
    models_compared: modelsToCompare,
    comparison_table: {},
  }

  for (const model of modelsToCompare) {
    const modelRecords = data.records.filter((r) => {
      const recordTime = new Date(r.timestamp)
      return r.model === model && recordTime >= cutoffTime
    })

    if (modelRecords.length > 0) {
      const metrics = computeMetrics(modelRecords)
      comparison.comparison_table[model] = {
        record_count: modelRecords.length,
        latency: {
          avg_ms: metrics.latency.avg,
          p95_ms: metrics.latency.p95,
          p99_ms: metrics.latency.p99,
        },
        cost: {
          total_usd: metrics.cost.total,
          avg_per_call: metrics.cost.avg,
        },
        accuracy: metrics.accuracy ? {
          avg: metrics.accuracy.avg,
          min: metrics.accuracy.min,
          max: metrics.accuracy.max,
        } : null,
        success_rate: metrics.success_rate,
      }
    }
  }

  // Identify best-performing model for each metric
  comparison.rankings = rankModelsByMetric(comparison.comparison_table)

  return comparison
}

async function handleReset(args) {
  const data = createPerformanceData()
  savePerformanceData(data)

  return {
    reset: true,
    message: 'All performance data cleared',
    new_session_id: data.session_id,
  }
}

// ============================================================================
// COMPUTATION: METRICS
// ============================================================================

function computeMetrics(records) {
  if (records.length === 0) {
    return null
  }

  const latencies = records.map((r) => r.latency_ms).filter((v) => v > 0)
  const costs = records.map((r) => r.cost_usd).filter((v) => v > 0)
  const accuracies = records.map((r) => r.accuracy).filter((v) => v !== null)
  const successes = records.filter((r) => r.success).length

  const metrics = {
    latency: latencies.length > 0 ? computePercentiles(latencies) : null,
    cost: {
      total: costs.reduce((a, b) => a + b, 0),
      avg: costs.length > 0 ? costs.reduce((a, b) => a + b, 0) / costs.length : 0,
      min: costs.length > 0 ? Math.min(...costs) : 0,
      max: costs.length > 0 ? Math.max(...costs) : 0,
      stddev: costs.length > 1 ? computeStdDev(costs) : 0,
    },
    accuracy: accuracies.length > 0 ? {
      avg: accuracies.reduce((a, b) => a + b, 0) / accuracies.length,
      min: Math.min(...accuracies),
      max: Math.max(...accuracies),
      stddev: accuracies.length > 1 ? computeStdDev(accuracies) : 0,
    } : null,
    tokens: {
      total_input: records.reduce((a, r) => a + r.input_tokens, 0),
      total_output: records.reduce((a, r) => a + r.output_tokens, 0),
      avg_input: records.reduce((a, r) => a + r.input_tokens, 0) / records.length,
      avg_output: records.reduce((a, r) => a + r.output_tokens, 0) / records.length,
    },
    success_rate: (successes / records.length) * 100,
    call_count: records.length,
  }

  return metrics
}

function computePercentiles(values) {
  const sorted = [...values].sort((a, b) => a - b)
  const len = sorted.length

  return {
    min: sorted[0],
    p25: sorted[Math.floor(len * 0.25)],
    p50: sorted[Math.floor(len * 0.5)],
    p75: sorted[Math.floor(len * 0.75)],
    p95: sorted[Math.floor(len * 0.95)],
    p99: sorted[Math.floor(len * 0.99)],
    max: sorted[len - 1],
    avg: sorted.reduce((a, b) => a + b, 0) / len,
    stddev: computeStdDev(sorted),
  }
}

function computeStdDev(values) {
  if (values.length < 2) return 0
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const variance = values.reduce((a, v) => a + Math.pow(v - mean, 2), 0) / Math.max(values.length - 1, 1)
  return Math.sqrt(variance)
}

// ============================================================================
// ANOMALY DETECTION
// ============================================================================

function detectAnomaliesForModel(records, modelName) {
  if (records.length < DEFAULT_CONFIG.anomaly_detection.min_samples_for_baseline) {
    return []
  }

  const anomalies = []
  const metricsToCheck = DEFAULT_CONFIG.anomaly_detection.metrics

  for (const metric of metricsToCheck) {
    const values = records.map((r) => r[metric]).filter((v) => v !== null && v !== undefined)

    if (values.length < DEFAULT_CONFIG.anomaly_detection.min_samples_for_baseline) {
      continue
    }

    const mean = values.reduce((a, b) => a + b, 0) / values.length
    const stddev = computeStdDev(values)
    const threshold = mean + stddev * DEFAULT_CONFIG.anomaly_detection.std_dev_threshold

    for (let i = 0; i < records.length; i++) {
      const value = records[i][metric]

      if (value !== null && value !== undefined && value > threshold) {
        anomalies.push({
          timestamp: records[i].timestamp,
          metric: metric,
          value: value,
          baseline_mean: mean,
          baseline_stddev: stddev,
          threshold: threshold,
          deviation_sigmas: (value - mean) / stddev,
          severity: computeAnomalySeverity((value - mean) / stddev),
        })
      }
    }
  }

  return anomalies.sort((a, b) => b.deviation_sigmas - a.deviation_sigmas)
}

function computeAnomalySeverity(sigmas) {
  if (sigmas > 4) return 'critical'
  if (sigmas > 3) return 'high'
  if (sigmas > 2.5) return 'medium'
  return 'low'
}

function checkAlertsForRecord(record, data) {
  const alerts = []

  if (record.latency_ms > DEFAULT_CONFIG.alerts.latency_warning_ms) {
    alerts.push({
      type: 'latency_high',
      severity: 'warning',
      message: `High latency: ${record.latency_ms}ms (threshold: ${DEFAULT_CONFIG.alerts.latency_warning_ms}ms)`,
    })
  }

  if (record.cost_usd > DEFAULT_CONFIG.alerts.cost_warning_usd) {
    alerts.push({
      type: 'cost_high',
      severity: 'warning',
      message: `High cost: $${record.cost_usd.toFixed(4)} (threshold: $${DEFAULT_CONFIG.alerts.cost_warning_usd.toFixed(4)})`,
    })
  }

  if (record.accuracy !== null && record.accuracy < DEFAULT_CONFIG.alerts.accuracy_warning) {
    alerts.push({
      type: 'accuracy_low',
      severity: 'warning',
      message: `Low accuracy: ${(record.accuracy * 100).toFixed(1)}% (threshold: ${DEFAULT_CONFIG.alerts.accuracy_warning * 100}%)`,
    })
  }

  if (!record.success) {
    alerts.push({
      type: 'execution_failure',
      severity: 'error',
      message: `Task execution failed: ${record.error || 'unknown error'}`,
    })
  }

  return alerts
}

// ============================================================================
// TRENDS ANALYSIS
// ============================================================================

function analyzeTrends(records) {
  if (records.length < 2) {
    return { message: 'Insufficient data for trend analysis', trends: [] }
  }

  const sorted = records.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
  const midpoint = Math.floor(sorted.length / 2)

  const firstHalf = sorted.slice(0, midpoint)
  const secondHalf = sorted.slice(midpoint)

  const firstMetrics = computeMetrics(firstHalf)
  const secondMetrics = computeMetrics(secondHalf)

  const trends = []

  if (firstMetrics && secondMetrics) {
    if (firstMetrics.latency && secondMetrics.latency) {
      const direction = secondMetrics.latency.avg > firstMetrics.latency.avg ? 'increasing' : 'decreasing'
      const change = ((secondMetrics.latency.avg - firstMetrics.latency.avg) / firstMetrics.latency.avg) * 100
      trends.push({
        metric: 'latency',
        direction: direction,
        change_percent: change.toFixed(2),
        interpretation: direction === 'increasing' ? 'Performance degradation' : 'Performance improvement',
      })
    }

    const costChange = ((secondMetrics.cost.avg - firstMetrics.cost.avg) / firstMetrics.cost.avg) * 100
    const costDirection = costChange > 0 ? 'increasing' : 'decreasing'
    trends.push({
      metric: 'cost',
      direction: costDirection,
      change_percent: costChange.toFixed(2),
      interpretation: costDirection === 'increasing' ? 'Cost per call increasing' : 'Cost per call decreasing',
    })

    if (firstMetrics.accuracy && secondMetrics.accuracy) {
      const accuracyChange = ((secondMetrics.accuracy.avg - firstMetrics.accuracy.avg) / firstMetrics.accuracy.avg) * 100
      const accuracyDirection = accuracyChange > 0 ? 'improving' : 'declining'
      trends.push({
        metric: 'accuracy',
        direction: accuracyDirection,
        change_percent: accuracyChange.toFixed(2),
        interpretation: accuracyDirection === 'improving' ? 'Accuracy improving' : 'Accuracy declining',
      })
    }
  }

  return trends
}

// ============================================================================
// REPORTS & VISUALIZATION
// ============================================================================

function generateExecutiveSummary(metrics, anomalies, trends) {
  if (!metrics) {
    return 'Insufficient data for analysis'
  }

  const summaryLines = []

  summaryLines.push(`Total Calls: ${metrics.call_count}`)
  summaryLines.push(`Success Rate: ${metrics.success_rate.toFixed(1)}%`)

  if (metrics.latency) {
    summaryLines.push(`Avg Latency: ${metrics.latency.avg.toFixed(0)}ms`)
  }

  summaryLines.push(`Total Cost: $${metrics.cost.total.toFixed(4)}`)

  if (metrics.accuracy) {
    summaryLines.push(`Avg Accuracy: ${(metrics.accuracy.avg * 100).toFixed(1)}%`)
  }

  if (anomalies.length > 0) {
    summaryLines.push(`Anomalies Detected: ${anomalies.length}`)
  }

  if (trends.length > 0) {
    summaryLines.push(`Trends: ${trends.length}`)
  }

  return summaryLines.join('\n')
}

function generateRecommendations(metrics, anomalies, trends) {
  const recommendations = []

  if (metrics.success_rate < 95) {
    recommendations.push('Low success rate detected. Investigate failure patterns.')
  }

  if (metrics.latency && metrics.latency.p99 > 10000) {
    recommendations.push('High latency at p99. Consider model optimization or request batching.')
  }

  if (anomalies.length > 5) {
    recommendations.push('Multiple anomalies detected. Review recent changes or load spikes.')
  }

  if (metrics.accuracy && metrics.accuracy.avg < 0.80) {
    recommendations.push('Below-target accuracy. Review training data or task specifications.')
  }

  if (trends.some((t) => t.metric === 'cost' && t.direction === 'increasing')) {
    recommendations.push('Cost per call increasing. Consider more cost-effective models.')
  }

  if (recommendations.length === 0) {
    recommendations.push('System performance is nominal. No immediate actions required.')
  }

  return recommendations
}

function generateWorkflowTable(records) {
  const byWorkflow = {}

  for (const record of records) {
    const wf = record.workflow_id || 'unknown'
    if (!byWorkflow[wf]) {
      byWorkflow[wf] = []
    }
    byWorkflow[wf].push(record)
  }

  const table = []
  for (const [workflow, recs] of Object.entries(byWorkflow)) {
    const metrics = computeMetrics(recs)
    table.push({
      workflow_id: workflow,
      call_count: recs.length,
      success_rate: metrics.success_rate.toFixed(1) + '%',
      avg_latency_ms: metrics.latency ? metrics.latency.avg.toFixed(0) : 'N/A',
      total_cost_usd: metrics.cost.total.toFixed(4),
    })
  }

  return table.sort((a, b) => b.call_count - a.call_count)
}

function generateTaskTypeTable(records) {
  const byTaskType = {}

  for (const record of records) {
    const task = record.task_type || 'unknown'
    if (!byTaskType[task]) {
      byTaskType[task] = []
    }
    byTaskType[task].push(record)
  }

  const table = []
  for (const [taskType, recs] of Object.entries(byTaskType)) {
    const metrics = computeMetrics(recs)
    table.push({
      task_type: taskType,
      call_count: recs.length,
      success_rate: metrics.success_rate.toFixed(1) + '%',
      avg_latency_ms: metrics.latency ? metrics.latency.avg.toFixed(0) : 'N/A',
      total_cost_usd: metrics.cost.total.toFixed(4),
    })
  }

  return table.sort((a, b) => b.call_count - a.call_count)
}

function generateModelTable(records) {
  const byModel = {}

  for (const record of records) {
    const model = record.model || 'unknown'
    if (!byModel[model]) {
      byModel[model] = []
    }
    byModel[model].push(record)
  }

  const table = []
  for (const [model, recs] of Object.entries(byModel)) {
    const metrics = computeMetrics(recs)
    table.push({
      model: model,
      call_count: recs.length,
      success_rate: metrics.success_rate.toFixed(1) + '%',
      avg_latency_ms: metrics.latency ? metrics.latency.avg.toFixed(0) : 'N/A',
      avg_cost_usd: metrics.cost.avg.toFixed(6),
      avg_accuracy: metrics.accuracy ? (metrics.accuracy.avg * 100).toFixed(1) + '%' : 'N/A',
    })
  }

  return table.sort((a, b) => b.call_count - a.call_count)
}

function generateTimeSeriesChart(records, metric, maxPoints) {
  const sorted = records.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))

  // Downsample if needed
  const step = Math.max(1, Math.floor(sorted.length / maxPoints))
  const sampled = []

  for (let i = 0; i < sorted.length; i += step) {
    sampled.push(sorted[i])
  }

  return sampled.map((r) => ({
    timestamp: r.timestamp,
    value: r[metric],
  }))
}

function generateModelDistribution(records) {
  const models = {}

  for (const record of records) {
    const model = record.model || 'unknown'
    models[model] = (models[model] || 0) + 1
  }

  return Object.entries(models).map(([model, count]) => ({
    model: model,
    count: count,
    percentage: ((count / records.length) * 100).toFixed(1),
  }))
}

function computeSystemHealth(records) {
  if (records.length === 0) {
    return {
      status: 'unknown',
      description: 'No data available',
    }
  }

  const metrics = computeMetrics(records)
  let status = 'healthy'
  const issues = []

  if (metrics.success_rate < 90) {
    status = 'degraded'
    issues.push(`Success rate ${metrics.success_rate.toFixed(1)}% < 90%`)
  }

  if (metrics.latency && metrics.latency.p95 > 5000) {
    status = 'degraded'
    issues.push(`P95 latency ${metrics.latency.p95.toFixed(0)}ms > 5000ms`)
  }

  if (metrics.accuracy && metrics.accuracy.avg < 0.80) {
    status = 'degraded'
    issues.push(`Accuracy ${(metrics.accuracy.avg * 100).toFixed(1)}% < 80%`)
  }

  if (metrics.success_rate < 70) {
    status = 'unhealthy'
  }

  return {
    status: status,
    success_rate: metrics.success_rate.toFixed(1) + '%',
    issues: issues.length > 0 ? issues : ['No issues detected'],
  }
}

function rankModelsByMetric(comparisonTable) {
  const rankings = {}

  // Rank by latency (lower is better)
  const byLatency = Object.entries(comparisonTable)
    .sort((a, b) => a[1].latency?.avg_ms - b[1].latency?.avg_ms)
    .map(([model]) => model)
  rankings.fastest = byLatency

  // Rank by cost (lower is better)
  const byCost = Object.entries(comparisonTable)
    .sort((a, b) => a[1].cost?.avg_per_call - b[1].cost?.avg_per_call)
    .map(([model]) => model)
  rankings.cheapest = byCost

  // Rank by accuracy (higher is better)
  const byAccuracy = Object.entries(comparisonTable)
    .filter(([, data]) => data.accuracy !== null)
    .sort((a, b) => b[1].accuracy?.avg - a[1].accuracy?.avg)
    .map(([model]) => model)
  rankings.most_accurate = byAccuracy

  // Rank by success rate (higher is better)
  const bySuccess = Object.entries(comparisonTable)
    .sort((a, b) => b[1].success_rate - a[1].success_rate)
    .map(([model]) => model)
  rankings.most_reliable = bySuccess

  return rankings
}

// ============================================================================
// MAIN EXPORT
// ============================================================================

export default async function main(args = {}) {
  try {
    const action = args.action || 'generateReport'

    let result

    switch (action) {
      case 'track':
        result = await handleTrack(args)
        break
      case 'getMetrics':
        result = await handleGetMetrics(args)
        break
      case 'getDashboard':
        result = await handleGetDashboard(args)
        break
      case 'generateReport':
        result = await handleGenerateReport(args)
        break
      case 'detectAnomalies':
        result = await handleDetectAnomalies(args)
        break
      case 'getTrends':
        result = await handleGetTrends(args)
        break
      case 'compareModels':
        result = await handleCompareModels(args)
        break
      case 'reset':
        result = await handleReset(args)
        break
      default:
        result = {
          error: `Unknown action: ${action}`,
          available_actions: [
            'track',
            'getMetrics',
            'getDashboard',
            'generateReport',
            'detectAnomalies',
            'getTrends',
            'compareModels',
            'reset',
          ],
        }
    }

    return result
  } catch (err) {
    return {
      error: err.message,
      stack: err.stack,
    }
  }
}
