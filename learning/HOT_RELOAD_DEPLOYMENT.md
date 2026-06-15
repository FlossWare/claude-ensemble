# Hot-Reload System Deployment Checklist

## Pre-Deployment Validation

### ✅ 1. Run Test Suite

```bash
cd /home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills

# Run all tests
node learning/test-hot-reload.js

# Expected: 30/30 tests pass
```

**Status**: ✅ All tests passing (30/30)

### ✅ 2. Verify File Structure

```bash
# Core files
ls -l shared/hot-reload.js
ls -l learning/discoveries.json
ls -l learning/apply-discoveries.js
ls -l learning/hot-reload-integration.js

# Modified files
ls -l orchestrator.js
ls -l background-learner.js
ls -l learning/thompson-sampling.js

# Documentation
ls -l learning/HOT_RELOAD_SYSTEM.md
ls -l learning/HOT_RELOAD_QUICKSTART.md
ls -l learning/HOT_RELOAD_IMPLEMENTATION_SUMMARY.md
```

**Status**: ✅ All files present

### ✅ 3. Check Thompson Sampling Cache Interval

```bash
grep "RELOAD_INTERVAL_MS" learning/thompson-sampling.js
```

**Expected**: `const RELOAD_INTERVAL_MS = 5000; // Reload every 5s`

**Status**: ✅ Verified

## Deployment Steps

### Step 1: Initialize Learning Database (if needed)

```bash
# Check if database exists
ls -l ~/.claude/learning/learning.db

# If not, initialize (will be created on first execution)
mkdir -p ~/.claude/learning
```

### Step 2: Start Background Learner

```bash
# Test single run
node background-learner.js

# Check status
node background-learner.js --status

# Start daemon
nohup node background-learner.js --daemon > ~/.claude/logs/learner.log 2>&1 &

# Or with custom interval (10s for faster iteration)
nohup node background-learner.js --daemon --interval 10 > ~/.claude/logs/learner.log 2>&1 &
```

**Verify**:
```bash
# Check process
ps aux | grep background-learner

# Check logs
tail -f ~/.claude/logs/learner.log
```

### Step 3: Enable Debug Logging (optional, for development)

```bash
# In your shell or .bashrc
export HOT_RELOAD_DEBUG=1
export LEARNING_DEBUG=1
```

### Step 4: Verify Hot-Reload in Action

```bash
# Run test workflow
node -e "
import('./learning/hot-reload-integration.js').then(async (mod) => {
  const result = await mod.selectModelWithDiscoveries('code-review', {
    cost_sensitivity: 'medium',
  });
  console.log('Selected:', result);
});
"
```

### Step 5: Monitor Thompson Sampling Updates

```bash
# Watch state file updates
watch -n 1 'stat ~/.claude/learning/bandit-state.json | grep Modify'

# View current state
cat ~/.claude/learning/bandit-state.json | jq '.models'
```

## Integration Checklist

### Workflow Updates

Update your workflows to use hot-reload:

**Before**:
```javascript
import * as orchestrator from './orchestrator.js';
```

**After**:
```javascript
import { hotImport } from './shared/hot-reload.js';
const orchestrator = await hotImport('./orchestrator.js');
```

### Files to Update

- [ ] `skills/ai-consensus.js`
- [ ] `skills/ai-consensus-*.js` (all variants)
- [ ] `skills/ai-pdf-deep-research.js`
- [ ] `skills/ai-web-learn*.js` (all variants)
- [ ] `skills/code-sdlc*.js` (all variants)
- [ ] Any custom workflows using `orchestrator.js`

### Discovery Customization

Edit `learning/discoveries.json` to add project-specific patterns:

```bash
# Edit discoveries
vim learning/discoveries.json

# Validate JSON
cat learning/discoveries.json | jq '.'

# Changes will be live in <5s
```

## Monitoring

### Health Checks

```bash
# 1. Background learner running?
ps aux | grep background-learner | grep -v grep

# 2. Thompson state recent?
stat ~/.claude/learning/bandit-state.json

# 3. Discovery file valid?
cat learning/discoveries.json | jq '.metadata'

# 4. Cache stats
node -e "
import('./shared/hot-reload.js').then(async (mod) => {
  const stats = mod.getCacheStats();
  console.log('Cache:', stats);
});
"
```

### Performance Monitoring

```bash
# Run performance test
node learning/test-hot-reload.js --test=performance --verbose
```

**Expected**:
- Cold import: <1s
- Cached import: <50ms
- Force reload: <1s

### Debug Logging

```bash
# Enable debug mode
export HOT_RELOAD_DEBUG=1
export LEARNING_DEBUG=1

# Run any workflow
node your-workflow.js

# Check logs for:
# - "[hot-reload] Loaded ..."
# - "[hot-reload] Cache hit ..."
# - "[apply-discoveries] Applied ..."
# - "[thompson-sampling] Selection ..."
```

## Rollback Plan

If issues occur, revert changes:

```bash
# 1. Stop background learner
pkill -f background-learner

# 2. Revert orchestrator.js
git checkout orchestrator.js

# 3. Revert background-learner.js
git checkout background-learner.js

# 4. Revert thompson-sampling.js
git checkout learning/thompson-sampling.js

# 5. Remove hot-reload files (if needed)
rm shared/hot-reload.js
rm learning/apply-discoveries.js
rm learning/discoveries.json
rm learning/hot-reload-integration.js
```

## Verification Tests

### Test 1: Code Hot-Swap

```bash
# Terminal 1: Start daemon with fast interval
node background-learner.js --daemon --interval 5

# Terminal 2: Monitor state file
watch -n 1 'cat ~/.claude/learning/bandit-state.json | jq ".updated"'

# Terminal 3: Make a change to background-learner.js
echo "// test change" >> background-learner.js

# Wait 5s, verify daemon picked up change (no restart needed)
```

### Test 2: Thompson State Propagation

```bash
# Terminal 1: Watch state file
watch -n 1 'cat ~/.claude/learning/bandit-state.json | jq ".models.opus"'

# Terminal 2: Record result
node -e "
import('./orchestrator.js').then(async (mod) => {
  await mod.recordResult('opus', 0.95);
  console.log('Result recorded');
});
"

# Verify state updates within 5s
```

### Test 3: Discovery Application

```bash
# Run discovery test
node learning/test-hot-reload.js --test=discovery --verbose

# Expected: All discoveries apply correctly
```

## Production Configuration

### Recommended Settings

```bash
# Background learner interval: 30s (default)
node background-learner.js --daemon --interval 30

# Thompson cache: 5s (already configured)
# Hot-reload cache: 1s code, 5s JSON (already configured)

# Disable debug logging in production
unset HOT_RELOAD_DEBUG
unset LEARNING_DEBUG
```

### Log Rotation

```bash
# Add to logrotate
sudo tee /etc/logrotate.d/claude-learner <<EOF
/home/sfloess/.claude/logs/learner.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
EOF
```

### Systemd Service (optional)

```bash
# Create service file
sudo tee /etc/systemd/system/claude-learner.service <<EOF
[Unit]
Description=Claude Background Learner
After=network.target

[Service]
Type=simple
User=sfloess
WorkingDirectory=/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
ExecStart=/usr/bin/node background-learner.js --daemon --interval 30
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable claude-learner
sudo systemctl start claude-learner

# Check status
sudo systemctl status claude-learner
```

## Troubleshooting

### Issue: Changes not propagating

**Check**:
1. Cache not cleared: `clearCache()`
2. TTL not expired: Wait 1s (code) or 5s (JSON)
3. Force reload: `hotImport(path, { force: true })`

### Issue: Thompson state stale

**Check**:
1. Background learner running: `ps aux | grep background-learner`
2. State file recent: `stat ~/.claude/learning/bandit-state.json`
3. Cache interval: Should be 5s

### Issue: Discoveries not applying

**Check**:
1. Discovery status: `"status": "active"`
2. Confidence threshold: Default 0.7
3. Conditions match: Verify context object
4. JSON valid: `cat learning/discoveries.json | jq '.'`

### Issue: Performance degradation

**Check**:
1. Cache stats: `getCacheStats()`
2. Expired entries: `cleanExpiredCache()`
3. Too many force reloads: Use cached imports
4. TTL too short: Default 1s/5s is optimal

## Success Criteria

- ✅ All tests pass (30/30)
- ✅ Background learner running
- ✅ Thompson state updates <5s
- ✅ Discoveries apply correctly
- ✅ Code changes propagate ~1s
- ✅ Performance benchmarks met
- ✅ No errors in logs
- ✅ Workflows using hot-reload

## Post-Deployment

### Week 1: Monitor

- Check learner logs daily
- Verify Thompson state freshness
- Monitor cache statistics
- Review discovery application

### Week 2: Optimize

- Add project-specific discoveries
- Tune background learner interval
- Optimize cache TTLs if needed
- Profile hot-reload overhead

### Month 1: Analyze

- Review Thompson Sampling effectiveness
- Evaluate discovery impact on quality/cost
- Consider auto-discovery generation
- Plan next enhancements

## Documentation Links

- **Quick Start**: `learning/HOT_RELOAD_QUICKSTART.md`
- **Full Docs**: `learning/HOT_RELOAD_SYSTEM.md`
- **Implementation**: `learning/HOT_RELOAD_IMPLEMENTATION_SUMMARY.md`
- **Tests**: `learning/test-hot-reload.js`

## Support

For issues or questions:
1. Check troubleshooting section above
2. Enable debug logging
3. Run test suite
4. Review documentation

---

**Deployment Date**: 2026-06-13  
**Version**: 1.0.0  
**Status**: ✅ Production Ready
