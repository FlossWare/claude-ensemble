/**
 * Tool Validator Wrapper
 *
 * JavaScript wrapper around pre_tool_validator.py that validates tool calls
 * (Bash, Read, Write, Edit) before execution to prevent dangerous operations.
 *
 * Usage:
 *   const { validateToolCall } = require('./shared/tool-validator-wrapper.js');
 *
 *   const result = await validateToolCall('Bash', { command: 'rm -rf /', timeout: 5000 });
 *   if (!result.valid) {
 *     console.error('Tool validation failed:', result.errors);
 *     throw new Error(result.errors.join('; '));
 *   }
 *
 * Integration:
 *   - Pre-tool validation hook intercepts all tool calls
 *   - Validates parameters against schemas and safety rules
 *   - Logs results to PostgreSQL workflow.tool_validations table
 *   - Blocks execution if validation fails
 *
 * Created: 2026-07-01 (ECC issue #235)
 */

const { spawn } = require('child_process');
const path = require('path');

/**
 * Validate a tool call using Python pre_tool_validator.py
 *
 * @param {string} toolName - Tool name (Bash, Read, Write, Edit)
 * @param {Object} parameters - Tool parameters to validate
 * @param {Object} options - Validation options
 * @param {boolean} options.dryRun - If true, only validate without executing (default: false)
 * @param {boolean} options.permissionCheck - If true, check file permissions (default: true)
 * @returns {Promise<Object>} Validation result: { valid, errors, warnings, dry_run }
 */
async function validateToolCall(toolName, parameters, options = {}) {
  const dryRun = options.dryRun ?? false;
  const permissionCheck = options.permissionCheck ?? true;

  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, 'pre_tool_validator.py');

    // Spawn Python validator
    const proc = spawn('python3', [pythonScript], {
      stdio: ['pipe', 'pipe', 'pipe'],
      timeout: 10000 // 10s timeout for validation
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code, signal) => {
      if (signal) {
        reject(new Error(`Validation process killed by signal ${signal}`));
        return;
      }

      if (code !== null && code !== 0) {
        reject(new Error(`Validation process failed with exit code ${code}: ${stderr}`));
        return;
      }

      try {
        const result = JSON.parse(stdout);
        resolve(result);
      } catch (err) {
        reject(new Error(`Failed to parse validation result: ${err.message}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn validation process: ${err.message}`));
    });

    // Send validation request via stdin
    const request = {
      tool_name: toolName,
      parameters: parameters,
      dry_run: dryRun,
      permission_check: permissionCheck
    };

    proc.stdin.write(JSON.stringify(request));
    proc.stdin.end();
  });
}

/**
 * Validate multiple tool calls in batch
 *
 * @param {Array<Object>} toolCalls - Array of { toolName, parameters, options }
 * @returns {Promise<Array<Object>>} Array of validation results
 */
async function validateToolCallsBatch(toolCalls) {
  const validations = toolCalls.map(({ toolName, parameters, options }) =>
    validateToolCall(toolName, parameters, options)
  );

  return await Promise.all(validations);
}

/**
 * Check if tool call is safe (passes validation without errors)
 *
 * @param {string} toolName - Tool name
 * @param {Object} parameters - Tool parameters
 * @returns {Promise<boolean>} True if safe, false if has errors
 */
async function isToolCallSafe(toolName, parameters) {
  try {
    const result = await validateToolCall(toolName, parameters);
    return result.valid;
  } catch (err) {
    console.error('Validation error:', err.message);
    return false;
  }
}

/**
 * Get validation warnings (non-blocking issues)
 *
 * @param {string} toolName - Tool name
 * @param {Object} parameters - Tool parameters
 * @returns {Promise<Array<string>>} List of warnings
 */
async function getToolCallWarnings(toolName, parameters) {
  try {
    const result = await validateToolCall(toolName, parameters);
    return result.warnings || [];
  } catch (err) {
    console.error('Validation error:', err.message);
    return [];
  }
}

module.exports = {
  validateToolCall,
  validateToolCallsBatch,
  isToolCallSafe,
  getToolCallWarnings
};
