# Setup Root SSH Access to aio-01

## Option 1: From laptop-01 (Easiest)

```bash
# Copy your SSH key to root@aio-01
ssh-copy-id -i ~/.ssh/id_rsa.pub root@aio-01
# Enter root password when prompted
```

## Option 2: Manually on aio-01

```bash
# SSH to aio-01 as root
ssh root@aio-01
# Enter password

# Create .ssh directory if it doesn't exist
mkdir -p /root/.ssh
chmod 700 /root/.ssh

# Copy your public key from laptop-01
# (Get the key first)
cat ~/.ssh/id_rsa.pub
# Copy the output

# Then on aio-01 as root:
cat >> /root/.ssh/authorized_keys << 'EOF'
# Paste your public key here
EOF

chmod 600 /root/.ssh/authorized_keys
```

## Option 3: One-liner from laptop-01

```bash
# This will prompt for password once
cat ~/.ssh/id_rsa.pub | ssh root@aio-01 'mkdir -p /root/.ssh && cat >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys && chmod 700 /root/.ssh'
```

## Verify Access

After any option above:
```bash
# Test passwordless SSH
ssh root@aio-01 "whoami"
# Should print: root (without password prompt)
```

## Then Complete Claude User Setup

Once root SSH works, I can run:
```bash
ssh root@aio-01 "useradd -m -s /bin/bash claude && ..."
# Full automation
```

---

**Recommended:** Use Option 1 (ssh-copy-id) - it's the simplest.
