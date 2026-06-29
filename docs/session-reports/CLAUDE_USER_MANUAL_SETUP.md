# Manual Setup: 'claude' User on Servers

## Problem
Need to create a dedicated `claude` user on server-01/02/03 for FREE AI resources, but:
- No `sudo` installed
- No `doas` installed  
- Only `su` available (needs root password)
- `sfloess` user not in admin groups

## Solution: Manual Setup Required

You need to SSH to each server as root and run these commands:

### On Each Server (server-01, server-02, server-03)

```bash
# SSH as root
ssh root@server-01  # (repeat for server-02, server-03)

# Create claude user
useradd -m -s /bin/bash -d /home/claude claude

# Setup API keys
cat > /home/claude/.bashrc << 'EOF'
# FREE AI API Keys ($0/month)
export GROQ_API_KEY="REDACTED_GROQ_KEY"
export OPENROUTER_API_KEY='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'
export CEREBRAS_API_KEY='cREDACTED_OPENROUTER_KEY'
export DEEPSEEK_API_KEY='REDACTED_DEEPSEEK_KEY'
export CLOUDFLARE_API_KEY='cfat_G7QETtzyQC6MGMBCPkwXhoIgfRydoqi937WC2PTP74cceced'
export CLOUDFLARE_ACCOUNT_ID='c38a4493830b64dceec5f528043bd3ac'

# NFS Models (via /mnt/nas to NAS, NOT to laptop-01)
export OLLAMA_MODELS=/mnt/nas/ai-models/ollama-from-laptop-01

# Path
export PATH=$HOME/.local/bin:$PATH
EOF

# Set ownership
chown -R claude:claude /home/claude
chmod 700 /home/claude
chmod 644 /home/claude/.bashrc

# Verify
ls -ld /home/claude
echo "✅ claude user created"
```

## Verification

After setup, test on each server:

```bash
ssh server-01
su - claude  # (as root, no password needed)
echo $GROQ_API_KEY | head -c 20  # Should show: gsk_hInKtmqg2gQobWrP
echo $HOME  # Should show: /home/claude
mount | grep $HOME  # Should NOT show NFS mount (local directory)
```

## Why This Setup?

1. **Local home directory** - NOT NFS mounted from laptop-01
2. **Only NAS models** - Via /mnt/nas (autofs)
3. **FREE resources only** - $0/month
4. **No Red Hat code access** - Isolated from laptop-01's proprietary work

## What Claude User Can Access

### FREE Cloud APIs (5)
- Groq - 500+ tok/s
- OpenRouter - Multi-model
- Cerebras - Fast inference
- DeepSeek - Code generation
- Cloudflare - Workers AI

### FREE Local Models (26+)
- 20+ Ollama models (137GB on NAS)
- 6+ GGUF models (88GB on NAS)

### Total Cost: $0/month

## Alternative: Install sudo

If you prefer automated setup, install sudo on each server first:

```bash
# As root on each server
ssh root@server-01
dnf install -y sudo
usermod -aG wheel sfloess

# Then I can automate the claude user creation
```

---

**Status:** Awaiting manual creation or sudo installation
