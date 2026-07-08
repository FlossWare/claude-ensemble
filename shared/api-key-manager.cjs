/**
 * API Key Manager with AES-256 Encryption
 *
 * SECURITY: Uses AES-256-GCM encryption for API keys at rest.
 * Encryption key MUST be in environment variable: API_KEY_ENCRYPTION_KEY
 *
 * Multi-account support:
 * - Store multiple API keys per service (work vs personal Gmail, etc.)
 * - Tag keys by purpose/context (redhat, personal, testing)
 * - Automatic key selection based on task type
 * - Usage tracking per key
 */

const crypto = require('crypto');
const { Pool } = require('pg');

// Encryption configuration
const ALGORITHM = 'aes-256-gcm';
const KEY_LENGTH = 32; // 256 bits
const IV_LENGTH = 16;  // 128 bits
const AUTH_TAG_LENGTH = 16;

/**
 * Get encryption key from environment
 * CRITICAL: This must be set in environment, NEVER hardcoded!
 */
function getEncryptionKey() {
  const key = process.env.API_KEY_ENCRYPTION_KEY;

  if (!key) {
    throw new Error(
      'API_KEY_ENCRYPTION_KEY environment variable not set! ' +
      'Generate one with: openssl rand -hex 32'
    );
  }

  // Convert hex string to buffer
  const keyBuffer = Buffer.from(key, 'hex');

  if (keyBuffer.length !== KEY_LENGTH) {
    throw new Error(
      `API_KEY_ENCRYPTION_KEY must be ${KEY_LENGTH * 2} hex characters (${KEY_LENGTH} bytes). ` +
      `Got: ${keyBuffer.length} bytes`
    );
  }

  return keyBuffer;
}

/**
 * Encrypt API key using AES-256-GCM
 * @param {string} plaintext - API key to encrypt
 * @returns {string} - Base64-encoded encrypted data (iv:authTag:ciphertext)
 */
function encryptKey(plaintext) {
  const key = getEncryptionKey();

  // Generate random IV (initialization vector)
  const iv = crypto.randomBytes(IV_LENGTH);

  // Create cipher
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

  // Encrypt
  const ciphertext = Buffer.concat([
    cipher.update(plaintext, 'utf8'),
    cipher.final()
  ]);

  // Get authentication tag (for GCM mode)
  const authTag = cipher.getAuthTag();

  // Combine iv:authTag:ciphertext and encode as base64
  const combined = Buffer.concat([iv, authTag, ciphertext]);
  return combined.toString('base64');
}

/**
 * Decrypt API key using AES-256-GCM
 * @param {string} encrypted - Base64-encoded encrypted data
 * @returns {string} - Decrypted API key
 */
function decryptKey(encrypted) {
  const key = getEncryptionKey();

  // Decode from base64
  const combined = Buffer.from(encrypted, 'base64');

  // Extract iv, authTag, ciphertext
  const iv = combined.subarray(0, IV_LENGTH);
  const authTag = combined.subarray(IV_LENGTH, IV_LENGTH + AUTH_TAG_LENGTH);
  const ciphertext = combined.subarray(IV_LENGTH + AUTH_TAG_LENGTH);

  // Create decipher
  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);

  // Decrypt
  const plaintext = Buffer.concat([
    decipher.update(ciphertext),
    decipher.final()
  ]);

  return plaintext.toString('utf8');
}

/**
 * Get PostgreSQL connection
 */
function getDB() {
  return new Pool({
    host: 'aio-01',
    port: 5433,
    user: 'claude',
    password: 'claude',
    database: 'learning',
  });
}

/**
 * Add API key to storage
 * @param {Object} keyData
 * @param {string} keyData.service - Service name (e.g., 'gmail', 'openai', 'anthropic')
 * @param {string} keyData.keyName - Unique name (e.g., 'work-gmail', 'personal-openai')
 * @param {string} keyData.apiKey - The actual API key (will be encrypted)
 * @param {string} keyData.purpose - Human-readable purpose
 * @param {Array<string>} keyData.tags - Tags for filtering (e.g., ['redhat', 'work'])
 * @param {string} keyData.notes - Optional notes
 * @returns {Promise<number>} - Key ID
 */
async function addKey(keyData) {
  const { service, keyName, apiKey, purpose, tags = [], notes = '' } = keyData;

  if (!service || !keyName || !apiKey) {
    throw new Error('service, keyName, and apiKey are required');
  }

  // Encrypt the API key
  const encryptedKey = encryptKey(apiKey);

  const db = getDB();

  try {
    const result = await db.query(`
      INSERT INTO config.api_keys (
        service, key_name, purpose, tags, encrypted_key,
        encryption_method, notes
      ) VALUES ($1, $2, $3, $4, $5, $6, $7)
      RETURNING id
    `, [
      service,
      keyName,
      purpose,
      JSON.stringify(tags),
      encryptedKey,
      'aes-256-gcm',
      notes
    ]);

    return result.rows[0].id;

  } finally {
    await db.end();
  }
}

/**
 * Get API key (decrypted)
 * @param {Object} options
 * @param {string} options.keyName - Exact key name
 * @param {string} options.service - Service name
 * @param {Array<string>} options.tags - Required tags (AND logic)
 * @returns {Promise<Object>} - Key data with decrypted API key
 */
async function getKey(options = {}) {
  const { keyName, service, tags } = options;

  const db = getDB();

  try {
    let query = `
      SELECT id, service, key_name, purpose, tags, encrypted_key,
             encryption_method, created_at, last_used, notes
      FROM config.api_keys
      WHERE is_active = true
    `;

    const params = [];
    let paramCount = 0;

    if (keyName) {
      params.push(keyName);
      query += ` AND key_name = $${++paramCount}`;
    }

    if (service) {
      params.push(service);
      query += ` AND service = $${++paramCount}`;
    }

    if (tags && tags.length > 0) {
      params.push(JSON.stringify(tags));
      query += ` AND tags @> $${++paramCount}::jsonb`;
    }

    query += ` ORDER BY created_at DESC LIMIT 1`;

    const result = await db.query(query, params);

    if (result.rows.length === 0) {
      throw new Error(`No API key found matching criteria: ${JSON.stringify(options)}`);
    }

    const row = result.rows[0];

    // Decrypt the API key
    const apiKey = decryptKey(row.encrypted_key);

    // Update last_used timestamp
    await db.query(
      `UPDATE config.api_keys SET last_used = NOW() WHERE id = $1`,
      [row.id]
    );

    return {
      id: row.id,
      service: row.service,
      keyName: row.key_name,
      purpose: row.purpose,
      tags: Array.isArray(row.tags) ? row.tags : JSON.parse(row.tags),
      apiKey: apiKey,  // DECRYPTED
      createdAt: row.created_at,
      lastUsed: row.last_used,
      notes: row.notes,
    };

  } finally {
    await db.end();
  }
}

/**
 * List all API keys (WITHOUT decrypting)
 * @param {Object} options
 * @param {string} options.service - Filter by service
 * @param {boolean} options.includeInactive - Include inactive keys
 * @returns {Promise<Array<Object>>} - List of keys (encrypted_key excluded)
 */
async function listKeys(options = {}) {
  const { service, includeInactive = false } = options;

  const db = getDB();

  try {
    let query = `
      SELECT id, service, key_name, purpose, tags, encryption_method,
             created_at, last_used, is_active, notes
      FROM config.api_keys
    `;

    const conditions = [];
    const params = [];
    let paramCount = 0;

    if (!includeInactive) {
      conditions.push('is_active = true');
    }

    if (service) {
      params.push(service);
      conditions.push(`service = $${++paramCount}`);
    }

    if (conditions.length > 0) {
      query += ' WHERE ' + conditions.join(' AND ');
    }

    query += ' ORDER BY service, key_name';

    const result = await db.query(query, params);

    return result.rows.map(row => ({
      id: row.id,
      service: row.service,
      keyName: row.key_name,
      purpose: row.purpose,
      tags: Array.isArray(row.tags) ? row.tags : JSON.parse(row.tags),
      encryptionMethod: row.encryption_method,
      createdAt: row.created_at,
      lastUsed: row.last_used,
      isActive: row.is_active,
      notes: row.notes,
    }));

  } finally {
    await db.end();
  }
}

/**
 * Deactivate API key (soft delete)
 * @param {string} keyName - Key name to deactivate
 */
async function deactivateKey(keyName) {
  const db = getDB();

  try {
    const result = await db.query(
      `UPDATE config.api_keys SET is_active = false WHERE key_name = $1 RETURNING id`,
      [keyName]
    );

    if (result.rows.length === 0) {
      throw new Error(`Key not found: ${keyName}`);
    }

    return result.rows[0].id;

  } finally {
    await db.end();
  }
}

/**
 * Delete API key permanently
 * @param {string} keyName - Key name to delete
 */
async function deleteKey(keyName) {
  const db = getDB();

  try {
    const result = await db.query(
      `DELETE FROM config.api_keys WHERE key_name = $1 RETURNING id`,
      [keyName]
    );

    if (result.rows.length === 0) {
      throw new Error(`Key not found: ${keyName}`);
    }

    return result.rows[0].id;

  } finally {
    await db.end();
  }
}

/**
 * Log key usage (for tracking)
 * @param {number} keyId - Key ID
 * @param {Object} usage
 * @param {string} usage.taskType - Task type
 * @param {string} usage.workflow - Workflow name
 * @param {number} usage.tokensUsed - Tokens consumed
 * @param {number} usage.costUsd - Cost in USD
 */
async function logKeyUsage(keyId, usage) {
  const { taskType, workflow, tokensUsed, costUsd } = usage;

  const db = getDB();

  try {
    await db.query(`
      INSERT INTO config.key_usage_log (
        key_id, task_type, workflow, tokens_used, cost_usd
      ) VALUES ($1, $2, $3, $4, $5)
    `, [keyId, taskType, workflow, tokensUsed, costUsd]);

  } finally {
    await db.end();
  }
}

/**
 * Get key for task context (automatic selection)
 * @param {Object} context
 * @param {string} context.service - Service needed
 * @param {string} context.taskType - Task type (e.g., 'redhat_code_review')
 * @returns {Promise<Object>} - Selected key with decrypted API key
 */
async function getKeyForContext(context) {
  const { service, taskType } = context;

  // Determine required tags based on task type
  const requiredTags = [];

  if (taskType && taskType.startsWith('redhat_')) {
    requiredTags.push('redhat');
    requiredTags.push('work');
  } else if (taskType && taskType.includes('personal')) {
    requiredTags.push('personal');
  }

  // Try to get key with required tags first
  try {
    return await getKey({ service, tags: requiredTags });
  } catch (error) {
    // Fallback: get any active key for this service
    return await getKey({ service });
  }
}

module.exports = {
  // Encryption
  encryptKey,
  decryptKey,

  // Key management
  addKey,
  getKey,
  listKeys,
  deactivateKey,
  deleteKey,

  // Usage tracking
  logKeyUsage,

  // Smart selection
  getKeyForContext,
};
