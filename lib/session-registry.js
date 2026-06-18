#!/usr/bin/env node
// Session Registry - Cross-session visibility and coordination
// Manages ~/.claude/sessions/registry.json for tracking active sessions

const fs = require('fs');
const path = require('path');
const os = require('os');

const REGISTRY_DIR = path.join(os.homedir(), '.claude', 'sessions');
const REGISTRY_FILE = path.join(REGISTRY_DIR, 'registry.json');
const HEARTBEAT_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

class SessionRegistry {
  constructor() {
    this.ensureRegistryExists();
  }

  ensureRegistryExists() {
    if (!fs.existsSync(REGISTRY_DIR)) {
      fs.mkdirSync(REGISTRY_DIR, { recursive: true });
    }
    if (!fs.existsSync(REGISTRY_FILE)) {
      this.writeRegistry({});
    }
  }

  readRegistry() {
    try {
      const data = fs.readFileSync(REGISTRY_FILE, 'utf8');
      return JSON.parse(data);
    } catch (err) {
      console.error(`Failed to read registry: ${err.message}`);
      return {};
    }
  }

  writeRegistry(registry) {
    const tempFile = `${REGISTRY_FILE}.tmp`;
    try {
      fs.writeFileSync(tempFile, JSON.stringify(registry, null, 2), 'utf8');
      fs.renameSync(tempFile, REGISTRY_FILE);
    } catch (err) {
      console.error(`Failed to write registry: ${err.message}`);
      if (fs.existsSync(tempFile)) {
        fs.unlinkSync(tempFile);
      }
    }
  }

  // Register current session
  register(sessionId, metadata = {}) {
    const registry = this.readRegistry();
    const sessionInfo = this.getSessionInfo();

    registry[sessionId] = {
      pid: process.pid,
      sessionId,
      cwd: process.cwd(),
      started: registry[sessionId]?.started || new Date().toISOString(),
      last_heartbeat: new Date().toISOString(),
      working_on: metadata.working_on || null,
      files_locked: metadata.files_locked || [],
      current_task: metadata.current_task || null,
      status: metadata.status || 'active',
      hostname: os.hostname(),
      user: os.userInfo().username,
      version: sessionInfo.version || 'unknown',
      ...metadata
    };

    this.writeRegistry(registry);
    return registry[sessionId];
  }

  // Update session heartbeat and metadata
  heartbeat(sessionId, metadata = {}) {
    const registry = this.readRegistry();

    if (!registry[sessionId]) {
      return this.register(sessionId, metadata);
    }

    registry[sessionId] = {
      ...registry[sessionId],
      last_heartbeat: new Date().toISOString(),
      ...metadata
    };

    this.writeRegistry(registry);
    return registry[sessionId];
  }

  // Unregister session (on clean exit)
  unregister(sessionId) {
    const registry = this.readRegistry();
    delete registry[sessionId];
    this.writeRegistry(registry);
  }

  // Get all active sessions (heartbeat within timeout)
  getActiveSessions() {
    const registry = this.readRegistry();
    const now = Date.now();
    const active = {};

    // Get all actual session PIDs from session files
    const sessionPids = new Set();
    try {
      const fs = require('fs');
      const path = require('path');
      const files = fs.readdirSync(SESSIONS_DIR)
        .filter(f => f.endsWith('.json') && f !== 'registry.json');

      for (const file of files) {
        try {
          const data = JSON.parse(fs.readFileSync(path.join(SESSIONS_DIR, file), 'utf8'));
          if (data.pid) sessionPids.add(data.pid);
        } catch (err) {
          // Ignore parse errors
        }
      }
    } catch (err) {
      // If we can't read session files, fall back to heartbeat-only checking
    }

    for (const [sessionId, info] of Object.entries(registry)) {
      const lastHeartbeat = new Date(info.last_heartbeat).getTime();
      const age = now - lastHeartbeat;

      // Check if session file exists OR heartbeat is recent
      const isAlive = sessionPids.has(info.pid) || age < 60000; // 60s grace period

      if (age < HEARTBEAT_TIMEOUT_MS && isAlive) {
        active[sessionId] = {
          ...info,
          age_ms: age,
          age_human: this.formatDuration(age)
        };
      } else if (!isAlive && age > HEARTBEAT_TIMEOUT_MS) {
        // Stale session - remove it
        console.warn(`Removing stale session ${sessionId} (pid ${info.pid})`);
        delete registry[sessionId];
      }
    }

    this.writeRegistry(registry);
    return active;
  }

  // Check if process is alive
  isProcessAlive(pid) {
    try {
      // Check if process exists
      const { execSync } = require('child_process');
      execSync(`ps -p ${pid}`, { stdio: 'ignore' });
      return true;
    } catch (err) {
      return false;
    }
  }

  // Get current session info from session file
  getSessionInfo() {
    try {
      const sessionFiles = fs.readdirSync(REGISTRY_DIR)
        .filter(f => f.endsWith('.json') && f !== 'registry.json')
        .map(f => path.join(REGISTRY_DIR, f));

      for (const file of sessionFiles) {
        const data = JSON.parse(fs.readFileSync(file, 'utf8'));
        if (data.pid === process.pid) {
          return data;
        }
      }
    } catch (err) {
      // Ignore errors, return empty
    }
    return {};
  }

  // Find sessions working on similar files
  findConflicts(files) {
    const active = this.getActiveSessions();
    const conflicts = [];

    for (const [sessionId, info] of Object.entries(active)) {
      if (sessionId === this.getCurrentSessionId()) continue;

      const locked = info.files_locked || [];
      const overlapping = files.filter(f =>
        locked.some(l => f.includes(l) || l.includes(f))
      );

      if (overlapping.length > 0) {
        conflicts.push({
          sessionId,
          pid: info.pid,
          working_on: info.working_on,
          conflicting_files: overlapping,
          cwd: info.cwd
        });
      }
    }

    return conflicts;
  }

  getCurrentSessionId() {
    const info = this.getSessionInfo();
    return info.sessionId || `pid-${process.pid}`;
  }

  formatDuration(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  }

  // Pretty print all active sessions
  listSessions() {
    const active = this.getActiveSessions();
    const sessions = Object.entries(active);

    if (sessions.length === 0) {
      console.log('No active sessions');
      return;
    }

    console.log(`\n${sessions.length} active session(s):\n`);

    for (const [sessionId, info] of sessions) {
      const isCurrent = sessionId === this.getCurrentSessionId();
      const marker = isCurrent ? '→' : ' ';

      console.log(`${marker} Session: ${sessionId.slice(0, 8)}...`);
      console.log(`  PID: ${info.pid} | Age: ${info.age_human} | Host: ${info.hostname}`);
      console.log(`  CWD: ${info.cwd}`);

      if (info.working_on) {
        console.log(`  Working on: ${info.working_on}`);
      }

      if (info.files_locked && info.files_locked.length > 0) {
        console.log(`  Files locked: ${info.files_locked.join(', ')}`);
      }

      console.log('');
    }
  }
}

// CLI interface
if (require.main === module) {
  const registry = new SessionRegistry();
  const command = process.argv[2];

  switch (command) {
    case 'list':
      registry.listSessions();
      break;

    case 'register':
      const sessionId = process.argv[3] || registry.getCurrentSessionId();
      const working_on = process.argv[4] || null;
      registry.register(sessionId, { working_on });
      console.log(`Registered session ${sessionId}`);
      break;

    case 'heartbeat':
      const sid = process.argv[3] || registry.getCurrentSessionId();
      registry.heartbeat(sid);
      console.log(`Updated heartbeat for ${sid}`);
      break;

    case 'unregister':
      const id = process.argv[3] || registry.getCurrentSessionId();
      registry.unregister(id);
      console.log(`Unregistered session ${id}`);
      break;

    case 'conflicts':
      const files = process.argv.slice(3);
      const conflicts = registry.findConflicts(files);
      if (conflicts.length > 0) {
        console.log('Potential conflicts found:');
        console.log(JSON.stringify(conflicts, null, 2));
      } else {
        console.log('No conflicts detected');
      }
      break;

    default:
      console.log('Usage: session-registry.js <command> [args]');
      console.log('Commands:');
      console.log('  list - Show all active sessions');
      console.log('  register [sessionId] [working_on] - Register session');
      console.log('  heartbeat [sessionId] - Update heartbeat');
      console.log('  unregister [sessionId] - Remove session');
      console.log('  conflicts <file1> [file2...] - Check for file conflicts');
  }
}

module.exports = SessionRegistry;
