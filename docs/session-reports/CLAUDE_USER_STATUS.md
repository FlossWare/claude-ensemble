# Claude User Setup Status

## Current Status: ⏳ PENDING MANUAL SETUP

### What's Done ✅
- ✅ Identified need for dedicated `claude` user
- ✅ Documented setup procedure
- ✅ Verified servers have local /home (not all NFS)
- ✅ Created manual setup guide

### What's Pending ⏳
- ⏳ Create `claude` user on server-01 (needs root access)
- ⏳ Create `claude` user on server-02 (needs root access)
- ⏳ Create `claude` user on server-03 (needs root access)
- ⏳ aio-01 is offline (skip for now)

### Why Pending
- No `sudo` or `doas` installed on servers
- `sfloess` user not in admin groups
- Only `su` available (requires root password)
- Cannot automate without root SSH access

### How to Complete

**Option 1: Manual (fastest)**
See: `~/CLAUDE_USER_MANUAL_SETUP.md`

**Option 2: Install sudo first**
```bash
ssh root@server-01 "dnf install -y sudo && usermod -aG wheel sfloess"
ssh root@server-02 "dnf install -y sudo && usermod -aG wheel sfloess"
ssh root@server-03 "dnf install -y sudo && usermod -aG wheel sfloess"
# Then I can automate the claude user creation
```

### When Complete

After creating the `claude` user on all servers:

```bash
# Verify
for s in server-01 server-02 server-03; do
  echo "=== $s ==="
  ssh $s "su - claude -c 'echo \$GROQ_API_KEY | head -c 20'"
done
```

---

**Next:** Complete manual setup OR install sudo, then re-run automation
