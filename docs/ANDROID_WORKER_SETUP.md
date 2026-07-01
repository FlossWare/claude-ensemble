# Android Worker Setup Guide (android-j7)

Setup android-j7 as a fleet worker using Termux

## Prerequisites

- Android phone (android-j7)
- WiFi connected to same network (192.168.1.x)
- ~100MB free space

## Step 1: Install Termux

**IMPORTANT: Install from F-Droid, NOT Google Play Store**

1. Open browser on phone
2. Go to: https://f-droid.org/
3. Download F-Droid APK
4. Install F-Droid
5. Open F-Droid, search "Termux"
6. Install Termux

**Why F-Droid?** Play Store version is outdated and broken.

## Step 2: Setup Termux

Open Termux and run:

```bash
# Update packages
pkg update && pkg upgrade -y

# Install required packages
pkg install python openssh curl -y

# Get phone's IP address
ifconfig wlan0 | grep inet
# Note the IP address (e.g., 192.168.1.50)
```

## Step 3: Setup SSH (Optional - for deployment)

If you want to deploy scripts via SSH:

```bash
# Set password
passwd

# Start SSH server (runs on port 8022 in Termux)
sshd

# Get your username
whoami
```

From laptop, test SSH:
```bash
ssh -p 8022 <username>@<phone-ip>
```

## Step 4: Deploy Worker Scripts

### Option A: Via SSH (if setup above)

From laptop:
```bash
PHONE_IP="192.168.1.50"  # Replace with actual IP
PHONE_USER="u0_a123"     # Replace with whoami output

# Deploy worker daemon
scp -P 8022 shared/worker-daemon.py $PHONE_USER@$PHONE_IP:~/

# Deploy registration script
scp -P 8022 shared/worker-register.sh $PHONE_USER@$PHONE_IP:~/

# Deploy worker client
scp -P 8022 shared/worker-client.sh $PHONE_USER@$PHONE_IP:~/

chmod +x ~/worker-daemon.py ~/worker-register.sh ~/worker-client.sh
```

### Option B: Manual Copy (no SSH)

On phone in Termux:

```bash
# Download scripts directly
curl -o ~/worker-daemon.py https://gitlab.cee.redhat.com/sfloess/claude-global-skills/-/raw/main/shared/worker-daemon.py

curl -o ~/worker-register.sh https://gitlab.cee.redhat.com/sfloess/claude-global-skills/-/raw/main/shared/worker-register.sh

curl -o ~/worker-client.sh https://gitlab.cee.redhat.com/sfloess/claude-global-skills/-/raw/main/shared/worker-client.sh

# Make executable
chmod +x ~/worker-daemon.py ~/worker-register.sh ~/worker-client.sh
```

### Option C: Type/Paste Manually

See scripts below to copy-paste into phone.

## Step 5: Configure Hostname

In Termux on phone:

```bash
# Termux doesn't let you change hostname permanently, but we can set it for scripts
export HOSTNAME=android-j7

# Add to ~/.bashrc to make permanent
echo 'export HOSTNAME=android-j7' >> ~/.bashrc
```

## Step 6: Start Worker Services

### Start Worker Daemon (HTTP service on port 8003)

```bash
# Run in foreground (for testing)
python ~/worker-daemon.py

# Or run in background
nohup python ~/worker-daemon.py > ~/worker-daemon.log 2>&1 &

# Check if running
curl http://localhost:8003/health
```

### Start Auto-Registration

```bash
# Update registry URL in script if needed
sed -i 's|REGISTRY_URL=.*|REGISTRY_URL="http://aio-01:8002"|' ~/worker-register.sh

# Run in background
nohup ~/worker-register.sh > ~/worker-register.log 2>&1 &
```

## Step 7: Verify Registration

From laptop:

```bash
# Check if android-j7 appears in registry
curl -s http://aio-01:8002/workers | jq '.workers[] | select(.hostname=="android-j7")'

# Test worker daemon
curl http://android-j7:8003/health

# Test command execution
curl -X POST http://android-j7:8003/execute \
  -H "Content-Type: application/json" \
  -d '{"command":"echo Hello from android-j7"}'
```

## Step 8: Test with Fleet

```bash
# From laptop
fleet workers  # Should show android-j7

fleet command "uptime" android-j7
```

## Keeping Services Running

Termux has Wake Lock - keep Termux running in background:

1. Open Termux
2. Pull down notification shade
3. Tap "ACQUIRE WAKELOCK" in Termux notification
4. Services will keep running even with screen off

**Note:** Android may kill Termux to save battery. For production:
- Keep phone plugged in
- Disable battery optimization for Termux
- Use Wake Lock

## Troubleshooting

### "Connection refused" when accessing worker daemon

```bash
# Check if daemon is running
ps aux | grep worker-daemon

# Check logs
tail ~/worker-daemon.log

# Restart
pkill -f worker-daemon
python ~/worker-daemon.py &
```

### Worker not appearing in registry

```bash
# Check registration script
ps aux | grep worker-register

# Check logs
tail ~/worker-register.log

# Check network
ping aio-01

# Manual registration test
curl -X POST http://aio-01:8002/register \
  -H "Content-Type: application/json" \
  -d "{
    \"hostname\": \"android-j7\",
    \"ip_address\": \"$(hostname -I | awk '{print $1}')\",
    \"cpu_cores\": $(nproc),
    \"ram_gb\": $(free -g | awk '/^Mem:/{print $2}'),
    \"architecture\": \"$(uname -m)\",
    \"roles\": [\"worker\", \"mobile\"],
    \"capabilities\": [\"api-only\", \"low-power\"]
  }"
```

### SSH not working

```bash
# Restart sshd
pkill sshd
sshd

# Check if running
pgrep sshd
```

## Phone Specs Detection

On android-j7:

```bash
# CPU cores
nproc

# RAM (GB)
free -g | awk '/^Mem:/{print $2}'

# Architecture
uname -m

# Android version
getprop ro.build.version.release
```

## Limitations on Android

1. **Battery drain** - Will drain battery if not plugged in
2. **Process killing** - Android may kill background processes
3. **No systemd** - Can't use systemd services
4. **Limited resources** - Phone has less CPU/RAM than servers
5. **Network** - May sleep when screen off (use Wake Lock)

## Best Practices for Phone Worker

1. Keep phone plugged in
2. Use Wake Lock in Termux
3. Disable battery optimization for Termux
4. Set phone to never sleep when plugged in
5. Use as lightweight worker only (not for heavy tasks)

## Estimated Setup Time

- With SSH: ~10 minutes
- Manual: ~15 minutes
- First time with Termux install: ~20 minutes
