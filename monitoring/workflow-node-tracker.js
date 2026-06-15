export const meta = {
  name: 'workflow-node-tracker',
  description: 'Track workflow-to-node mapping: parse transcripts to determine which node executed which agent, recording workflow ID, node, AI model, start time, duration, and status',
  whenToUse: 'When you need to map workflow execution across distributed nodes, track agent deployment, monitor node utilization, or debug workflow execution paths',
  phases: [
    { title: 'Init', detail: 'Load transcript data and initialize tracking store' },
    { title: 'Parse', detail: 'Parse workflow transcripts to extract execution events' },
    { title: 'Analyze', detail: 'Correlate events to nodes, compute metrics, detect anomalies' },
    { title: 'Report', detail: 'Generate execution maps, node utilization, and performance insights' },
  ],
}

// ============================================================================
// USAGE:
//
// --- Parse a workflow transcript and track node assignments ---
// const result = await workflow('workflow-node-tracker', {
//   action: 'trackExecution',
//   workflow_id: 'code-review-run-42',
//   transcript: rawTranscriptText,
//   node_id: 'node-01',     // optional, can be inferred from transcript
//   model: 'opus',          // optional, can be parsed from transcript
// })
//
// --- Get workflow execution map ---
// const map = await workflow('workflow-node-tracker', {
//   action: 'getExecutionMap',
//   workflow_id: 'code-review-run-42',  // optional, show all if omitted
// })
//
// --- Get node utilization report ---
// const utilization = await workflow('workflow-node-tracker', {
//   action: 'getNodeUtilization',
//   node_id: 'node-01',     // optional, show all if omitted
//   time_window_hours: 24,
// })
//
// --- Get model deployment map ---
// const deployment = await workflow('workflow-node-tracker', {
//   action: 'getModelDeployment',
//   model: 'opus',          // optional
//   time_window_hours: 24,
// })
//
// --- Analyze workflow paths and branching ---
// const analysis = await workflow('workflow-node-tracker', {
//   action: 'analyzeExecutionPath',
//   workflow_id: 'code-review-run-42',
// })
//
// --- Get performance metrics per node/model combination ---
// const metrics = await workflow('workflow-node-tracker', {
//   action: 'getMetrics',
//   node_id: 'node-01',     // optional
//   model: 'opus',          // optional
//   metric_type: 'latency', // latency, throughput, error_rate, cost
// })
//
// --- Generate comprehensive execution report ---
// const report = await workflow('workflow-node-tracker', {
//   action: 'generateReport',
//   report_type: 'full',    // full, summary, nodes, models
//   time_window_hours: 168,
// })
//
// --- Reset all tracking data ---
// const reset = await workflow('workflow-node-tracker', { action: 'reset' })
// ============================================================================

import fs from 'fs'
import path from 'path'

// ============================================================================
// CONFIGURATION
// ============================================================================

const DEFAULT_CONFIG = {
  data_dir: '~/.claude/repos/claude-global-skills/memory',
  data_file: 'workflow-node-tracking.json',
  transcript_dir: '~/.claude/repos/claude-global-skills/transcripts',
  max_records: 10000,
  time_windows: {
    default_hours: 24,
    min_hours: 1,
    max_hours: 720,  // 30 days
  },
}

// ============================================================================
// TRANSCRIPT PARSING PATTERNS
// ============================================================================

const TRANSCRIPT_PATTERNS = {
  // Detect workflow start
  workflow_start: /\[WORKFLOW\]\s+(\w[\w-]*)\s+(?:started|initiated).*?(?:on\s+node\s+(\w[\w-]*))?\s*$/im,
  // Detect agent execution
  agent_execution: /\[AGENT\]\s+(\w[\w-]*)\s+(?:running|executing).*?(?:model:\s*(\w[\w-]*))?\s*$/im,
  // Detect node assignment
  node_assignment: /(?:assigned\s+to|executing\s+on|node[:\s]+)(\w[\w-]*)/im,
  // Detect model specification
  model_spec: /(?:model|using|with)\s+(?:model\s+)?(\w[\w-]*?)(?:\s|$|,|\))/im,
  // Detect timing: start time
  start_time: /(?:start|begin|initiated)\s+(?:at|time:\s+)(\d{2}:\d{2}:\d{2})/im,
  // Detect timing: end time / duration
  end_time: /(?:end|completed|finished)\s+(?:at|time:\s+)(\d{2}:\d{2}:\d{2})/im,
  duration_ms: /(?:duration|took|elapsed|time)\s+(\d+(?:\.\d+)?)\s*(?:ms|milliseconds)/im,
  // Detect status outcomes
  status_success: /(?:success|completed|finished|done)\s+✓/im,
  status_error: /(?:error|failed|exception)\s+✗/im,
  // Detect phase transitions
  phase_marker: /\[PHASE\]\s+(\w[\w\s]*?)(?:\s+\||$)/im,
  // Detect function/operation
  function_call: /(?:calling|invoking|executing)\s+([a-zA-Z_]\w*)/im,
}

// ============================================================================
// DATA STRUCTURES
// ============================================================================

function createNodeRecord(args = {}) {
  return {
    id: args.id || generateId('node'),
    workflow_id: args.workflow_id || null,
    node_id: args.node_id || null,
    model: args.model || null,
    start_time: args.start_time || new Date().toISOString(),
    end_time: args.end_time || null,
    duration_ms: args.duration_ms || null,
    status: args.status || 'pending',  // pending, running, success, error, timeout
    error: args.error || null,
    metadata: args.metadata || {},
    phases: args.phases || [],
    operations: args.operations || [],
  }
}

function createPhaseRecord(name, startTime) {
  return {
    name,
    start_time: startTime || new Date().toISOString(),
    end_time: null,
    duration_ms: null,
    status: 'running',
  }
}

function createOperationRecord(name, args = {}) {
  return {
    name,
    function: args.function || null,
    start_time: args.start_time || new Date().toISOString(),
    end_time: null,
    duration_ms: null,
    status: 'pending',
    input: args.input || null,
    output: args.output || null,
    error: args.error || null,
  }
}

function createTrackingData() {
  return {
    version: '1.0',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    session_id: generateId('session'),
    records: [],
    node_index: {},      // node_id -> array of record IDs
    workflow_index: {},  // workflow_id -> array of record IDs
    model_index: {},     // model -> array of record IDs
    stats: {
      total_workflows: 0,
      total_nodes: 0,
      total_models: 0,
      total_records: 0,
    },
  }
}

function generateId(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

// ============================================================================
// FILE I/O
// ============================================================================

function ensureDataDir() {
  try {
    const dir = path.dirname(expandPath(DEFAULT_CONFIG.data_dir))
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true })
    }
  } catch (err) {
    log(`WARNING: Could not ensure data directory: ${err.message}`)
  }
}

function expandPath(p) {
  return p.replace(/^~/, require('os').homedir())
}

function getDataPath() {
  return path.join(expandPath(DEFAULT_CONFIG.data_dir), DEFAULT_CONFIG.data_file)
}

function loadTrackingData() {
  try {
    const dataPath = getDataPath()
    if (fs.existsSync(dataPath)) {
      const raw = fs.readFileSync(dataPath, 'utf-8')
      return JSON.parse(raw)
    }
  } catch (err) {
    log(`WARNING: Could not load tracking data: ${err.message}`)
  }
  return createTrackingData()
}

function saveTrackingData(data) {
  try {
    ensureDataDir()
    const dataPath = getDataPath()
    fs.writeFileSync(dataPath, JSON.stringify(data, null, 2), 'utf-8')
  } catch (err) {
    log(`WARNING: Could not save tracking data: ${err.message}`)
  }
}

// ============================================================================
// TRANSCRIPT PARSING
// ============================================================================

function parseTranscript(transcript) {
  if (!transcript || typeof transcript !== 'string') {
    return { error: 'Invalid transcript format' }
  }

  const lines = transcript.split('\n')
  const events = []
  let currentPhase = null
  let currentTime = new Date()

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    // Check for phase markers
    const phaseMatch = line.match(TRANSCRIPT_PATTERNS.phase_marker)
    if (phaseMatch) {
      currentPhase = phaseMatch[1]
      events.push({
        type: 'phase',
        name: currentPhase,
        timestamp: currentTime.toISOString(),
      })
      continue
    }

    // Check for workflow start
    const workflowMatch = line.match(TRANSCRIPT_PATTERNS.workflow_start)
    if (workflowMatch) {
      events.push({
        type: 'workflow_start',
        workflow_id: workflowMatch[1],
        node_id: workflowMatch[2] || null,
        timestamp: currentTime.toISOString(),
      })
      continue
    }

    // Check for agent execution
    const agentMatch = line.match(TRANSCRIPT_PATTERNS.agent_execution)
    if (agentMatch) {
      events.push({
        type: 'agent_execution',
        agent: agentMatch[1],
        model: agentMatch[2] || null,
        timestamp: currentTime.toISOString(),
      })
      continue
    }

    // Check for node assignment
    const nodeMatch = line.match(TRANSCRIPT_PATTERNS.node_assignment)
    if (nodeMatch && !workflowMatch && !agentMatch) {
      events.push({
        type: 'node_assignment',
        node_id: nodeMatch[1],
        timestamp: currentTime.toISOString(),
      })
      continue
    }

    // Check for model specification
    const modelMatch = line.match(TRANSCRIPT_PATTERNS.model_spec)
    if (modelMatch && !agentMatch) {
      events.push({
        type: 'model_spec',
        model: modelMatch[1],
        timestamp: currentTime.toISOString(),
      })
      continue
    }

    // Check for timing information
    const startMatch = line.match(TRANSCRIPT_PATTERNS.start_time)
    if (startMatch) {
      events.push({
        type: 'timing',
        subtype: 'start_time',
        time: startMatch[1],
        timestamp: currentTime.toISOString(),
      })
    }

    const endMatch = line.match(TRANSCRIPT_PATTERNS.end_time)
    if (endMatch) {
      events.push({
        type: 'timing',
        subtype: 'end_time',
        time: endMatch[1],
        timestamp: currentTime.toISOString(),
      })
    }

    const durationMatch = line.match(TRANSCRIPT_PATTERNS.duration_ms)
    if (durationMatch) {
      events.push({
        type: 'timing',
        subtype: 'duration',
        duration_ms: parseFloat(durationMatch[1]),
        timestamp: currentTime.toISOString(),
      })
    }

    // Check for status
    if (line.match(TRANSCRIPT_PATTERNS.status_success)) {
      events.push({
        type: 'status',
        status: 'success',
        timestamp: currentTime.toISOString(),
      })
    }

    if (line.match(TRANSCRIPT_PATTERNS.status_error)) {
      events.push({
        type: 'status',
        status: 'error',
        timestamp: currentTime.toISOString(),
      })
    }

    // Check for function calls
    const funcMatch = line.match(TRANSCRIPT_PATTERNS.function_call)
    if (funcMatch) {
      events.push({
        type: 'function_call',
        function: funcMatch[1],
        timestamp: currentTime.toISOString(),
      })
    }
  }

  return events
}

function synthesizeRecord(workflowId, events, nodeId, model) {
  const record = createNodeRecord({
    workflow_id: workflowId,
    node_id: nodeId,
    model: model,
  })

  const phases = []
  let currentPhase = null
  let totalDuration = 0

  for (const event of events) {
    switch (event.type) {
      case 'phase':
        if (currentPhase) {
          phases.push(currentPhase)
        }
        currentPhase = createPhaseRecord(event.name, event.timestamp)
        break

      case 'agent_execution':
        if (!record.model && event.model) {
          record.model = event.model
        }
        break

      case 'node_assignment':
        if (!record.node_id) {
          record.node_id = event.node_id
        }
        break

      case 'model_spec':
        if (!record.model) {
          record.model = event.model
        }
        break

      case 'timing':
        if (event.subtype === 'duration') {
          totalDuration += event.duration_ms || 0
        }
        break

      case 'status':
        record.status = event.status
        break

      case 'function_call':
        record.operations.push(createOperationRecord(event.function))
        break
    }
  }

  if (currentPhase) {
    phases.push(currentPhase)
  }

  record.phases = phases
  if (totalDuration > 0) {
    record.duration_ms = totalDuration
  }

  return record
}

// ============================================================================
// ACTION: trackExecution
// ============================================================================

function trackExecution(data, workflowId, transcript, nodeId, model) {
  const events = parseTranscript(transcript)

  if (events.error) {
    return {
      status: 'error',
      error: events.error,
    }
  }

  const record = synthesizeRecord(workflowId, events, nodeId, model)

  // Add record to data
  data.records.push(record)
  if (data.records.length > DEFAULT_CONFIG.max_records) {
    data.records.shift()  // Remove oldest
  }

  // Update indices
  if (!data.workflow_index[record.workflow_id]) {
    data.workflow_index[record.workflow_id] = []
    data.stats.total_workflows += 1
  }
  data.workflow_index[record.workflow_id].push(record.id)

  if (record.node_id) {
    if (!data.node_index[record.node_id]) {
      data.node_index[record.node_id] = []
      data.stats.total_nodes += 1
    }
    data.node_index[record.node_id].push(record.id)
  }

  if (record.model) {
    if (!data.model_index[record.model]) {
      data.model_index[record.model] = []
      data.stats.total_models += 1
    }
    data.model_index[record.model].push(record.id)
  }

  data.stats.total_records = data.records.length
  data.updated_at = new Date().toISOString()

  saveTrackingData(data)

  return {
    status: 'tracked',
    record_id: record.id,
    workflow_id: record.workflow_id,
    node_id: record.node_id,
    model: record.model,
    duration_ms: record.duration_ms,
    phases_count: record.phases.length,
    operations_count: record.operations.length,
  }
}

// ============================================================================
// ACTION: getExecutionMap
// ============================================================================

function getExecutionMap(data, workflowId) {
  let records = []

  if (workflowId) {
    const ids = data.workflow_index[workflowId] || []
    records = data.records.filter(r => ids.includes(r.id))
  } else {
    records = data.records
  }

  const map = {
    total_records: records.length,
    workflows: {},
    execution_graph: {
      nodes: [],
      edges: [],
    },
  }

  for (const record of records) {
    if (!map.workflows[record.workflow_id]) {
      map.workflows[record.workflow_id] = {
        executions: [],
        total_duration_ms: 0,
        status: 'unknown',
        nodes_used: new Set(),
        models_used: new Set(),
      }
    }

    const wf = map.workflows[record.workflow_id]
    wf.executions.push({
      record_id: record.id,
      node_id: record.node_id,
      model: record.model,
      start_time: record.start_time,
      duration_ms: record.duration_ms,
      status: record.status,
    })

    if (record.duration_ms) {
      wf.total_duration_ms += record.duration_ms
    }
    wf.status = record.status
    if (record.node_id) wf.nodes_used.add(record.node_id)
    if (record.model) wf.models_used.add(record.model)

    // Add to execution graph
    map.execution_graph.nodes.push({
      id: record.id,
      workflow: record.workflow_id,
      node: record.node_id,
      model: record.model,
      status: record.status,
    })
  }

  // Convert sets to arrays
  for (const wf of Object.values(map.workflows)) {
    wf.nodes_used = Array.from(wf.nodes_used)
    wf.models_used = Array.from(wf.models_used)
  }

  return map
}

// ============================================================================
// ACTION: getNodeUtilization
// ============================================================================

function getNodeUtilization(data, nodeId, timeWindowHours) {
  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000)
  let records = data.records.filter(r => new Date(r.start_time) >= cutoffTime)

  if (nodeId) {
    const ids = data.node_index[nodeId] || []
    records = records.filter(r => ids.includes(r.id))
  }

  const utilization = {
    time_window_hours: timeWindowHours,
    time_window_start: cutoffTime.toISOString(),
    time_window_end: new Date().toISOString(),
    nodes: {},
  }

  const nodeRecords = {}
  for (const record of records) {
    if (!record.node_id) continue
    if (!nodeRecords[record.node_id]) {
      nodeRecords[record.node_id] = []
    }
    nodeRecords[record.node_id].push(record)
  }

  for (const [nodeId, nodeRecs] of Object.entries(nodeRecords)) {
    const totalDuration = nodeRecs.reduce((sum, r) => sum + (r.duration_ms || 0), 0)
    const successCount = nodeRecs.filter(r => r.status === 'success').length
    const errorCount = nodeRecs.filter(r => r.status === 'error').length

    utilization.nodes[nodeId] = {
      total_executions: nodeRecs.length,
      successful: successCount,
      failed: errorCount,
      error_rate: nodeRecs.length > 0 ? errorCount / nodeRecs.length : 0,
      total_duration_ms: totalDuration,
      avg_duration_ms: nodeRecs.length > 0 ? totalDuration / nodeRecs.length : 0,
      models_deployed: [...new Set(nodeRecs.map(r => r.model).filter(Boolean))],
      workflows_executed: [...new Set(nodeRecs.map(r => r.workflow_id).filter(Boolean))],
    }
  }

  return utilization
}

// ============================================================================
// ACTION: getModelDeployment
// ============================================================================

function getModelDeployment(data, model, timeWindowHours) {
  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000)
  let records = data.records.filter(r => new Date(r.start_time) >= cutoffTime)

  if (model) {
    const ids = data.model_index[model] || []
    records = records.filter(r => ids.includes(r.id))
  }

  const deployment = {
    time_window_hours: timeWindowHours,
    models: {},
  }

  const modelRecords = {}
  for (const record of records) {
    if (!record.model) continue
    if (!modelRecords[record.model]) {
      modelRecords[record.model] = []
    }
    modelRecords[record.model].push(record)
  }

  for (const [modelId, modelRecs] of Object.entries(modelRecords)) {
    const successCount = modelRecs.filter(r => r.status === 'success').length
    const errorCount = modelRecs.filter(r => r.status === 'error').length
    const totalDuration = modelRecs.reduce((sum, r) => sum + (r.duration_ms || 0), 0)

    deployment.models[modelId] = {
      total_executions: modelRecs.length,
      successful: successCount,
      failed: errorCount,
      error_rate: modelRecs.length > 0 ? errorCount / modelRecs.length : 0,
      total_duration_ms: totalDuration,
      avg_duration_ms: modelRecs.length > 0 ? totalDuration / modelRecs.length : 0,
      nodes_deployed_on: [...new Set(modelRecs.map(r => r.node_id).filter(Boolean))],
      workflows_executed: [...new Set(modelRecs.map(r => r.workflow_id).filter(Boolean))],
    }
  }

  return deployment
}

// ============================================================================
// ACTION: analyzeExecutionPath
// ============================================================================

function analyzeExecutionPath(data, workflowId) {
  const ids = data.workflow_index[workflowId] || []
  const records = data.records.filter(r => ids.includes(r.id)).sort((a, b) =>
    new Date(a.start_time) - new Date(b.start_time)
  )

  if (records.length === 0) {
    return { error: `No execution path found for workflow ${workflowId}` }
  }

  const analysis = {
    workflow_id: workflowId,
    execution_count: records.length,
    path_nodes: [],
    total_duration_ms: 0,
    critical_path: null,
    branching_detected: false,
    phases_by_execution: [],
  }

  for (const record of records) {
    analysis.path_nodes.push({
      node_id: record.node_id,
      model: record.model,
      status: record.status,
      duration_ms: record.duration_ms,
    })

    if (record.duration_ms) {
      analysis.total_duration_ms += record.duration_ms
    }

    if (record.phases.length > 0) {
      analysis.phases_by_execution.push({
        node: record.node_id,
        phases: record.phases.map(p => ({
          name: p.name,
          status: p.status,
          duration_ms: p.duration_ms,
        })),
      })
    }
  }

  // Detect branching (multiple nodes executing in same workflow)
  const nodeSet = new Set(records.map(r => r.node_id).filter(Boolean))
  analysis.branching_detected = nodeSet.size > 1

  // Find critical path (longest single execution)
  const maxDuration = Math.max(...records.map(r => r.duration_ms || 0))
  const criticalRecord = records.find(r => r.duration_ms === maxDuration)
  if (criticalRecord) {
    analysis.critical_path = {
      node_id: criticalRecord.node_id,
      model: criticalRecord.model,
      duration_ms: criticalRecord.duration_ms,
    }
  }

  return analysis
}

// ============================================================================
// ACTION: getMetrics
// ============================================================================

function getMetrics(data, nodeId, model, metricType, timeWindowHours) {
  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000)
  let records = data.records.filter(r => new Date(r.start_time) >= cutoffTime)

  if (nodeId) {
    const ids = data.node_index[nodeId] || []
    records = records.filter(r => ids.includes(r.id))
  }

  if (model) {
    const ids = data.model_index[model] || []
    records = records.filter(r => ids.includes(r.id))
  }

  const metrics = {
    filter: { nodeId, model, metricType, timeWindowHours },
    total_records: records.length,
    results: {},
  }

  if (records.length === 0) {
    return metrics
  }

  switch (metricType) {
    case 'latency': {
      const durations = records.map(r => r.duration_ms || 0).filter(d => d > 0)
      if (durations.length > 0) {
        const sorted = durations.sort((a, b) => a - b)
        const sum = sorted.reduce((a, b) => a + b, 0)
        const mean = sum / sorted.length
        const variance = sorted.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / sorted.length
        const stdDev = Math.sqrt(variance)

        metrics.results = {
          count: durations.length,
          min_ms: sorted[0],
          max_ms: sorted[sorted.length - 1],
          mean_ms: mean,
          median_ms: sorted[Math.floor(sorted.length / 2)],
          p95_ms: sorted[Math.floor(sorted.length * 0.95)],
          p99_ms: sorted[Math.floor(sorted.length * 0.99)],
          stddev_ms: stdDev,
        }
      }
      break
    }

    case 'throughput': {
      const timeSpan = Math.max(...records.map(r => new Date(r.start_time).getTime())) -
                       Math.min(...records.map(r => new Date(r.start_time).getTime()))
      const hoursSpan = timeSpan / (3600 * 1000)

      metrics.results = {
        total_executions: records.length,
        time_span_hours: hoursSpan,
        executions_per_hour: hoursSpan > 0 ? records.length / hoursSpan : 0,
      }
      break
    }

    case 'error_rate': {
      const errorCount = records.filter(r => r.status === 'error').length
      metrics.results = {
        total_executions: records.length,
        successful: records.length - errorCount,
        failed: errorCount,
        error_rate: errorCount / records.length,
      }
      break
    }

    case 'cost': {
      // Cost calculation based on estimated token usage
      const avgDuration = records.reduce((sum, r) => sum + (r.duration_ms || 0), 0) / records.length
      metrics.results = {
        total_executions: records.length,
        total_duration_ms: records.reduce((sum, r) => sum + (r.duration_ms || 0), 0),
        avg_duration_ms: avgDuration,
        estimated_total_cost_usd: (records.length * 0.005),  // Placeholder
      }
      break
    }

    default:
      return { error: `Unknown metric type: ${metricType}` }
  }

  return metrics
}

// ============================================================================
// ACTION: generateReport
// ============================================================================

function generateReport(data, reportType, timeWindowHours) {
  const cutoffTime = new Date(Date.now() - timeWindowHours * 3600 * 1000)
  const records = data.records.filter(r => new Date(r.start_time) >= cutoffTime)

  const lines = []
  lines.push('='.repeat(80))
  lines.push('WORKFLOW-NODE EXECUTION TRACKING REPORT')
  lines.push('='.repeat(80))
  lines.push(`Generated: ${new Date().toISOString()}`)
  lines.push(`Report Type: ${reportType}`)
  lines.push(`Time Window: ${timeWindowHours} hours`)
  lines.push(`Records Analyzed: ${records.length}`)
  lines.push('')

  if (reportType === 'summary' || reportType === 'full') {
    lines.push('--- SUMMARY ---')
    lines.push(`Total Workflows: ${data.stats.total_workflows}`)
    lines.push(`Total Nodes: ${data.stats.total_nodes}`)
    lines.push(`Total Models: ${data.stats.total_models}`)
    lines.push(`Total Records: ${data.stats.total_records}`)
    lines.push('')

    const successCount = records.filter(r => r.status === 'success').length
    const errorCount = records.filter(r => r.status === 'error').length
    lines.push('--- EXECUTION HEALTH ---')
    lines.push(`Successful: ${successCount} (${(successCount / records.length * 100).toFixed(1)}%)`)
    lines.push(`Failed: ${errorCount} (${(errorCount / records.length * 100).toFixed(1)}%)`)
    lines.push(`Total Duration: ${records.reduce((sum, r) => sum + (r.duration_ms || 0), 0).toLocaleString()}ms`)
    lines.push('')
  }

  if (reportType === 'nodes' || reportType === 'full') {
    lines.push('--- NODE UTILIZATION ---')
    const nodeMap = {}
    for (const record of records) {
      if (!record.node_id) continue
      if (!nodeMap[record.node_id]) {
        nodeMap[record.node_id] = { count: 0, duration: 0, models: new Set() }
      }
      nodeMap[record.node_id].count += 1
      nodeMap[record.node_id].duration += record.duration_ms || 0
      if (record.model) nodeMap[record.node_id].models.add(record.model)
    }

    for (const [nodeId, info] of Object.entries(nodeMap).sort()) {
      lines.push(`  ${nodeId}:`)
      lines.push(`    Executions: ${info.count}`)
      lines.push(`    Total Duration: ${info.duration.toLocaleString()}ms`)
      lines.push(`    Models: ${Array.from(info.models).join(', ')}`)
    }
    lines.push('')
  }

  if (reportType === 'models' || reportType === 'full') {
    lines.push('--- MODEL DEPLOYMENT ---')
    const modelMap = {}
    for (const record of records) {
      if (!record.model) continue
      if (!modelMap[record.model]) {
        modelMap[record.model] = { count: 0, nodes: new Set() }
      }
      modelMap[record.model].count += 1
      if (record.node_id) modelMap[record.model].nodes.add(record.node_id)
    }

    for (const [modelId, info] of Object.entries(modelMap).sort()) {
      lines.push(`  ${modelId}:`)
      lines.push(`    Executions: ${info.count}`)
      lines.push(`    Deployed On: ${Array.from(info.nodes).join(', ')}`)
    }
    lines.push('')
  }

  lines.push('='.repeat(80))
  return lines.join('\n')
}

// ============================================================================
// MAIN WORKFLOW
// ============================================================================

const action = args.action || 'generateReport'

phase('Init')

const data = loadTrackingData()

log('='.repeat(70))
log('WORKFLOW-NODE TRACKER')
log('='.repeat(70))
log(`Action: ${action}`)
log(`Session: ${data.session_id}`)
log(`Total Records: ${data.stats.total_records}`)
log('')

phase('Parse & Execute')

let result

switch (action) {
  case 'trackExecution': {
    const workflowId = args.workflow_id
    const transcript = args.transcript
    const nodeId = args.node_id || null
    const model = args.model || null

    if (!workflowId || !transcript) {
      log('ERROR: "workflow_id" and "transcript" are required')
      return { error: 'workflow_id and transcript are required' }
    }

    result = trackExecution(data, workflowId, transcript, nodeId, model)
    log(`✓ Tracked execution for workflow: ${workflowId}`)
    log(`  Record ID: ${result.record_id}`)
    log(`  Node: ${result.node_id || 'unknown'}`)
    log(`  Model: ${result.model || 'unknown'}`)
    break
  }

  case 'getExecutionMap': {
    result = getExecutionMap(data, args.workflow_id || null)
    log(`✓ Generated execution map`)
    log(`  Workflows: ${Object.keys(result.workflows).length}`)
    log(`  Total Records: ${result.total_records}`)
    break
  }

  case 'getNodeUtilization': {
    const timeWindow = args.time_window_hours || 24
    result = getNodeUtilization(data, args.node_id || null, timeWindow)
    log(`✓ Generated node utilization report`)
    log(`  Time Window: ${timeWindow} hours`)
    log(`  Nodes: ${Object.keys(result.nodes).length}`)
    break
  }

  case 'getModelDeployment': {
    const timeWindow = args.time_window_hours || 24
    result = getModelDeployment(data, args.model || null, timeWindow)
    log(`✓ Generated model deployment map`)
    log(`  Time Window: ${timeWindow} hours`)
    log(`  Models: ${Object.keys(result.models).length}`)
    break
  }

  case 'analyzeExecutionPath': {
    const workflowId = args.workflow_id
    if (!workflowId) {
      log('ERROR: "workflow_id" is required')
      return { error: 'workflow_id is required' }
    }
    result = analyzeExecutionPath(data, workflowId)
    if (result.error) {
      log(`ERROR: ${result.error}`)
    } else {
      log(`✓ Analyzed execution path for workflow: ${workflowId}`)
      log(`  Executions: ${result.execution_count}`)
      log(`  Branching: ${result.branching_detected ? 'Yes' : 'No'}`)
      log(`  Total Duration: ${result.total_duration_ms.toLocaleString()}ms`)
    }
    break
  }

  case 'getMetrics': {
    const metricType = args.metric_type || 'latency'
    const timeWindow = args.time_window_hours || 24
    result = getMetrics(data, args.node_id || null, args.model || null, metricType, timeWindow)
    log(`✓ Generated metrics report`)
    log(`  Metric Type: ${metricType}`)
    log(`  Records: ${result.total_records}`)
    break
  }

  case 'generateReport': {
    const reportType = args.report_type || 'full'
    const timeWindow = args.time_window_hours || 24
    const reportText = generateReport(data, reportType, timeWindow)
    log(reportText)
    result = { status: 'success', report: reportText }
    break
  }

  case 'reset': {
    const newData = createTrackingData()
    saveTrackingData(newData)
    result = { status: 'reset', session_id: newData.session_id }
    log('✓ Tracking data has been reset')
    break
  }

  default: {
    log(`ERROR: Unknown action "${action}"`)
    return { error: `Unknown action: ${action}` }
  }
}

phase('Report')

log('')
log('='.repeat(70))

return result
