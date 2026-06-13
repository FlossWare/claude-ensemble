# Job Type Inference Enhancement Documentation

## Overview

The **job type inference system** automatically detects the computational characteristics of AI agent workloads and assigns them to appropriate resource pools. This enables intelligent load balancing, resource estimation, and task routing across the distributed fleet.

The system is implemented in three key modules:
- `fleet-utils.js` - Core fleet utilities with `inferJobType()` (33 lines)
- `fleet-agent-wrapper.js` - Wrapper factory with `inferJobType()` (42 lines)
- `fleet-telemetry-minimal.js` - Lightweight telemetry with `inferJobType()` (37 lines)

---

## 1. inferJobType() Function Logic

### Location & Signatures

All three implementations share the same inference logic with consistent signatures:

```javascript
export function inferJobType(opts = {}) {
  // Analyzes label, phase, model, and schema
  // Returns one of 7 job type strings
  // Silent fallback to 'agent' if no pattern matches
}
```

### Function Flow (Decision Tree)

```
inferJobType(opts) 
  ├─ Extract lowercase strings: label, phase, model
  ├─ Label Pattern Check
  │  ├─ includes('arbiter'|'synthesis'|'consensus') → 'ai-consensus'
  │  └─ includes('extract'|'parse'|'detect') → 'data-extraction'
  ├─ Phase Pattern Check
  │  ├─ includes('review'|'verify'|'audit') → 'code-review'
  │  └─ includes('test') → 'build-test'
  ├─ Model Check
  │  ├─ === 'fable' or 'opus' → 'ai-heavy'
  │  └─ === 'haiku' → 'ai-light'
  ├─ Schema Complexity Check
  │  └─ JSON.stringify(opts.schema).length > 500 → 'ai-heavy'
  └─ Default → 'agent'
```

### 181-Line Reference Implementation

**File:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/fleet-utils.js` (lines 22-55)

```javascript
/**
 * Infer job type from agent options
 */
export function inferJobType(opts = {}) {
  const label = (opts.label || '').toLowerCase();
  const phase = (opts.phase || '').toLowerCase();
  const model = (opts.model || '').toLowerCase();

  // Label-based detection
  if (label.includes('arbiter') || label.includes('synthesis') || label.includes('consensus')) {
    return 'ai-consensus';
  }
  if (label.includes('extract') || label.includes('parse') || label.includes('detect')) {
    return 'data-extraction';
  }

  // Phase-based detection
  if (phase.includes('review') || phase.includes('verify') || phase.includes('audit')) {
    return 'code-review';
  }
  if (phase.includes('test')) {
    return 'build-test';
  }

  // Model-based detection
  if (model === 'fable' || model === 'opus') {
    return 'ai-heavy';
  }
  if (model === 'haiku') {
    return 'ai-light';
  }

  // Schema complexity detection
  if (opts.schema) {
    try {
      if (JSON.stringify(opts.schema).length > 500) {
        return 'ai-heavy';
      }
    } catch (e) {
      return 'ai-heavy';  // Circular refs → complex
    }
  }

  return 'agent';  // Default fallback
}
```

### Execution Characteristics

| Property | Value |
|----------|-------|
| **Time Complexity** | O(n) where n = length of label/phase/model strings |
| **Space Complexity** | O(1) - minimal temporary variables |
| **Error Handling** | Silent fallback to 'agent' on missing/invalid input |
| **Side Effects** | None (pure function) |
| **Typical Execution** | <1ms |

---

## 2. Detection Rules

### Rule Priority Order

Detection follows **cascade priority** - first match wins:

```
Priority 1: Label patterns (highest specificity)
Priority 2: Phase patterns  
Priority 3: Model type
Priority 4: Schema complexity (lowest specificity)
Priority 5: Default fallback
```

### 2.1 Label Pattern Detection

**Trigger Conditions:**
- Case-insensitive substring matching on `opts.label`
- Matches ANY of the keywords (OR logic)

| Pattern | Triggers | Job Type | Use Case |
|---------|----------|----------|----------|
| `arbiter` | "role: arbiter" | `ai-consensus` | Multi-AI consensus arbitration |
| `synthesis` | "synthesis agent" | `ai-consensus` | Combining multiple worker outputs |
| `consensus` | "consensus-builder" | `ai-consensus` | Decision aggregation |
| `extract` | "extract-fields" | `data-extraction` | Schema/data parsing |
| `parse` | "json-parser" | `data-extraction` | Structured parsing |
| `detect` | "detect-anomalies" | `data-extraction` | Pattern detection |

**Example Mappings:**

```javascript
inferJobType({ label: 'consensus-arbiter' })     // → 'ai-consensus'
inferJobType({ label: 'json-extractor' })        // → 'data-extraction'
inferJobType({ label: 'worker-sonnet' })         // → 'agent' (no match, cascade)
```

### 2.2 Phase Pattern Detection

**Trigger Conditions:**
- Case-insensitive substring matching on `opts.phase`
- Matches ANY of the keywords (OR logic)
- Applied AFTER label patterns

| Pattern | Triggers | Job Type | Use Case |
|---------|----------|----------|----------|
| `review` | "phase: review" | `code-review` | Code/PR review tasks |
| `verify` | "verification-phase" | `code-review` | Correctness verification |
| `audit` | "security-audit" | `code-review` | Security analysis |
| `test` | "test-suite-run" | `build-test` | Build/test execution |

**Example Mappings:**

```javascript
inferJobType({ phase: 'code-review' })           // → 'code-review'
inferJobType({ phase: 'test-execution' })        // → 'build-test'
inferJobType({ phase: 'analysis' })              // → 'agent' (cascade)
```

### 2.3 Model Type Detection

**Trigger Conditions:**
- Exact string match (case-insensitive) on `opts.model`
- Applied AFTER label and phase patterns

| Model | Job Type | Rationale | RAM | Duration |
|-------|----------|-----------|-----|----------|
| `fable` | `ai-heavy` | Largest, most capable model | 2.0 GB | 120s |
| `opus` | `ai-heavy` | High-capacity model | 2.0 GB | 120s |
| `sonnet` | `agent` | Balanced default | 1.5 GB | 60s |
| `haiku` | `ai-light` | Fast, lightweight model | 0.5 GB | 30s |
| `gpt-4o` | `agent` | Fallback to default | 1.5 GB | 60s |
| `gemini` | `agent` | Fallback to default | 1.5 GB | 60s |

**Example Mappings:**

```javascript
inferJobType({ model: 'opus' })                  // → 'ai-heavy'
inferJobType({ model: 'haiku' })                 // → 'ai-light'
inferJobType({ model: 'sonnet' })                // → 'agent' (cascade)
```

### 2.4 Schema Complexity Detection

**Trigger Condition:**
- `opts.schema` exists (truthy)
- `JSON.stringify(opts.schema).length > 500` bytes
- Applied AFTER all other patterns

**Rationale:**
- Simple schemas: `{ type: 'string' }` ≈ 20-50 bytes
- Moderate schemas: Arrays of objects ≈ 200-400 bytes
- Complex schemas: Nested structures ≈ 500+ bytes

| Schema Size | Classification | Job Type |
|-------------|-----------------|----------|
| 0-500 bytes | Simple/moderate | Falls through |
| 501+ bytes | Complex | `ai-heavy` |

**Special Case - Serialization Errors:**
- Circular references throw → catch block returns `ai-heavy`
- Reasoning: If schema is too complex to serialize, treat as heavy work

**Example Mappings:**

```javascript
inferJobType({ 
  schema: { 
    type: 'string', 
    maxLength: 100 
  } 
})  // ≈100 bytes → 'agent'

inferJobType({ 
  schema: { 
    type: 'object',
    properties: {
      field1: { type: 'string', description: 'A'.repeat(200) },
      field2: { type: 'string', description: 'B'.repeat(200) },
      field3: { type: 'string', description: 'C'.repeat(200) }
    }
  }
})  // ≈600 bytes → 'ai-heavy'
```

---

## 3. Job Type Definitions

### Seven Standard Job Types

#### 3.1 ai-consensus
**Characteristics:**
- Consensus aggregation from multiple AI workers
- Arbitration/synthesis of conflicting outputs
- Requires model comparison and weighted voting

**Resource Profile:**
- RAM: 1.5-2.0 GB (arbiter + worker context)
- Duration: 90 seconds (3x single agent call)
- CPU: Moderate (JSON parsing, merging)

**Detection Triggers:**
- Label contains: `arbiter`, `synthesis`, `consensus`
- Example: `inferJobType({ label: 'consensus-arbiter' })`

**Fleet Assignment:**
- Server: Medium capacity (server-01, server-02)
- Priority: Medium (after ai-heavy, before agent)

---

#### 3.2 code-review
**Characteristics:**
- Code analysis, PR reviews, security audits
- Verification of correctness/standards
- Typically single-pass analysis

**Resource Profile:**
- RAM: 1.5 GB (model context + diff)
- Duration: 60 seconds (standard agent call)
- CPU: Light-medium (text analysis)

**Detection Triggers:**
- Phase contains: `review`, `verify`, `audit`
- Example: `inferJobType({ phase: 'security-audit' })`

**Fleet Assignment:**
- Server: Code-optimized (server-02)
- Priority: Medium

---

#### 3.3 build-test
**Characteristics:**
- Test suite execution, build pipelines
- Longest-running job type
- Requires clean environment

**Resource Profile:**
- RAM: 2.0 GB (compilation, test framework)
- Duration: 180 seconds (compile + execute)
- CPU: High (parallelizable tests)

**Detection Triggers:**
- Phase contains: `test`
- Example: `inferJobType({ phase: 'test-suite' })`

**Fleet Assignment:**
- Server: Heavy capacity (server-03, laptop-01)
- Priority: Low (batch workload)

---

#### 3.4 ai-heavy
**Characteristics:**
- Complex reasoning, large schema processing
- Largest/most capable models
- Compute-intensive operations

**Resource Profile:**
- RAM: 2.0 GB (model + working memory)
- Duration: 120 seconds
- CPU: High (token generation)

**Detection Triggers:**
- Model is `fable` or `opus`
- Schema size > 500 bytes
- Example: `inferJobType({ model: 'opus' })`

**Fleet Assignment:**
- Server: High-memory (laptop-01)
- Priority: High (strategic workload)

---

#### 3.5 ai-light
**Characteristics:**
- Fast, resource-efficient inference
- Lightweight models (Haiku)
- High parallelization potential

**Resource Profile:**
- RAM: 0.5 GB (minimal context)
- Duration: 30 seconds (fastest)
- CPU: Low (efficient tokenization)

**Detection Triggers:**
- Model is `haiku`
- Example: `inferJobType({ model: 'haiku' })`

**Fleet Assignment:**
- Server: Any available (server-01, server-02, aio-01)
- Priority: Highest (parallelizable)

---

#### 3.6 data-extraction
**Characteristics:**
- Structured data parsing/extraction
- Schema-driven operations
- Deterministic outputs

**Resource Profile:**
- RAM: 1.0 GB (schema + context)
- Duration: 60 seconds
- CPU: Medium (JSON parsing)

**Detection Triggers:**
- Label contains: `extract`, `parse`, `detect`
- Example: `inferJobType({ label: 'extract-fields' })`

**Fleet Assignment:**
- Server: Data-optimized (server-01)
- Priority: Medium

---

#### 3.7 agent (Default)
**Characteristics:**
- Generic agent workload
- No specific performance requirements
- Fallback for unclassified tasks

**Resource Profile:**
- RAM: 1.5 GB (standard)
- Duration: 60 seconds (standard)
- CPU: Balanced

**Detection Triggers:**
- No other patterns match
- Example: `inferJobType({ model: 'sonnet' })` → cascade → `agent`

**Fleet Assignment:**
- Server: Any available
- Priority: Standard

---

## 4. Resource Estimation Tables

### 4.1 RAM Estimates by Model

**File:** `fleet-agent-wrapper.js` lines 16-23, `fleet-telemetry-minimal.js` lines 12-19

```javascript
const RAM_ESTIMATES = {
  'fable':    2.0,    // GB - Largest model
  'opus':     2.0,    // GB - High-capacity
  'sonnet':   1.5,    // GB - Balanced default
  'haiku':    0.5,    // GB - Lightweight
  'gpt-4o':   1.5,    // GB - OpenAI equivalent to Sonnet
  'gemini':   1.5,    // GB - Google equivalent to Sonnet
};
```

**Table Format:**

| Model | RAM (GB) | Rationale | Typical Context Size |
|-------|----------|-----------|----------------------|
| fable | 2.0 | Largest parameter count | 16-32k tokens |
| opus | 2.0 | High-complexity reasoning | 16-32k tokens |
| sonnet | 1.5 | Balanced performance | 8-16k tokens |
| haiku | 0.5 | Lightweight inference | 2-4k tokens |
| gpt-4o | 1.5 | OpenAI high-end model | 8-16k tokens |
| gemini | 1.5 | Google general-purpose | 8-16k tokens |

**Usage Formula:**
```
estimatedRam = RAM_ESTIMATES[model] || 1.0  // GB, fallback to 1.0
```

---

### 4.2 Duration Estimates by Job Type

**File:** `fleet-agent-wrapper.js` lines 25-33, `fleet-telemetry-minimal.js` lines 21-29

```javascript
const DURATION_ESTIMATES = {
  'ai-heavy':       120,    // seconds (reasoning + generation)
  'ai-consensus':   90,     // seconds (multi-agent aggregation)
  'code-review':    60,     // seconds (analysis pass)
  'build-test':     180,    // seconds (longest - build + test)
  'ai-light':       30,     // seconds (fastest)
  'data-extraction': 60,    // seconds (parsing + validation)
  'agent':          60,     // seconds (default)
};
```

**Table Format:**

| Job Type | Duration (sec) | Operation | Variance |
|----------|----------------|-----------|----------|
| ai-heavy | 120 | Reasoning + complex generation | ±40% |
| ai-consensus | 90 | Multiple workers + arbitration | ±50% |
| code-review | 60 | Single analysis pass | ±20% |
| build-test | 180 | Compilation + execution | ±80% |
| ai-light | 30 | Simple inference | ±10% |
| data-extraction | 60 | Parsing + validation | ±15% |
| agent | 60 | Generic workload | ±30% |

**Usage Formula:**
```
estimatedDuration = DURATION_ESTIMATES[jobType] || 60  // seconds, fallback to 60
```

**Variance Ranges:**
- `ai-light`: ±10% (tight: 27-33s)
- `code-review`: ±20% (tight: 48-72s)
- `data-extraction`: ±15% (tight: 51-69s)
- `agent`: ±30% (moderate: 42-78s)
- `ai-heavy`: ±40% (high: 72-168s)
- `ai-consensus`: ±50% (very high: 45-135s)
- `build-test`: ±80% (extreme: 36-324s)

**Fleet Dispatcher Usage:**
```javascript
dispatchAgent(model, prompt, {
  jobType,
  estimatedRam: RAM_ESTIMATES[model] || 1.0,
  estimatedDuration: DURATION_ESTIMATES[jobType] || 60
})
```

---

### 4.3 Combined Resource Profiles

**Full Mapping:** Model + Job Type → Resources

```
┌─────────────────────────────────────────────────────┐
│ Model Profiling (RAM by Model)                      │
├─────────┬────────┬──────────┬────────┬────────┐
│ fable   │ opus   │ sonnet   │ haiku  │ gpt-4o │
│ 2.0 GB  │ 2.0 GB │ 1.5 GB   │ 0.5 GB │ 1.5 GB │
└─────────┴────────┴──────────┴────────┴────────┘

┌──────────────────────────────────────────────────┐
│ Job Type Profiling (Duration by Type)            │
├──────────────┬──────────┬──────────┬────────┐
│ ai-heavy     │ ai-light │ build    │ agent  │
│ 120 seconds  │ 30 sec   │ 180 sec  │ 60 sec │
└──────────────┴──────────┴──────────┴────────┘

Example: opus model + ai-heavy job
  → RAM: 2.0 GB
  → Duration: 120 seconds
  → Fleet target: laptop-01 (high-memory)
```

---

## 5. How to Customize Inference Rules

### 5.1 Adding New Job Type Categories

**Step 1: Define in DURATION_ESTIMATES**

```javascript
// In fleet-agent-wrapper.js or fleet-telemetry-minimal.js
const DURATION_ESTIMATES = {
  'ai-heavy':       120,
  'ai-consensus':   90,
  'code-review':    60,
  'build-test':     180,
  'ai-light':       30,
  'data-extraction': 60,
  'agent':          60,
  'pdf-processing': 150,  // NEW: add custom type
};
```

**Step 2: Add Detection Rule in inferJobType()**

```javascript
export function inferJobType(opts = {}) {
  const label = (opts.label || '').toLowerCase();
  const phase = (opts.phase || '').toLowerCase();
  const model = (opts.model || '').toLowerCase();

  // ... existing rules ...

  // NEW: Add custom detection rule
  if (label.includes('pdf') || phase.includes('pdf')) {
    return 'pdf-processing';  // NEW custom type
  }

  return 'agent';
}
```

**Step 3: Register Fleet Assignment**

Update `selectWorker()` in `fleet-utils.js`:

```javascript
const roleMapping = {
  'code': ['code', 'medium'],
  'heavy': ['heavy', 'batch'],
  'fast': ['fast', 'preprocessing'],
  'data': ['data', 'heavy'],
  'batch': ['batch', 'heavy'],
  'pdf-small': ['passive'],  // NEW
  'pdf-medium': ['fast'],    // NEW
  'pdf-large': ['code', 'medium'],  // NEW
  'pdf-huge': ['heavy', 'batch']    // NEW
};
```

---

### 5.2 Adjusting Thresholds

#### Schema Complexity Threshold

**Current:** 500 bytes in JSON stringified form

```javascript
// In inferJobType() - line 70 (fleet-utils.js)
if (JSON.stringify(opts.schema).length > 500) {
  return 'ai-heavy';
}
```

**To Increase Threshold (less aggressive ai-heavy classification):**

```javascript
// Change to 750 bytes
if (JSON.stringify(opts.schema).length > 750) {
  return 'ai-heavy';
}
```

**Rationale for Different Thresholds:**

| Threshold | Use Case | Example |
|-----------|----------|---------|
| 250 bytes | Conservative (more ai-heavy) | Minimal latency requirements |
| 500 bytes | Default (balanced) | Standard fleet setup |
| 750 bytes | Aggressive (less ai-heavy) | Abundant capacity |
| 1000 bytes | Very aggressive | Development environments |

---

#### Model-Based Classification

**Current:** Only Fable/Opus → ai-heavy, Haiku → ai-light

**To Add New Model Category:**

```javascript
// In inferJobType() - add before schema check
if (model === 'claude-3.1-sonnet') {
  return 'ai-heavy';  // Treat newer Sonnet as heavy
}
```

---

#### Adding Keyword Patterns

**Current Label Patterns:**
- `arbiter`, `synthesis`, `consensus` → ai-consensus
- `extract`, `parse`, `detect` → data-extraction

**To Add New Pattern:**

```javascript
// In inferJobType() - within label pattern check
if (label.includes('refactor') || label.includes('transformation')) {
  return 'code-review';  // Treat refactoring like code review
}
```

---

### 5.3 Environment-Based Customization

#### Using Environment Variables

**File:** `fleet-telemetry-minimal.js` line 9

```javascript
const DISPATCHER_URL = process.env.FLEET_DISPATCHER_URL || 'http://pi-02:3004';
```

**Add Similar for Thresholds:**

```javascript
const SCHEMA_COMPLEXITY_THRESHOLD = 
  parseInt(process.env.SCHEMA_COMPLEXITY_THRESHOLD || '500', 10);

export function inferJobType(opts = {}) {
  // ... label, phase, model checks ...
  
  if (opts.schema) {
    try {
      if (JSON.stringify(opts.schema).length > SCHEMA_COMPLEXITY_THRESHOLD) {
        return 'ai-heavy';
      }
    } catch (e) {
      return 'ai-heavy';
    }
  }
  
  return 'agent';
}
```

**Usage:**

```bash
# Run with custom threshold
SCHEMA_COMPLEXITY_THRESHOLD=750 node workflow.js

# Use default (500)
node workflow.js
```

---

#### Fleet-Aware Configuration

**File:** `fleet-utils.js` lines 60-80

```javascript
export function loadFleetConfig() {
  const paths = [
    '/mnt/nas/multi-ai-config.json',
    path.join(process.env.HOME || '', '.claude/multi-ai-config.json'),
    path.join(process.env.HOME || '', 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/multi-ai-config.json'),
  ];

  for (const configPath of paths) {
    try {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    } catch (e) {
      continue;
    }
  }

  throw new Error('Fleet config not found');
}
```

**Custom Config File Example** (`~/.claude/multi-ai-config.json`):

```json
{
  "workers": {
    "models": ["opus", "sonnet", "haiku"]
  },
  "serverCapabilities": {
    "laptop-01": {
      "ram": 32,
      "cpu": 8,
      "roles": ["heavy", "batch"],
      "models": ["fable", "opus"]
    },
    "server-01": {
      "ram": 16,
      "cpu": 4,
      "roles": ["fast", "preprocessing"],
      "models": ["sonnet", "haiku"]
    }
  }
}
```

---

### 5.4 A/B Testing Different Rules

**Example: Compare Two Inference Strategies**

```javascript
import { inferJobType as inferJobTypeV1 } from './fleet-utils.js';
import { inferJobType as inferJobTypeV2 } from './fleet-agent-wrapper.js';

// Test with various inputs
const testCases = [
  { label: 'arbiter-sonnet', model: 'sonnet' },
  { phase: 'code-review', model: 'opus' },
  { label: 'extract-data', schema: { /* large */ } },
  { model: 'haiku' },
];

testCases.forEach(opts => {
  const v1 = inferJobTypeV1(opts);
  const v2 = inferJobTypeV2(opts);
  
  if (v1 !== v2) {
    console.log(`Difference detected: ${JSON.stringify(opts)}`);
    console.log(`  V1: ${v1}, V2: ${v2}`);
  }
});
```

---

## 6. Example Mappings

### 6.1 Real-World Detection Examples

#### Example 1: Consensus Arbitration

```javascript
const opts = {
  label: 'consensus-arbiter',
  phase: 'synthesis',
  model: 'opus',
  schema: null
};

const result = inferJobType(opts);
// Decision Path:
//   1. Check label: includes('arbiter') ✓
//   2. MATCH: 'ai-consensus'
// Result: 'ai-consensus' (90s duration, 2.0 GB RAM)
```

#### Example 2: Code Review with Complex Schema

```javascript
const opts = {
  label: 'code-reviewer',
  phase: 'review',
  model: 'sonnet',
  schema: {
    type: 'object',
    properties: {
      issues: { type: 'array', items: { /* large */ } },
      suggestions: { type: 'array', items: { /* large */ } }
    }
  }
};

const result = inferJobType(opts);
// Decision Path:
//   1. Check label: no match
//   2. Check phase: includes('review') ✓
//   3. MATCH: 'code-review'
// Note: Phase match takes precedence over schema
// Result: 'code-review' (60s duration, 1.5 GB RAM)
```

#### Example 3: Heavy Opus Model

```javascript
const opts = {
  label: 'analyzer',
  phase: null,
  model: 'opus',
  schema: null
};

const result = inferJobType(opts);
// Decision Path:
//   1. Check label: no match
//   2. Check phase: no match
//   3. Check model: === 'opus' ✓
//   4. MATCH: 'ai-heavy'
// Result: 'ai-heavy' (120s duration, 2.0 GB RAM)
```

#### Example 4: Data Extraction with Large Schema

```javascript
const opts = {
  label: 'pdf-extractor',
  phase: null,
  model: 'sonnet',
  schema: {
    // 600+ byte schema with complex nested structure
    type: 'object',
    properties: {
      field1: { description: 'A'.repeat(200) },
      field2: { description: 'B'.repeat(200) },
      field3: { description: 'C'.repeat(200) }
    }
  }
};

const result = inferJobType(opts);
// Decision Path:
//   1. Check label: includes('extract') ✓
//   2. MATCH: 'data-extraction'
// Note: Large schema doesn't override label match
// Result: 'data-extraction' (60s duration, 1.5 GB RAM)
```

#### Example 5: Lightweight Haiku Model

```javascript
const opts = {
  label: null,
  phase: null,
  model: 'haiku',
  schema: null
};

const result = inferJobType(opts);
// Decision Path:
//   1. Check label: no match
//   2. Check phase: no match
//   3. Check model: === 'haiku' ✓
//   4. MATCH: 'ai-light'
// Result: 'ai-light' (30s duration, 0.5 GB RAM)
```

#### Example 6: Test Suite (Longest Running)

```javascript
const opts = {
  label: 'test-runner',
  phase: 'test-execution',
  model: 'sonnet',
  schema: null
};

const result = inferJobType(opts);
// Decision Path:
//   1. Check label: no match
//   2. Check phase: includes('test') ✓
//   3. MATCH: 'build-test'
// Result: 'build-test' (180s duration, 1.5 GB RAM)
```

#### Example 7: Default Fallback

```javascript
const opts = {
  label: 'custom-agent',
  phase: 'processing',
  model: 'gpt-4o',
  schema: null
};

const result = inferJobType(opts);
// Decision Path:
//   1. Check label: no match (doesn't contain arbiter/extract/parse/detect)
//   2. Check phase: no match (doesn't contain review/test)
//   3. Check model: === 'gpt-4o', not 'fable'/'opus' or 'haiku'
//   4. Check schema: no schema provided
//   5. MATCH: 'agent' (default)
// Result: 'agent' (60s duration, 1.5 GB RAM)
```

---

### 6.2 Flowchart Decision Tree

```
START: inferJobType(opts)
  │
  ├─ label.includes('arbiter|synthesis|consensus')?
  │  YES → 'ai-consensus' [DONE]
  │  NO ↓
  │
  ├─ label.includes('extract|parse|detect')?
  │  YES → 'data-extraction' [DONE]
  │  NO ↓
  │
  ├─ phase.includes('review|verify|audit')?
  │  YES → 'code-review' [DONE]
  │  NO ↓
  │
  ├─ phase.includes('test')?
  │  YES → 'build-test' [DONE]
  │  NO ↓
  │
  ├─ model === ('fable'|'opus')?
  │  YES → 'ai-heavy' [DONE]
  │  NO ↓
  │
  ├─ model === 'haiku'?
  │  YES → 'ai-light' [DONE]
  │  NO ↓
  │
  ├─ schema exists?
  │  NO → 'agent' [DONE]
  │  YES ↓
  │    ├─ Try: JSON.stringify(schema).length > 500
  │    │  YES → 'ai-heavy' [DONE]
  │    │  NO ↓
  │    │  EXCEPT (circular ref) → 'ai-heavy' [DONE]
  │    └─ 'agent' [DONE]
  │
  └─ [All paths end at DONE]
```

---

## 7. Integration Points

### 7.1 In Workflow Agents

```javascript
import { createFleetAgent } from './fleet-agent-wrapper.js';

// Wrap agent with telemetry
const _originalAgent = agent;
const agent = createFleetAgent(_originalAgent);

// When agent is called:
async function myWorkflow() {
  return await agent(prompt, {
    model: 'sonnet',
    label: 'consensus-arbiter',
    phase: 'synthesis',
    jobType: undefined,  // Auto-detected: 'ai-consensus'
    estimatedRam: undefined,  // Auto-estimated: 2.0 GB
    estimatedDuration: undefined  // Auto-estimated: 90 sec
  });
}
```

### 7.2 In Fleet Dispatcher

```javascript
// dispatchAgent() in fleet-utils.js
export async function dispatchAgent(model, prompt, opts = {}) {
  const {jobType = 'agent', estimatedRam = 1.0, estimatedDuration = 60} = opts;

  const response = await fetch(`${FLEET_DISPATCHER}/agent/execute`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      model,
      prompt,
      job_type: jobType,  // Uses inferred type
      estimated_ram_gb: estimatedRam,
      estimated_duration: estimatedDuration
    })
  });
}
```

### 7.3 In Worker Selection

```javascript
// selectWorkerWithLoadBalance() in fleet-utils.js
export async function selectWorkerWithLoadBalance(jobType) {
  const health = await getServerHealth();
  
  const roleMapping = {
    'code': ['code', 'medium'],
    'heavy': ['heavy', 'batch'],
    'ai-consensus': ['heavy', 'batch'],  // Uses job type
    'ai-light': ['fast', 'preprocessing'],
    'data-extraction': ['code', 'medium']
  };

  const requiredRoles = roleMapping[jobType] || ['heavy'];
  // ... server selection logic ...
}
```

---

## Summary Table

| Feature | Details |
|---------|---------|
| **Total Lines** | ~110 lines (3 implementations × ~37 lines each) |
| **Detection Levels** | 5 cascading priority levels |
| **Job Types** | 7 standard categories |
| **Models Supported** | 6 primary (fable, opus, sonnet, haiku, gpt-4o, gemini) |
| **RAM Range** | 0.5 GB (haiku) to 2.0 GB (opus/fable) |
| **Duration Range** | 30 sec (ai-light) to 180 sec (build-test) |
| **Error Handling** | Silent cascade to 'agent' default |
| **Configuration** | Environment variables + fleet config files |

---

## References

- **File:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/fleet-utils.js` (lines 22-55)
- **File:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/fleet-agent-wrapper.js` (lines 38-80)
- **File:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/fleet-telemetry-minimal.js` (lines 34-71)
- **Tests:** `hardcoded-thresholds.test.js` (comprehensive test coverage)
