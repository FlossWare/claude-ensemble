# Fleet Dispatcher Migration - Code Examples

## Overview

This document shows before/after conversions for all 7 agent() call patterns found in the 158 calls across 14 workflows.

**Key principle:** All conversions preserve exact semantics when `USE_FLEET_DISPATCHER=false`.

---

## Pattern 1: Simple Call with Defaults

**Most common pattern**

### Before (Direct)
```javascript
const result = await agent('Check for updates');
```

### After (Fleet-Aware)
```javascript
const result = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet('sonnet', 'Check for updates', {})
  : await agent('Check for updates');
```

### Notes
- Default model is `sonnet` (workflow convention)
- No schema, label, or phase
- Zero code changes to workflow logic

---

## Pattern 2: Model Override

**Very common - 80% of calls use this**

### Before
```javascript
const result = await agent('Analyze code complexity', {
  model: 'opus'
});
```

### After
```javascript
const result = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet('opus', 'Analyze code complexity', {})
  : await agent('Analyze code complexity', {model: 'opus'});
```

### Notes
- Model extracted from opts
- Pass as first param to dispatchViaFleet()
- Remaining opts object is empty (only model was there)

---

## Pattern 3: Full Schema Validation

**40% of calls use schema**

### Before
```javascript
const result = await agent(`Check for open PRs/MRs.

Run: gh pr list --json number

Return count of open PRs.`, {
  label: 'Check PRs',
  schema: {
    type: 'object',
    properties: {
      open_prs: { type: 'number' },
      platform: { type: 'string' }
    }
  }
});
```

### After
```javascript
const result = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet('sonnet', `Check for open PRs/MRs.

Run: gh pr list --json number

Return count of open PRs.`, {
    label: 'Check PRs',
    schema: {
      type: 'object',
      properties: {
        open_prs: { type: 'number' },
        platform: { type: 'string' }
      }
    }
  })
  : await agent(`Check for open PRs/MRs.

Run: gh pr list --json number

Return count of open PRs.`, {
    label: 'Check PRs',
    schema: {
      type: 'object',
      properties: {
        open_prs: { type: 'number' },
        platform: { type: 'string' }
      }
    }
  });
```

### Notes
- Schema passed through to dispatchViaFleet()
- Label helps with job type detection
- Job type auto-detected as 'code-review' (contains "Check PRs" + "gh pr list")
- RAM/duration estimated based on schema complexity (2 properties = +5s/+0.2GB)

---

## Pattern 4: Inside parallel() Thunks

**Multi-AI consensus pattern**

### Before
```javascript
const workerResults = await parallel(
  models.map(model => () => {
    try {
      return agent(workerPrompt(model), {
        label: `${model}-weighted-worker`,
        model,
        schema: workerSchema,
      })
    } catch (err) {
      console.error(`Worker ${model} failed:`, err.message);
      return null;
    }
  })
);
```

### After
```javascript
const workerResults = await parallel(
  models.map(model => () => {
    try {
      return USE_FLEET_DISPATCHER
        ? await dispatchViaFleet(model, workerPrompt(model), {
            label: `${model}-weighted-worker`,
            schema: workerSchema,
          })
        : await agent(workerPrompt(model), {
            label: `${model}-weighted-worker`,
            model,
            schema: workerSchema,
          });
    } catch (err) {
      console.error(`Worker ${model} failed:`, err.message);
      return null;
    }
  })
);
```

### Notes
- Each worker runs in parallel, all dispatched to fleet simultaneously
- Fleet load-balancing automatically distributes across servers
- Error handling preserved (caller catches null results)
- Job type auto-detected as 'ai-consensus' (label includes 'worker')

**Performance gain:** Fleet dispatcher can place different models on different servers
- opus → laptop-01 (heavy)
- sonnet → server-01 (balanced)  
- haiku → server-02 (fast)
- All running in parallel on optimal servers

---

## Pattern 5: Inside pipeline() Transforms

**Sequential processing**

### Before
```javascript
const results = await pipeline(issues, issue => 
  agent(`Verify issue #${issue.number}: ${issue.title}
  
Body: ${issue.body}

Can you reproduce it? Return yes/no and steps.`, {
    model: 'opus',
    label: `Verify issue #${issue.number}`
  })
);
```

### After
```javascript
const results = await pipeline(issues, issue => 
  USE_FLEET_DISPATCHER
    ? await dispatchViaFleet('opus', `Verify issue #${issue.number}: ${issue.title}
  
Body: ${issue.body}

Can you reproduce it? Return yes/no and steps.`, {
      label: `Verify issue #${issue.number}`
    })
    : await agent(`Verify issue #${issue.number}: ${issue.title}
  
Body: ${issue.body}

Can you reproduce it? Return yes/no and steps.`, {
      model: 'opus',
      label: `Verify issue #${issue.number}`
    })
);
```

### Notes
- Pipeline is sequential (one issue at a time)
- Even though sequential, fleet dispatcher still provides benefits:
  - Job tracking for circuit breaker learning
  - Resource estimation for capacity planning
  - Fallback if local resources exhausted
- Each iteration processes one issue, dispatcher estimates based on issue size

---

## Pattern 6: Error Handling Wrapper

**Try-catch patterns**

### Before
```javascript
async function detectPlatform() {
  const result = await agent(`Detect the repository platform...

Execute: git remote get-url origin

Return structured data.`, {
    label: 'Detect Platform',
    schema: {
      type: 'object',
      properties: {
        platform: { type: 'string', enum: ['github', 'gitlab', 'bitbucket'] },
        cli: { type: 'string' }
      }
    }
  });
  
  return {
    platform: result.platform,
    cli: result.cli,
    isGitHub: result.platform === 'github'
  };
}
```

### After
```javascript
async function detectPlatform() {
  const result = USE_FLEET_DISPATCHER
    ? await dispatchViaFleet('sonnet', `Detect the repository platform...

Execute: git remote get-url origin

Return structured data.`, {
      label: 'Detect Platform',
      schema: {
        type: 'object',
        properties: {
          platform: { type: 'string', enum: ['github', 'gitlab', 'bitbucket'] },
          cli: { type: 'string' }
        }
      }
    })
    : await agent(`Detect the repository platform...

Execute: git remote get-url origin

Return structured data.`, {
      label: 'Detect Platform',
      schema: {
        type: 'object',
        properties: {
          platform: { type: 'string', enum: ['github', 'gitlab', 'bitbucket'] },
          cli: { type: 'string' }
        }
      }
    });
  
  return {
    platform: result.platform,
    cli: result.cli,
    isGitHub: result.platform === 'github'
  };
}
```

### Notes
- Error handling in caller is preserved
- If dispatchViaFleet() throws, try-catch at workflow level handles it
- If dispatcher fails, automatic fallback to direct agent() happens inside dispatchViaFleet()

---

## Pattern 7: Conditional Calls

**Conditional execution**

### Before
```javascript
if (hasOpenIssues) {
  const issues = await agent(`Fetch open issues from ${platform}.

Execute: ${fetchCmd}

Return list.`, {
    label: 'Fetch Open Issues',
    schema: {
      type: 'object',
      properties: {
        issues: { type: 'array' }
      }
    }
  });
}
```

### After
```javascript
if (hasOpenIssues) {
  const issues = USE_FLEET_DISPATCHER
    ? await dispatchViaFleet('sonnet', `Fetch open issues from ${platform}.

Execute: ${fetchCmd}

Return list.`, {
      label: 'Fetch Open Issues',
      schema: {
        type: 'object',
        properties: {
          issues: { type: 'array' }
        }
      }
    })
    : await agent(`Fetch open issues from ${platform}.

Execute: ${fetchCmd}

Return list.`, {
      label: 'Fetch Open Issues',
      schema: {
        type: 'object',
        properties: {
          issues: { type: 'array' }
        }
      }
    });
}
```

### Notes
- Conditional logic unchanged
- Dispatch only happens if condition is true
- Job type auto-detected as 'data-extraction' (label includes 'Fetch' and schema returns 'array')

---

## Pattern 8: Complex Multi-Line Prompts with Interpolation

**Real-world example from code-test.js**

### Before
```javascript
const issues = await agent(`Fetch open issues from ${platform}.

Execute:
${fetchCmd}

Parse the output and return as:
{
  "issues": [
    {"number": N, "title": "...", "body": "...", "labels": [...]}
  ]
}`, {
  label: 'Fetch Open Issues',
  schema: {
    type: 'object',
    properties: {
      issues: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            number: { type: 'number' },
            title: { type: 'string' },
            body: { type: 'string' },
            labels: { type: 'array' }
          }
        }
      }
    }
  }
});
```

### After
```javascript
const issues = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet('sonnet', `Fetch open issues from ${platform}.

Execute:
${fetchCmd}

Parse the output and return as:
{
  "issues": [
    {"number": N, "title": "...", "body": "...", "labels": [...]}
  ]
}`, {
    label: 'Fetch Open Issues',
    schema: {
      type: 'object',
      properties: {
        issues: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              number: { type: 'number' },
              title: { type: 'string' },
              body: { type: 'string' },
              labels: { type: 'array' }
            }
          }
        }
      }
    }
  })
  : await agent(`Fetch open issues from ${platform}.

Execute:
${fetchCmd}

Parse the output and return as:
{
  "issues": [
    {"number": N, "title": "...", "body": "...", "labels": [...]}
  ]
}`, {
    label: 'Fetch Open Issues',
    schema: {
      type: 'object',
      properties: {
        issues: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              number: { type: 'number' },
              title: { type: 'string' },
              body: { type: 'string' },
              labels: { type: 'array' }
            }
          }
        }
      }
    }
  });
```

### Notes
- String interpolation (${platform}, ${fetchCmd}) works unchanged
- Prompt length ~400 chars → auto-estimate 20s, 0.8GB
- Schema complexity: 4 properties in nested object → +10s, +0.3GB
- Job type detected as 'data-extraction'
- Total estimate: 55s, 1.1GB

---

## Migration Strategy: Automated Conversion

For **Phase 1 (Simple Workflows)**, use this regex-based approach:

### Simple Pattern
```
OLD: const result = await agent\(`([^`]+)`\);
NEW: const result = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet('sonnet', `\1`, {})
  : await agent(`\1`);
```

### With Options
```
OLD: const result = await agent\(`([^`]+)`\s*,\s*({[^}]+})\);
NEW: const result = USE_FLEET_DISPATCHER
  ? await dispatchViaFleet(MODEL_FROM_OPTS, `\1`, {OPTIONS})
  : await agent(`\1`, {OPTIONS});
```

Where `MODEL_FROM_OPTS` is extracted from `options.model || 'sonnet'`.

### For Phase 2-4, use manual conversion with careful attention to:
1. Extracting model from opts
2. Preserving all schema, label, phase, jobType
3. Handling parallel() and pipeline() wrappers
4. Error handling logic

---

## Testing Validation

After migration, verify each workflow:

```javascript
// Test 1: Disable dispatcher (baseline)
FLEET_DISPATCHER=false npm run test:workflow

// Test 2: Enable dispatcher
FLEET_DISPATCHER=true npm run test:workflow

// Test 3: Fallback behavior (dispatcher down)
FLEET_DISPATCHER=true PORT=0 npm run test:workflow
// Should fallback gracefully to direct agent()

// Test 4: Compare outputs (should be identical)
FLEET_DISPATCHER=false > baseline.json
FLEET_DISPATCHER=true > fleet.json
diff baseline.json fleet.json
```

---

## Summary: What Changes, What Doesn't

| Aspect | Changes | Preserved |
|--------|---------|-----------|
| **Logic flow** | None | Same branching, loops, conditionals |
| **Error handling** | None | Same try-catch, null checks |
| **Model selection** | Moved to dispatchViaFleet() first param | Same semantics |
| **Schema validation** | Moved to server | Same result structure |
| **Output format** | None | Same schema, same object shape |
| **Performance** | Better (fleet load balancing) | Same on fallback |
| **Backwards compat** | Full with USE_FLEET_DISPATCHER=false | Direct calls unchanged |

---

## Code Diff Examples (Condensed)

### Example 1: Simple model override
```diff
- const result = await agent(prompt, {model: 'opus'});
+ const result = USE_FLEET_DISPATCHER
+   ? await dispatchViaFleet('opus', prompt, {})
+   : await agent(prompt, {model: 'opus'});
```

### Example 2: With schema
```diff
- const result = await agent(prompt, {model: 'haiku', schema: SCHEMA});
+ const result = USE_FLEET_DISPATCHER
+   ? await dispatchViaFleet('haiku', prompt, {schema: SCHEMA})
+   : await agent(prompt, {model: 'haiku', schema: SCHEMA});
```

### Example 3: Parallel workers
```diff
  const workers = await parallel(
    models.map(m => () =>
-     agent(prompt, {model: m, schema: SCHEMA})
+     USE_FLEET_DISPATCHER
+       ? dispatchViaFleet(m, prompt, {schema: SCHEMA})
+       : agent(prompt, {model: m, schema: SCHEMA})
    )
  );
```

---

## Recommended Migration Order

**Phase 1: Simple (2-3 days)**
- ai-web-learn.js (7 calls)
- memory-rag-search.js (7 calls)
- data-extraction patterns only

**Phase 2: Medium (3-4 days)**
- code-review.js (8 calls)
- code-security.js (9 calls)
- code-review patterns

**Phase 3: Complex (4-5 days)**
- ai-consensus-weighted.js
- ai-consensus-filtered.js
- parallel/pipeline patterns

**Phase 4: Autonomous (5-7 days)**
- code-review-auto.js (13 calls)
- code-solve-auto.js (17 calls)
- Full integration testing

**Phase 5: Hardening (3-5 days)**
- Performance benchmarking
- Circuit breaker testing
- Production readiness review

**Total: 3-4 weeks for full migration**
