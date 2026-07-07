/**
 * Input Validator - Centralized input validation and sanitization
 *
 * Provides three core validators for use across all HTTP endpoints:
 *   - sanitizeHtml(input)       - Strip HTML/script tags, prevent XSS
 *   - validateFilePath(path)    - Block path traversal (../) and null bytes
 *   - validateModelInput(input) - Validate model names against allowlist
 *
 * Design: Each function either returns sanitized/validated input or throws
 * a descriptive Error. Callers should catch and return 400 responses.
 *
 * This module is intentionally framework-agnostic (no Express/FastAPI deps)
 * so it works with raw http.createServer, Express, FastAPI bridges, etc.
 *
 * Created: 2026-07-07
 * Issue: #323 (Security hardening)
 */

import path from 'path';
import { homedir } from 'os';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = process.env.HOME || homedir();

/** Maximum input string length to prevent DoS via oversized payloads */
const MAX_INPUT_LENGTH = 50000;

/** Directories where file access is permitted */
const ALLOWED_DIRS = [
  path.join(HOME, '.claude'),
  path.join(HOME, 'Development'),
  '/tmp',
  '/var/tmp',
];

/** Model names accepted by the system */
const KNOWN_MODELS = new Set([
  'opus', 'sonnet', 'haiku', 'fable',
  'gpt-4o', 'gpt-4o-mini',
  'gemini', 'gemini-2.0-flash-exp', 'gemini-1.5-pro',
  'automl', 'multi-model-adversarial',
  'deepseek-r1', 'qwen-coder-32b', 'llama-70b-fast',
  'cerebras-120b',
]);

/** Patterns that are never allowed even inside permitted directories */
const FORBIDDEN_PATH_PATTERNS = [
  /\/etc\/passwd$/,
  /\/etc\/shadow$/,
  /\.ssh\/id_rsa$/,
  /\.ssh\/id_ed25519$/,
  /\.env$/,
  /secrets\.json$/,
  /credentials\.json$/,
  /\.aws\/credentials$/,
];

// ============================================================================
// sanitizeHtml(input)
// ============================================================================

/**
 * Sanitize a string by removing HTML tags, script content, and dangerous
 * markup that could enable XSS attacks.
 *
 * Behavior:
 *  - Strips <script>...</script> and <style>...</style> blocks entirely
 *  - Removes all remaining HTML/XML tags (iteratively to handle nested tags)
 *  - Encodes residual angle brackets as HTML entities
 *  - Strips null bytes
 *  - Enforces maximum length
 *
 * @param {string} input - Raw user input
 * @param {Object} [options]
 * @param {number} [options.maxLength=50000] - Maximum allowed length
 * @param {boolean} [options.allowNewlines=true] - Whether to preserve newlines
 * @returns {string} Sanitized string (never contains HTML tags)
 * @throws {Error} If input is not a string or exceeds max length
 *
 * @example
 *   sanitizeHtml('<script>alert(1)</script>hello')  // => 'hello'
 *   sanitizeHtml('a<b>bold</b>c')                   // => 'aboldc'
 *   sanitizeHtml('<img src=x onerror=alert(1)>')     // => ''
 */
export function sanitizeHtml(input, options = {}) {
  const { maxLength = MAX_INPUT_LENGTH, allowNewlines = true } = options;

  if (typeof input !== 'string') {
    throw new Error('Input must be a string');
  }

  if (input.length === 0) {
    return '';
  }

  if (input.length > maxLength) {
    throw new Error(
      `Input too long: ${input.length} characters (max ${maxLength})`
    );
  }

  let sanitized = input;

  // 1. Remove null bytes (injection vector)
  sanitized = sanitized.replace(/\0/g, '');

  // 2. Remove <script> blocks and their content (case-insensitive, dotAll)
  sanitized = sanitized.replace(
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    ''
  );

  // 3. Remove <style> blocks and their content
  sanitized = sanitized.replace(
    /<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi,
    ''
  );

  // 4. Remove event handler attributes (onerror, onclick, onload, etc.)
  sanitized = sanitized.replace(/\bon\w+\s*=\s*(['"]?).*?\1/gi, '');

  // 5. Remove javascript: and data: URIs in attributes
  sanitized = sanitized.replace(/(?:javascript|data)\s*:/gi, '');

  // 6. Iteratively strip all remaining HTML/XML tags
  //    Loop handles cases like <<script>script>
  let previousLength;
  do {
    previousLength = sanitized.length;
    sanitized = sanitized.replace(/<[^>]*>/g, '');
  } while (sanitized.length !== previousLength && sanitized.includes('<'));

  // 7. Encode any residual angle brackets as HTML entities
  sanitized = sanitized.replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // 8. Handle newlines
  if (!allowNewlines) {
    sanitized = sanitized.replace(/[\r\n]+/g, ' ');
  }

  // 9. Collapse excessive whitespace
  sanitized = sanitized.replace(/[ \t]+/g, ' ').trim();

  return sanitized;
}

// ============================================================================
// validateFilePath(path)
// ============================================================================

/**
 * Validate a file path to prevent path traversal attacks.
 *
 * Checks performed:
 *  1. Type and emptiness check
 *  2. Blocks any occurrence of '..' (path traversal)
 *  3. Blocks null bytes
 *  4. Resolves to absolute path and checks against allowed directories
 *  5. Checks against forbidden file patterns (secrets, credentials)
 *
 * @param {string} filePath - Path to validate
 * @param {Object} [options]
 * @param {string[]} [options.allowedDirs] - Override default allowed directories
 * @returns {string} Resolved absolute path (safe to use)
 * @throws {Error} If path is invalid, contains traversal, or is outside allowed dirs
 *
 * @example
 *   validateFilePath('/tmp/output.json')          // => '/tmp/output.json'
 *   validateFilePath('../../../etc/passwd')        // throws Error
 *   validateFilePath('/home/user/.ssh/id_rsa')     // throws Error
 */
export function validateFilePath(filePath, options = {}) {
  const { allowedDirs = ALLOWED_DIRS } = options;

  // Type check
  if (typeof filePath !== 'string') {
    throw new Error('File path must be a string');
  }

  // Empty check
  if (filePath.trim().length === 0) {
    throw new Error('File path cannot be empty');
  }

  // Path traversal check (before normalization to catch encoded variants)
  if (filePath.includes('..')) {
    throw new Error('Path traversal detected: ".." is not allowed in file paths');
  }

  // Null byte check (before any path operations)
  if (filePath.includes('\0')) {
    throw new Error('Null byte detected in file path');
  }

  // Resolve to absolute path
  const resolved = path.resolve(filePath);

  // Double-check resolved path for traversal (catches edge cases)
  if (resolved.includes('..')) {
    throw new Error('Path traversal detected after resolution');
  }

  // Allowlist check: path must be under an allowed directory
  const isAllowed = allowedDirs.some((dir) => {
    const normalizedDir = path.resolve(dir);
    return (
      resolved === normalizedDir ||
      resolved.startsWith(normalizedDir + path.sep)
    );
  });

  if (!isAllowed) {
    throw new Error(
      `Access denied: path is outside allowed directories [${allowedDirs.join(', ')}]`
    );
  }

  // Forbidden pattern check
  for (const pattern of FORBIDDEN_PATH_PATTERNS) {
    if (pattern.test(resolved)) {
      throw new Error(`Access denied: path matches a forbidden pattern`);
    }
  }

  return resolved;
}

// ============================================================================
// validateModelInput(input)
// ============================================================================

/**
 * Validate a model name or model-related input string.
 *
 * Checks performed:
 *  1. Type and emptiness check
 *  2. Character allowlist (alphanumeric, dash, dot, underscore, colon)
 *  3. Length limit (max 64 characters)
 *  4. Optionally checks against known model names
 *
 * @param {string} input - Model name or identifier to validate
 * @param {Object} [options]
 * @param {boolean} [options.strict=false] - If true, reject unknown model names
 * @param {Set<string>} [options.knownModels] - Override the set of known models
 * @param {number} [options.maxLength=64] - Maximum model name length
 * @returns {string} Sanitized model name (trimmed, lowercased)
 * @throws {Error} If input is invalid or (in strict mode) unknown
 *
 * @example
 *   validateModelInput('Sonnet')               // => 'sonnet'
 *   validateModelInput('gpt-4o')               // => 'gpt-4o'
 *   validateModelInput('<script>')              // throws Error
 *   validateModelInput('unknown', {strict: true}) // throws Error
 */
export function validateModelInput(input, options = {}) {
  const {
    strict = false,
    knownModels = KNOWN_MODELS,
    maxLength = 64,
  } = options;

  // Type check
  if (typeof input !== 'string') {
    throw new Error('Model input must be a string');
  }

  // Trim and lowercase
  const sanitized = input.trim().toLowerCase();

  // Empty check
  if (sanitized.length === 0) {
    throw new Error('Model input cannot be empty');
  }

  // Length check
  if (sanitized.length > maxLength) {
    throw new Error(
      `Model input too long: ${sanitized.length} characters (max ${maxLength})`
    );
  }

  // Character allowlist: only a-z, 0-9, dash, dot, underscore, colon
  // Colon is needed for Ollama model tags like "qwen2.5-coder:7b"
  if (!/^[a-z0-9\-._:]+$/.test(sanitized)) {
    throw new Error(
      'Model input contains invalid characters (allowed: a-z, 0-9, -, ., _, :)'
    );
  }

  // Strict mode: check against known models
  if (strict && !knownModels.has(sanitized)) {
    throw new Error(
      `Unknown model: "${sanitized}" (known models: ${[...knownModels].join(', ')})`
    );
  }

  return sanitized;
}

// ============================================================================
// MIDDLEWARE HELPERS
// ============================================================================

/**
 * Parse and validate a JSON request body from a Node.js http.IncomingMessage.
 * Enforces a maximum body size to prevent memory exhaustion.
 *
 * @param {import('http').IncomingMessage} req - HTTP request
 * @param {Object} [options]
 * @param {number} [options.maxBodySize=1048576] - Max body size in bytes (default 1MB)
 * @returns {Promise<Object>} Parsed JSON body
 * @throws {Error} If body is too large, not valid JSON, or not an object
 */
export function parseAndValidateBody(req, options = {}) {
  const { maxBodySize = 1048576 } = options;

  return new Promise((resolve, reject) => {
    let body = '';
    let size = 0;

    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > maxBodySize) {
        req.destroy();
        reject(new Error(`Request body too large (max ${maxBodySize} bytes)`));
        return;
      }
      body += chunk;
    });

    req.on('end', () => {
      if (body.length === 0) {
        resolve({});
        return;
      }

      try {
        const parsed = JSON.parse(body);
        if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
          reject(new Error('Request body must be a JSON object'));
          return;
        }

        // Prototype pollution prevention
        const dangerous = ['__proto__', 'constructor', 'prototype'];
        for (const key of dangerous) {
          if (Object.prototype.hasOwnProperty.call(parsed, key)) {
            reject(new Error(`Request body contains forbidden key: ${key}`));
            return;
          }
        }

        resolve(parsed);
      } catch (err) {
        reject(new Error(`Invalid JSON: ${err.message}`));
      }
    });

    req.on('error', (err) => {
      reject(new Error(`Request stream error: ${err.message}`));
    });
  });
}

/**
 * Validate a query parameter string to prevent injection.
 * Strips HTML and limits length.
 *
 * @param {string} value - Query parameter value
 * @param {Object} [options]
 * @param {number} [options.maxLength=500] - Maximum parameter length
 * @returns {string} Sanitized parameter value
 * @throws {Error} If value is invalid
 */
export function validateQueryParam(value, options = {}) {
  const { maxLength = 500 } = options;

  if (typeof value !== 'string') {
    throw new Error('Query parameter must be a string');
  }

  if (value.length > maxLength) {
    throw new Error(
      `Query parameter too long: ${value.length} characters (max ${maxLength})`
    );
  }

  // Strip any HTML from query params
  return sanitizeHtml(value, { maxLength, allowNewlines: false });
}

// ============================================================================
// EXPORTS
// ============================================================================

export default {
  sanitizeHtml,
  validateFilePath,
  validateModelInput,
  parseAndValidateBody,
  validateQueryParam,
  KNOWN_MODELS,
  ALLOWED_DIRS,
};
