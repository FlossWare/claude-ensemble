# Code Review Findings - Fleet Orchestration System
**Date:** 2026-07-01  
**Reviewers:** 4-worker fleet (server-01, laptop-01, pi-01, pi-02)

## Critical Issues (SEVERITY: high)

### 1. worker-daemon.py
- **LINE 123:** Command injection via `subprocess` with user input ⚠️
- **LINE 201:** Path traversal via `os` module with user input ⚠️
- **LINE 91:** No input validation before executing commands ⚠️
- **LINE 22:** No authentication enforcement ⚠️

### 2. fleet-control-api.py
- **LINE 123:** SQL injection via string formatting ⚠️
- **LINE 56:** Missing input validation ⚠️

### 3. worker-registry-service.py (POST /failure)
- **LINE 123:** Race condition on failure_count updates ⚠️
- **LINE 145:** SQL race condition without transactions ⚠️
- **LINE 100:** No transaction handling ⚠️

### 4. fleet-ssh-orchestrator.js
- **LINE 238:** Missing `await` on async registryReporter call ⚠️
- **LINE 265:** Missing `await` on httpClient.get ⚠️

## Medium Severity Issues

### worker-daemon.py
- **LINE 156:** No error handling for file I/O
- **LINE 129:** Subprocess exceptions not caught
- **LINE 41:** No resource limits on task queue
- **LINE 68:** Race condition on shared task_queue

### fleet-control-api.py
- **LINE 201:** Race condition in background tasks
- **LINE 31:** No rate limiting
- **LINE 91:** Database connections not closed

### worker-registry-service.py
- **LINE 90:** Integer overflow potential on failure_count
- **LINE 120:** Inadequate error handling
- **LINE 50:** No input validation

### fleet-ssh-orchestrator.js
- **LINE 245, 252:** Race conditions in failure tracking
- **LINE 259:** Inadequate HTTP error handling

## Low Severity Issues

- worker-daemon.py LINE 136: File descriptor leak in Popen
- fleet-control-api.py LINE 142: Poor error handling in async
- fleet-ssh-orchestrator.js LINE 263: No HTTP timeout configured

## Immediate Actions Required

1. **Fix authentication** - worker-daemon.py has NO auth check
2. **Fix SQL injection** - Use parameterized queries in fleet-control-api.py
3. **Fix command injection** - Properly sanitize commands in worker-daemon.py
4. **Add transactions** - Wrap DB operations in worker-registry-service.py
5. **Fix async/await** - Add missing awaits in fleet-ssh-orchestrator.js
6. **Add input validation** - All user inputs need validation

## Testing Blocked Until Fixed

Cannot proceed with deployment until critical security issues are resolved.
