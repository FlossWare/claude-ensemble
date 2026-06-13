# Integration Guide

**Version**: 12 | **Last Updated**: 2026-06-13 | **Status**: Production Ready

How to integrate, configure, extend, and migrate Claude Global Skills workflows. Includes step-by-step examples, migration guides, and patterns for building new skills.

---

## Table of Contents

- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [First Run Verification](#first-run-verification)
- [Integrating Skills into Your Project](#integrating-skills-into-your-project)
  - [Symlinking Approach](#symlinking-approach)
  - [Direct Invocation](#direct-invocation)
  - [CI/CD Integration](#cicd-integration)
- [Workflow Integration Patterns](#workflow-integration-patterns)
  - [Interactive Workflow Usage](#interactive-workflow-usage)
  - [Autonomous Workflow Usage](#autonomous-workflow-usage)
  - [Continuous SDLC Loop](#continuous-sdlc-loop)
  - [Fleet-Aware Usage](#fleet-aware-usage)
- [Building New Skills](#building-new-skills)
  - [Skill File Structure](#skill-file-structure)
  - [Workflow File Structure](#workflow-file-structure)
  - [Adding Multi-AI Consensus](#adding-multi-ai-consensus)
  - [Adding Fleet Awareness](#adding-fleet-awareness)
  - [Adding Attribution Tracking](#adding-attribution-tracking)
- [Multi-AI Configuration](#multi-ai-configuration)
  - [Configuration File Format](#configuration-file-format)
  - [Strategy Selection](#strategy-selection)
  - [Per-Workflow Override](#per-workflow-override)
  - [Cost vs Quality Tradeoffs](#cost-vs-quality-tradeoffs)
- [Fleet Configuration](#fleet-configuration)
  - [fleet.json Setup](#fleetjson-setup)
  - [SSH Requirements](#ssh-requirements)
  - [NFS Requirements](#nfs-requirements)
  - [Compliance Configuration](#compliance-configuration)
- [Migration Guide](#migration-guide)
  - [From Single-AI to Multi-AI](#from-single-ai-to-multi-ai)
  - [From Hardcoded Models to Config-Driven](#from-hardcoded-models-to-config-driven)
  - [From -bulk/-fleet Variants to Unified Skills](#from--bulk-fleet-variants-to-unified-skills)
  - [From Local to Fleet-Distributed Processing](#from-local-to-fleet-distributed-processing)
  - [From Interactive to Autonomous Mode](#from-interactive-to-autonomous-mode)
- [Integration Examples](#integration-examples)
  - [Example 1: Code Review in GitHub Actions](#example-1-code-review-in-github-actions)
  - [Example 2: Nightly Security Scan](#example-2-nightly-security-scan)
  - [Example 3: Pre-Release Quality Gate](#example-3-pre-release-quality-gate)
  - [Example 4: Custom Consensus Workflow](#example-4-custom-consensus-workflow)
  - [Example 5: Fleet-Distributed PDF Research](#example-5-fleet-distributed-pdf-research)
  - [Example 6: Memory RAG Integration](#example-6-memory-rag-integration)
- [Token Budget Guidelines](#token-budget-guidelines)
- [Error Handling Patterns](#error-handling-patterns)
- [Cross-References](#cross-references)

---

## Getting Started

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Node.js | >= 18 | Workflow execution, ChromaDB client |
| Python 3 | >= 3.8 | RAG features, vector storage |
| Claude Code | Latest | Workflow runtime |
| SSH (key-based) | Any | Fleet distribution (optional) |
| Git | >= 2.x | Version control, worktree isolation |

### Installation

```bash
# Clone the repository
git clone https://gitlab.cee.redhat.com/sfloess/claude-global-skills.git
cd claude-global-skills

# Install Node.js dependencies
npm install

# Install Python dependencies (optional, for RAG features)
pip install -r requirements.txt

# Set up permissions for autonomous execution
./fix-permissions.sh
```

### First Run Verification

```bash
# Verify skills are visible
claude --list-skills
# Should show: code-review, code-solve, ai-prompt, etc.

# Test a simple multi-AI prompt
/ai-prompt "What are the benefits of code review?"

# Verify workflow syntax (no execution)
node --check code-review.js
node --check code-solve.js
```

---

## Integrating Skills into Your Project

### Symlinking Approach

Share components across multiple projects by symlinking into your Claude Code directories:

```bash
# Skills (user-facing definitions)
ln -s /path/to/claude-global-skills/skills ~/.claude/skills

# Workflows (implementations)
ln -s /path/to/claude-global-skills/workflows ~/.claude/workflows

# Shared components (for direct import)
ln -s /path/to/claude-global-skills/shared ~/my-project/shared

# Memory (cross-session learning)
ln -s /path/to/claude-global-skills/memory ~/.claude/projects/<project>/memory
```

After symlinking, all skills are available via `/skill-name` in any Claude Code session.

### Direct Invocation

Invoke skills directly from the command line:

```bash
# Interactive mode (prompts before actions)
/code-review
/code-solve 42
/ai-prompt "Explain rate limiting approaches"

# Autonomous mode (auto-creates issues/PRs)
claude run code-review-auto
claude run code-solve-auto
claude run code-sdlc-auto

# With token budget
claude run code-sdlc +500k
```

### CI/CD Integration

#### GitHub Actions

```yaml
name: Code Quality
on:
  pull_request:
    branches: [main]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Claude Code
        run: npm install -g @anthropic-ai/claude-code
      - name: Run autonomous code review
        run: claude run code-review-auto
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - name: Run security audit
        run: claude run code-security-auto
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

#### GitLab CI

```yaml
code_review:
  stage: review
  script:
    - claude run code-review-auto
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
  tags:
    - claude

security_scan:
  stage: security
  script:
    - claude run code-security-auto --local
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
```

#### Crontab (Nightly Automation)

```bash
# Nightly code review at 2 AM
0 2 * * * cd ~/my-project && claude run code-sdlc-auto +800k

# Weekly security scan on Mondays at 9 AM
0 9 * * 1 cd ~/my-project && claude run code-security-auto

# Monthly test review on the 1st
0 9 1 * * cd ~/my-project && claude run code-test-auto
```

---

## Workflow Integration Patterns

### Interactive Workflow Usage

Interactive workflows prompt for user decisions at key points:

```bash
# Code review with user approval gates
/code-review
# Output: "Found 12 issues (3 critical, 5 major, 4 minor)"
# Prompt: "Create issues for ALL/HIGH_ONLY/CRITICAL_ONLY/NONE?"
# User selects, workflow proceeds accordingly

# Issue solving with review
/code-solve 42
# Shows proposed fix, asks for confirmation before applying

# Full SDLC with decision gates
/code-sdlc
# Pauses between phases for user approval
```

### Autonomous Workflow Usage

Autonomous workflows make decisions based on confidence thresholds:

```bash
# Auto-creates issues for findings with consensus >= 70%
claude run code-review-auto

# Auto-creates PRs for fixes with confidence >= 85%
claude run code-solve-auto

# Runs entire pipeline without human interaction
claude run code-sdlc-auto +500k
```

### Continuous SDLC Loop

Run all SDLC phases repeatedly until the codebase is clean:

```bash
# Via shell script
sdlc-loop.sh 5 500k
# Argument 1: max iterations (default: 5)
# Argument 2: token budget per iteration (default: 200k)

# Via workflow
claude run code-sdlc-auto-continuous iterations=5 budget=500k
```

Each iteration runs: review -> solve -> test -> PR review -> security -> docs -> release notes. The loop exits when an iteration finds zero issues or max iterations are reached.

### Fleet-Aware Usage

Skills auto-detect fleet availability and choose the optimal execution mode:

```bash
# Auto-detect: uses fleet if available AND items exceed threshold
/ai-pdf-deep-research /path/to/many/pdfs/*.pdf
# Output: "Fleet Detection: 3 workers available, 600 items >= 10 threshold"
# Output: "Fleet mode: Distributing 600 PDFs across 3 workers"

# Force local processing (useful for debugging)
/ai-pdf-deep-research /path/to/many/pdfs/*.pdf --local

# Force fleet processing (fails if fleet unavailable)
/ai-pdf-deep-research /path/to/many/pdfs/*.pdf --fleet

# Dry-run fleet distribution (show plan without executing)
./scripts/fleet/bulk-pdf-ingest.sh --dry-run /path/to/pdfs/*.pdf
```

---

## Building New Skills

### Skill File Structure

A skill consists of 1-3 files:

```
skills/
  my-skill.md          # Required: trigger description
  my-skill.sh          # Optional: shell implementation
  my-skill.json        # Optional: slash command configuration
```

**my-skill.md** (trigger description):
```markdown
---
name: my-skill
description: Short description of what the skill does
arguments:
  - name: target
    description: What to analyze
    required: true
---

# My Skill

When the user invokes /my-skill, perform the following:

1. Analyze the target
2. Generate findings
3. Report results
```

### Workflow File Structure

For complex multi-phase skills, create a workflow `.js` file:

```javascript
// CRITICAL: export const meta must be the FIRST meaningful statement
export const meta = {
  name: 'my-skill',
  description: 'What this skill does',
  version: '1.0',
}

// Parse args (handle both string and object)
let parsedArgs = args
if (typeof args === 'string') {
  const trimmed = args.trim()
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try { parsedArgs = JSON.parse(trimmed) }
    catch (e) { parsedArgs = { query: trimmed } }
  } else {
    parsedArgs = { query: trimmed }
  }
}

// Phase 1: Gather data
phase('Gather')
log('Gathering data...')
const data = await agent('Read and analyze the target file...', {
  label: 'gather',
  schema: { type: 'object', properties: { files: { type: 'array' } } }
})

// Phase 2: Multi-AI Analysis
phase('Analysis')
log('Multi-AI analysis...')
const workers = await parallel([
  () => agent(analysisPrompt, { model: 'fable', label: 'fable-worker', schema }),
  () => agent(analysisPrompt, { model: 'opus', label: 'opus-worker', schema }),
  () => agent(analysisPrompt, { model: 'sonnet', label: 'sonnet-worker', schema }),
  () => agent(analysisPrompt, { model: 'haiku', label: 'haiku-worker', schema }),
  () => agent(analysisPrompt, { model: 'gpt-4o', label: 'gpt4o-worker', schema }),
  () => agent(analysisPrompt, { model: 'gemini', label: 'gemini-worker', schema }),
])
const validWorkers = workers.filter(Boolean)

// Phase 3: Arbiter Synthesis
phase('Synthesis')
const synthesis = await agent(arbiterPrompt, {
  model: 'fable',
  label: 'arbiter',
  schema: arbiterSchema,
})

log(`Result: ${synthesis.summary}`)
```

### Adding Multi-AI Consensus

Follow this pattern for every phase that makes a decision:

```javascript
// 1. Workers analyze independently
const workers = await parallel(
  ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'].map(model => () =>
    agent(prompt, {
      model,
      label: `${model}-worker`,
      schema: workerSchema,
    })
  )
)

// 2. Filter failed workers (graceful degradation)
const validWorkers = workers.filter(Boolean)
log(`${validWorkers.length}/6 workers completed`)

// 3. Arbiter synthesizes
const synthesis = await agent(`Review ${validWorkers.length} worker responses:

${validWorkers.map((w, i) => `Worker ${i + 1}: ${JSON.stringify(w)}`).join('\n')}

Select the BEST answer. Explain why. Rate confidence (0-100).`, {
  model: 'fable',
  label: 'arbiter',
  schema: {
    type: 'object',
    properties: {
      winning_worker: { type: 'string' },
      why_selected: { type: 'string' },
      confidence: { type: 'number' },
      result: { /* task-specific */ },
    },
  },
})
```

**When to use multi-AI**: Every phase that analyzes, rates, discovers, validates, or decides.

**When NOT to use multi-AI**: Pure mechanical operations (reading a file, listing files, running a shell command).

### Adding Fleet Awareness

To make a skill fleet-aware, follow the canonical pattern from `ai-pdf-deep-research.js`:

```javascript
import { resolveFleetMode } from './shared/fleet-utils.js';
import { execSync } from 'child_process';

const BREAK_EVEN_THRESHOLD = 20; // Adjust based on per-item processing cost

// 1. Parse fleet-related args
const fleetArgs = (typeof args === 'string' ? args : '').split(/\s+/);
const fleetDecision = resolveFleetMode(fleetArgs, items.length, BREAK_EVEN_THRESHOLD);

log(`Fleet mode: ${fleetDecision.mode} (${fleetDecision.reason})`);

// 2. Branch on fleet decision
if (fleetDecision.mode === 'fleet') {
  // Delegate to fleet bash script
  const scriptPath = `${__dirname}/scripts/fleet/bulk-my-skill.sh`;
  const result = execSync(
    `${scriptPath} ${itemArgs}`,
    { stdio: 'inherit', timeout: 7200000 }
  );
  return { status: 'success', mode: 'fleet', workers_used: fleetDecision.workers.length };
} else {
  // Process locally (existing logic)
  for (const item of items) {
    await processItem(item);
  }
}
```

Then create the corresponding fleet bash script in `scripts/fleet/`:

```bash
#!/bin/bash
source "$(dirname "$0")/fleet-bulk-lib.sh"

fleet_discover_workers
fleet_check_compliance
fleet_init_session "my-skill"
fleet_distribute_roundrobin "$items_file"
fleet_dispatch_workers "/my-skill" "$prompt_template"
fleet_wait_workers
fleet_collect_results
fleet_merge_json "$output_file"
fleet_summary "my-skill" "$start_time" "$total_items"
```

### Adding Attribution Tracking

```javascript
import { AttributionTracker } from './shared/attribution.js';

const tracker = new AttributionTracker();

// Record what each worker found
workers.forEach(worker => {
  worker.findings.forEach(finding => {
    tracker.recordWorker(worker.model, finding.description, {
      file: finding.file,
      severity: finding.severity,
    });
  });
});

// Find consensus and unique findings
const consensus = tracker.findConsensus(2);  // 2+ models agree
const unique = tracker.findUnique();          // only 1 model found it

// Record arbiter decision
tracker.recordArbiter('fable', 'approve', 'All consensus findings validated');

// Generate report
const report = tracker.toMarkdown();
log(report);
```

---

## Multi-AI Configuration

### Configuration File Format

File: `multi-ai-config.json` (project root) or `~/.claude/workflows/multi-ai-config.json`

```json
{
  "enabled": true,
  "default_strategy": "maximum-coverage",
  "workers": {
    "models": ["fable", "opus", "sonnet", "haiku", "gpt-4o", "gemini"],
    "count": 6
  },
  "arbiter": {
    "enabled": true,
    "model": "fable",
    "fallback": ["fable", "opus", "sonnet", "haiku", "gpt-4o", "gemini"]
  },
  "presets": {
    "maximum-coverage": { "workers": { "models": ["fable", "opus", "sonnet", "haiku", "gpt-4o", "gemini"], "count": 6 } },
    "triple-consensus": { "workers": { "models": ["opus", "sonnet", "haiku"], "count": 3 } },
    "fast-consensus": { "workers": { "models": ["haiku", "sonnet", "llama-70b-fast"], "count": 3 } }
  }
}
```

### Strategy Selection

| Strategy | Models | Cost | Use Case |
|----------|--------|------|----------|
| maximum-coverage | 6-9 models | 7-10x | Default. Quality over cost. |
| fleet-balanced | 6 models | 7x | Balanced across fleet servers |
| code-specialist | 4 models | 5x | Code-heavy tasks |
| fast-consensus | 3 fast models | 4x | Speed-sensitive tasks |
| triple-consensus | 3 models | 4x | Minimum meaningful consensus |
| dual-consensus | 2 models | 3x | Lightweight consensus |

### Per-Workflow Override

Override global config in any workflow:

```javascript
// Force single-AI for a phase (skip consensus overhead)
const result = await agent(prompt, { model: 'haiku', schema })

// Force specific model set (ignore config)
const workers = await parallel([
  () => agent(prompt, { model: 'opus', schema }),
  () => agent(prompt, { model: 'sonnet', schema }),
])
```

### Cost vs Quality Tradeoffs

Assuming 1 phase = 50k tokens per agent:

| Mode | Workers | Arbiter | Total Tokens | Cost Multiplier |
|------|---------|---------|--------------|-----------------|
| Single-AI | 0 | No | 50k | 1x |
| Dual | 2 | Yes | 150k | 3x |
| Triple | 3 | Yes | 200k | 4x |
| Quad | 4 | Yes | 250k | 5x |
| Maximum (6) | 6 | Yes | 350k | 7x |
| Maximum (9) | 9 | Yes | 500k | 10x |

**Token budget guidelines by repository size**:

| Repo Size | Recommended Budget | Coverage |
|-----------|-------------------|----------|
| Small (<1k files) | +300k-500k | All phases, moderate depth |
| Medium (1k-5k files) | +500k-800k | All phases, full depth |
| Large (5k+ files) | +800k-1.5M | All phases, maximum thoroughness |

---

## Fleet Configuration

### fleet.json Setup

Create `~/.claude/fleet.json`:

```json
{
  "machines": [
    {
      "hostname": "server-01",
      "role": "worker",
      "memory_gb": 32,
      "cpus": 16,
      "priority": 1,
      "tags": ["compute"],
      "capabilities": ["python", "nodejs", "docker"]
    },
    {
      "hostname": "server-02",
      "role": "worker",
      "memory_gb": 64,
      "cpus": 32,
      "priority": 2,
      "capabilities": ["python", "nodejs"]
    }
  ],
  "policies": {
    "health_check_timeout_ms": 2000,
    "max_parallel_workers": 10
  },
  "compliance": {
    "forbidden_paths": ["/home/user/proprietary/"],
    "reason": "Proprietary work must not leave controlled infrastructure"
  }
}
```

**Key fields**:
- `machines[].role`: `controller` (orchestration), `worker` (compute), `sentinel` (monitoring)
- `machines[].priority`: Lower = higher priority. Workers sorted for assignment.
- `machines[].capabilities`: For filtering (e.g., only workers with Docker)
- `policies.health_check_timeout_ms`: SSH probe timeout (2s is good for LAN)
- `compliance.forbidden_paths`: Directories where fleet mode is blocked

### SSH Requirements

```bash
# Set up key-based authentication to all workers
ssh-copy-id server-01
ssh-copy-id server-02
ssh-copy-id server-03

# Verify BatchMode works (no password prompts)
ssh -o BatchMode=yes server-01 echo OK

# Optional: add to ~/.ssh/config
Host server-01 server-02 server-03
  StrictHostKeyChecking accept-new
  BatchMode yes
```

### NFS Requirements

For fleet distribution to work:

1. `/home/sfloess/Development` must be NFS-exported from the controller to all workers
2. All workers must mount the share at the same path
3. Workers use local `/tmp` for scratch work (avoids NFS write contention)
4. Results are collected via SSH `cat`, not by reading NFS directly

### Compliance Configuration

The compliance system has two layers:

**Layer 1: Fleet Mode Blocking** (`forbidden_paths`) -- All-or-nothing fleet disable per directory:

```json
{
  "compliance": {
    "forbidden_paths": ["/home/sfloess/Development/redhat/"],
    "reason": "Red Hat proprietary work must not leave controlled infrastructure"
  }
}
```

- Any directory under `forbidden_paths` automatically disables fleet mode
- Symlink bypasses are prevented via `fs.realpathSync()`
- Skills fall back silently to local processing (no error)

**Layer 2: Model Restrictions** (`path_restrictions`) -- Selective model deny/allow per directory:

```json
{
  "compliance": {
    "forbidden_paths": ["/home/sfloess/Development/redhat/"],
    "path_restrictions": [
      {
        "path": "/home/sfloess/Development/redhat/",
        "denied_models": ["gpt-*"],
        "reason": "Red Hat compliance - no OpenAI"
      },
      {
        "path": "/home/sfloess/Development/client-work/",
        "allowed_models": ["claude-*"],
        "reason": "Client contract - Anthropic only"
      }
    ],
    "reason": "Red Hat proprietary work must not leave controlled infrastructure"
  }
}
```

- `denied_models`: Block specific model families using wildcard patterns (`gpt-*`, `ollama-*`)
- `allowed_models`: Only permit matching models (all others denied)
- Most specific path wins (longest prefix match takes precedence)
- Multi-AI workflows auto-filter workers and arbiters via `getCompliantWorkers()` and `getCompliantArbiter()` from `shared/model-compliance.js`
- Clear error messages when a model is denied: includes reason and list of alternatives

---

## Migration Guide

### From Single-AI to Multi-AI

**Before** (single model):
```javascript
const result = await agent('Analyze this code for bugs', { model: 'sonnet', schema })
```

**After** (multi-AI consensus):
```javascript
const workers = await parallel(
  ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'].map(model => () =>
    agent('Analyze this code for bugs', { model, label: `${model}-worker`, schema })
  )
)
const validWorkers = workers.filter(Boolean)

const synthesis = await agent(`Review ${validWorkers.length} analyses:
${validWorkers.map((w, i) => `Worker ${i+1}: ${JSON.stringify(w)}`).join('\n')}
Select best. Rate confidence.`, {
  model: 'fable', label: 'arbiter', schema: arbiterSchema
})
```

**Effort**: ~30 minutes per phase. Add workers + arbiter, add `.filter(Boolean)` for graceful degradation.

### From Hardcoded Models to Config-Driven

**Before** (hardcoded):
```javascript
const workers = await parallel([
  () => agent(prompt, { model: 'opus', schema }),
  () => agent(prompt, { model: 'sonnet', schema }),
  () => agent(prompt, { model: 'haiku', schema }),
])
```

**After** (config-driven):
```javascript
// Load config using agent (workflows cannot use fs directly)
const config = await agent(`Read and parse:
cat ${process.env.HOME}/.claude/workflows/multi-ai-config.json 2>/dev/null || echo '{"workers":{"models":["opus","sonnet","haiku"]}}'
Return the JSON.`, { schema: configSchema })

const models = config.workers.models
const workers = await parallel(
  models.map(model => () =>
    agent(prompt, { model, label: `${model}-worker`, schema })
  )
)
```

**Current status**: Config system is documented and ready. Most workflows still use hardcoded lists and will be migrated incrementally.

### From -bulk/-fleet Variants to Unified Skills

**Before** (three separate files):
```
ai-pdf-deep-research.js       # Base skill (local only)
ai-pdf-deep-research-bulk.js   # Bulk processing variant
ai-pdf-deep-research-fleet.js  # Fleet distribution variant
```

**After** (one unified file):
```
ai-pdf-deep-research.js        # Handles local, bulk, AND fleet
```

The unified skill calls `resolveFleetMode()` at the start to determine execution mode. No user action needed -- the deprecated variants still exist but are hidden.

### From Local to Fleet-Distributed Processing

**Step 1**: Add fleet-utils import and threshold constant:
```javascript
import { resolveFleetMode } from './shared/fleet-utils.js';
const BREAK_EVEN_THRESHOLD = 20;
```

**Step 2**: Parse fleet args and resolve mode:
```javascript
const fleetArgs = (typeof args === 'string' ? args : '').split(/\s+/);
const fleetDecision = resolveFleetMode(fleetArgs, items.length, BREAK_EVEN_THRESHOLD);
```

**Step 3**: Branch on mode:
```javascript
if (fleetDecision.mode === 'fleet') {
  // Delegate to fleet script
  execSync(`scripts/fleet/bulk-my-skill.sh ${itemArgs}`, { stdio: 'inherit' });
} else {
  // Existing local logic
}
```

**Step 4**: Create the fleet bash script using `fleet-bulk-lib.sh`.

### From Interactive to Autonomous Mode

**Step 1**: Create `my-skill-auto.js` alongside `my-skill.js`.

**Step 2**: Replace decision prompts with threshold checks:
```javascript
// Interactive version
const decision = await askUser('Create issues for ALL/HIGH_ONLY/NONE?')

// Autonomous version
const highConfidenceFindings = findings.filter(f => f.confidence >= 0.70)
const decision = highConfidenceFindings.length > 0 ? 'HIGH_ONLY' : 'NONE'
```

**Step 3**: Add auto-decision criteria in the meta block:
```javascript
export const meta = {
  name: 'my-skill-auto',
  description: 'Autonomous variant -- auto-creates issues for consensus >= 70%',
  autonomous: true,
}
```

---

## Integration Examples

### Example 1: Code Review in GitHub Actions

```yaml
name: Multi-AI Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Autonomous code review
        run: claude run code-review-auto
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
```

### Example 2: Nightly Security Scan

```bash
#!/bin/bash
# nightly-security.sh - Run from crontab: 0 2 * * * /path/to/nightly-security.sh
cd /path/to/my-project
claude run code-security-auto --local +500k 2>&1 | tee /var/log/security-scan.log

# Optional: send notification on findings
if grep -q "CRITICAL" /var/log/security-scan.log; then
  curl -d "Critical security findings detected!" https://ntfy.sh/my-alerts
fi
```

### Example 3: Pre-Release Quality Gate

```bash
#!/bin/bash
# pre-release.sh - Run before tagging a release
set -e

echo "Step 1: Find and fix all issues"
claude run code-review-and-solve +800k

echo "Step 2: Security audit"
claude run code-security-auto +500k

echo "Step 3: Test quality analysis"
claude run code-test-auto +300k

echo "Step 4: Generate release notes"
claude run code-release-notes-auto

echo "All quality gates passed"
```

### Example 4: Custom Consensus Workflow

```javascript
export const meta = {
  name: 'custom-analysis',
  description: 'Custom multi-AI analysis with weighted consensus',
  version: '1.0',
}

phase('Worker Analysis')

const analysisPrompt = `Analyze this codebase for performance bottlenecks.
Focus on: database queries, memory allocation, API calls, loop complexity.`

const schema = {
  type: 'object',
  properties: {
    bottlenecks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          location: { type: 'string' },
          type: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          confidence: { type: 'number' },
          recommendation: { type: 'string' },
        },
      },
    },
  },
}

const workers = await parallel([
  () => agent(analysisPrompt, { model: 'fable', label: 'fable-perf', schema }),
  () => agent(analysisPrompt, { model: 'opus', label: 'opus-perf', schema }),
  () => agent(analysisPrompt, { model: 'sonnet', label: 'sonnet-perf', schema }),
  () => agent(analysisPrompt, { model: 'haiku', label: 'haiku-perf', schema }),
  () => agent(analysisPrompt, { model: 'gpt-4o', label: 'gpt4o-perf', schema }),
  () => agent(analysisPrompt, { model: 'gemini', label: 'gemini-perf', schema }),
])

const validWorkers = workers.filter(Boolean)
log(`${validWorkers.length}/6 workers completed`)

phase('Arbiter Synthesis')

const arbiterPrompt = `Review ${validWorkers.length} independent performance analyses.
Worker results: ${JSON.stringify(validWorkers)}
Synthesize: select findings with 2+ model agreement, rank by severity.`

const synthesis = await agent(arbiterPrompt, {
  model: 'fable',
  label: 'arbiter',
  schema: {
    type: 'object',
    properties: {
      consensus_bottlenecks: { type: 'array' },
      unique_findings: { type: 'array' },
      overall_assessment: { type: 'string' },
      confidence: { type: 'number' },
    },
  },
})

log(`Found ${synthesis.consensus_bottlenecks.length} consensus bottlenecks`)
log(`Confidence: ${synthesis.confidence}%`)
```

### Example 5: Fleet-Distributed PDF Research

```bash
# Process 200 PDFs about Kubernetes -- auto-distributes across fleet
/ai-pdf-deep-research /path/to/k8s-papers/*.pdf --topic "Kubernetes"

# Expected output:
# Fleet Detection: 3 workers available, 200 items >= 10 threshold
# Fleet mode: Distributing 200 PDFs across 3 workers
#   server-01: 67 PDFs
#   server-02: 66 PDFs (highest memory, gets priority)
#   server-03: 67 PDFs
# Processing...
# Results merged: 847 verified claims, 123 refuted claims
# Report saved to: memory/pdf-research-Kubernetes-best-practices.md
```

### Example 6: Memory RAG Integration

```bash
# Index all memories (run once, then periodically)
claude run memory-rag-index

# Search by meaning (not just keywords)
claude run memory-rag-search query="how to parallelize agents"
# Returns semantically relevant memories even if they don't contain "parallelize"

# Learn from web pages (stores in memory for future RAG queries)
/ai-web-learn https://docs.example.com/api https://docs.example.com/guide
```

---

## Token Budget Guidelines

| Repo Size | Budget | Phases Covered |
|-----------|--------|----------------|
| Small (<1k files) | +300k-500k | All phases, moderate depth |
| Medium (1k-5k files) | +500k-800k | All phases, full depth |
| Large (5k+ files) | +800k-1.5M | All phases, maximum thoroughness |

**Individual workflow costs** (approximate):

| Workflow | Cost | Time | Agent Calls |
|----------|------|------|-------------|
| /code-review | $15-25 | 10-15 min | ~60 |
| /code-solve (single) | $2-4 | 2-5 min | ~5 |
| /code-solve loop | $20-30 | 20-30 min | ~50 |
| /code-security | $10-15 | 8-12 min | ~30 |
| /code-review-and-solve | $40-50 | 25-35 min | ~70 |
| /code-sdlc (full) | $60-100 | 40-60 min | ~100+ |

---

## Error Handling Patterns

### Graceful Model Degradation

Models that fail return `null` and are filtered:

```javascript
const workers = await parallel([
  () => agent(prompt, { model: 'fable', schema }),  // Might fail
  () => agent(prompt, { model: 'opus', schema }),    // Might fail
  () => agent(prompt, { model: 'sonnet', schema }),  // Usually works
])

const validWorkers = workers.filter(Boolean)
// Continue with whatever responded. Even 1 worker is usable.

if (validWorkers.length === 0) {
  log('All workers failed. Falling back to single-model analysis.')
  const fallback = await agent(prompt, { model: 'sonnet', schema })
  return fallback
}
```

### Fleet Fallback

If fleet workers fail (>50%), fall back to local processing:

```javascript
const fleetDecision = resolveFleetMode(args, items.length, threshold)
if (fleetDecision.mode === 'fleet') {
  try {
    return await processViaFleet(items, fleetDecision.workers)
  } catch (e) {
    log(`Fleet failed: ${e.message}. Falling back to local.`)
    return await processLocally(items)
  }
}
```

### Arbiter Fallback Chain

If the primary arbiter fails, try each fallback in order:

```javascript
const fallbackModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
for (const model of fallbackModels) {
  try {
    return await agent(arbiterPrompt, { model, label: 'arbiter', schema })
  } catch (e) {
    log(`${model} arbiter failed, trying next...`)
  }
}
throw new Error('All arbiter models failed')
```

---

## Cross-References

- **[ARCHITECTURE.md](ARCHITECTURE.md)** -- System design, components, architecture decisions
- **[OPERATIONS.md](OPERATIONS.md)** -- Deployment, monitoring, troubleshooting
- **[API_REFERENCE.md](API_REFERENCE.md)** -- Complete API documentation for shared libraries
- **[FLEET_AWARE_SKILLS.md](FLEET_AWARE_SKILLS.md)** -- Detailed fleet-aware skill implementation
- **[MULTI_AI_CONFIG.md](../MULTI_AI_CONFIG.md)** -- Multi-AI configuration details
- **[PERMISSIONS.md](../PERMISSIONS.md)** -- Detailed permissions setup
- **[WORKFLOWS.md](../WORKFLOWS.md)** -- Complete workflow guide
