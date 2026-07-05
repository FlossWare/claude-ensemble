/**
 * Input Validation Module
 *
 * Security-hardened validation for user inputs across the system.
 * Prevents SQL injection, path traversal, command injection, and XSS.
 *
 * Created: 2026-07-04
 * Issue: #323 Part 3
 */

const path = require('path');
const { homedir } = require('os');

/**
 * Validation error class
 */
class ValidationError extends Error {
  constructor(message, field, value) {
    super(message);
    this.name = 'ValidationError';
    this.field = field;
    this.value = value;
  }
}

/**
 * Sanitize task description
 * Removes dangerous characters, limits length, prevents injection attacks
 *
 * @param {string} desc - Raw task description
 * @param {Object} options - { maxLength: 5000, allowNewlines: true }
 * @returns {string} Sanitized description
 * @throws {ValidationError} If input is invalid
 */
function sanitizeTaskDescription(desc, options = {}) {
  const { maxLength = 5000, allowNewlines = true } = options;

  // Type check
  if (typeof desc !== 'string') {
    throw new ValidationError('Task description must be a string', 'taskDescription', desc);
  }

  // Length check
  if (desc.length === 0) {
    throw new ValidationError('Task description cannot be empty', 'taskDescription', desc);
  }

  if (desc.length > maxLength) {
    throw new ValidationError(
      `Task description too long (${desc.length} > ${maxLength} chars)`,
      'taskDescription',
      desc
    );
  }

  // Remove dangerous characters that could be used for injection
  let sanitized = desc;

  // Remove HTML/XML tags (prevents XSS)
  // First remove dangerous tags and their content
  sanitized = sanitized.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  sanitized = sanitized.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');

  // Then remove remaining tags
  let previousLength;
  do {
    previousLength = sanitized.length;
    sanitized = sanitized.replace(/<[^>]*>/g, '');
  } while (sanitized.length !== previousLength && sanitized.includes('<'));

  // Remove SQL injection attempts (common patterns)
  const sqlPatterns = [
    /(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|DECLARE)\b)/gi,
    /(--|\/\*|\*\/|;)/g, // SQL comment markers and semicolons
    /(\$\(|\`|eval\(|exec\()/gi, // Command injection patterns
  ];

  for (const pattern of sqlPatterns) {
    if (pattern.test(sanitized)) {
      throw new ValidationError(
        'Task description contains disallowed SQL/command patterns',
        'taskDescription',
        desc
      );
    }
  }

  // Handle newlines
  if (!allowNewlines) {
    sanitized = sanitized.replace(/[\r\n]+/g, ' ');
  }

  // Trim whitespace
  sanitized = sanitized.trim();

  // Normalize whitespace (collapse multiple spaces)
  sanitized = sanitized.replace(/\s+/g, ' ');

  return sanitized;
}

/**
 * Validate and sanitize file path
 * Prevents path traversal attacks, validates against allowlist
 *
 * @param {string} filePath - Raw file path
 * @param {Object} options - { allowedDirs: [], allowSymlinks: false, mustExist: false }
 * @returns {string} Normalized absolute path
 * @throws {ValidationError} If path is invalid or not allowed
 */
function validateFilePath(filePath, options = {}) {
  const {
    allowedDirs = [
      path.join(homedir(), '.claude'),
      path.join(homedir(), 'Development'),
      '/tmp'
    ],
    allowSymlinks = false,
    mustExist = false
  } = options;

  // Type check
  if (typeof filePath !== 'string') {
    throw new ValidationError('File path must be a string', 'filePath', filePath);
  }

  // Empty check
  if (filePath.trim().length === 0) {
    throw new ValidationError('File path cannot be empty', 'filePath', filePath);
  }

  // Path traversal check (before normalization)
  // Reject paths with ../ or ..\ patterns
  if (filePath.includes('..')) {
    throw new ValidationError(
      'Path traversal detected in file path',
      'filePath',
      filePath
    );
  }

  // Normalize and resolve to absolute path
  const normalized = path.normalize(path.resolve(filePath));

  // Null byte injection check
  if (normalized.includes('\0')) {
    throw new ValidationError(
      'Null byte detected in file path',
      'filePath',
      filePath
    );
  }

  // Allowlist check
  const isAllowed = allowedDirs.some(allowedDir => {
    const normalizedAllowedDir = path.normalize(path.resolve(allowedDir));
    return normalized.startsWith(normalizedAllowedDir);
  });

  if (!isAllowed) {
    throw new ValidationError(
      `File path not in allowed directories: ${allowedDirs.join(', ')}`,
      'filePath',
      filePath
    );
  }

  // Symlink check (if not allowed)
  if (!allowSymlinks && mustExist) {
    const fs = require('fs');
    try {
      const stats = fs.lstatSync(normalized);
      if (stats.isSymbolicLink()) {
        throw new ValidationError(
          'Symlinks not allowed',
          'filePath',
          filePath
        );
      }
    } catch (err) {
      if (err.code === 'ENOENT' && mustExist) {
        throw new ValidationError(
          'File does not exist',
          'filePath',
          filePath
        );
      }
      // Other errors (e.g., permission denied) - let them bubble up
      if (err.code !== 'ENOENT') {
        throw err;
      }
    }
  }

  return normalized;
}

/**
 * Sanitize model name
 * Validates model name against known models
 *
 * @param {string} modelName - Raw model name
 * @param {Object} options - { allowedModels: [], allowUnknown: false }
 * @returns {string} Validated model name
 * @throws {ValidationError} If model name is invalid
 */
function sanitizeModelName(modelName, options = {}) {
  const {
    allowedModels = [
      'opus', 'sonnet', 'haiku', 'fable',
      'gpt-4o', 'gpt-4o-mini',
      'gemini-2.0-flash-exp', 'gemini-1.5-pro',
      'automl', 'multi-model-adversarial'
    ],
    allowUnknown = false
  } = options;

  // Type check
  if (typeof modelName !== 'string') {
    throw new ValidationError('Model name must be a string', 'modelName', modelName);
  }

  // Trim and lowercase
  const sanitized = modelName.trim().toLowerCase();

  // Empty check
  if (sanitized.length === 0) {
    throw new ValidationError('Model name cannot be empty', 'modelName', modelName);
  }

  // Alphanumeric + dash + dot only
  if (!/^[a-z0-9\-\.]+$/.test(sanitized)) {
    throw new ValidationError(
      'Model name contains invalid characters (only a-z, 0-9, -, . allowed)',
      'modelName',
      modelName
    );
  }

  // Allowlist check (unless allowUnknown)
  if (!allowUnknown && !allowedModels.includes(sanitized)) {
    throw new ValidationError(
      `Unknown model name: ${sanitized} (allowed: ${allowedModels.join(', ')})`,
      'modelName',
      modelName
    );
  }

  return sanitized;
}

/**
 * Validate numeric input
 * Ensures value is a valid number within bounds
 *
 * @param {*} value - Raw value
 * @param {Object} options - { min: null, max: null, integer: false, field: 'value' }
 * @returns {number} Validated number
 * @throws {ValidationError} If value is invalid
 */
function validateNumber(value, options = {}) {
  const { min = null, max = null, integer = false, field = 'value' } = options;

  // Type coercion
  const num = Number(value);

  // NaN check
  if (isNaN(num) || !isFinite(num)) {
    throw new ValidationError(
      `${field} must be a valid number`,
      field,
      value
    );
  }

  // Integer check
  if (integer && !Number.isInteger(num)) {
    throw new ValidationError(
      `${field} must be an integer`,
      field,
      value
    );
  }

  // Min check
  if (min !== null && num < min) {
    throw new ValidationError(
      `${field} must be >= ${min}`,
      field,
      value
    );
  }

  // Max check
  if (max !== null && num > max) {
    throw new ValidationError(
      `${field} must be <= ${max}`,
      field,
      value
    );
  }

  return num;
}

/**
 * Validate confidence score (0.0 - 1.0)
 *
 * @param {*} confidence - Raw confidence value
 * @returns {number} Validated confidence (0.0 - 1.0)
 * @throws {ValidationError} If confidence is invalid
 */
function validateConfidence(confidence) {
  return validateNumber(confidence, {
    min: 0.0,
    max: 1.0,
    integer: false,
    field: 'confidence'
  });
}

/**
 * Validate worker count (1-16)
 *
 * @param {*} workerCount - Raw worker count
 * @returns {number} Validated worker count (1-16)
 * @throws {ValidationError} If worker count is invalid
 */
function validateWorkerCount(workerCount) {
  return validateNumber(workerCount, {
    min: 1,
    max: 16,
    integer: true,
    field: 'workerCount'
  });
}

/**
 * Validate duration (0 - 1 hour = 3,600,000 ms)
 *
 * @param {*} duration - Raw duration in milliseconds
 * @returns {number} Validated duration (0 - 3,600,000 ms)
 * @throws {ValidationError} If duration is invalid
 */
function validateDuration(duration) {
  return validateNumber(duration, {
    min: 0,
    max: 3600000, // 1 hour max
    integer: true,
    field: 'duration_ms'
  });
}

/**
 * Validate cost (0 - $100)
 *
 * @param {*} cost - Raw cost in USD
 * @returns {number} Validated cost (0 - $100)
 * @throws {ValidationError} If cost is invalid
 */
function validateCost(cost) {
  return validateNumber(cost, {
    min: 0,
    max: 100,
    integer: false,
    field: 'cost_usd'
  });
}

/**
 * Validate token count (0 - 1,000,000)
 *
 * @param {*} tokens - Raw token count
 * @returns {number} Validated token count (0 - 1,000,000)
 * @throws {ValidationError} If token count is invalid
 */
function validateTokenCount(tokens) {
  return validateNumber(tokens, {
    min: 0,
    max: 1000000,
    integer: true,
    field: 'tokens'
  });
}

/**
 * Validate workflow ID
 * Ensures ID matches expected format (alphanumeric + dash + underscore)
 *
 * @param {string} workflowId - Raw workflow ID
 * @returns {string} Validated workflow ID
 * @throws {ValidationError} If workflow ID is invalid
 */
function validateWorkflowId(workflowId) {
  // Type check
  if (typeof workflowId !== 'string') {
    throw new ValidationError('Workflow ID must be a string', 'workflowId', workflowId);
  }

  // Trim
  const sanitized = workflowId.trim();

  // Empty check
  if (sanitized.length === 0) {
    throw new ValidationError('Workflow ID cannot be empty', 'workflowId', workflowId);
  }

  // Length check (max 64 chars)
  if (sanitized.length > 64) {
    throw new ValidationError(
      `Workflow ID too long (${sanitized.length} > 64 chars)`,
      'workflowId',
      workflowId
    );
  }

  // Format check (alphanumeric + dash + underscore)
  if (!/^[a-zA-Z0-9\-_]+$/.test(sanitized)) {
    throw new ValidationError(
      'Workflow ID contains invalid characters (only a-z, A-Z, 0-9, -, _ allowed)',
      'workflowId',
      workflowId
    );
  }

  return sanitized;
}

/**
 * Validate JSON metadata
 * Ensures metadata is valid JSON object, prevents prototype pollution
 *
 * @param {*} metadata - Raw metadata
 * @param {Object} options - { maxDepth: 5, maxSize: 10000 }
 * @returns {Object} Validated metadata object
 * @throws {ValidationError} If metadata is invalid
 */
function validateMetadata(metadata, options = {}) {
  const { maxDepth = 5, maxSize = 10000 } = options;

  // Type check
  if (metadata === null || typeof metadata !== 'object' || Array.isArray(metadata)) {
    throw new ValidationError('Metadata must be a plain object', 'metadata', metadata);
  }

  // Check for prototype pollution attempts (only at top level)
  const dangerousKeys = ['__proto__', 'constructor', 'prototype'];
  for (const key of dangerousKeys) {
    if (Object.prototype.hasOwnProperty.call(metadata, key)) {
      throw new ValidationError(
        `Metadata contains dangerous key: ${key}`,
        'metadata',
        metadata
      );
    }
  }

  // Recursive depth check
  function checkDepth(obj, depth = 0) {
    if (depth > maxDepth) {
      throw new ValidationError(
        `Metadata too deeply nested (max depth: ${maxDepth})`,
        'metadata',
        metadata
      );
    }

    for (const [key, value] of Object.entries(obj)) {
      if (value !== null && typeof value === 'object') {
        checkDepth(value, depth + 1);
      }
    }
  }

  checkDepth(metadata);

  // Size check (JSON stringified size)
  const jsonString = JSON.stringify(metadata);
  if (jsonString.length > maxSize) {
    throw new ValidationError(
      `Metadata too large (${jsonString.length} > ${maxSize} chars)`,
      'metadata',
      metadata
    );
  }

  return metadata;
}

/**
 * Validate outcome value
 * Ensures outcome is one of the allowed values
 *
 * @param {string} outcome - Raw outcome value
 * @returns {string} Validated outcome
 * @throws {ValidationError} If outcome is invalid
 */
function validateOutcome(outcome) {
  const allowedOutcomes = ['success', 'failed', 'error', 'cancelled'];

  // Type check
  if (typeof outcome !== 'string') {
    throw new ValidationError('Outcome must be a string', 'outcome', outcome);
  }

  // Lowercase
  const sanitized = outcome.trim().toLowerCase();

  // Allowlist check
  if (!allowedOutcomes.includes(sanitized)) {
    throw new ValidationError(
      `Invalid outcome: ${sanitized} (allowed: ${allowedOutcomes.join(', ')})`,
      'outcome',
      outcome
    );
  }

  return sanitized;
}

/**
 * Validate workflow storage input
 * Comprehensive validation for workflow execution data
 *
 * @param {Object} workflowData - Raw workflow data
 * @returns {Object} Validated workflow data
 * @throws {ValidationError} If any field is invalid
 */
function validateWorkflowExecution(workflowData) {
  return {
    workflow_id: validateWorkflowId(workflowData.workflow_id),
    workflow_name: sanitizeTaskDescription(workflowData.workflow_name, { maxLength: 255 }),
    task_description: sanitizeTaskDescription(workflowData.task_description),
    total_workers: validateWorkerCount(workflowData.total_workers),
    total_duration_ms: validateDuration(workflowData.total_duration_ms),
    outcome: validateOutcome(workflowData.outcome),
    metadata: validateMetadata(workflowData.metadata || {})
  };
}

/**
 * Validate worker result input
 *
 * @param {Object} workerData - Raw worker result data
 * @returns {Object} Validated worker data
 * @throws {ValidationError} If any field is invalid
 */
function validateWorkerResult(workerData) {
  return {
    workflow_execution_id: validateNumber(workerData.workflow_execution_id, {
      min: 1,
      integer: true,
      field: 'workflow_execution_id'
    }),
    worker_id: validateWorkflowId(workerData.worker_id),
    model: sanitizeModelName(workerData.model),
    task_assigned: sanitizeTaskDescription(workerData.task_assigned),
    result: sanitizeTaskDescription(workerData.result, { maxLength: 50000 }),
    confidence: validateConfidence(workerData.confidence),
    duration_ms: validateDuration(workerData.duration_ms),
    input_tokens: validateTokenCount(workerData.input_tokens),
    output_tokens: validateTokenCount(workerData.output_tokens),
    cost_usd: validateCost(workerData.cost_usd),
    outcome: validateOutcome(workerData.outcome),
    metadata: validateMetadata(workerData.metadata || {})
  };
}

module.exports = {
  ValidationError,
  sanitizeTaskDescription,
  validateFilePath,
  sanitizeModelName,
  validateNumber,
  validateConfidence,
  validateWorkerCount,
  validateDuration,
  validateCost,
  validateTokenCount,
  validateWorkflowId,
  validateMetadata,
  validateOutcome,
  validateWorkflowExecution,
  validateWorkerResult
};
