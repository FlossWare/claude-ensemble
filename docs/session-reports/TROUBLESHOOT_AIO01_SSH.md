# Troubleshoot aio-01 Root SSH Access

## Common Issues

### 1. Check if key was added correctly

On aio-01 as root:
```bash
cat /root/.ssh/authorized_keys
# Should contain the ssh-rsa key starting with AAAAB3NzaC1yc2...
```

### 2. Check permissions (CRITICAL)

On aio-01 as root:
```bash
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
chown -R root:root /root/.ssh
restorecon -R /root/.ssh  # If SELinux is enabled
```

### 3. Check SSH config

On aio-01, check `/etc/ssh/sshd_config`:
```bash
grep -E "^PermitRootLogin|^PubkeyAuthentication|^AuthorizedKeysFile" /etc/ssh/sshd_config
```

Should show:
```
PubkeyAuthentication yes
PermitRootLogin yes  # or "without-password" or "prohibit-password"
AuthorizedKeysFile .ssh/authorized_keys
```

If any are wrong, edit `/etc/ssh/sshd_config` and restart:
```bash
systemctl restart sshd
```

### 4. Check SELinux (if enabled)

On aio-01:
```bash
getenforce
# If "Enforcing", run:
restorecon -Rv /root/.ssh
```

### 5. Check SSH logs

On aio-01:
```bash
tail -f /var/log/secure
# Then try SSH from laptop-01 and watch for errors
```

## Quick Fix Script

Run this on aio-01 as root:
```bash
# Fix everything at once
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
chown -R root:root /root/.ssh
restorecon -Rv /root/.ssh 2>/dev/null || true
systemctl restart sshd
echo "✅ Fixed permissions and restarted SSH"
```

## Alternative: Use sfloess user with sudo

If root SSH doesn't work, we can use:
```bash
# From laptop-01
ssh aio-01 "sudo bash -c '...commands...'"
```

But this requires sudo to be installed and sfloess to be in sudo/wheel group.
