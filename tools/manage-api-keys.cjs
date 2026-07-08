#!/usr/bin/env node
/**
 * API Key Management CLI
 *
 * Usage:
 *   node tools/manage-api-keys.cjs add <service> <key-name> <api-key> --purpose "..." --tags tag1,tag2
 *   node tools/manage-api-keys.cjs list [service]
 *   node tools/manage-api-keys.cjs get <key-name>
 *   node tools/manage-api-keys.cjs deactivate <key-name>
 *   node tools/manage-api-keys.cjs delete <key-name>
 *
 * Examples:
 *   # Add work Gmail key
 *   node tools/manage-api-keys.cjs add gmail work-gmail "xxx" --purpose "Red Hat work email" --tags redhat,work
 *
 *   # Add personal Gmail key
 *   node tools/manage-api-keys.cjs add gmail personal-gmail "yyy" --purpose "Personal email" --tags personal
 *
 *   # List all keys
 *   node tools/manage-api-keys.cjs list
 *
 *   # Get specific key (decrypted)
 *   node tools/manage-api-keys.cjs get work-gmail
 */

const {
  addKey,
  getKey,
  listKeys,
  deactivateKey,
  deleteKey,
} = require('../shared/api-key-manager.cjs');

const COMMANDS = {
  add: cmdAdd,
  list: cmdList,
  get: cmdGet,
  deactivate: cmdDeactivate,
  delete: cmdDelete,
  help: cmdHelp,
};

async function cmdAdd(args) {
  const [service, keyName, apiKey] = args;

  if (!service || !keyName || !apiKey) {
    console.error('Usage: add <service> <key-name> <api-key> [--purpose "..."] [--tags tag1,tag2]');
    process.exit(1);
  }

  // Parse optional flags
  const purposeIdx = process.argv.indexOf('--purpose');
  const tagsIdx = process.argv.indexOf('--tags');
  const notesIdx = process.argv.indexOf('--notes');

  const purpose = purposeIdx !== -1 ? process.argv[purposeIdx + 1] : '';
  const tags = tagsIdx !== -1 ? process.argv[tagsIdx + 1].split(',') : [];
  const notes = notesIdx !== -1 ? process.argv[notesIdx + 1] : '';

  console.log(`Adding API key: ${keyName} (${service})`);
  console.log(`Purpose: ${purpose}`);
  console.log(`Tags: ${tags.join(', ')}`);

  const keyId = await addKey({
    service,
    keyName,
    apiKey,
    purpose,
    tags,
    notes,
  });

  console.log(`✓ Key added successfully! ID: ${keyId}`);
  console.log('');
  console.log('IMPORTANT: The API key is now encrypted and stored in PostgreSQL.');
  console.log(`To retrieve it: node tools/manage-api-keys.cjs get ${keyName}`);
}

async function cmdList(args) {
  const [service] = args;

  console.log('API Keys:');
  console.log('─────────────────────────────────────────');

  const keys = await listKeys({ service });

  if (keys.length === 0) {
    console.log('No keys found.');
    return;
  }

  for (const key of keys) {
    const active = key.isActive ? '✓' : '✗';
    const tags = key.tags.join(', ');
    const lastUsed = key.lastUsed ? new Date(key.lastUsed).toLocaleDateString() : 'never';

    console.log('');
    console.log(`${active} ${key.keyName} (${key.service})`);
    console.log(`  Purpose: ${key.purpose || 'none'}`);
    console.log(`  Tags: ${tags || 'none'}`);
    console.log(`  Created: ${new Date(key.createdAt).toLocaleDateString()}`);
    console.log(`  Last used: ${lastUsed}`);
    console.log(`  Encryption: ${key.encryptionMethod}`);
    if (key.notes) {
      console.log(`  Notes: ${key.notes}`);
    }
  }

  console.log('');
  console.log(`Total: ${keys.length} keys`);
}

async function cmdGet(args) {
  const [keyName] = args;

  if (!keyName) {
    console.error('Usage: get <key-name>');
    process.exit(1);
  }

  const key = await getKey({ keyName });

  console.log('API Key Details:');
  console.log('─────────────────────────────────────────');
  console.log(`Name: ${key.keyName}`);
  console.log(`Service: ${key.service}`);
  console.log(`Purpose: ${key.purpose || 'none'}`);
  console.log(`Tags: ${key.tags.join(', ')}`);
  console.log(`Created: ${new Date(key.createdAt).toLocaleString()}`);
  console.log(`Last used: ${key.lastUsed ? new Date(key.lastUsed).toLocaleString() : 'never'}`);
  console.log('');
  console.log('⚠️  DECRYPTED API KEY (do not share):');
  console.log(`    ${key.apiKey}`);
  console.log('');
  console.log('Notes:', key.notes || 'none');
}

async function cmdDeactivate(args) {
  const [keyName] = args;

  if (!keyName) {
    console.error('Usage: deactivate <key-name>');
    process.exit(1);
  }

  const keyId = await deactivateKey(keyName);
  console.log(`✓ Key deactivated: ${keyName} (ID: ${keyId})`);
  console.log('The key is still in the database but marked inactive.');
  console.log(`To permanently delete: node tools/manage-api-keys.cjs delete ${keyName}`);
}

async function cmdDelete(args) {
  const [keyName] = args;

  if (!keyName) {
    console.error('Usage: delete <key-name>');
    process.exit(1);
  }

  console.log(`⚠️  WARNING: This will PERMANENTLY delete the key: ${keyName}`);
  console.log('Press Ctrl+C to cancel, or wait 5 seconds to continue...');

  await new Promise(resolve => setTimeout(resolve, 5000));

  const keyId = await deleteKey(keyName);
  console.log(`✓ Key permanently deleted: ${keyName} (ID: ${keyId})`);
}

function cmdHelp() {
  console.log(`
API Key Management CLI

Usage:
  node tools/manage-api-keys.cjs <command> [args]

Commands:
  add <service> <key-name> <api-key> [--purpose "..."] [--tags tag1,tag2] [--notes "..."]
      Add a new API key

  list [service]
      List all API keys (optional: filter by service)

  get <key-name>
      Get API key details (decrypted)

  deactivate <key-name>
      Deactivate API key (soft delete)

  delete <key-name>
      Permanently delete API key

  help
      Show this help message

Examples:
  # Add work Gmail key
  node tools/manage-api-keys.cjs add gmail work-gmail "xxx" --purpose "Red Hat work" --tags redhat,work

  # Add personal OpenAI key
  node tools/manage-api-keys.cjs add openai personal-openai "sk-xxx" --purpose "Personal projects" --tags personal

  # List all Gmail keys
  node tools/manage-api-keys.cjs list gmail

  # Get decrypted key
  node tools/manage-api-keys.cjs get work-gmail

Environment:
  API_KEY_ENCRYPTION_KEY must be set (64 hex characters)
  Generate one with: openssl rand -hex 32

Security:
  - Keys are encrypted at rest using AES-256-GCM
  - Encryption key stored in environment variable (never in database)
  - Each key has its own random IV (initialization vector)
  - Authentication tag prevents tampering
`);
}

async function main() {
  const [,, command, ...args] = process.argv;

  if (!command || command === 'help') {
    cmdHelp();
    process.exit(0);
  }

  const handler = COMMANDS[command];

  if (!handler) {
    console.error(`Unknown command: ${command}`);
    console.error('Run "node tools/manage-api-keys.cjs help" for usage.');
    process.exit(1);
  }

  try {
    await handler(args);
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

main();
