#!/usr/bin/env node
// Session Orchestrator - Central coordinator for multi-session work distribution
// Runs as daemon, manages work queue, detects conflicts, coordinates sessions

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

const SessionRegistry = require('./session-registry');
const SessionMessenger = require('./session-messenger');

const ORCHESTRATOR_DIR = path.join(os.homedir(), '.claude', 'orchestrator');
const WORK_QUEUE_FILE = path.join(ORCHESTRATOR_DIR, 'work-queue.json');
const STATE_FILE = path.join(ORCHESTRATOR_DIR, 'state.json');
const PID_FILE = path.join(ORCHESTRATOR_DIR, 'orchestrator.pid');
const LOG_FILE = path.join(ORCHESTRATOR_DIR, 'orchestrator.log');

class SessionOrchestrator {
  constructor() {
    this.registry = new SessionRegistry();
    this.messenger = new SessionMessenger('orchestrator');
    this.workQueue = [];
    this.state = {
      started: new Date().toISOString(),
      assignments: {},
      completions: [],
      conflicts: []
    };

    this.ensureDirectories();
    this.loadState();
  }

  ensureDirectories() {
    if (!fs.existsSync(ORCHESTRATOR_DIR)) {
      fs.mkdirSync(ORCHESTRATOR_DIR, { recursive: true });
    }
  }

  loadState() {
    try {
      if (fs.existsSync(STATE_FILE)) {
        this.state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
      }
      if (fs.existsSync(WORK_QUEUE_FILE)) {
        this.workQueue = JSON.parse(fs.readFileSync(WORK_QUEUE_FILE, 'utf8'));
      }
    } catch (err) {
      this.log(`Failed to load state: ${err.message}`);
    }
  }

  saveState() {
    try {
      fs.writeFileSync(STATE_FILE, JSON.stringify(this.state, null, 2), 'utf8');
      fs.writeFileSync(WORK_QUEUE_FILE, JSON.stringify(this.workQueue, null, 2), 'utf8');
    } catch (err) {
      this.log(`Failed to save state: ${err.message}`);
    }
  }

  log(message) {
    const timestamp = new Date().toISOString();
    const logLine = `[${timestamp}] ${message}\n`;

    console.log(logLine.trim());

    try {
      fs.appendFileSync(LOG_FILE, logLine, 'utf8');
    } catch (err) {
      // Ignore log errors
    }
  }

  // Add work to the queue
  enqueueWork(work) {
    const workId = `work-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const workItem = {
      id: workId,
      description: work.description,
      files: work.files || [],
      priority: work.priority || 'normal',
      requires: work.requires || [],
      estimatedCost: work.estimatedCost || 'unknown',
      status: 'queued',
      assignedTo: null,
      enqueuedAt: new Date().toISOString(),
      ...work
    };

    this.workQueue.push(workItem);
    this.saveState();
    this.log(`Enqueued work: ${workItem.id} - ${workItem.description}`);

    return workItem;
  }

  // Assign work to a session
  assignWork(workId, sessionId) {
    const work = this.workQueue.find(w => w.id === workId);

    if (!work) {
      this.log(`Work ${workId} not found`);
      return null;
    }

    if (work.status !== 'queued') {
      this.log(`Work ${workId} already ${work.status}`);
      return null;
    }

    // Check for conflicts
    const conflicts = this.registry.findConflicts(work.files);
    if (conflicts.length > 0) {
      this.log(`Conflicts detected for ${workId}: ${JSON.stringify(conflicts)}`);
      this.state.conflicts.push({
        workId,
        sessionId,
        conflicts,
        timestamp: new Date().toISOString()
      });
      return null;
    }

    work.status = 'assigned';
    work.assignedTo = sessionId;
    work.assignedAt = new Date().toISOString();

    this.state.assignments[workId] = sessionId;
    this.saveState();

    // Send message to session
    this.messenger.send(sessionId, {
      type: 'work_assignment',
      priority: 'high',
      payload: work
    });

    this.log(`Assigned work ${workId} to session ${sessionId}`);
    return work;
  }

  // Auto-assign work to available sessions
  autoAssign() {
    const sessions = this.registry.getActiveSessions();
    const availableWork = this.workQueue.filter(w => w.status === 'queued');

    if (availableWork.length === 0) {
      return 0;
    }

    let assigned = 0;

    for (const work of availableWork) {
      // Find least busy session
      const sessionLoads = Object.entries(sessions).map(([id, info]) => {
        const assignedWork = this.workQueue.filter(w => w.assignedTo === id && w.status === 'assigned');
        return { id, load: assignedWork.length };
      });

      sessionLoads.sort((a, b) => a.load - b.load);

      if (sessionLoads.length > 0) {
        const result = this.assignWork(work.id, sessionLoads[0].id);
        if (result) assigned++;
      }
    }

    return assigned;
  }

  // Mark work as complete
  completeWork(workId, result = {}) {
    const work = this.workQueue.find(w => w.id === workId);

    if (!work) {
      this.log(`Work ${workId} not found`);
      return false;
    }

    work.status = 'completed';
    work.completedAt = new Date().toISOString();
    work.result = result;

    this.state.completions.push({
      workId,
      sessionId: work.assignedTo,
      completedAt: work.completedAt,
      result
    });

    this.saveState();
    this.log(`Work ${workId} completed by ${work.assignedTo}`);

    return true;
  }

  // Process incoming messages
  processMessages() {
    const messages = this.messenger.receive();

    for (const msg of messages) {
      this.log(`Processing message ${msg.id} from ${msg.from}`);

      switch (msg.type) {
        case 'work_request':
          this.handleWorkRequest(msg);
          break;

        case 'work_complete':
          this.handleWorkComplete(msg);
          break;

        case 'conflict_report':
          this.handleConflictReport(msg);
          break;

        case 'status_query':
          this.handleStatusQuery(msg);
          break;

        default:
          this.log(`Unknown message type: ${msg.type}`);
      }

      this.messenger.markRead(msg.id);
    }
  }

  handleWorkRequest(msg) {
    const sessionId = msg.from;
    const availableWork = this.workQueue.filter(w => w.status === 'queued');

    if (availableWork.length > 0) {
      this.assignWork(availableWork[0].id, sessionId);
    } else {
      this.messenger.send(sessionId, {
        type: 'no_work_available',
        payload: { message: 'No work in queue' }
      });
    }
  }

  handleWorkComplete(msg) {
    const { workId, result } = msg.payload;
    this.completeWork(workId, result);
  }

  handleConflictReport(msg) {
    this.log(`Conflict reported: ${JSON.stringify(msg.payload)}`);
    this.state.conflicts.push({
      ...msg.payload,
      reportedBy: msg.from,
      timestamp: new Date().toISOString()
    });
    this.saveState();
  }

  handleStatusQuery(msg) {
    const status = {
      workQueue: this.workQueue.length,
      queued: this.workQueue.filter(w => w.status === 'queued').length,
      assigned: this.workQueue.filter(w => w.status === 'assigned').length,
      completed: this.state.completions.length,
      activeSessions: Object.keys(this.registry.getActiveSessions()).length,
      conflicts: this.state.conflicts.length
    };

    this.messenger.send(msg.from, {
      type: 'status_response',
      payload: status
    });
  }

  // Main orchestration loop
  async run() {
    this.log('Session orchestrator starting...');

    // Write PID file
    fs.writeFileSync(PID_FILE, process.pid.toString(), 'utf8');

    const intervalMs = 5000; // 5 seconds

    const tick = () => {
      try {
        // Process messages
        this.processMessages();

        // Auto-assign work
        this.autoAssign();

        // Cleanup stale sessions
        this.registry.getActiveSessions();

        // Cleanup expired messages
        this.messenger.cleanup();

      } catch (err) {
        this.log(`Error in orchestration loop: ${err.message}`);
      }
    };

    // Initial tick
    tick();

    // Schedule recurring ticks
    this.interval = setInterval(tick, intervalMs);

    this.log('Orchestrator running (Ctrl+C to stop)');

    // Graceful shutdown
    process.on('SIGINT', () => this.stop());
    process.on('SIGTERM', () => this.stop());
  }

  stop() {
    this.log('Orchestrator stopping...');

    if (this.interval) {
      clearInterval(this.interval);
    }

    this.saveState();

    if (fs.existsSync(PID_FILE)) {
      fs.unlinkSync(PID_FILE);
    }

    this.log('Orchestrator stopped');
    process.exit(0);
  }

  // Get status
  getStatus() {
    return {
      running: fs.existsSync(PID_FILE),
      workQueue: this.workQueue,
      state: this.state,
      activeSessions: this.registry.getActiveSessions()
    };
  }
}

// CLI interface
if (require.main === module) {
  const command = process.argv[2];
  const orchestrator = new SessionOrchestrator();

  switch (command) {
    case 'start':
      if (fs.existsSync(PID_FILE)) {
        const pid = fs.readFileSync(PID_FILE, 'utf8').trim();
        console.error(`Orchestrator already running (PID ${pid})`);
        process.exit(1);
      }
      orchestrator.run();
      break;

    case 'stop':
      if (!fs.existsSync(PID_FILE)) {
        console.error('Orchestrator not running');
        process.exit(1);
      }
      const pid = fs.readFileSync(PID_FILE, 'utf8').trim();
      process.kill(parseInt(pid), 'SIGTERM');
      console.log(`Stopped orchestrator (PID ${pid})`);
      break;

    case 'status':
      const status = orchestrator.getStatus();
      console.log(JSON.stringify(status, null, 2));
      break;

    case 'enqueue':
      const description = process.argv[3];
      if (!description) {
        console.error('Usage: session-orchestrator.js enqueue <description>');
        process.exit(1);
      }
      orchestrator.enqueueWork({ description });
      break;

    case 'logs':
      if (fs.existsSync(LOG_FILE)) {
        console.log(fs.readFileSync(LOG_FILE, 'utf8'));
      } else {
        console.log('No logs found');
      }
      break;

    default:
      console.log('Usage: session-orchestrator.js <command>');
      console.log('Commands:');
      console.log('  start - Start orchestrator daemon');
      console.log('  stop - Stop orchestrator daemon');
      console.log('  status - Show orchestrator status');
      console.log('  enqueue <description> - Add work to queue');
      console.log('  logs - Show orchestrator logs');
  }
}

module.exports = SessionOrchestrator;
