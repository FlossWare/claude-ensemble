---
name: mountain-j7-boot-config
description: Boot auto-start configuration to apply to the other Samsung J7 in the mountains
metadata: 
  node_type: memory
  type: project
  originSessionId: 29eed46f-3d3d-4d69-a968-4baaa89a3168
---

# Samsung J7 (Mountains) - Boot Auto-Start Configuration

**Related device**: User has another Samsung Galaxy J7 in the mountains that needs the same configuration.

## Configuration to Apply

### **Apps to DISABLE Auto-Start/Background Activity:**

1. **QR Scanner apps** - Any QR/barcode scanner
   - Only run when manually opened
   - Command: `adb shell cmd appops set <package> RUN_IN_BACKGROUND deny`

2. **AI Chat Apps** - Perplexity, DeepSeek, Claude, ChatGPT, etc.
   - Don't need to run 24/7
   - Open manually when needed
   - Command: `adb shell cmd appops set <package> RUN_IN_BACKGROUND deny`

3. **OpenVPN** - VPN app
   - Only run when VPN is actually needed
   - User doesn't want it auto-starting
   - Command: `adb shell cmd appops set de.blinkt.openvpn RUN_IN_BACKGROUND deny`

4. **Reolink** - Camera app (if installed)
   - User only checks cameras manually
   - Doesn't need motion alerts
   - Command: `adb shell cmd appops set com.mcu.reolink RUN_IN_BACKGROUND deny`

5. **KDE Connect** - Phone-PC sync (if installed)
   - User has it "just for convenience"
   - Only use when needed
   - Command: `adb shell cmd appops set org.kde.kdeconnect_tp RUN_IN_BACKGROUND deny`

### **Apps to KEEP Enabled:**

1. **Termux:Boot** - SSH server auto-start
   - This should auto-start (user set it up intentionally)
   - Provides remote access to the phone

### **Why This Configuration:**

User wants:
- ✅ Faster boot time
- ✅ Better battery life
- ✅ Less RAM usage
- ✅ Only essential services running
- ✅ Apps still work when manually opened (not removed, just don't auto-start)

### **Detection Commands:**

Find apps that auto-start on boot:
```bash
# List user apps
adb shell pm list packages -3

# Check which apps listen to BOOT_COMPLETED
for pkg in <package-list>; do 
  adb shell dumpsys package $pkg 2>/dev/null | grep -q "BOOT_COMPLETED" && echo "$pkg - starts on boot"
done
```

### **Disable Auto-Start Template:**

```bash
# Stop the app
adb shell am force-stop <package>

# Deny background activity (prevents auto-start and background running)
adb shell cmd appops set <package> RUN_IN_BACKGROUND deny

# Verify it's stopped
adb shell ps -A | grep <package-name>
```

### **Common Packages to Check:**

- `com.scannerreader.qrcode.creatorfree` - QR Scanner (disable)
- `ai.perplexity.app.android` - Perplexity (disable)
- `ai.chatbot.ask.chat.deep.seek.assistant.search.free` - DeepSeek (disable)
- `com.anthropic.claude` - Claude (disable)
- `com.deepseek.chat` - DeepSeek Chat (disable)
- `de.blinkt.openvpn` - OpenVPN (disable)
- `com.mcu.reolink` - Reolink (disable)
- `org.kde.kdeconnect_tp` - KDE Connect (disable)
- `com.termux.boot` - Termux:Boot (KEEP enabled)

### **Expected Result:**

After applying this configuration:
- Boot time: Much faster
- Battery drain: Significantly reduced
- Background apps: Only Termux SSH server
- Functionality: All apps still work when manually opened

### **User Preference Notes:**

- User wants to use apps manually, not have them auto-start
- User confirmed: "i still want to be able to use the app" - meaning apps should work when opened, just not auto-start
- User doesn't need:
  - QR scanner running constantly
  - AI apps running in background
  - VPN auto-connecting
  - Camera app notifications (checks manually)
  - KDE Connect auto-syncing (uses "just for convenience")

## How to Apply to Mountain J7

1. Connect mountain J7 via ADB
2. Run detection commands to find auto-starting apps
3. Apply `RUN_IN_BACKGROUND deny` to unnecessary apps
4. Keep only Termux:Boot enabled for SSH access
5. Verify apps are stopped
6. Test after reboot

[[samsung-j7-main]] - Configuration applied to main J7 (this device)
