# API Credential Distribution

**Last Updated:** 2026-06-28  
**Audit Scope:** 8 workers + 1 orchestrator  
**Security Model:** Environment variables only (no credential files)

## Overview

This document describes how API credentials are distributed across the fleet for secure access to LLM providers.

## Credential Matrix

| Worker | Providers | Tier | Notes |
|--------|-----------|------|-------|
| **server-01** | groq, deepseek, cerebras, cloudflare, openrouter, google | Free | 8 cores, high RAM |
| **server-02** | groq, deepseek, cerebras, cloudflare, openrouter, google | Free | 8 cores, high RAM |
| **server-03** | groq, deepseek, cerebras, cloudflare, openrouter, google | Free | 8 cores, high RAM |
| **laptop-01** | anthropic, openai, google, groq, deepseek, cerebras, cloudflare, openrouter | Mixed | Development node, runs orchestration |
| **pi-01** | None | None | Lightweight tasks only |
| **pi-02** | None | None | Monitoring + lightweight tasks |
| **desktop-ap** | None | None | API-only, no credentials yet |
| **server-ap** | None | None | API-only, no credentials yet |
| **aio-01** | N/A | N/A | Infrastructure only (not a worker) |

## Provider Details

### Free Tier Providers (server-01/02/03)

All three servers have identical credentials for:

- **Groq**: Fast inference, 30 req/min
  - Env var: `GROQ_API_KEY`
  - Models: llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768

- **DeepSeek**: Code-specialized models
  - Env var: `DEEPSEEK_API_KEY`
  - Models: deepseek-coder, deepseek-chat

- **Cerebras**: Fast inference
  - Env var: `CEREBRAS_API_KEY`
  - Models: llama-3.1-70b

- **Cloudflare**: Workers AI
  - Env var: `CLOUDFLARE_API_KEY`
  - Models: Various via Workers AI

- **OpenRouter**: Multi-provider aggregator
  - Env var: `OPENROUTER_API_KEY`
  - Models: Multiple providers routed through OpenRouter

- **Google**: Gemini API
  - Env var: `GOOGLE_API_KEY` (currently empty on servers)

### Paid Tier Providers (laptop-01 only)

**IMPORTANT:** Only laptop-01 has access to paid APIs per fleet policy.

- **Anthropic**: Claude models
  - Env var: `ANTHROPIC_API_KEY`
  - Models: claude-opus-4, claude-sonnet-4.5, claude-haiku-4
  - Policy: laptop-01 only

- **OpenAI**: GPT models
  - Env var: `OPENAI_API_KEY`
  - Models: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
  - Policy: laptop-01 only

- **Google**: Gemini (paid tier)
  - Env var: `GOOGLE_API_KEY`
  - Models: gemini-2.0-flash-exp, gemini-1.5-pro
  - Policy: laptop-01 only (if using paid tier)

### Unconfigured Workers

**pi-01, pi-02, desktop-ap, server-ap** have no API credentials configured. These workers are available for:
- Lightweight computational tasks
- Local model inference (when local models enabled)
- Monitoring and metrics collection

## Security Best Practices

### 1. Environment Variables Only

**DO:**
- Store credentials in `~/.bashrc` or `~/.profile`
- Use `export` to make available to processes
- Keep credentials out of version control

**DON'T:**
- Store credentials in files (e.g., `~/.config/*/credentials`)
- Commit credentials to git
- Log or print credential values

### 2. Access Control

**Policy Enforcement:**
- Paid APIs (Anthropic, OpenAI) restricted to laptop-01
- Free APIs distributed across server-01/02/03
- Pre-flight checks validate worker has required credentials

**Implementation:**
```javascript
const { hasCredential } = require('./shared/credential-manager.cjs');

if (!hasCredential('anthropic', 'laptop-01')) {
  throw new Error('Anthropic API only allowed on laptop-01');
}
```

### 3. Credential Storage Format

**On server-01/02/03 (`~/.bashrc`):**
```bash
export GROQ_API_KEY="gsk_..."
export OPENROUTER_API_KEY="sk-or-v1-..."
export CEREBRAS_API_KEY="csk-..."
export DEEPSEEK_API_KEY="sk-..."
export CLOUDFLARE_API_KEY="cfat_..."
export GOOGLE_API_KEY=""
```

**On laptop-01:**
```bash
# Same as servers, plus:
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

### 4. Validation

**Pre-flight check before routing:**
```javascript
const { validateCredentials } = require('./shared/credential-manager.cjs');

const validation = validateCredentials();
if (!validation.valid) {
  console.error('Credential issues:', validation.issues);
}
```

## Usage

### Basic Usage

```javascript
const { getCredentialForProvider } = require('./shared/credential-manager.cjs');

// Get Groq API key for server-01
const groqKey = getCredentialForProvider('groq', 'server-01');

// Get Anthropic API key for laptop-01
const anthropicKey = getCredentialForProvider('anthropic', 'laptop-01');
```

### Routing with Credentials

```javascript
const { getWorkersForProvider, getCredentialForProvider } = require('./shared/credential-manager.cjs');

// Find all workers that can use Groq
const groqWorkers = getWorkersForProvider('groq');
// Returns: ['server-01', 'server-02', 'server-03', 'laptop-01']

// Route task to first available worker
const worker = groqWorkers[0];
const apiKey = getCredentialForProvider('groq', worker);

// Make API call with credential
await makeGroqCall(apiKey, prompt);
```

### Pre-flight Validation

```javascript
const { validateCredentials, hasCredential } = require('./shared/credential-manager.cjs');

// Validate all credentials
const validation = validateCredentials();
if (!validation.valid) {
  console.error('Missing credentials:', validation.issues);
  process.exit(1);
}

// Check specific worker/provider
if (!hasCredential('anthropic', 'laptop-01')) {
  console.error('Anthropic API not configured on laptop-01');
}
```

## Adding New Providers

### 1. Add Environment Variable Mapping

Edit `shared/credential-manager.cjs`:
```javascript
const PROVIDER_ENV_MAP = {
  // ... existing providers ...
  'newprovider': 'NEWPROVIDER_API_KEY'
};
```

### 2. Configure Credentials on Workers

SSH to each worker and add to `~/.bashrc`:
```bash
export NEWPROVIDER_API_KEY="your-key-here"
```

Source the file:
```bash
source ~/.bashrc
```

### 3. Update Credential Matrix

Edit `CREDENTIAL_MATRIX` in `shared/credential-manager.cjs`:
```javascript
const CREDENTIAL_MATRIX = {
  'server-01': {
    providers: ['groq', 'deepseek', ..., 'newprovider'],
    tier: 'free'
  },
  // ... update other workers ...
};
```

### 4. Update Fleet Policy

Edit `lib/fleet-api-policy.json`:
```json
{
  "free_apis": [
    {
      "provider": "newprovider",
      "models": ["model-1", "model-2"],
      "rate_limit": "varies",
      "notes": "Description"
    }
  ]
}
```

### 5. Validate

Run validation:
```javascript
const { validateCredentials } = require('./shared/credential-manager.cjs');
const validation = validateCredentials();
console.log(validation);
```

## Security Issues Identified

### 1. Hardcoded Credentials in Shell Files ⚠️

**Issue:** API keys are stored in plaintext in `~/.bashrc` files.

**Severity:** MEDIUM - Keys are exposed if shell files are accidentally committed or shared.

**Mitigation:**
- Never commit shell files to git
- Use `.gitignore` for `~/.bashrc`, `~/.profile`
- Consider using secret management system (e.g., HashiCorp Vault)

**Status:** ACCEPTED - Environment variables are the standard for local development

### 2. Shared Credentials Across Workers ⚠️

**Issue:** server-01/02/03 share identical API keys.

**Severity:** LOW - If one key is compromised, all three servers affected.

**Mitigation:**
- Use separate API keys per worker when possible
- Monitor API usage for anomalies
- Implement key rotation strategy

**Status:** ACCEPTED - Free tier providers typically limit to one key per account

### 3. No Credential Rotation ⚠️

**Issue:** No automated credential rotation implemented.

**Severity:** LOW - Credentials never expire unless manually rotated.

**Mitigation:**
- Implement `rotateCredentials()` function
- Schedule periodic rotation (e.g., every 90 days)
- Test rotation in staging before production

**Status:** TODO - Placeholder function exists in credential-manager.cjs

### 4. Google API Key Empty on Servers ℹ️

**Issue:** `GOOGLE_API_KEY=''` on server-01/02/03 (empty string).

**Severity:** INFO - Not a security issue, just incomplete configuration.

**Mitigation:**
- Either configure Google API key or remove the empty export
- Update credential matrix to reflect actual state

**Status:** TODO - Decide if Google API should be configured on servers

### 5. Pi Workers Have No Credentials ℹ️

**Issue:** pi-01 and pi-02 have no API credentials configured.

**Severity:** INFO - Not a security issue, but limits functionality.

**Mitigation:**
- Configure at least free tier APIs on pi workers for distributed load
- Or document that pi workers are for local/monitoring tasks only

**Status:** ACCEPTED - Pi workers used for lightweight tasks only

## Credential Rotation

### Manual Rotation Process

1. **Generate new API key** from provider dashboard
2. **Update on all workers** (SSH to each):
   ```bash
   ssh claude@server-01 'sed -i "s/OLD_KEY/NEW_KEY/" ~/.bashrc'
   ```
3. **Source updated file**:
   ```bash
   ssh claude@server-01 'source ~/.bashrc'
   ```
4. **Validate new credentials**:
   ```javascript
   const validation = validateCredentials();
   console.log(validation);
   ```
5. **Revoke old key** from provider dashboard

### Automated Rotation (Future)

The `rotateCredentials()` function is a placeholder for future implementation:

```javascript
const { rotateCredentials } = require('./shared/credential-manager.cjs');

// This will implement:
// 1. API call to provider to generate new key
// 2. Update environment variables on all workers
// 3. Verify new credentials work
// 4. Revoke old credentials
await rotateCredentials('groq');
```

## Monitoring

### Credential Usage

Track which workers are using which providers:

```javascript
const { getWorkersForProvider, getCredentialMatrix } = require('./shared/credential-manager.cjs');

// See all workers for a provider
console.log('Groq workers:', getWorkersForProvider('groq'));

// See full credential matrix
console.log('Credential matrix:', getCredentialMatrix());
```

### Failed Authentication

Monitor for authentication failures:

```javascript
try {
  const key = getCredentialForProvider('anthropic', 'server-01');
  // This will return null and log warning
} catch (error) {
  console.error('Credential access failed:', error);
}
```

## Troubleshooting

### Problem: "Worker does not have credentials for provider"

**Cause:** Attempting to use a provider on a worker that doesn't have credentials.

**Solution:**
1. Check credential matrix: `getCredentialMatrix()`
2. Route task to a worker that has the provider
3. Or configure credentials on the worker

### Problem: "Missing PROVIDER_API_KEY on worker"

**Cause:** Environment variable not set or empty.

**Solution:**
1. SSH to worker: `ssh claude@worker-hostname`
2. Check environment: `echo $PROVIDER_API_KEY`
3. Edit `~/.bashrc` and add: `export PROVIDER_API_KEY="..."`
4. Source file: `source ~/.bashrc`
5. Verify: `echo $PROVIDER_API_KEY`

### Problem: "Failed to fetch credential from worker"

**Cause:** SSH connection failed or timed out.

**Solution:**
1. Check worker is online: `ping worker-hostname`
2. Check SSH access: `ssh claude@worker-hostname 'echo OK'`
3. Verify SSH user 'claude' exists on worker
4. Check firewall rules

## References

- Fleet API Policy: `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/lib/fleet-api-policy.json`
- Credential Manager: `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/credential-manager.cjs`
- Fleet Topology: `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/shared/fleet-topology.js`
