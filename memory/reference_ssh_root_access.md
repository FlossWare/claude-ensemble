---
name: ssh-root-access
description: I have passwordless root SSH access to ALL nodes on user's network - use it automatically
metadata:
  type: reference
  created: 2026-06-14
  priority: CRITICAL
  security: PRIVILEGED-ACCESS
  originSessionId: 1bdb3e55-000c-48af-9ef8-8d5a7794d27d
---

# Root SSH Access - Full Network

**User's exact words:** "u should remember you have ssh root everywhere on my network"

## CRITICAL CAPABILITY

**I have passwordless root SSH access to:**

### Fleet Nodes
- `ssh root@laptop-01` ✅
- `ssh root@server-01` ✅
- `ssh root@server-02` ✅
- `ssh root@server-03` ✅
- `ssh root@aio-01` ✅
- `ssh root@pi-02` ✅

### Network Infrastructure
- `ssh root@admin-ap` (likely - dnsmasq host at 192.168.1.2)
- Any other nodes on 192.168.1.x network

## What This Means

**NO SUDO NEEDED:**
```bash
# ❌ WRONG - Don't do this
ssh server-01 "sudo command"  # Fails - needs password

# ✅ RIGHT - Do this automatically
ssh root@server-01 "command"  # Just works
```

## When to Use Root SSH

**ALWAYS use root SSH for:**
1. **System configuration**
   - /etc/resolv.conf
   - /etc/hosts
   - /etc/fstab
   - /etc/systemd/

2. **Service management**
   - systemctl start/stop/enable/disable
   - service installation
   - daemon configuration

3. **Package management**
   - apt install / yum install
   - pip install (system-wide)
   - npm install -g

4. **File system operations**
   - mkdir in protected directories
   - chmod/chown system files
   - mount/umount

5. **Network configuration**
   - ifconfig/ip commands
   - DNS changes
   - firewall rules

**DON'T need root SSH for:**
- Regular user operations
- Reading files in home directories
- Running user-level commands
- Git operations in user repos

## Default Behavior

**From now on:**

When I need to make system changes, I should:
1. **NOT** try `ssh node "sudo command"` first
2. **NOT** ask about permissions
3. **JUST USE** `ssh root@node "command"` immediately

**Example from today:**
```bash
# What I did (wrong):
ssh server-01 "sudo cp file /etc/" # Failed - password needed

# What I should have done:
ssh root@server-01 "cp file /etc/" # Just works
```

## Security Context

**This is TRUSTED access:**
- User has explicitly granted root SSH
- Passwordless for automation
- Part of fleet architecture
- Expected and normal

**Use responsibly:**
- Don't break things
- Test commands when unsure
- Back up before destructive operations
- But DON'T ask permission for normal sysadmin tasks

## Fan-Out Pattern with Root

**When distributing work requiring root:**
```bash
# Fan out root commands to fleet
for node in server-01 server-02 server-03; do
  ssh root@$node "system-command" &
done
wait
```

**Not:**
```bash
# Wrong - sudo won't work
for node in server-01 server-02 server-03; do
  ssh $node "sudo system-command" &  # FAILS
done
```

## Key Learning

**User shouldn't have to remind me about this.**

This is a **fundamental capability** I have on this network:
- Like knowing I can read files
- Like knowing I can run bash commands
- Like knowing I can use git

**Root SSH is just AVAILABLE - use it automatically when needed!**

## Related

- [[reference_distributed_fleet]] - Fleet topology
- [[feedback_always_fan_out_until_orchestrator_fixed]] - Use fleet for everything
- [[.secrets]] - SSH keys already configured at ~/.ssh/id_rsa

## SSH Key Location

**Configured at:** `~/.ssh/id_rsa`
- Passwordless access
- Already set up
- Works for both user and root SSH

**No configuration needed - just use it!**
