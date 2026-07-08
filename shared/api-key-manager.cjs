/**
 * API Key Manager - REST API Client
 *
 * SECURITY:
 * - Encryption happens CLIENT-SIDE (this file)
 * - API only stores encrypted keys
 * - Decryption happens CLIENT-SIDE on retrieval
 *
 * Multi-account support:
 * - Store multiple API keys per service (work vs personal Gmail, etc.)
 * - Tag keys by purpose/context (redhat, personal, testing)
 * - Automatic key selection based on task type
 */

const crypto = require('crypto');
const http = require('http');

// Encryption configuration
const ALGORITHM = 'aes-256-gcm';
const KEY_LENGTH = 32; // 256 bits
const IV_LENGTH = 16;  // 128 bits
const AUTH_TAG_LENGTH = 16;

// API endpoint
const API_HOST = process.env.ORCHESTRATOR_API_HOST || 'aio-01';
const API_PORT = process.env.ORCHESTRATOR_API_PORT || 5000;

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
 * Make HTTP request to API
 */
function apiRequest(method, path, data = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: API_HOST,
      port: API_PORT,
      path: `/api${path}`,
      method: method,
      headers: { 'Content-Type': 'application/json' },
      timeout: 5000,
    };

    const req = http.request(options, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(body));
          } catch (e) {
            reject(new Error(`Invalid JSON response: ${body}`));
          }
        } else {
          reject(new Error(`API error: ${res.statusCode} ${body}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('API timeout'));
    });

    if (data) req.write(JSON.stringify(data));
    req.end();
  });
}

/**
 * Add API key to storage
 * @param {Object} keyData
 * @param {string} keyData.service - Service name (e.g., 'gmail', 'openai', 'anthropic')
 * @param {string} keyData.keyName - Unique name (e.g., 'work-gmail', 'personal-openai')
 * @param {string} keyData.apiKey - The actual API key (will be encrypted CLIENT-SIDE)
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

  // ENCRYPT CLIENT-SIDE (API only stores encrypted keys)
  const encryptedKey = encryptKey(apiKey);

  const result = await apiRequest('POST', '/api-keys', {
    service,
    key_name: keyName,
    encrypted_key: encryptedKey,
    purpose,
    tags,
    notes
  });

  return result.id;
}

/**
 * Get API key (with CLIENT-SIDE decryption)
 * @param {Object} options
 * @param {string} options.keyName - Exact key name
 * @returns {Promise<Object>} - Key data with decrypted API key
 */
async function getKey(options = {}) {
  const { keyName } = options;

  if (!keyName) {
    throw new Error('keyName is required');
  }

  const result = await apiRequest('GET', `/api-keys/${encodeURIComponent(keyName)}`);

  // DECRYPT CLIENT-SIDE (API returns encrypted key)
  const apiKey = decryptKey(result.encrypted_key);

  return {
    id: result.id,
    service: result.service,
    keyName: result.key_name,
    purpose: result.purpose,
    tags: result.tags,
    apiKey: apiKey,  // DECRYPTED
    createdAt: result.created_at,
    lastUsed: result.last_used,
    notes: result.notes,
  };
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

  // Determine key name based on task type
  let keyName;
  if (taskType && taskType.startsWith('redhat_')) {
    keyName = `${service}-work`;  // e.g., "gmail-work"
  } else {
    keyName = `${service}-personal`;
  }

  try {
    return await getKey({ keyName });
  } catch (error) {
    // Fallback: try base service name
    keyName = service;
    return await getKey({ keyName });
  }
}

module.exports = {
  // Encryption (client-side only)
  encryptKey,
  decryptKey,

  // Key management (via REST API)
  addKey,
  getKey,
  getKeyForContext,
};
