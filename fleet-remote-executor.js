/**
 * Fleet Remote Executor - SSH + claude -p execution engine
 *
 * Phase 3 remote execution module. Encapsulates the battle-tested
 * SSH + claude -p pattern from fleet-bulk-lib.sh into a reusable
 * async JavaScript class.
 *
 * Architecture:
 *   Caller -> RemoteExecutor.execute(server, model, prompt, opts)
 *          -> Builds SSH + claude -p command
 *          -> Uses async child_process.exec (preserves parallelism)
 *          -> Parses claude JSON output envelope
 *          -> Returns {result, cost, remoteDuration}
 *
 * Prompt handling:
 *   - Prompts < 4KB: passed inline via SSH command (properly escaped)
 *   - Prompts >= 4KB: written to NFS shared file, read by remote claude
 *
 * Failure modes:
 *   - SSH connection failure -> throws with code 'SSH_CONNECT_FAILED'
 *   - claude -p failure -> throws with code 'CLAUDE_EXECUTION_FAILED'
 *   - Output parse failure -> throws with code 'OUTPUT_PARSE_FAILED'
 *   - Timeout -> throws with code 'EXECUTION_TIMEOUT'
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';

const execAsync = promisify(exec);

// Maximum prompt size to pass inline via SSH command line
const MAX_INLINE_PROMPT_BYTES = 4096;

// SSH options used across all connections (matches fleet-bulk-lib.sh)
const SSH_OPTS = '-o BatchMode=yes -o StrictHostKeyChecking=accept-new';

/**
 * Remote execution engine for fleet agent dispatch
 */
export class RemoteExecutor {
  /**
   * @param {Object} config
   * @param {string} config.nfsRoot - NFS shared root (default: ~/Development)
   * @param {string} config.vertexProjectId - Vertex AI project ID
   * @param {string} config.claudeCodeUseVertex - '1' to enable Vertex
   * @param {string} config.googleGenaiUseVertexAI - 'True' to enable Vertex for Gemini
   * @param {number} config.sshTimeoutSec - SSH connect timeout in seconds (default: 10)
   * @param {number} config.maxPromptCmdLength - Max inline prompt bytes (default: 4096)
   * @param {number} config.maxTurns - Max claude turns (default: 50)
   * @param {string[]} config.forbiddenPaths - Paths where fleet execution is blocked
   */
  constructor(config = {}) {
    this.nfsRoot = config.nfsRoot || process.env.NFS_ROOT || path.join(process.env.HOME || '/home/sfloess', 'Development');
    this.vertexProjectId = config.vertexProjectId || process.env.ANTHROPIC_VERTEX_PROJECT_ID || 'itpc-gcp-uie-eng-claude';
    this.claudeCodeUseVertex = config.claudeCodeUseVertex || process.env.CLAUDE_CODE_USE_VERTEX || '1';
    this.googleGenaiUseVertexAI = config.googleGenaiUseVertexAI || process.env.GOOGLE_GENAI_USE_VERTEXAI || 'True';
    this.sshTimeoutSec = config.sshTimeoutSec || 10;
    this.maxPromptCmdLength = config.maxPromptCmdLength || MAX_INLINE_PROMPT_BYTES;
    this.maxTurns = config.maxTurns || 50;
    this.forbiddenPaths = config.forbiddenPaths || [];

    // NFS directories for prompt/result exchange
    this.promptsDir = path.join(this.nfsRoot, 'fleet-results', '.prompts');
    this.resultsDir = path.join(this.nfsRoot, 'fleet-results', '.results');
  }

  /**
   * Execute an agent on a remote server via SSH + claude -p
   *
   * @param {string} server - Server hostname (e.g., 'server-01')
   * @param {string} model - AI model name (e.g., 'opus', 'sonnet')
   * @param {string} prompt - Full agent prompt
   * @param {Object} opts
   * @param {string} opts.jobId - Job ID for file-based prompt passing
   * @param {number} opts.timeoutMs - Execution timeout in milliseconds (default: 180000)
   * @param {Object} opts.schema - Expected output schema for validation
   * @returns {Promise<{result: any, cost: number, remoteDuration: number}>}
   */
  async execute(server, model, prompt, opts = {}) {
    const {
      jobId = `job-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timeoutMs = 180000,
      schema = null,
    } = opts;

    let usedPromptFile = false;

    try {
      // Build and execute SSH command
      const command = await this.buildCommand(server, prompt, model, jobId);
      usedPromptFile = Buffer.byteLength(prompt, 'utf8') >= this.maxPromptCmdLength;

      const rawOutput = await this._execWithTimeout(command, timeoutMs);

      // Parse claude output envelope
      const parsed = this.parseClaudeOutput(rawOutput, schema);

      return parsed;
    } finally {
      // Always cleanup temp files
      if (usedPromptFile) {
        await this.cleanup(jobId).catch(() => {});
      }
    }
  }

  /**
   * Build the full SSH + claude -p command
   *
   * @param {string} server - Server hostname
   * @param {string} prompt - Agent prompt
   * @param {string} model - AI model
   * @param {string} jobId - Job ID for file-based ops
   * @returns {Promise<string>} Full SSH command string
   */
  async buildCommand(server, prompt, model, jobId) {
    const promptBytes = Buffer.byteLength(prompt, 'utf8');

    // Environment variable exports (matches fleet-bulk-lib.sh lines 384-387)
    const envExports = [
      `export ANTHROPIC_VERTEX_PROJECT_ID='${this.vertexProjectId}'`,
      `export CLAUDE_CODE_USE_VERTEX='${this.claudeCodeUseVertex}'`,
      `export GOOGLE_GENAI_USE_VERTEXAI='${this.googleGenaiUseVertexAI}'`,
    ].join(' && ');

    // Claude command flags
    const claudeFlags = [
      '--dangerously-skip-permissions',
      '--output-format json',
      `--max-turns ${this.maxTurns}`,
      '--no-session-persistence',
    ].join(' ');

    let claudeCmd;

    if (promptBytes >= this.maxPromptCmdLength) {
      // Large prompt: write to NFS file, read on remote
      const promptFile = await this.writePromptFile(jobId, prompt);
      claudeCmd = `claude -p ${claudeFlags} "$(cat '${promptFile}')"`;
    } else {
      // Small prompt: pass inline with proper escaping
      const escaped = this.escapeForSsh(prompt);
      claudeCmd = `claude -p ${claudeFlags} '${escaped}'`;
    }

    // Full SSH command
    const remoteCmd = `${envExports} && cd '${this.nfsRoot}' && ${claudeCmd}`;

    return `ssh ${SSH_OPTS} -o ConnectTimeout=${this.sshTimeoutSec} ${server} "${this.escapeForDoubleQuotes(remoteCmd)}"`;
  }

  /**
   * Escape a string for use inside SSH single-quoted argument
   * Handles: single quotes, preserves everything else
   *
   * @param {string} str - String to escape
   * @returns {string} Escaped string
   */
  escapeForSsh(str) {
    // Replace single quotes: end quote, escaped quote, start quote
    // 'hello's world' -> 'hello'\''s world'
    return str.replace(/'/g, "'\\''");
  }

  /**
   * Escape a string for use inside double-quoted SSH command wrapper
   *
   * @param {string} str - String to escape
   * @returns {string} Escaped string
   */
  escapeForDoubleQuotes(str) {
    // Escape characters special inside double quotes: \ $ ` " !
    return str
      .replace(/\\/g, '\\\\')
      .replace(/\$/g, '\\$')
      .replace(/`/g, '\\`')
      .replace(/"/g, '\\"')
      .replace(/!/g, '\\!');
  }

  /**
   * Write prompt to NFS file for large prompt handling
   *
   * @param {string} jobId - Job identifier
   * @param {string} prompt - Prompt text
   * @returns {Promise<string>} Path to prompt file (NFS-visible)
   */
  async writePromptFile(jobId, prompt) {
    await fs.promises.mkdir(this.promptsDir, { recursive: true });
    const filePath = path.join(this.promptsDir, `${jobId}.txt`);
    await fs.promises.writeFile(filePath, prompt, 'utf8');
    return filePath;
  }

  /**
   * Read result from NFS file
   *
   * @param {string} jobId - Job identifier
   * @returns {Promise<Object>} Parsed JSON result
   */
  async readResultFile(jobId) {
    const filePath = path.join(this.resultsDir, `${jobId}.json`);
    const content = await fs.promises.readFile(filePath, 'utf8');
    return JSON.parse(content);
  }

  /**
   * Clean up temporary NFS files for a job
   *
   * @param {string} jobId - Job identifier
   * @returns {Promise<void>}
   */
  async cleanup(jobId) {
    const promptFile = path.join(this.promptsDir, `${jobId}.txt`);
    const resultFile = path.join(this.resultsDir, `${jobId}.json`);

    await Promise.all([
      fs.promises.unlink(promptFile).catch(() => {}),
      fs.promises.unlink(resultFile).catch(() => {}),
    ]);
  }

  /**
   * Parse claude -p --output-format json output envelope
   *
   * Claude output format:
   * {
   *   "type": "result",
   *   "subtype": "success",
   *   "cost_usd": 0.xx,
   *   "duration_ms": NNN,
   *   "duration_api_ms": NNN,
   *   "is_error": false,
   *   "num_turns": N,
   *   "result": "<string content>",
   *   "session_id": "..."
   * }
   *
   * @param {string} rawOutput - Raw JSON string from claude -p
   * @param {Object|null} schema - Expected output schema (for result parsing)
   * @returns {{result: any, cost: number, remoteDuration: number}}
   */
  parseClaudeOutput(rawOutput, schema = null) {
    if (!rawOutput || rawOutput.trim().length === 0) {
      const error = new Error('Empty output from remote agent');
      error.code = 'OUTPUT_PARSE_FAILED';
      throw error;
    }

    // Filter out bash completion messages and other non-JSON lines
    const lines = rawOutput.split('\n').filter(line =>
      !line.includes('Universal AI bash completion') &&
      !line.includes('bash completion loaded') &&
      line.trim().length > 0
    );

    const cleanOutput = lines.join('\n').trim();
    if (!cleanOutput || cleanOutput.length === 0) {
      const error = new Error('Empty output from remote agent after filtering');
      error.code = 'OUTPUT_PARSE_FAILED';
      throw error;
    }

    let envelope;
    try {
      envelope = JSON.parse(cleanOutput);
    } catch (e) {
      const error = new Error(`Failed to parse claude output envelope: ${e.message}`);
      error.code = 'OUTPUT_PARSE_FAILED';
      error.rawOutput = cleanOutput.slice(0, 500);
      throw error;
    }

    // Check for error responses
    if (envelope.is_error === true) {
      const error = new Error(`Remote agent error: ${envelope.result || 'Unknown error'}`);
      error.code = 'CLAUDE_EXECUTION_FAILED';
      error.cost = envelope.cost_usd || 0;
      throw error;
    }

    // Extract result string
    const resultStr = envelope.result;
    if (resultStr === null || resultStr === undefined || resultStr === '') {
      const error = new Error('Empty result from remote agent');
      error.code = 'OUTPUT_PARSE_FAILED';
      throw error;
    }

    // Parse result based on schema expectation
    let result = resultStr;
    if (schema && typeof resultStr === 'string') {
      const trimmed = resultStr.trim();
      if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
          result = JSON.parse(trimmed);
        } catch (e) {
          // If JSON parsing fails with schema expected, still return raw string
          // Let caller decide how to handle
          result = trimmed;
        }
      }
    }

    return {
      result,
      cost: envelope.cost_usd || 0,
      remoteDuration: envelope.duration_ms || 0,
    };
  }

  /**
   * Check compliance - verify cwd is not under forbidden paths
   *
   * @returns {{compliant: boolean, reason: string}}
   */
  checkCompliance() {
    if (this.forbiddenPaths.length === 0) {
      // Try loading from fleet.json
      try {
        const fleetConfigPath = path.join(process.env.HOME || '/home/sfloess', '.claude', 'fleet.json');
        const config = JSON.parse(fs.readFileSync(fleetConfigPath, 'utf8'));
        this.forbiddenPaths = config.compliance?.forbidden_paths || [];
      } catch (e) {
        return { compliant: true, reason: 'No fleet.json found, assuming compliant' };
      }
    }

    let cwd;
    try {
      cwd = fs.realpathSync(process.cwd());
    } catch (e) {
      cwd = process.cwd();
    }

    for (const forbidden of this.forbiddenPaths) {
      if (cwd.startsWith(forbidden)) {
        return {
          compliant: false,
          reason: `Current directory ${cwd} is under forbidden path ${forbidden}`,
        };
      }
    }

    return { compliant: true, reason: 'OK' };
  }

  /**
   * Execute SSH command with timeout using AbortController
   *
   * @param {string} command - Full SSH command
   * @param {number} timeoutMs - Timeout in milliseconds
   * @returns {Promise<string>} stdout from command
   * @private
   */
  async _execWithTimeout(command, timeoutMs) {
    const controller = new AbortController();
    const { signal } = controller;

    const timer = setTimeout(() => {
      controller.abort();
    }, timeoutMs);

    try {
      const { stdout, stderr } = await execAsync(command, {
        encoding: 'utf8',
        maxBuffer: 50 * 1024 * 1024, // 50MB buffer for large outputs
        signal,
        timeout: timeoutMs + 5000, // exec timeout as backup (5s grace)
      });

      return stdout;
    } catch (error) {
      if (error.killed || error.code === 'ABORT_ERR' || signal.aborted) {
        const timeoutError = new Error(`Remote execution timed out after ${timeoutMs}ms`);
        timeoutError.code = 'EXECUTION_TIMEOUT';
        timeoutError.timeoutMs = timeoutMs;
        throw timeoutError;
      }

      // SSH connection failures
      if (error.message && (
        error.message.includes('Connection refused') ||
        error.message.includes('Connection timed out') ||
        error.message.includes('No route to host') ||
        error.message.includes('Host key verification failed')
      )) {
        const sshError = new Error(`SSH connection failed to server: ${error.message}`);
        sshError.code = 'SSH_CONNECT_FAILED';
        throw sshError;
      }

      // claude -p execution failure (non-zero exit)
      if (error.code !== 0 && error.stdout) {
        // Try to parse stdout as claude JSON output (may contain error details)
        try {
          const envelope = JSON.parse(error.stdout.trim());
          if (envelope.is_error) {
            const claudeError = new Error(`Remote claude error: ${envelope.result || 'Unknown'}`);
            claudeError.code = 'CLAUDE_EXECUTION_FAILED';
            claudeError.cost = envelope.cost_usd || 0;
            throw claudeError;
          }
        } catch (parseErr) {
          if (parseErr.code === 'CLAUDE_EXECUTION_FAILED') throw parseErr;
          // Not parseable - fall through to generic error
        }
      }

      // Generic remote execution failure
      const execError = new Error(`Remote execution failed: ${error.message}`);
      execError.code = 'CLAUDE_EXECUTION_FAILED';
      execError.stderr = error.stderr || '';
      execError.exitCode = error.code;
      throw execError;
    } finally {
      clearTimeout(timer);
    }
  }
}

/**
 * Factory function for convenience
 * @param {Object} config - RemoteExecutor configuration
 * @returns {RemoteExecutor}
 */
export function createRemoteExecutor(config = {}) {
  return new RemoteExecutor(config);
}

export default {
  RemoteExecutor,
  createRemoteExecutor,
};
