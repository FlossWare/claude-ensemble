# Canary Testing Guide - ai-prompt.js Fleet Migration

## Purpose
Validate fleet migration fixes on ai-prompt.js before deploying to all 31 remaining workflows.

## Test Duration
24 hours from initial deployment (2026-06-13 00:00 to 2026-06-14 00:00)

## Pre-Deployment Checklist

- [ ] FLEET_REMOTE_EXECUTION=false in ~/.bashrc
- [ ] Phase 2 blocks removed from ai-prompt.js
- [ ] agent() converted to _agent()
- [ ] fleet-agent-wrapper dynamic import added
- [ ] Schema validation enabled in fleet-remote-executor.js
- [ ] Model compliance implemented (matchesModelPattern, checkModelCompliance, isModelAllowed)
- [ ] path_restrictions configured in ~/.claude/fleet.json
- [ ] Model filtering working in ai-prompt.js workflow

## Canary Testing Procedures

### Test 1: Basic Execution (Immediate)
```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Test 1a: Local execution
export FLEET_REMOTE_EXECUTION=false
node -e "import('./workflows/ai-prompt.js').then(w => console.log('✓ Local load OK'))"

# Test 1b: With fleet env (should fallback)
export FLEET_DISPATCHER=true
node -e "import('./workflows/ai-prompt.js').then(w => console.log('✓ Fleet fallback OK'))"
```

**Success Criteria**: Both complete without errors

### Test 2: Integration Test (Within 1 hour)
```bash
# Run actual ai-prompt workflow
export FLEET_REMOTE_EXECUTION=false

# Simple test prompt
node -e "
import('./workflows/ai-prompt.js').then(w => w.default({test: true}))
  .then(r => console.log('✓ Workflow OK', r.status))
  .catch(e => console.error('✗ Workflow failed', e.message))
"
```

**Success Criteria**:
- Workflow completes in < 30 seconds
- No fleet-related errors in output
- Status shows 'completed'

### Test 3: Repeated Execution (Throughout 24h)
```bash
# Run every 2 hours for 24 hours
for hour in {0..12}; do
  echo "Test run #$hour at $(date)"
  FLEET_REMOTE_EXECUTION=false node workflows/ai-prompt.js --test
  
  # Check for errors
  if [ $? -ne 0 ]; then
    echo "✗ CANARY FAILED at hour $hour"
    exit 1
  fi
  
  sleep 7200  # Wait 2 hours
done

echo "✓ CANARY PASSED - All 24h tests successful"
```

**Success Criteria**:
- All runs complete successfully
- Execution time consistent (no degradation)
- Zero fleet-related errors
- Zero compliance violations

### Test 4: Log Analysis (Throughout 24h)
```bash
# Monitor for fleet-related messages
tail -f ~/.claude/logs/*.log | grep -i "fleet\|dispatcher\|remote"

# Expected: No matches (fleet should be quiet)
# If matches appear: Canary has failed, investigate
```

### Test 5: Model Compliance (Immediate)
```bash
# Test 5a: Check model filtering in Red Hat directory
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

node -e "
import('./shared/model-compliance.js').then(m => {
  const models = ['opus', 'sonnet', 'haiku', 'gemini', 'gpt-4o', 'fable'];
  const allowed = m.filterAllowedModels(models);
  
  console.log('Allowed models in Red Hat dir:', allowed);
  
  // Check that gpt-4o is filtered out
  if (!allowed.includes('gpt-4o')) {
    console.log('✓ GPT-4o correctly denied (gpt-* pattern)')
  } else {
    console.log('✗ GPT-4o should be denied but was allowed')
  }
  
  // Check that opus is allowed
  if (allowed.includes('opus')) {
    console.log('✓ Opus correctly allowed (not in denied list)')
  } else {
    console.log('✗ Opus should be allowed but was denied')
  }
})
"

# Expected output:
# Allowed models in Red Hat dir: [ 'opus', 'sonnet', 'haiku', 'gemini', 'fable' ]
# ✓ GPT-4o correctly denied
# ✓ Opus correctly allowed
```

### Test 5b: Performance Baseline (Immediate + After 24h)
```bash
# Record baseline (before 24h test)
echo "Baseline Test"
time node workflows/ai-prompt.js --measure

# After 24h, compare with same command
echo "Final Test"
time node workflows/ai-prompt.js --measure

# Expected: Times within 10% variance
```

## Failure Scenarios

### Scenario 1: Workflow Errors
**If**: `node workflows/ai-prompt.js` exits with error
**Action**:
1. Check error message
2. Review recent changes in ai-prompt.js
3. Verify fleet-agent-wrapper exists or is optional
4. **DECISION**: Rollback to backup if critical

### Scenario 2: Fleet Unexpectedly Activates
**If**: Logs show remote execution despite FLEET_REMOTE_EXECUTION=false
**Action**:
1. Verify `FLEET_REMOTE_EXECUTION=false` is set: `echo $FLEET_REMOTE_EXECUTION`
2. Check ~/.bashrc was updated correctly
3. **DECISION**: This is a blocker - do not proceed with migration

### Scenario 3: Performance Degradation
**If**: Execution time increases > 20%
**Action**:
1. Profile with `node --prof`
2. Check for new imports or overhead
3. Verify fleet-agent-wrapper isn't being loaded on local runs
4. **DECISION**: Investigate, may indicate wrapper issues

### Scenario 4: Intermittent Failures
**If**: Some runs fail, some succeed
**Action**:
1. Collect error logs from 3+ failed runs
2. Look for patterns (time-based, memory-based, etc.)
3. **DECISION**: Investigate thoroughly before proceeding

## Success Criteria - Go/No-Go Decision

### GO (Proceed with migration)
- ✅ 100% of 24h test runs complete successfully
- ✅ Zero fleet-related errors in logs
- ✅ No compliance violations detected
- ✅ Performance within 10% of baseline
- ✅ Manual testing confirms local-only execution

### NO-GO (Rollback and investigate)
- ❌ Any test run fails with error
- ❌ Fleet activates despite FLEET_REMOTE_EXECUTION=false
- ❌ Performance degrades > 20%
- ❌ Compliance violations detected
- ❌ Intermittent failures appear

## Approval Sign-Off

After completing 24h of testing:

```bash
# If GO: Create canary success record
date > /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/.canary-success-20260614

# Then migrate remaining 31 workflows
bash /tmp/migrate-remaining-workflows.sh

# If NO-GO: Rollback
bash /tmp/rollback-fleet-fixes.sh
```

---

Canary Start: [Record start time]
Canary End: [Record end time]
Result: [GO / NO-GO]
Approved By: [Name]
Date: [Date]
