---
name: session-2026-06-14-fleet-config-audit
description: Fleet configuration audit session - discovered critical inconsistencies across 31 config files
metadata: 
  node_type: memory
  type: learning
  session_date: 2026-06-14
  session_length: very_long
  outcome: audit_completed_issues_created
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Fleet Configuration Audit Session - 2026-06-14

## What We Discovered

Comprehensive audit of all fleet configuration files revealed **deep inconsistencies** across the entire fleet infrastructure.

### Files Audited: 31 Configuration Sources

1. **Primary Configs:**
   - `~/.claude/fleet.json` (declared source of truth)
   - `~/fleet-coordinator/services/pi02-job-queue.py` (Flask orchestrator)
   - `~/fleet-coordinator/hardware-aware-orchestrator.js` (Node.js orchestrator)
   - `multi-ai-config.json` (GitLab repo)

2. **Memory References:**
   - `reference_distributed_fleet.md`
   - `reference_server01_fan_issue.md`
   - `reference_server02_dimm_issue.md`
   - `reference_claude_fleet_deployment.md`

3. **Documentation:**
   - `README.md` (GitLab repo)
   - Various fleet utility scripts and orchestrators

### Critical Conflicts Found: 12 Total

#### 1. laptop-01 Missing from fleet.json (CRITICAL)
- **Issue:** fleet.json doesn't include laptop-01 at all
- **Reality:** laptop-01 exists, used by orchestrators, has 8 CPUs and 31GB RAM
- **Impact:** Workflows using fleet.json cannot route work to laptop-01
- **Files affected:** 5 files reference laptop-01 but fleet.json doesn't have it

#### 2. laptop-01 CPU Count Conflicts (HIGH)
- **Documented:** 4 CPUs in orchestrator files
- **Actual:** 8 CPUs (verified via nproc)
- **Files with wrong count:** hardware-aware-orchestrator.js, pi02-job-queue.py, multi-ai-config.json
- **Files with correct count:** README.md (recently updated)

#### 3. server-02 RAM in fleet.json Wrong (CRITICAL)
- **fleet.json claims:** 31 GB
- **Actual:** 23 GB usable (verified)
- **Impact:** Jobs assigned to server-02 expecting 31GB will fail
- **The DIMM failure story may be wrong:** Verification shows 24GB installed (not 32GB), no DIMM failure detected

#### 4. server-02 DIMM Failure Narrative Questionable (HIGH)
- **Memory doc claims:** 32GB installed, 9GB lost to DIMM failures, 23GB usable
- **Verification shows:** 24GB installed, 23.5GB usable, dimmFailure: false
- **Conclusion:** May simply have 24GB installed, not a DIMM failure at all
- **Files with DIMM story:** reference_server02_dimm_issue.md, hardware-aware-orchestrator.js, README.md

#### 5. aio-01 RAM: Three Different Values (MEDIUM)
- 7 GB: fleet.json, reference_distributed_fleet.md, hardware-aware-orchestrator.js
- 7.4 GB: pi02-job-queue.py, README.md
- 8 GB: multi-ai-config.json
- **Not verified** (couldn't SSH to aio-01 in verification phase)

#### 6. pi-02 RAM: Two Values (LOW)
- 1 GB: fleet.json, reference docs, multi-ai-config.json
- 942 MB: README.md (probably accurate - Raspberry Pi 3B with GPU/firmware overhead)

### Orchestrator Implementation Confusion

**Problem:** Documentation references `pi02-job-queue.py` but this file is NOT in the GitLab repo.

**Reality:**
- `~/fleet-coordinator/services/pi02-job-queue.py` EXISTS (Python/Flask)
- GitLab repo has `pi02-orchestrator-api.cjs` (Node.js)
- Both files exist in different locations
- Unclear which is deployed/running on pi-02

**Line references break:** README references "TODO at line 68" but file isn't in repo.

### Multi-AI Consensus Routing: Planned but Not Implemented

**Documentation claims:** Orchestrator uses 6-model consensus (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini) for job routing.

**Reality:** Line 68 of pi02-job-queue.py has `# TODO: Replace with actual multi-AI consensus call`

**Current implementation:** Simple if/elif heuristics, NOT multi-AI consensus.

**Impact:** README documented aspirational features as if implemented.

## GitLab Issues Created

### #119: Fix fleet.json with accurate machine specifications
- Add laptop-01 (8 CPU, 31GB RAM)
- Fix server-02 to 23GB (not 31GB)
- Update other specs to match reality
- Priority: CRITICAL

### #120: Clarify orchestrator implementation (Python vs Node.js)
- Determine which orchestrator is actually running
- Add missing files to GitLab repo or update docs
- Fix line number references
- Priority: HIGH

### #121: Move fleet-coordinator into GitLab repo
- Reverse symlink direction
- Move ~/fleet-coordinator → repo/fleet-coordinator/
- Create symlink ~/fleet-coordinator → repo location
- Track orchestrator code in git
- Priority: MEDIUM

## Workflows Run

1. **update-readme-simple.js** - REJECTED (1/3 approved, 47.7 avg score)
   - Found that README changes conflicted with fleet.json
   - Revealed deeper config issues

2. **audit-fleet-config.js** - COMPLETED (0/3 approved - too many issues)
   - Discovered 31 config files
   - Found 12 conflicts, 4 missing machines
   - Created 10 issue definitions

3. **review-orchestrator-fleet.js** - IN PROGRESS (wd297hpkd)
   - Fleet-distributed 6-model code review
   - Reviewing all orchestrator code in ~/fleet-coordinator/

## What Didn't Work

### README Update Attempts
- **Attempt 1:** Complex multi-phase workflow using Fable hit Vertex permission issues
- **Attempt 2:** Simplified workflow documented features that don't exist (multi-AI routing, stale detection)
- **Attempt 3:** Would have same issues until underlying configs are fixed

**Lesson:** Can't fix README until we fix the source configs (fleet.json, orchestrator code).

### SSH Access Limitations
- Could not SSH to pi-02 (password required, no key auth)
- Could not verify aio-01 specs
- Limited hardware verification to laptop-01, server-01, server-02

## Key Learnings

### 1. Fleet Configuration is Deeply Broken
Not just a README problem - the entire configuration ecosystem has conflicts:
- Source of truth (fleet.json) missing machines
- Multiple files with different specs for same machine
- Documentation documenting unimplemented features

### 2. Always Verify Before Documenting
The workflow initially documented multi-AI consensus routing as implemented because the services/README.md said so. Code review revealed it's a TODO.

**Saved to:** feedback_always_verify_before_documenting.md

### 3. Orchestrator Code Not in Git is a Problem
Can't track changes, can't reference line numbers in issues, can't commit fixes. Issue #121 will fix this.

### 4. Math.random() Breaks Workflow Resume
Used Math.random() to distribute models - workflow failed. Fixed by using `idx % 6` instead.

**Saved to:** feedback_workflow_no_math_random.md

### 5. fleet.json is NOT the Single Source of Truth
Despite being declared as such, many files have their own specs that differ. True source of truth is the actual hardware.

## Next Session Should

### Immediate Priority: Fix fleet.json (Issue #119)
1. SSH to each machine and verify actual specs
2. Update fleet.json with verified values
3. Add laptop-01 entry
4. Multi-AI review
5. Commit to git (if we move fleet.json to GitLab repo?)

### High Priority: Clarify Orchestrator (Issue #120)
1. Determine which orchestrator runs on pi-02
2. Move orchestrator code into GitLab repo (Issue #121)
3. Update README with accurate implementation status
4. Document TODO features separately from implemented features

### Medium Priority: Implement Multi-AI Routing
Once orchestrator is in git, implement the actual multi-AI consensus routing:
- Replace heuristics with 6-model worker analysis
- Add arbiter synthesis
- Use user's ALWAYS multi-AI policy

### Systematic Config Sync
Create a workflow that:
1. Verifies actual hardware on each machine
2. Updates ALL config files simultaneously
3. Single source of truth approach
4. Multi-AI review before committing

## Files Modified This Session

**NOT committed yet:**
- README.md (multiple attempted updates, all rejected by review)
- Various workflow scripts in /tmp/

**GitLab issues created:**
- #119, #120, #121 (via glab CLI)

## Session Statistics

- **Duration:** Very long session (~155k tokens before compaction, 124k after)
- **Workflows launched:** 5 (3 completed, 1 failed, 1 in progress)
- **Agents spawned:** ~30+ across all workflows
- **Files discovered:** 31 configuration files
- **Conflicts found:** 12 critical/high/medium issues
- **GitLab issues created:** 3
- **Commits made:** 0 (nothing approved for commit)
- **Multi-AI reviews run:** 4 (all rejected - found more issues than they solved)

## Related Memory Files

- feedback_always_multi_ai_review_before_commit.md
- feedback_workflow_no_fs_execsync.md
- reference_claude_fleet_deployment.md
- reference_server02_dimm_issue.md (may need updating)
- reference_distributed_fleet.md (needs laptop-01 added)
