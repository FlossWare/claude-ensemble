# GitLab Issues TODO - 2026-06-14

## Issues Created This Session

### #117: Fix orchestrator workflow execution end-to-end (OPEN - from previous session)
**Status:** BLOCKED - NFS/autofs conflict prevents service from starting  
**Priority:** HIGH  
**Created:** Previous session  
**Blocks:** All orchestrator functionality

**Problem:**
- Orchestrator service (pi02-job-queue.py) won't start on pi-02
- Static /etc/fstab entry conflicts with autofs
- Service exit code 209/STDOUT

**Requires:**
1. Remove static fstab entry for fleet-coordinator mount
2. Configure autofs on pi-02 instead
3. Restart pi02-orchestrator.service
4. Test workflow execution end-to-end
5. Multi-AI review of execute_workflow() implementation
6. Commit if approved, close issue

**Files affected:**
- `/home/sfloess/fleet-coordinator/services/pi02-job-queue.py` (execute_workflow function)
- `/etc/fstab` on pi-02 (remove line 17)
- `/etc/auto.master` on pi-02 (add autofs config)
- `/etc/auto.home` on pi-02 (create with fleet-coordinator mount)

---

### #119: Fix fleet.json with accurate machine specifications
**Status:** OPEN  
**Priority:** CRITICAL  
**Created:** 2026-06-14 (this session)  
**Blocks:** #120 (README updates), all fleet workflows

**Problem:**
- fleet.json missing laptop-01 entirely
- server-02 shows 31GB but actual is 23GB
- Multiple spec inconsistencies across config files

**Requires:**
1. SSH to each machine and verify actual specs:
   ```bash
   ssh laptop-01 'nproc && free -h'
   ssh server-01 'nproc && free -h'
   ssh server-02 'nproc && free -h && dmesg | grep -i dimm'
   ssh server-03 'nproc && free -h'
   ssh aio-01 'nproc && free -h'  # if accessible
   ssh pi-02 'nproc && free -h'   # if accessible
   ```

2. Update `~/.claude/fleet.json` with verified values:
   - **Add laptop-01:** 8 CPU, 31 GB RAM, role: heavy, can_run_workflows: true
   - **Fix server-02:** Change from 31 GB to 23 GB
   - **Verify aio-01:** Determine if 7 GB, 7.4 GB, or 8 GB
   - **Verify pi-02:** Confirm 1 GB or 942 MB
   - **Add laptop-01 Claude Code deployment:** web/desktop (no CLI)

3. Investigate server-02 DIMM issue:
   - Currently documented as "32GB installed, 9GB lost to DIMM failures"
   - Verification shows "24GB installed, no DIMM failure detected"
   - Determine actual hardware configuration
   - Update `reference_server02_dimm_issue.md` if story is wrong

4. Multi-AI review (3-6 models) of fleet.json changes

5. Consider: Should fleet.json be moved into GitLab repo?
   - Currently in `~/.claude/fleet.json` (not version controlled)
   - Could move to repo for tracking
   - Or keep as user-specific config

6. Commit verified changes, close issue

**Files to update:**
- `~/.claude/fleet.json` (primary)
- `memory/reference_distributed_fleet.md` (add laptop-01)
- `memory/reference_server02_dimm_issue.md` (if DIMM story is wrong)

---

### #120: Clarify orchestrator implementation (Python vs Node.js)
**Status:** OPEN  
**Priority:** HIGH  
**Created:** 2026-06-14 (this session)  
**Depends on:** #121 (moving orchestrator to repo)

**Problem:**
- Documentation references `pi02-job-queue.py` but file isn't in GitLab repo
- GitLab repo has `pi02-orchestrator-api.cjs` (Node.js)
- Both files exist in different locations
- Line number references break (README says "TODO at line 68")

**Requires:**
1. SSH to pi-02 and determine which service is actually running:
   ```bash
   ssh pi-02 'systemctl status pi02-orchestrator'
   ssh pi-02 'ps aux | grep -E "python|node" | grep orchestrator'
   ssh pi-02 'netstat -tlnp | grep :3002'
   ```

2. Document actual implementation:
   - Which file runs on pi-02?
   - What port(s) does it use?
   - Python/Flask or Node.js?

3. After #121 completed (orchestrator in repo):
   - Update README.md with correct file references
   - Fix line number references
   - Document multi-AI consensus as **PLANNED** (not implemented)
   - Add "What Does NOT Exist Yet" section:
     - Multi-AI consensus routing (TODO at line 68)
     - Stale session detection (not implemented)
     - Heartbeat interval enforcement (not implemented)

4. Multi-AI review of documentation updates

5. Commit and close issue

**Files to update:**
- README.md (Fleet Orchestrator section)
- `fleet-coordinator/services/README.md` (fix aspirational claims)

---

### #121: Move fleet-coordinator into GitLab repo and create symlink
**Status:** OPEN  
**Priority:** MEDIUM  
**Created:** 2026-06-14 (this session)  
**Enables:** #120 (orchestrator documentation)

**Problem:**
- `~/fleet-coordinator/` exists outside of GitLab repo
- Orchestrator code not version controlled
- Cannot commit/push orchestrator fixes
- Cannot reference files in GitLab issues

**Requires:**
1. **Prepare:**
   ```bash
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   
   # Verify current symlink
   ls -la fleet-coordinator  # Should show symlink to ~/fleet-coordinator
   
   # Check what's in the directory
   ls -la ~/fleet-coordinator/
   ```

2. **Execute move:**
   ```bash
   # Remove symlink from repo
   rm ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/fleet-coordinator
   
   # Move actual directory into repo
   mv ~/fleet-coordinator ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/fleet-coordinator
   
   # Create reverse symlink (backward compatibility)
   ln -s ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/fleet-coordinator ~/fleet-coordinator
   
   # Verify symlink works
   ls -la ~/fleet-coordinator
   ls -la ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/fleet-coordinator
   ```

3. **Update .gitignore:**
   ```
   fleet-coordinator/logs/
   fleet-coordinator/*.log
   fleet-coordinator/services/*.log
   ```

4. **Add to git:**
   ```bash
   cd ~/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills
   git add fleet-coordinator/
   git add .gitignore
   ```

5. Multi-AI review of the move:
   - Verify no sensitive files included
   - Verify logs excluded
   - Verify symlink maintains backward compatibility

6. If approved:
   ```bash
   git commit -m "Add fleet-coordinator orchestrator service to GitLab repo

   Moved ~/fleet-coordinator/ into repo for version control.
   Created reverse symlink at ~/fleet-coordinator for backward compatibility.
   
   Benefits:
   - Orchestrator code now tracked in GitLab
   - Can commit/push orchestrator fixes
   - GitLab issues can reference file paths
   - Documentation references are accurate
   
   Closes #121
   
   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   
   git push
   glab issue close 121
   ```

7. Verify pi-02 orchestrator still works after symlink change

**Files affected:**
- Everything in `~/fleet-coordinator/` moves to repo
- Symlink created at `~/fleet-coordinator/`
- `.gitignore` updated

---

## Workflow for Fixing These Issues

### Recommended Order:

1. **#121 first** (move orchestrator to repo)
   - Quick, enables other work
   - Makes orchestrator code trackable
   - Required for #120

2. **#119 second** (fix fleet.json)
   - CRITICAL priority
   - Blocks all fleet workflows
   - Verify actual hardware specs
   - Update all config files

3. **#120 third** (clarify orchestrator docs)
   - Depends on #121 being complete
   - Document actual vs planned features
   - Fix file/line references

4. **#117 last** (fix orchestrator execution)
   - Requires NFS/autofs knowledge
   - May need pi-02 SSH access
   - Test end-to-end after fix

### For Each Issue:

1. ✅ Make the fix
2. ✅ Multi-AI review (3-6 models) - **REQUIRED, no exceptions**
3. ✅ Only commit if review approves (APPROVE_COMMIT decision)
4. ✅ If NEEDS_WORK: fix and re-review
5. ✅ If REJECT: investigate alternative approach
6. ✅ Commit locally with Co-Authored-By
7. ✅ Push to GitLab
8. ✅ Close the issue with `glab issue close <number>`

## Additional Work Needed (Not Yet Issues)

### Implement Multi-AI Consensus Routing
**After #119, #120, #121 are complete:**

Create new issue to replace heuristic routing with actual 6-model consensus:
- Line 68 of pi02-job-queue.py has TODO
- Replace if/elif with actual multi-AI analysis
- 6 workers (Fable, Opus, Sonnet, Haiku, GPT-4o, Gemini)
- Arbiter synthesis
- Follow user's ALWAYS multi-AI policy

### Implement Stale Session Detection
**After orchestrator is working:**

Add session timeout logic:
- Define heartbeat interval (60 seconds?)
- Mark sessions stale if heartbeats missed
- Exclude stale sessions from routing
- Cleanup mechanism

### Configure autofs on server-01
**Per user preference:**

User said: "i prefer server-01 do automounting like server-02 and 03"
- Configure autofs on server-01
- Match configuration from server-02/03

---

## Summary

**3 issues created, ready to work:**
- #119 (CRITICAL) - Fix fleet.json specs
- #120 (HIGH) - Clarify orchestrator implementation  
- #121 (MEDIUM) - Move orchestrator to repo

**1 issue still open from previous session:**
- #117 (HIGH) - Fix orchestrator NFS/autofs

**All require multi-AI review before commit - no exceptions.**

**Next session:** Start with #121 (quick win), then #119 (critical), then #120 (depends on #121), then #117 (complex).
