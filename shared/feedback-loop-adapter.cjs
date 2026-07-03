/**
 * Feedback Loop Optimizer Adapter
 *
 * JavaScript/Node.js interface to feedback_loop_optimizer.py
 * Provides real-time monitoring and intervention for multi-AI workflows
 *
 * Created: 2026-07-03
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;

/**
 * Run feedback loop analysis
 *
 * @param {Object} options - Analysis options
 * @param {number} options.windowDays - Analysis window in days (default: 7)
 * @param {boolean} options.saveToDb - Save risks to database (default: true)
 * @param {boolean} options.quiet - Suppress progress output (default: false)
 * @returns {Promise<Object>} Analysis result
 */
async function analyzeFeedbackLoops(options = {}) {
  const {
    windowDays = 7,
    saveToDb = true,
    quiet = false
  } = options;

  return new Promise((resolve, reject) => {
    const scriptPath = path.join(__dirname, '../tools/feedback_loop_optimizer.py');
    const tmpOutput = `/tmp/feedback-loop-${Date.now()}.json`;

    const args = [
      scriptPath,
      '--window', String(windowDays),
      '--output', tmpOutput
    ];

    if (!saveToDb) {
      args.push('--no-save');
    }

    if (quiet) {
      args.push('--quiet');
    }

    const proc = spawn('python3', args, {
      stdio: quiet ? ['pipe', 'pipe', 'pipe'] : ['pipe', 'inherit', 'inherit'],
      timeout: 60000 // 60s timeout
    });

    let stdout = '';
    let stderr = '';

    if (quiet) {
      proc.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr.on('data', (data) => {
        stderr += data.toString();
      });
    }

    proc.on('close', async (code) => {
      try {
        // Read result from temp file
        const resultJson = await fs.readFile(tmpOutput, 'utf-8');
        const result = JSON.parse(resultJson);

        // Clean up temp file
        await fs.unlink(tmpOutput).catch(() => {});

        // Add exit code to result
        result.exit_code = code;

        resolve(result);
      } catch (err) {
        reject(new Error(`Failed to read analysis result: ${err.message}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn analysis process: ${err.message}`));
    });
  });
}

/**
 * Check if system is healthy (no critical/high risks)
 *
 * @param {number} windowDays - Analysis window in days
 * @returns {Promise<boolean>} True if healthy
 */
async function isSystemHealthy(windowDays = 7) {
  const analysis = await analyzeFeedbackLoops({ windowDays, quiet: true });
  return analysis.summary.critical === 0 && analysis.summary.high === 0;
}

/**
 * Get model distribution analysis
 *
 * @param {number} windowDays - Analysis window in days
 * @returns {Promise<Object>} Model distribution { model: percentage }
 */
async function getModelDistribution(windowDays = 7) {
  const analysis = await analyzeFeedbackLoops({ windowDays, quiet: true });
  return analysis.model_distribution;
}

/**
 * Get risks filtered by type
 *
 * @param {string} riskType - Risk type ('model_dominance', 'eval_gen_coupling', 'reward_hacking', 'concept_collapse')
 * @param {number} windowDays - Analysis window in days
 * @returns {Promise<Array>} Filtered risks
 */
async function getRisksByType(riskType, windowDays = 7) {
  const analysis = await analyzeFeedbackLoops({ windowDays, quiet: true });
  return analysis.risks.filter(r => r.risk_type === riskType);
}

/**
 * Get critical risks (severity > 0.8)
 *
 * @param {number} windowDays - Analysis window in days
 * @returns {Promise<Array>} Critical risks
 */
async function getCriticalRisks(windowDays = 7) {
  const analysis = await analyzeFeedbackLoops({ windowDays, quiet: true });
  return analysis.risks.filter(r => r.severity > 0.8);
}

/**
 * Middleware for workflow execution: check feedback loops before running
 *
 * Usage in workflows:
 *   const { beforeWorkflow } = require('./shared/feedback-loop-adapter.cjs');
 *   await beforeWorkflow({ criticalOnly: true });
 *
 * @param {Object} options - Middleware options
 * @param {boolean} options.criticalOnly - Only fail on critical risks (default: false)
 * @param {number} options.windowDays - Analysis window (default: 7)
 * @throws {Error} If critical risks detected
 */
async function beforeWorkflow(options = {}) {
  const { criticalOnly = false, windowDays = 7 } = options;

  const analysis = await analyzeFeedbackLoops({ windowDays, quiet: true });

  const threshold = criticalOnly ? 0.8 : 0.6;
  const highRisks = analysis.risks.filter(r => r.severity > threshold);

  if (highRisks.length > 0) {
    const riskDescriptions = highRisks.map(r =>
      `  - [${r.risk_type}] ${r.description} (severity=${r.severity.toFixed(2)})`
    ).join('\n');

    throw new Error(
      `Feedback loop risks detected:\n${riskDescriptions}\n\n` +
      `Recommendations:\n${analysis.recommendations.map(r => `  - ${r}`).join('\n')}`
    );
  }
}

/**
 * Middleware for workflow completion: analyze after execution
 *
 * Usage in workflows:
 *   const { afterWorkflow } = require('./shared/feedback-loop-adapter.cjs');
 *   await afterWorkflow({ workflowId: execId });
 *
 * @param {Object} options - Middleware options
 * @param {number} options.workflowId - Workflow execution ID (for logging)
 * @param {boolean} options.warnOnly - Only warn, don't throw (default: true)
 * @returns {Promise<Object>} Analysis result
 */
async function afterWorkflow(options = {}) {
  const { workflowId, warnOnly = true } = options;

  const analysis = await analyzeFeedbackLoops({ windowDays: 1, quiet: true });

  const criticalRisks = analysis.risks.filter(r => r.severity > 0.8);

  if (criticalRisks.length > 0) {
    const message = `Workflow ${workflowId || 'unknown'} may have introduced feedback loop risks:\n` +
      criticalRisks.map(r => `  - ${r.description}`).join('\n');

    if (warnOnly) {
      console.warn(message);
    } else {
      throw new Error(message);
    }
  }

  return analysis;
}

/**
 * Auto-monitoring: check every N hours in background
 *
 * Usage in long-running services:
 *   const { startMonitoring } = require('./shared/feedback-loop-adapter.cjs');
 *   startMonitoring({ intervalHours: 6, onRisk: (analysis) => { ... } });
 *
 * @param {Object} options - Monitoring options
 * @param {number} options.intervalHours - Check interval in hours (default: 6)
 * @param {Function} options.onRisk - Callback when risks detected
 * @param {number} options.windowDays - Analysis window (default: 7)
 * @returns {Object} { stop: () => void } - Stop monitoring
 */
function startMonitoring(options = {}) {
  const {
    intervalHours = 6,
    onRisk = (analysis) => {
      console.warn('[Feedback Loop Monitor] Risks detected:', analysis.summary);
    },
    windowDays = 7
  } = options;

  const intervalMs = intervalHours * 60 * 60 * 1000;

  const check = async () => {
    try {
      const analysis = await analyzeFeedbackLoops({ windowDays, quiet: true });

      if (analysis.summary.critical > 0 || analysis.summary.high > 0) {
        onRisk(analysis);
      }
    } catch (err) {
      console.error('[Feedback Loop Monitor] Check failed:', err.message);
    }
  };

  // Run first check immediately
  check();

  // Schedule periodic checks
  const timer = setInterval(check, intervalMs);

  return {
    stop: () => {
      clearInterval(timer);
    }
  };
}

module.exports = {
  analyzeFeedbackLoops,
  isSystemHealthy,
  getModelDistribution,
  getRisksByType,
  getCriticalRisks,
  beforeWorkflow,
  afterWorkflow,
  startMonitoring
};
