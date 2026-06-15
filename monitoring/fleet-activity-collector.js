/**
 * Fleet Activity Collector
 *
 * Tracks which workflows run on which nodes across the fleet.
 * Collects workflow transcripts, SSH sessions, process lists,
 * resource usage per workflow, and AI model-to-server assignments.
 *
 * Data sources:
 *   - SSH to each node: process lists, resource usage
 *   - Fleet dispatcher (pi-02:3004): active jobs, model assignments
 *   - Workflow journals (~/.claude/projects/...): transcript data
 *   - NFS fleet-results: prompt/result files for active jobs
 *
 * Output:
 *   - JSON activity snapshots written to ~/.claude/learning/fleet-activity/
 *   - Prometheus-compatible metrics at /metrics endpoint
 *   - Real-time summary via collect() or HTTP /status
 *
 * Usage:
 *   import { FleetActivityCollector } from './fleet-activity-collector.js';
 *   const collector = new FleetActivityCollector();
 *   const snapshot = await collector.collect();
 *
 *   // Or run as continuous collector with HTTP endpoint:
 *   node monitoring/fleet-activity-collector.js [--port 9091] [--interval 60]
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import http from 'http';

// ---------------------------------------------------------------------------
// Fleet topology (matches multi-ai-config.json and deploy-fleet-prometheus.js)
// ---------------------------------------------------------------------------
const FLEET_NODES = [
  { hostname: 'laptop-01', role: 'heavy',      arch: 'amd64', models: ['fable', 'opus'] },
  { hostname: 'server-01', role: 'fast',        arch: 'amd64', models: ['sonnet', 'haiku', 'llama-70b-fast'] },
  { hostname: 'server-02', role: 'code',        arch: 'amd64', models: ['gpt-4o', 'qwen-coder-32b'] },
  { hostname: 'server-03', role: 'heavy',       arch: 'amd64', models: ['gemini', 'cerebras-120b'] },
  { hostname: 'aio-01',    role: 'passive',     arch: 'amd64', models: [] },
  { hostname: 'pi-02',     role: 'coordinator', arch: 'arm64', models: [] },
];

const FLEET_DISPATCHER = process.env.FLEET_DISPATCHER_URL || 'http://pi-02:3004';
const HOME = process.env.HOME || '/home/sfloess';
const NFS_ROOT = process.env.NFS_ROOT || path.join(HOME, 'Development');
const ACTIVITY_DIR = path.join(HOME, '.claude', 'learning', 'fleet-activity');
const SSH_OPTS = '-o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5';

// ---------------------------------------------------------------------------
// SSH helper (synchronous, matches fleet patterns)
// ---------------------------------------------------------------------------
function sshExec(hostname, command, timeoutMs = 15000) {
  // Validate hostname to prevent injection
  if (!/^[a-zA-Z0-9._-]+$/.test(hostname)) {
    return { hostname, success: false, stdout: '', error: `Invalid hostname: ${hostname}` };
  }

  const escaped = command.replace(/'/g, "'\\''");
  const sshCmd = `ssh ${SSH_OPTS} -- '${hostname}' '${escaped}'`;

  try {
    const stdout = execSync(sshCmd, {
      encoding: 'utf8',
      timeout: timeoutMs,
      stdio: 'pipe',
    });
    return { hostname, success: true, stdout: stdout.trim(), error: null };
  } catch (error) {
    return {
      hostname,
      success: false,
      stdout: error.stdout?.toString().trim() || '',
      error: error.stderr?.toString().trim() || error.message,
    };
  }
}

// ---------------------------------------------------------------------------
// FleetActivityCollector
// ---------------------------------------------------------------------------
export class FleetActivityCollector {
  /**
   * @param {Object} config
   * @param {string[]} config.nodes - Hostnames to monitor (default: all fleet nodes)
   * @param {string} config.dispatcherUrl - Fleet dispatcher URL
   * @param {string} config.activityDir - Directory for snapshot storage
   * @param {number} config.maxSnapshots - Max snapshots to retain (default: 1440 = 24h at 1/min)
   * @param {number} config.sshTimeoutMs - SSH command timeout (default: 15000)
   */
  constructor(config = {}) {
    this.nodes = config.nodes || FLEET_NODES;
    this.dispatcherUrl = config.dispatcherUrl || FLEET_DISPATCHER;
    this.activityDir = config.activityDir || ACTIVITY_DIR;
    this.maxSnapshots = config.maxSnapshots || 1440;
    this.sshTimeoutMs = config.sshTimeoutMs || 15000;

    // In-memory state
    this._history = [];          // Recent snapshots (ring buffer)
    this._modelAssignments = {}; // model -> server tracking
    this._workflowNodes = {};    // workflowId -> {node, model, startTime, ...}
    this._lastSnapshot = null;

    // Ensure activity directory exists
    try {
      fs.mkdirSync(this.activityDir, { recursive: true });
    } catch (e) {
      // Non-fatal: snapshots will stay in memory only
    }
  }

  /**
   * Collect a full activity snapshot across the fleet.
   * Gathers process lists, resource usage, SSH sessions,
   * workflow transcripts, and model assignments.
   *
   * @returns {Object} Activity snapshot
   */
  async collect() {
    const startTime = Date.now();
    const timestamp = new Date().toISOString();

    // Run independent collectors in parallel
    const [
      nodeActivity,
      dispatcherStatus,
      workflowTranscripts,
      nfsActivity,
    ] = await Promise.all([
      this._collectNodeActivity(),
      this._collectDispatcherStatus(),
      this._collectWorkflowTranscripts(),
      this._collectNfsActivity(),
    ]);

    // Merge model assignments from dispatcher and node processes
    const modelAssignments = this._mergeModelAssignments(
      nodeActivity,
      dispatcherStatus
    );

    // Build workflow-to-node mapping
    const workflowNodeMap = this._buildWorkflowNodeMap(
      nodeActivity,
      dispatcherStatus,
      workflowTranscripts
    );

    const snapshot = {
      timestamp,
      collectionDurationMs: Date.now() - startTime,
      nodes: nodeActivity,
      dispatcher: dispatcherStatus,
      workflows: workflowTranscripts,
      nfsActivity,
      modelAssignments,
      workflowNodeMap,
      summary: this._buildSummary(nodeActivity, dispatcherStatus, workflowNodeMap),
    };

    // Store snapshot
    this._lastSnapshot = snapshot;
    this._history.push(snapshot);
    if (this._history.length > this.maxSnapshots) {
      this._history.shift();
    }

    // Persist to disk (best-effort)
    this._persistSnapshot(snapshot);

    return snapshot;
  }

  // -------------------------------------------------------------------------
  // Node activity: processes, resources, SSH sessions
  // -------------------------------------------------------------------------
  async _collectNodeActivity() {
    const results = {};

    // Collect from all nodes in parallel using Promise.all
    const nodePromises = this.nodes.map(async (node) => {
      const activity = {
        hostname: node.hostname,
        role: node.role,
        assignedModels: node.models,
        reachable: false,
        processes: [],
        sshSessions: [],
        resources: null,
        claudeProcesses: [],
        error: null,
      };

      // Single SSH call with combined commands for efficiency
      const combinedCmd = [
        // 1. Resource usage (CPU, memory, load)
        'echo "===RESOURCES===";',
        'uptime;',
        'free -m | head -3;',
        'nproc;',
        // 2. Claude/agent processes
        'echo "===CLAUDE===";',
        'ps aux | grep -E "claude|node.*agent|node.*workflow|node.*consensus" | grep -v grep || true;',
        // 3. SSH sessions
        'echo "===SSH===";',
        'who 2>/dev/null || true;',
        // 4. Top CPU consumers
        'echo "===TOP===";',
        'ps aux --sort=-%cpu | head -6;',
      ].join(' ');

      const result = sshExec(node.hostname, combinedCmd, this.sshTimeoutMs);

      if (!result.success) {
        activity.error = result.error;
        return { hostname: node.hostname, activity };
      }

      activity.reachable = true;

      try {
        const sections = result.stdout.split(/===(\w+)===/);
        // sections: ['', 'RESOURCES', '...', 'CLAUDE', '...', 'SSH', '...', 'TOP', '...']

        const sectionMap = {};
        for (let i = 1; i < sections.length; i += 2) {
          sectionMap[sections[i]] = (sections[i + 1] || '').trim();
        }

        // Parse resources
        activity.resources = this._parseResources(sectionMap.RESOURCES || '');

        // Parse claude processes
        activity.claudeProcesses = this._parseClaudeProcesses(sectionMap.CLAUDE || '');

        // Parse SSH sessions
        activity.sshSessions = this._parseSshSessions(sectionMap.SSH || '');

        // Parse top processes
        activity.processes = this._parseTopProcesses(sectionMap.TOP || '');
      } catch (parseErr) {
        activity.error = `Parse error: ${parseErr.message}`;
      }

      return { hostname: node.hostname, activity };
    });

    const nodeResults = await Promise.all(nodePromises);
    for (const { hostname, activity } of nodeResults) {
      results[hostname] = activity;
    }

    return results;
  }

  /**
   * Parse resource info from uptime + free + nproc output
   */
  _parseResources(raw) {
    if (!raw) return null;

    const lines = raw.split('\n').filter(l => l.trim());
    const resources = {
      loadAvg: [0, 0, 0],
      memTotalMb: 0,
      memUsedMb: 0,
      memAvailMb: 0,
      cpuCores: 0,
      uptime: '',
    };

    for (const line of lines) {
      // uptime line: " 14:30:01 up 5 days, ... load average: 1.23, 0.89, 0.67"
      const loadMatch = line.match(/load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)/);
      if (loadMatch) {
        resources.loadAvg = [
          parseFloat(loadMatch[1]),
          parseFloat(loadMatch[2]),
          parseFloat(loadMatch[3]),
        ];
        const uptimeMatch = line.match(/up\s+(.+?),\s+\d+\s+user/);
        if (uptimeMatch) {
          resources.uptime = uptimeMatch[1].trim();
        }
      }

      // free -m "Mem:" line: "Mem:       31234    12456    8901    ..."
      const memMatch = line.match(/^Mem:\s+(\d+)\s+(\d+)\s+(\d+)\s+\d+\s+\d+\s+(\d+)/);
      if (memMatch) {
        resources.memTotalMb = parseInt(memMatch[1], 10);
        resources.memUsedMb = parseInt(memMatch[2], 10);
        resources.memAvailMb = parseInt(memMatch[4], 10);
      }

      // nproc output (just a number)
      if (/^\d+$/.test(line.trim())) {
        resources.cpuCores = parseInt(line.trim(), 10);
      }
    }

    return resources;
  }

  /**
   * Parse claude/agent/workflow processes from ps aux output
   */
  _parseClaudeProcesses(raw) {
    if (!raw) return [];

    return raw.split('\n')
      .filter(l => l.trim())
      .map(line => {
        const parts = line.trim().split(/\s+/);
        if (parts.length < 11) return null;

        return {
          user: parts[0],
          pid: parseInt(parts[1], 10),
          cpu: parseFloat(parts[2]),
          mem: parseFloat(parts[3]),
          vsz: parseInt(parts[4], 10),
          rss: parseInt(parts[5], 10),
          startTime: parts[8],
          elapsed: parts[9],
          command: parts.slice(10).join(' '),
        };
      })
      .filter(Boolean);
  }

  /**
   * Parse SSH sessions from 'who' output
   */
  _parseSshSessions(raw) {
    if (!raw) return [];

    return raw.split('\n')
      .filter(l => l.trim())
      .map(line => {
        // Format: "user pts/0  2026-06-13 14:30 (192.168.1.100)"
        const match = line.match(/^(\S+)\s+(\S+)\s+(.+?)(?:\s+\((.+?)\))?$/);
        if (!match) return null;

        return {
          user: match[1],
          terminal: match[2],
          loginTime: match[3].trim(),
          remoteHost: match[4] || 'local',
        };
      })
      .filter(Boolean);
  }

  /**
   * Parse top CPU-consuming processes from ps aux output
   */
  _parseTopProcesses(raw) {
    if (!raw) return [];

    return raw.split('\n')
      .filter(l => l.trim() && !l.startsWith('USER'))
      .slice(0, 5)
      .map(line => {
        const parts = line.trim().split(/\s+/);
        if (parts.length < 11) return null;

        return {
          user: parts[0],
          pid: parseInt(parts[1], 10),
          cpu: parseFloat(parts[2]),
          mem: parseFloat(parts[3]),
          command: parts.slice(10).join(' ').substring(0, 120),
        };
      })
      .filter(Boolean);
  }

  // -------------------------------------------------------------------------
  // Fleet dispatcher status
  // -------------------------------------------------------------------------
  async _collectDispatcherStatus() {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(`${this.dispatcherUrl}/fleet/status`, {
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        return { available: false, error: `HTTP ${response.status}` };
      }

      const data = await response.json();

      // Extract active jobs and model health
      return {
        available: true,
        servers: (data.servers || []).map(s => ({
          instance: s.instance,
          hostname: s.instance?.replace(':9100', '') || 'unknown',
          load1m: s.load_1m,
          cpuPct: s.cpu_usage_pct,
          availRamGb: s.avail_ram_gb,
          totalRamGb: s.total_ram_gb,
          isOverloaded: s.is_overloaded,
          pendingJobs: s.pending_jobs || 0,
          activeJobs: s.active_jobs || 0,
        })),
        modelHealth: data.model_health || {},
        activeJobs: data.active_jobs || [],
        totalPendingJobs: (data.servers || []).reduce(
          (sum, s) => sum + (s.pending_jobs || 0), 0
        ),
      };
    } catch (error) {
      return {
        available: false,
        error: error.name === 'AbortError'
          ? 'Dispatcher timeout (10s)'
          : error.message,
      };
    }
  }

  // -------------------------------------------------------------------------
  // Workflow transcripts
  // -------------------------------------------------------------------------
  async _collectWorkflowTranscripts() {
    const projectsBase = path.join(HOME, '.claude', 'projects');
    const transcripts = [];

    try {
      // Find recent workflow journal files (last 2 hours)
      const findCmd = `find '${projectsBase}' -name 'journal.jsonl' -mmin -120 -type f 2>/dev/null | head -20`;
      const result = execSync(findCmd, {
        encoding: 'utf8',
        timeout: 10000,
        stdio: 'pipe',
      }).trim();

      if (!result) return transcripts;

      const journalPaths = result.split('\n').filter(p => p.trim());

      for (const journalPath of journalPaths) {
        try {
          const transcript = this._parseWorkflowJournal(journalPath);
          if (transcript) {
            transcripts.push(transcript);
          }
        } catch (e) {
          // Skip unparseable journals
        }
      }
    } catch (e) {
      // find command failed or timed out
    }

    return transcripts;
  }

  /**
   * Parse a workflow journal.jsonl file for activity info
   */
  _parseWorkflowJournal(journalPath) {
    let content;
    try {
      content = fs.readFileSync(journalPath, 'utf8');
    } catch (e) {
      return null;
    }

    const lines = content.split('\n').filter(l => l.trim());
    if (lines.length === 0) return null;

    // Extract workflow ID from path
    // Pattern: .../<sessionId>/subagents/workflows/<workflowId>/journal.jsonl
    const pathParts = journalPath.split('/');
    const workflowIdx = pathParts.indexOf('workflows');
    const workflowId = workflowIdx >= 0 ? pathParts[workflowIdx + 1] : 'unknown';

    // Parse journal entries (JSONL)
    let workflowName = '';
    let currentPhase = '';
    let agentCount = 0;
    let isRunning = false;
    let startTime = null;
    let lastActivity = null;
    let models = new Set();
    let errors = [];

    // Only parse last 50 lines for efficiency
    const recentLines = lines.slice(-50);

    for (const line of recentLines) {
      try {
        const entry = JSON.parse(line);

        if (entry.type === 'workflow_start' || entry.type === 'started') {
          workflowName = entry.workflow || entry.name || '';
          startTime = entry.timestamp || entry.time;
          isRunning = true;
        }

        if (entry.type === 'phase' || entry.type === 'phase_start') {
          currentPhase = entry.phase || entry.title || '';
        }

        if (entry.type === 'agent_start' || entry.type === 'agent_spawn') {
          agentCount++;
          if (entry.model) models.add(entry.model);
          lastActivity = entry.timestamp || entry.time;
        }

        if (entry.type === 'agent_complete' || entry.type === 'agent_result') {
          lastActivity = entry.timestamp || entry.time;
        }

        if (entry.type === 'completed' || entry.type === 'workflow_complete') {
          isRunning = false;
        }

        if (entry.type === 'error') {
          errors.push(entry.message || entry.error || 'unknown error');
          if (errors.length > 5) errors.shift();
        }

        // Capture model from label/opts
        if (entry.model) models.add(entry.model);
        if (entry.opts?.model) models.add(entry.opts.model);
        if (entry.label && entry.label.includes('model:')) {
          const m = entry.label.match(/model:(\S+)/);
          if (m) models.add(m[1]);
        }
      } catch (e) {
        // Skip unparseable lines
      }
    }

    return {
      workflowId,
      workflowName,
      journalPath,
      currentPhase,
      agentCount,
      isRunning,
      startTime,
      lastActivity,
      modelsUsed: [...models],
      recentErrors: errors,
      journalLines: lines.length,
    };
  }

  // -------------------------------------------------------------------------
  // NFS activity (fleet-results directory)
  // -------------------------------------------------------------------------
  async _collectNfsActivity() {
    const resultsDir = path.join(NFS_ROOT, 'fleet-results');

    try {
      // Check for active prompt files (indicates in-flight jobs)
      const promptsDir = path.join(resultsDir, '.prompts');
      const resultsSubDir = path.join(resultsDir, '.results');

      let activePrompts = [];
      let recentResults = [];

      // Active prompts = jobs in flight
      try {
        const promptFiles = fs.readdirSync(promptsDir)
          .filter(f => f.endsWith('.txt'))
          .map(f => {
            const stat = fs.statSync(path.join(promptsDir, f));
            return {
              jobId: f.replace('.txt', ''),
              sizeBytes: stat.size,
              createdAt: stat.mtime.toISOString(),
              ageMinutes: Math.round((Date.now() - stat.mtime.getTime()) / 60000),
            };
          })
          .sort((a, b) => b.ageMinutes - a.ageMinutes);

        activePrompts = promptFiles;
      } catch (e) {
        // Prompts dir may not exist
      }

      // Recent results (last 30 minutes)
      try {
        const resultFiles = fs.readdirSync(resultsSubDir)
          .filter(f => f.endsWith('.json'))
          .map(f => {
            const stat = fs.statSync(path.join(resultsSubDir, f));
            const ageMinutes = Math.round((Date.now() - stat.mtime.getTime()) / 60000);
            if (ageMinutes > 30) return null;
            return {
              jobId: f.replace('.json', ''),
              sizeBytes: stat.size,
              completedAt: stat.mtime.toISOString(),
              ageMinutes,
            };
          })
          .filter(Boolean)
          .sort((a, b) => a.ageMinutes - b.ageMinutes);

        recentResults = resultFiles;
      } catch (e) {
        // Results dir may not exist
      }

      return {
        available: true,
        activePrompts,
        recentResults,
        inFlightCount: activePrompts.length,
        recentCompletionCount: recentResults.length,
      };
    } catch (e) {
      return { available: false, error: e.message };
    }
  }

  // -------------------------------------------------------------------------
  // Model-to-server assignment tracking
  // -------------------------------------------------------------------------
  _mergeModelAssignments(nodeActivity, dispatcherStatus) {
    const assignments = {};

    // Static assignments from fleet config
    for (const node of this.nodes) {
      for (const model of node.models) {
        assignments[model] = {
          configuredServer: node.hostname,
          activeOnServer: null,
          lastSeenAt: null,
        };
      }
    }

    // Dynamic assignments from running processes
    for (const [hostname, activity] of Object.entries(nodeActivity)) {
      if (!activity.reachable) continue;

      for (const proc of activity.claudeProcesses) {
        // Detect model from process command line
        const modelMatch = proc.command.match(
          /--model\s+(\S+)|model[=:]\s*["']?(\w+)/i
        );
        if (modelMatch) {
          const model = modelMatch[1] || modelMatch[2];
          if (assignments[model]) {
            assignments[model].activeOnServer = hostname;
            assignments[model].lastSeenAt = new Date().toISOString();
          } else {
            assignments[model] = {
              configuredServer: 'unknown',
              activeOnServer: hostname,
              lastSeenAt: new Date().toISOString(),
            };
          }
        }
      }
    }

    // Assignments from dispatcher active jobs
    if (dispatcherStatus.available && dispatcherStatus.activeJobs) {
      for (const job of dispatcherStatus.activeJobs) {
        const model = job.model;
        const server = job.server || job.instance?.replace(':9100', '');
        if (model && server) {
          if (!assignments[model]) {
            assignments[model] = { configuredServer: 'unknown' };
          }
          assignments[model].activeOnServer = server;
          assignments[model].lastSeenAt = new Date().toISOString();
          assignments[model].activeJobId = job.job_id;
        }
      }
    }

    // Update persistent tracking
    this._modelAssignments = assignments;

    return assignments;
  }

  // -------------------------------------------------------------------------
  // Workflow-to-node mapping
  // -------------------------------------------------------------------------
  _buildWorkflowNodeMap(nodeActivity, dispatcherStatus, workflowTranscripts) {
    const map = {};

    // From workflow transcripts + dispatcher
    for (const transcript of workflowTranscripts) {
      const entry = {
        workflowId: transcript.workflowId,
        workflowName: transcript.workflowName,
        isRunning: transcript.isRunning,
        phase: transcript.currentPhase,
        modelsUsed: transcript.modelsUsed,
        agentCount: transcript.agentCount,
        nodes: [],
        startTime: transcript.startTime,
        lastActivity: transcript.lastActivity,
      };

      // Map models to their servers
      for (const model of transcript.modelsUsed) {
        const nodeForModel = this.nodes.find(n => n.models.includes(model));
        if (nodeForModel && !entry.nodes.includes(nodeForModel.hostname)) {
          entry.nodes.push(nodeForModel.hostname);
        }
      }

      map[transcript.workflowId] = entry;
    }

    // From dispatcher active jobs (may reference workflows)
    if (dispatcherStatus.available && dispatcherStatus.activeJobs) {
      for (const job of dispatcherStatus.activeJobs) {
        const wfId = job.workflow_id || job.label?.match(/wf_[\w-]+/)?.[0];
        if (wfId && map[wfId]) {
          const server = job.server || job.instance?.replace(':9100', '');
          if (server && !map[wfId].nodes.includes(server)) {
            map[wfId].nodes.push(server);
          }
        }
      }
    }

    // From node processes (detect workflow IDs in command lines)
    for (const [hostname, activity] of Object.entries(nodeActivity)) {
      if (!activity.reachable) continue;

      for (const proc of activity.claudeProcesses) {
        const wfMatch = proc.command.match(/wf_[\w-]+/);
        if (wfMatch) {
          const wfId = wfMatch[0];
          if (!map[wfId]) {
            map[wfId] = {
              workflowId: wfId,
              workflowName: 'unknown (detected from process)',
              isRunning: true,
              phase: 'unknown',
              modelsUsed: [],
              agentCount: 0,
              nodes: [],
            };
          }
          if (!map[wfId].nodes.includes(hostname)) {
            map[wfId].nodes.push(hostname);
          }
        }
      }
    }

    // Persist for history
    for (const [wfId, entry] of Object.entries(map)) {
      this._workflowNodes[wfId] = {
        ...this._workflowNodes[wfId],
        ...entry,
        lastSeen: new Date().toISOString(),
      };
    }

    return map;
  }

  // -------------------------------------------------------------------------
  // Summary builder
  // -------------------------------------------------------------------------
  _buildSummary(nodeActivity, dispatcherStatus, workflowNodeMap) {
    const reachableNodes = Object.values(nodeActivity)
      .filter(a => a.reachable).length;
    const totalNodes = Object.keys(nodeActivity).length;

    const totalClaudeProcesses = Object.values(nodeActivity)
      .reduce((sum, a) => sum + (a.claudeProcesses?.length || 0), 0);

    const totalSshSessions = Object.values(nodeActivity)
      .reduce((sum, a) => sum + (a.sshSessions?.length || 0), 0);

    const activeWorkflows = Object.values(workflowNodeMap)
      .filter(w => w.isRunning).length;

    const totalWorkflows = Object.keys(workflowNodeMap).length;

    const nodeLoads = {};
    for (const [hostname, activity] of Object.entries(nodeActivity)) {
      if (activity.reachable && activity.resources) {
        nodeLoads[hostname] = {
          load1m: activity.resources.loadAvg[0],
          memUsedPct: activity.resources.memTotalMb > 0
            ? Math.round((activity.resources.memUsedMb / activity.resources.memTotalMb) * 100)
            : 0,
          claudeProcesses: activity.claudeProcesses?.length || 0,
          sshSessions: activity.sshSessions?.length || 0,
        };
      }
    }

    // Find busiest node
    let busiestNode = null;
    let busiestLoad = 0;
    for (const [hostname, load] of Object.entries(nodeLoads)) {
      if (load.load1m > busiestLoad) {
        busiestLoad = load.load1m;
        busiestNode = hostname;
      }
    }

    // Active models (models with running processes)
    const activeModels = new Set();
    for (const activity of Object.values(nodeActivity)) {
      for (const proc of (activity.claudeProcesses || [])) {
        const modelMatch = proc.command.match(
          /--model\s+(\S+)|model[=:]\s*["']?(\w+)/i
        );
        if (modelMatch) {
          activeModels.add(modelMatch[1] || modelMatch[2]);
        }
      }
    }

    return {
      nodesReachable: reachableNodes,
      nodesTotal: totalNodes,
      dispatcherAvailable: dispatcherStatus.available,
      totalClaudeProcesses,
      totalSshSessions,
      activeWorkflows,
      totalWorkflows,
      activeModels: [...activeModels],
      busiestNode,
      busiestLoad,
      nodeLoads,
      pendingJobs: dispatcherStatus.totalPendingJobs || 0,
    };
  }

  // -------------------------------------------------------------------------
  // Persistence
  // -------------------------------------------------------------------------
  _persistSnapshot(snapshot) {
    try {
      const filename = `snapshot-${snapshot.timestamp.replace(/[:.]/g, '-')}.json`;
      const filePath = path.join(this.activityDir, filename);
      fs.writeFileSync(filePath, JSON.stringify(snapshot, null, 2));

      // Also write latest.json for quick access
      const latestPath = path.join(this.activityDir, 'latest.json');
      fs.writeFileSync(latestPath, JSON.stringify(snapshot, null, 2));

      // Prune old snapshots
      this._pruneSnapshots();
    } catch (e) {
      // Non-fatal
    }
  }

  _pruneSnapshots() {
    try {
      const files = fs.readdirSync(this.activityDir)
        .filter(f => f.startsWith('snapshot-') && f.endsWith('.json'))
        .sort()
        .reverse();

      // Keep only maxSnapshots files
      for (const file of files.slice(this.maxSnapshots)) {
        fs.unlinkSync(path.join(this.activityDir, file));
      }
    } catch (e) {
      // Non-fatal
    }
  }

  // -------------------------------------------------------------------------
  // Prometheus metrics generation
  // -------------------------------------------------------------------------
  generatePrometheusMetrics() {
    const snapshot = this._lastSnapshot;
    if (!snapshot) return '# No data collected yet\n';

    let metrics = '';

    const addMetric = (name, help, type, value, labels = '') => {
      metrics += `# HELP ${name} ${help}\n`;
      metrics += `# TYPE ${name} ${type}\n`;
      metrics += `${name}${labels} ${value}\n\n`;
    };

    const addGauge = (name, help, value, labels = '') =>
      addMetric(name, help, 'gauge', value, labels);

    // Fleet-level metrics
    addGauge('fleet_activity_nodes_reachable',
      'Number of fleet nodes reachable via SSH',
      snapshot.summary.nodesReachable);

    addGauge('fleet_activity_nodes_total',
      'Total number of fleet nodes',
      snapshot.summary.nodesTotal);

    addGauge('fleet_activity_dispatcher_up',
      'Whether the fleet dispatcher is available',
      snapshot.summary.dispatcherAvailable ? 1 : 0);

    addGauge('fleet_activity_claude_processes_total',
      'Total claude/agent processes across all nodes',
      snapshot.summary.totalClaudeProcesses);

    addGauge('fleet_activity_ssh_sessions_total',
      'Total SSH sessions across all nodes',
      snapshot.summary.totalSshSessions);

    addGauge('fleet_activity_active_workflows',
      'Number of currently running workflows',
      snapshot.summary.activeWorkflows);

    addGauge('fleet_activity_pending_jobs',
      'Number of pending jobs in dispatcher queue',
      snapshot.summary.pendingJobs);

    addGauge('fleet_activity_active_models_count',
      'Number of AI models currently running',
      snapshot.summary.activeModels.length);

    addGauge('fleet_activity_collection_duration_ms',
      'Time taken to collect activity snapshot',
      snapshot.collectionDurationMs);

    // Per-node metrics
    for (const [hostname, load] of Object.entries(snapshot.summary.nodeLoads || {})) {
      const labels = `{node="${hostname}"}`;
      metrics += `fleet_activity_node_load_1m${labels} ${load.load1m}\n`;
      metrics += `fleet_activity_node_mem_used_pct${labels} ${load.memUsedPct}\n`;
      metrics += `fleet_activity_node_claude_processes${labels} ${load.claudeProcesses}\n`;
      metrics += `fleet_activity_node_ssh_sessions${labels} ${load.sshSessions}\n`;
    }

    if (Object.keys(snapshot.summary.nodeLoads || {}).length > 0) {
      metrics = metrics.replace(
        /fleet_activity_node_load_1m/,
        '# HELP fleet_activity_node_load_1m 1-minute load average per node\n' +
        '# TYPE fleet_activity_node_load_1m gauge\n' +
        'fleet_activity_node_load_1m'
      );
    }

    // Per-model metrics
    for (const [model, assignment] of Object.entries(snapshot.modelAssignments || {})) {
      const active = assignment.activeOnServer ? 1 : 0;
      const server = assignment.activeOnServer || assignment.configuredServer || 'none';
      metrics += `fleet_activity_model_active{model="${model}",server="${server}"} ${active}\n`;
    }

    // NFS in-flight
    if (snapshot.nfsActivity?.available) {
      addGauge('fleet_activity_nfs_inflight_jobs',
        'Number of in-flight jobs (prompt files on NFS)',
        snapshot.nfsActivity.inFlightCount);
      addGauge('fleet_activity_nfs_recent_completions',
        'Number of recently completed jobs (last 30 min)',
        snapshot.nfsActivity.recentCompletionCount);
    }

    return metrics;
  }

  // -------------------------------------------------------------------------
  // Convenience: get latest snapshot
  // -------------------------------------------------------------------------
  getLatestSnapshot() {
    return this._lastSnapshot;
  }

  /**
   * Get history of snapshots
   * @param {number} count - Number of recent snapshots to return
   */
  getHistory(count = 10) {
    return this._history.slice(-count);
  }

  /**
   * Get model assignment history
   */
  getModelAssignments() {
    return { ...this._modelAssignments };
  }

  /**
   * Get workflow-to-node mapping (persists across snapshots)
   */
  getWorkflowNodeHistory() {
    return { ...this._workflowNodes };
  }
}

// ---------------------------------------------------------------------------
// HTTP server for continuous collection
// ---------------------------------------------------------------------------
async function startServer(port = 9091, intervalSec = 60) {
  const collector = new FleetActivityCollector();

  // Initial collection
  console.log('[fleet-activity-collector] Running initial collection...');
  await collector.collect();
  console.log('[fleet-activity-collector] Initial collection complete');

  // Set up periodic collection
  const intervalId = setInterval(async () => {
    try {
      const snapshot = await collector.collect();
      const s = snapshot.summary;
      console.log(
        `[${new Date().toISOString()}] ` +
        `nodes=${s.nodesReachable}/${s.nodesTotal} ` +
        `claude_procs=${s.totalClaudeProcesses} ` +
        `workflows=${s.activeWorkflows}/${s.totalWorkflows} ` +
        `models=${s.activeModels.join(',')||'none'} ` +
        `busiest=${s.busiestNode||'none'}(${s.busiestLoad.toFixed(1)}) ` +
        `collected_in=${snapshot.collectionDurationMs}ms`
      );
    } catch (e) {
      console.error(`[fleet-activity-collector] Collection error: ${e.message}`);
    }
  }, intervalSec * 1000);

  // HTTP server
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${port}`);

    if (url.pathname === '/metrics') {
      // Prometheus metrics
      const metrics = collector.generatePrometheusMetrics();
      res.writeHead(200, { 'Content-Type': 'text/plain; version=0.0.4' });
      res.end(metrics);
      return;
    }

    if (url.pathname === '/status') {
      // Latest snapshot summary
      const snapshot = collector.getLatestSnapshot();
      if (!snapshot) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'No data collected yet' }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(snapshot.summary, null, 2));
      return;
    }

    if (url.pathname === '/snapshot') {
      // Full latest snapshot
      const snapshot = collector.getLatestSnapshot();
      if (!snapshot) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'No data collected yet' }));
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(snapshot, null, 2));
      return;
    }

    if (url.pathname === '/models') {
      // Model-to-server assignments
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(collector.getModelAssignments(), null, 2));
      return;
    }

    if (url.pathname === '/workflows') {
      // Workflow-to-node map
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(collector.getWorkflowNodeHistory(), null, 2));
      return;
    }

    if (url.pathname === '/history') {
      // Recent snapshots
      const count = parseInt(url.searchParams.get('count') || '10', 10);
      const history = collector.getHistory(count).map(s => ({
        timestamp: s.timestamp,
        summary: s.summary,
      }));
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(history, null, 2));
      return;
    }

    if (url.pathname === '/collect') {
      // Trigger immediate collection
      try {
        const snapshot = await collector.collect();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(snapshot.summary, null, 2));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
      return;
    }

    if (url.pathname === '/health') {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end('OK');
      return;
    }

    // Default: list endpoints
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end([
      'Fleet Activity Collector',
      '',
      'Endpoints:',
      '  /status     - Latest summary (JSON)',
      '  /snapshot   - Full latest snapshot (JSON)',
      '  /models     - Model-to-server assignments (JSON)',
      '  /workflows  - Workflow-to-node mapping (JSON)',
      '  /history    - Recent snapshot summaries (JSON, ?count=N)',
      '  /collect    - Trigger immediate collection (JSON)',
      '  /metrics    - Prometheus-compatible metrics',
      '  /health     - Health check',
      '',
      `Collection interval: ${intervalSec}s`,
      `Snapshots retained: ${collector.maxSnapshots}`,
      `Storage: ${collector.activityDir}`,
    ].join('\n'));
  });

  server.listen(port, () => {
    console.log(`[fleet-activity-collector] HTTP server on http://localhost:${port}`);
    console.log(`[fleet-activity-collector] Metrics at http://localhost:${port}/metrics`);
    console.log(`[fleet-activity-collector] Status at http://localhost:${port}/status`);
    console.log(`[fleet-activity-collector] Collection interval: ${intervalSec}s`);
  });

  // Graceful shutdown
  const shutdown = () => {
    console.log('[fleet-activity-collector] Shutting down...');
    clearInterval(intervalId);
    server.close(() => {
      console.log('[fleet-activity-collector] Server closed');
      process.exit(0);
    });
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  return { server, collector, intervalId };
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------
const isMainModule = process.argv[1] &&
  (process.argv[1].endsWith('fleet-activity-collector.js') ||
   process.argv[1].includes('fleet-activity-collector'));

if (isMainModule) {
  const args = process.argv.slice(2);

  // Parse --port and --interval flags
  let port = 9091;
  let interval = 60;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--port' && args[i + 1]) {
      port = parseInt(args[i + 1], 10);
      i++;
    } else if (args[i] === '--interval' && args[i + 1]) {
      interval = parseInt(args[i + 1], 10);
      i++;
    } else if (args[i] === '--once') {
      // Single collection mode (no server)
      const collector = new FleetActivityCollector();
      const snapshot = await collector.collect();
      console.log(JSON.stringify(snapshot, null, 2));
      process.exit(0);
    }
  }

  startServer(port, interval).catch(err => {
    console.error('[fleet-activity-collector] Failed to start:', err.message);
    process.exit(1);
  });
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------
export { startServer };

export default {
  FleetActivityCollector,
  startServer,
  FLEET_NODES,
};
