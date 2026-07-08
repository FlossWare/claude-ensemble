# Model Compliance Enforcer

**Location:** `~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/`  
**Created:** 2026-07-08

## Purpose

Prevents AI model compliance violations by enforcing path-based restrictions.

## Rules

| Path | Allowed Models | Count |
|------|----------------|-------|
| `~/Development/redhat/scm/gitlab/**` | **Anthropic ONLY** | 4 |
| `~/Development/github/**` | **ALL models** | 10+ |
| Other paths | **ALL models** | 10+ |

## Red Hat Approved Models (4)

**Anthropic Cloud:**
- **fable** (claude-fable-5)
- **opus** (claude-opus-4-8)
- **sonnet** (claude-sonnet-4-6)
- **haiku** (claude-haiku-4-5)

## Red Hat BLOCKED Models

❌ OpenAI (ALL models)  
❌ Google (ALL models)  
❌ DeepSeek (ALL models)  
❌ Groq (ALL models)  
❌ Cerebras (ALL models)  
❌ OpenRouter (ALL models)  
❌ Cloudflare Workers AI (ALL models)

**Reason:** Red Hat compliance - proprietary code cannot be sent to external vendor APIs

## Usage

### CLI

```bash
node model-compliance-enforcer.js <path> <model>

# Example - BLOCKED
node model-compliance-enforcer.js ~/Development/redhat/scm/gitlab/cee/sfloess/disseminator gpt-4o
# ❌ COMPLIANCE VIOLATION: gpt-4o blocked for Red Hat code

# Example - ALLOWED
node model-compliance-enforcer.js ~/Development/redhat/scm/gitlab/cee/sfloess/disseminator fable
# ✅ ALLOWED: Model on Red Hat allowlist

# Example - Personal repo (all allowed)
node model-compliance-enforcer.js ~/Development/github/FlossWare/de-converter gpt-4o
# ✅ ALLOWED: Personal repository - no restrictions
```

### JavaScript API

```javascript
const { validateModelForPath, getAllowedModelsFlat } = require('./model-compliance-enforcer.js');

// Validate specific model
const result = validateModelForPath(
  '/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/disseminator',
  'gpt-4o'
);

if (!result.allowed) {
  throw new Error(result.reason);
  // Error: gpt-4o blocked for Red Hat code: Red Hat compliance - proprietary code cannot be sent to external vendor APIs
}

// Get all allowed models for a path
const models = getAllowedModelsFlat('/home/sfloess/Development/github/FlossWare/de-converter');
console.log(models); // ['ALL']

const redhatModels = getAllowedModelsFlat('/home/sfloess/Development/redhat/scm/gitlab/...');
console.log(redhatModels);
// ['claude-fable-5', 'fable', 'claude-opus-4-8', 'opus', 'claude-sonnet-4-6', 'sonnet', 'claude-sonnet-4-5', 'claude-haiku-4-5', 'haiku']
```

## API Reference

### `validateModelForPath(targetPath, model)`

Validates if a model is allowed for a given path.

**Returns:**
```javascript
{
  allowed: boolean,
  reason: string,
  pathType: 'redhat' | 'personal',
  matchedPath: string | null,
  model: string,
  normalizedModel: string
}
```

### `getAllowedModelsFlat(targetPath)`

Returns array of allowed model names for a path.

**Returns:** `string[]` (or `['ALL']` for unrestricted)

### `getRestrictedModels(targetPath)`

Returns blocked models object for a path.

**Returns:** `object` (or `[]` for unrestricted)

### `getSafeModels(targetPath)`

Returns the allowed models configuration for a path.

**Returns:** `object` (or `'ALL'` for unrestricted)

### `classifyPath(targetPath)`

Classifies a path as 'redhat' or 'personal'.

**Returns:**
```javascript
{
  type: 'redhat' | 'personal',
  rule: object,
  matchedPath: string | null
}
```

## Integration Example

```javascript
// In a workflow or agent caller
const { validateModelForPath } = require('./model-compliance-enforcer.js');

function callAgent(prompt, model, cwd = process.cwd()) {
  // Validate before calling
  const validation = validateModelForPath(cwd, model);
  
  if (!validation.allowed) {
    throw new Error(`[COMPLIANCE] ${validation.reason}`);
  }
  
  // Proceed with agent call
  return agent(prompt, { model });
}

// Usage
try {
  await callAgent('Review this code', 'gpt-4o', '~/Development/redhat/scm/gitlab/...');
} catch (error) {
  console.error(error.message);
  // [COMPLIANCE] gpt-4o blocked for Red Hat code: Red Hat compliance...
  
  // Fallback to compliant model
  await callAgent('Review this code', 'fable', '~/Development/redhat/scm/gitlab/...');
}
```

## Testing

Create a test file:

```javascript
const { validateModelForPath } = require('./model-compliance-enforcer.js');

const tests = [
  { path: '~/Development/redhat/scm/gitlab/test', model: 'fable', expected: true },
  { path: '~/Development/redhat/scm/gitlab/test', model: 'gpt-4o', expected: false },
  { path: '~/Development/github/test', model: 'gpt-4o', expected: true }
];

tests.forEach(t => {
  const result = validateModelForPath(t.path, t.model);
  const pass = result.allowed === t.expected;
  console.log(`${pass ? '✅' : '❌'} ${t.path} + ${t.model}`);
});
```

## Files

- `model-compliance-enforcer.js` - Main enforcement logic (executable + module)
- `README_COMPLIANCE.md` - This documentation

## Notes

- **No local models**: System only has cloud API access (Anthropic, OpenAI, Google, etc.)
- **Default unrestricted**: Unknown paths default to personal (all models allowed)
- **Normalize paths**: `~` expanded to `/home/sfloess`, paths resolved to absolute
- **Case insensitive**: Model names normalized to lowercase for matching
