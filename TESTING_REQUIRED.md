# Testing Required - Fleet Orchestration System

**Status:** Code complete, testing incomplete
**Created:** 2026-07-01
**Priority:** HIGH - Production deployment blocked until testing complete

## Summary

Built 4 major systems this session:
1. Worker auto-registration (port 8002)
2. API proxy with autostorage (port 8000)
3. Worker HTTP daemon (port 8003, replaces SSH)
4. Fleet Control API (port 8004, remote orchestration)

**Only #1 and #2 are fully tested. #3 and #4 need comprehensive testing.**

---

## ✅ TESTED AND WORKING

### 1. API Proxy with Autostorage (port 8000)
- ✅ All 8 workers tested
- ✅ All 3 code paths (primary, fallback, cache) store to PostgreSQL
- ✅ X-Worker-ID header working
- ✅ Autostorage table verified (19 entries)
- **Status:** PRODUCTION READY

### 2. Worker Registry (port 8002)
- ✅ All 8 workers registered
- ✅ Heartbeat every 60s working
- ✅ Active worker detection (2-min timeout)
- ✅ Dynamic topology loading
- ✅ Fleet orchestrator using registry
- **Status:** PRODUCTION READY

---

## ⚠️ PARTIALLY TESTED

### 3. Failure Detection and Handling
**What works:**
- ✅ Health checks prevent using unavailable workers
- ✅ Automatic failover to healthy workers

**What needs testing:**
- ❌ Failure reporting to registry (code exists but not incrementing failure_count)
- ❌ Status progression: active → degraded (1 failure) → failed (3 failures)
- ❌ Recovery: heartbeat resets failure_count to 0
- ❌ Orchestrator behavior with degraded/failed workers

**Test Plan:**
1. Simulate worker failure (firewall rule, not stopping SSH)
2. Verify orchestrator reports failure to registry
3. Verify failure_count increments
4. Trigger 3 failures, verify status changes to 'failed'
5. Restore worker, send heartbeat, verify status resets to 'active'

---

## ❌ NOT TESTED

### 4. Worker HTTP Daemon (port 8003)
**Implementation:** Complete
**Testing:** Local only (laptop-01)

**What was tested:**
- ✅ Health check endpoint
- ✅ Authentication (Bearer token)
- ✅ File deployment
- ❌ Command execution (blocked by whitelist)

**What needs testing:**
1. Deploy to all 8 workers
2. Test command execution with whitelisted commands:
   - `worker-client.sh "test prompt"`
   - `python3 -c "print('test')"`
   - `node -e "console.log('test')"`
3. Test unauthorized access (no token)
4. Test invalid commands (not in whitelist)
5. Test file deployment to all workers
6. Test concurrent requests (multiple workers in parallel)
7. Test on android-j7 (Termux)

**Deployment script:** `scripts/deploy-worker-daemon.sh`

### 5. Fleet Control API (port 8004)
**Implementation:** Complete
**Testing:** NONE

**What needs testing:**
1. **Dependencies:**
   - Install `requests` library: `pip install requests`
   - Set WORKER_AUTH_TOKEN environment variable

2. **Task Submission:**
   ```bash
   curl -X POST http://aio-01:8004/task \
     -H "Content-Type: application/json" \
     -d '{"prompt":"Test task", "model":"llama-3.3-70b-versatile"}'
   ```
   - Verify task stored in fleet.tasks table
   - Verify task executes
   - Verify results stored
   - Retrieve with GET /tasks/{task_id}

3. **Workflow Triggering:**
   ```bash
   curl -X POST http://aio-01:8004/workflow \
     -H "Content-Type: application/json" \
     -d '{"workflow_name":"test-workflow", "args":{}}'
   ```
   - Verify workflow executes
   - Verify results stored

4. **Command Execution:**
   ```bash
   curl -X POST http://aio-01:8004/command \
     -H "Content-Type: application/json" \
     -d '{"command":"uptime", "workers":["server-01"]}'
   ```
   - Verify command executes on worker via port 8003
   - Verify results returned in response
   - Verify results stored in fleet.command_results
   - Retrieve with GET /commands/{command_id}

5. **Status Endpoints:**
   - GET /status - verify worker counts
   - GET /workers - verify worker list

6. **CLI Testing:**
   ```bash
   fleet task "Test from CLI"
   fleet command "uptime" server-01
   fleet status
   fleet workers
   ```

**Deployment:**
```bash
scp admin-api/fleet-control-api.py root@aio-01:/opt/
scp /tmp/fleet-control.service root@aio-01:/etc/systemd/system/
ssh root@aio-01 'systemctl daemon-reload && systemctl enable fleet-control && systemctl start fleet-control'
```

---

## Code Review Needed

### Issues to Review:

1. **fleet-control-api.py:**
   - Line 349+: execute_command() runs sequentially, should be parallel
   - No timeout handling for slow workers
   - No retry logic for failed workers
   - Using requests library (sync) instead of async HTTP

2. **worker-daemon.py:**
   - Command whitelist may be too restrictive
   - No rate limiting (could be DoS'd)
   - shell=True security risk if command contains pipes
   - No logging/audit trail

3. **Failure reporting (fleet-ssh-orchestrator.js):**
   - Lines 229-251: Failure reporting added but not working
   - Need to debug why failure_count not incrementing

4. **Authentication:**
   - All APIs use same WORKER_AUTH_TOKEN
   - Should have different tokens for different APIs
   - No token rotation mechanism

---

## Integration Testing Needed

**End-to-End Scenarios:**

1. **Submit task remotely from phone:**
   - From phone browser: curl aio-01:8004/task
   - Verify task executes on worker
   - Verify autostorage captures it
   - Retrieve results

2. **Cron job triggers workflow:**
   - crontab calls: fleet workflow cleanup
   - Verify workflow executes
   - Verify results stored

3. **Remote command on all workers:**
   - Run: fleet command 'df -h'
   - Verify executes on all 8 workers
   - Verify results returned

4. **Worker failure recovery:**
   - Stop worker
   - Verify marked as failed after timeout
   - Restart worker
   - Verify recovers to active

---

## Security Review Needed

1. **Authentication:**
   - Bearer token security
   - Token storage (environment variables)
   - No HTTPS (plain HTTP)

2. **Command execution:**
   - Whitelist effectiveness
   - shell=True injection risk
   - Path traversal in file deployment

3. **Rate limiting:**
   - No rate limits on any API
   - Could overwhelm workers

---

## Performance Testing Needed

1. **Concurrent task submission:**
   - Submit 100 tasks simultaneously
   - Verify workers handle load

2. **Large command output:**
   - Run command with 10MB+ output
   - Verify doesn't crash

3. **Worker timeout behavior:**
   - Submit task to dead worker
   - Verify timeout and failover

---

## Documentation Needed

1. **Deployment guide**
2. **API reference**
3. **Troubleshooting guide**
4. **Architecture diagram**

---

## Blockers

1. **pi-02 SSH down** - Need to reboot for testing
2. **android-j7 not set up** - Need Termux + SSH
3. **No WORKER_AUTH_TOKEN generated yet**

---

## Next Steps (Priority Order)

1. ✅ Commit all code (DONE)
2. ❌ Fix pi-02 (reboot)
3. ❌ Deploy worker daemon to all 8 workers
4. ❌ Test worker daemon on all workers
5. ❌ Deploy Fleet Control API to aio-01
6. ❌ Test Fleet Control API end-to-end
7. ❌ Fix failure reporting bug
8. ❌ Test failure detection/recovery
9. ❌ Setup android-j7
10. ❌ Security review
11. ❌ Documentation

---

## Estimated Time

- Worker daemon testing: 2 hours
- Fleet Control API testing: 3 hours
- Failure detection fixes: 2 hours
- Integration testing: 2 hours
- Security review: 1 hour
- Documentation: 2 hours

**Total: ~12 hours of testing/fixing work**
