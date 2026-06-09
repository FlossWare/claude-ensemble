# Attribution Tracking - Know Which AI Said What

**Concept:** Track contributions from each AI model in multi-AI consensus workflows.

**Source:** `shared/attribution.js`  
**Status:** ✅ Proven, ready for FlossWare consensus-ai  
**Issue:** FlossWare/consensus-ai#11

---

## Why This Matters

### The Problem

**Without attribution:**
```
Result: "Found 5 bugs"
```
You don't know:
- Which AI found which bugs?
- Did all AIs agree?
- Were any findings unique to one AI?
- Can you trust this result?

**With attribution:**
```
Result: "Found 5 bugs"
- Bug #1: Opus, Sonnet, GPT-4o ✓ (consensus!)
- Bug #2: Opus, Sonnet ✓ (consensus)
- Bug #3: GPT-4o only (unique - needs verification)
- Bug #4: Opus only (unique - might be false positive)
- Bug #5: Sonnet, GPT-4o ✓ (consensus)

Consensus rate: 60% (3/5 bugs)
```

Now you know:
- ✅ 3 bugs have high confidence (2+ AIs agreed)
- ⚠️ 2 bugs need verification (only 1 AI found them)
- 📊 High consensus = trust the results

---

## How It Works

### 1. Track Worker Contributions

```javascript
const tracker = new AttributionTracker()

// Each worker records what they found
tracker.recordWorker('opus', 'SQL injection in login.js line 42', {
  file: 'login.js',
  line: 42,
  severity: 'critical'
})

tracker.recordWorker('sonnet', 'SQL injection in login.js line 42', {
  file: 'login.js',
  line: 42,
  severity: 'critical'
})

tracker.recordWorker('gpt4', 'XSS vulnerability in dashboard.js', {
  file: 'dashboard.js',
  severity: 'high'
})
```

### 2. Find Consensus

```javascript
const consensus = tracker.findConsensus(2)  // 2+ AIs must agree

// Returns:
[
  {
    text: 'SQL injection in login.js line 42',
    models: ['opus', 'sonnet'],
    count: 2
  }
]
```

### 3. Find Unique Findings

```javascript
const unique = tracker.findUnique()

// Returns:
[
  {
    text: 'XSS vulnerability in dashboard.js',
    model: 'gpt4',
    count: 1
  }
]
```

### 4. Record Arbiter Decision

```javascript
tracker.recordArbiter('opus', 'approve', 'Both findings are valid - SQL injection confirmed by 2 AIs, XSS needs code review')
```

### 5. Generate Report

```javascript
const report = tracker.toMarkdown()
```

Output:
```markdown
# Attribution Report

## Workers
- **opus**: 1 contribution(s)
- **sonnet**: 1 contribution(s)
- **gpt4**: 1 contribution(s)

## Arbiter
- **opus**
  - Reasoning: Both findings are valid...

## Consensus Findings
Found 1 findings with agreement:

1. **opus, sonnet** agreed:
   SQL injection in login.js line 42

## Unique Findings
Found 1 findings from single AI:

1. **gpt4** only:
   XSS vulnerability in dashboard.js

## Statistics
- Total contributions: 3
- Consensus rate: 33.3%
```

---

## Real Example: Code Review Workflow

```javascript
// Code review with attribution
const tracker = new AttributionTracker()

phase('Review')

// Workers review code
const reviews = await parallel([
  () => agent('Review for security bugs', { model: 'opus' }),
  () => agent('Review for security bugs', { model: 'sonnet' }),
  () => agent('Review for security bugs', { model: 'gpt4' })
])

// Record attributions
reviews.forEach(review => {
  review.findings.forEach(finding => {
    tracker.recordWorker(review.model, finding.description, {
      file: finding.file,
      line: finding.line,
      severity: finding.severity
    })
  })
})

phase('Consensus')

const consensus = tracker.findConsensus(2)
const unique = tracker.findUnique()

log(`Consensus: ${consensus.length} findings`)
log(`Unique: ${unique.length} findings`)

// Arbiter validates
const arbiterDecision = await agent(`
  Consensus findings (${consensus.length}):
  ${JSON.stringify(consensus)}
  
  Unique findings (${unique.length}):
  ${JSON.stringify(unique)}
  
  Validate and decide.
`, { model: 'opus' })

tracker.recordArbiter('opus', arbiterDecision.verdict, arbiterDecision.reasoning)

// Final report
console.log(tracker.toMarkdown())
```

---

## Benefits

### 1. Trust Through Transparency

**See what each AI contributed:**
```
Opus found: A, B, C
Sonnet found: A, B, D
GPT-4o found: A, E

Consensus (all 3): A
Consensus (2/3): B
Unique findings: C, D, E (need verification)
```

### 2. Quality Through Consensus

**High consensus = high confidence:**
- 3/3 AIs agree → Very high confidence
- 2/3 AIs agree → High confidence  
- 1/3 AIs agree → Low confidence (verify)

### 3. Diversity Through Unique Findings

**Each AI brings unique perspective:**
- Opus might find architectural issues
- Sonnet might find logic bugs
- GPT-4o might find performance problems

**Don't dismiss unique findings** - they might be valuable insights!

### 4. Debugging Through Attribution

**Know which AI disagreed:**
```
Bug found by: Opus ✓, Sonnet ✗, GPT-4o ✗

Action: Opus might have found something others missed
        OR Opus might have false positive
        → Arbiter investigates
```

---

## Integration with Performance Tracking

**Attribution enables performance learning:**

```javascript
// After workflow completes
const summary = tracker.summarize()

// Record performance
performance.recordTask('opus', 'security', {
  findings: opusFindings.length,
  accuracy: opusConsensus.length / opusFindings.length,
  consensus: summary.consensusRate
})

// Next time, query which model is best at security
const best = performance.getBestModel('security')
// Returns: 'opus' (based on historical accuracy)
```

---

## API Reference

### `AttributionTracker`

**Constructor:**
```javascript
const tracker = new AttributionTracker()
```

**Methods:**

**`recordWorker(model, contribution, metadata)`**
- `model` (string): AI model name ('opus', 'sonnet', 'gpt4', etc.)
- `contribution` (string): What this AI contributed
- `metadata` (object): Optional metadata (file, line, severity, etc.)
- Returns: Record object

**`recordArbiter(model, decision, reasoning, metadata)`**
- `model` (string): Arbiter model name
- `decision` (string): Decision made ('approve', 'reject', etc.)
- `reasoning` (string): Why this decision
- `metadata` (object): Optional metadata
- Returns: Record object

**`findConsensus(threshold = 2)`**
- `threshold` (number): Minimum AIs that must agree
- Returns: Array of consensus findings

**`findUnique()`**
- Returns: Array of unique findings (only 1 AI found)

**`summarize()`**
- Returns: Summary object with workers, arbiter, consensus, unique, stats

**`toMarkdown()`**
- Returns: Formatted markdown report

---

## Migration to FlossWare consensus-ai

**Issue:** https://github.com/FlossWare/consensus-ai/issues/11

**Implementation checklist:**
- [ ] Port `attribution.js` to Python (`attribution.py`)
- [ ] Keep JavaScript version (`attribution.js`)
- [ ] Integrate with `ConsensusOrchestrator`
- [ ] Add attribution to all consensus methods
- [ ] Add `enable_attribution=True` parameter
- [ ] Generate markdown reports
- [ ] Add tests
- [ ] Update README with examples

**Working code available at:**
https://gitlab.cee.redhat.com/sfloess/claude-global-skills/-/blob/main/shared/attribution.js
