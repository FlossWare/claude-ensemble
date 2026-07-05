/**
 * Path Validation Library - Prevents path traversal vulnerabilities
 *
 * Usage:
 *   import { validatePath, validateReadPath, validateWritePath } from './shared/path-validator.js';
 *
 *   // Throws error if path is unsafe
 *   validatePath('/tmp/../etc/passwd');  // Error: Path traversal attempt
 *
 *   // Validate against specific allowed directories
 *   validateReadPath('/home/user/.claude/learning/data.json');  // OK
 *   validateWritePath('/tmp/output.json');  // OK
 */

import path from 'path';
import { homedir } from 'os';

// ============================================================================
// ALLOWED DIRECTORIES
// ============================================================================

const HOME = process.env.HOME || homedir();

// Directories where we can READ files (most permissive)
const ALLOWED_READ_DIRS = [
  path.join(HOME, '.claude'),
  path.join(HOME, 'Development'),
  '/tmp',
  '/var/tmp',
];

// Directories where we can WRITE files (more restrictive)
const ALLOWED_WRITE_DIRS = [
  path.join(HOME, '.claude', 'learning'),
  path.join(HOME, '.claude', 'reports'),
  path.join(HOME, '.claude', 'logs'),
  path.join(HOME, 'Development', 'redhat', 'scm', 'gitlab', 'cee', 'sfloess', 'claude-global-skills'),
  '/tmp',
];

// Forbidden patterns (even within allowed dirs)
const FORBIDDEN_PATTERNS = [
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
// VALIDATION FUNCTIONS
// ============================================================================

/**
 * Validate a file path to prevent traversal attacks
 *
 * @param {string} filePath - Path to validate
 * @param {string[]} allowedDirs - Array of allowed base directories
 * @throws {Error} If path is unsafe or outside allowed directories
 * @returns {string} Resolved absolute path
 */
export function validatePath(filePath, allowedDirs = ALLOWED_READ_DIRS) {
  if (!filePath || typeof filePath !== 'string') {
    throw new Error('Invalid file path: must be non-empty string');
  }

  // Resolve to absolute path (prevents ../ tricks)
  const resolved = path.resolve(filePath);

  // Check for null bytes (common injection technique)
  if (resolved.includes('\0')) {
    throw new Error('Path traversal attempt: null byte detected');
  }

  // Check if path is within allowed directories
  const isAllowed = allowedDirs.some(dir => {
    const normalizedDir = path.resolve(dir);
    return resolved.startsWith(normalizedDir + path.sep) || resolved === normalizedDir;
  });

  if (!isAllowed) {
    throw new Error(`Access denied: ${resolved} is outside allowed directories`);
  }

  // Check for forbidden patterns
  for (const pattern of FORBIDDEN_PATTERNS) {
    if (pattern.test(resolved)) {
      throw new Error(`Access denied: ${resolved} matches forbidden pattern`);
    }
  }

  return resolved;
}

/**
 * Validate path for READ operations (most permissive)
 *
 * @param {string} filePath - Path to validate
 * @returns {string} Resolved absolute path
 */
export function validateReadPath(filePath) {
  return validatePath(filePath, ALLOWED_READ_DIRS);
}

/**
 * Validate path for WRITE operations (more restrictive)
 *
 * @param {string} filePath - Path to validate
 * @returns {string} Resolved absolute path
 */
export function validateWritePath(filePath) {
  return validatePath(filePath, ALLOWED_WRITE_DIRS);
}

/**
 * Check if a path is safe without throwing
 *
 * @param {string} filePath - Path to check
 * @param {string[]} allowedDirs - Allowed directories
 * @returns {boolean} True if path is safe
 */
export function isPathSafe(filePath, allowedDirs = ALLOWED_READ_DIRS) {
  try {
    validatePath(filePath, allowedDirs);
    return true;
  } catch (_err) {
    return false;
  }
}

/**
 * Validate multiple paths at once
 *
 * @param {string[]} paths - Array of paths to validate
 * @param {string[]} allowedDirs - Allowed directories
 * @returns {string[]} Array of resolved paths
 */
export function validatePaths(paths, allowedDirs = ALLOWED_READ_DIRS) {
  return paths.map(p => validatePath(p, allowedDirs));
}

// ============================================================================
// SAFE FILE OPERATIONS (convenience wrappers)
// ============================================================================

import { readFileSync, writeFileSync, existsSync } from 'fs';

/**
 * Safe readFileSync with path validation
 */
export function safeReadFile(filePath, options) {
  const validPath = validateReadPath(filePath);
  return readFileSync(validPath, options);
}

/**
 * Safe writeFileSync with path validation
 */
export function safeWriteFile(filePath, data, options) {
  const validPath = validateWritePath(filePath);
  return writeFileSync(validPath, data, options);
}

/**
 * Safe existsSync with path validation
 */
export function safeExists(filePath) {
  try {
    const validPath = validateReadPath(filePath);
    return existsSync(validPath);
  } catch (_err) {
    return false;
  }
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  validatePath,
  validateReadPath,
  validateWritePath,
  isPathSafe,
  validatePaths,
  safeReadFile,
  safeWriteFile,
  safeExists,
};
