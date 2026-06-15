---
name: server-01-fan-issue
description: server-01 requires powersave CPU governor or fan runs excessively loud - thermal/cooling constraint
metadata: 
  node_type: memory
  type: reference
  created: 2026-06-14
  priority: high
  hardware_constraint: true
  originSessionId: 39a38f09-c545-4579-9ac1-6c31a694eba2
---

# server-01 Fan Issue

**Problem:** server-01 (i7-3630QM) has aggressive fan behavior when NOT using powersave governor

**Symptom:** Fan runs crazy/excessively loud on non-powersave governors (schedutil, performance, ondemand)

**Solution:** ALWAYS use powersave CPU governor on server-01 - MANDATORY, NEVER allow performance scaling

**CRITICAL:** server-01 MUST stay in powersave with max frequency locked to 1.2 GHz. Do NOT allow CPU to scale up even under heavy load. User prefers reduced performance over loud fan noise.

**Implementation:**
```bash
# Set powersave (temporary - until reboot)
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do 
  echo powersave > $cpu
done

# Make persistent across reboots
echo 'GOVERNOR="powersave"' >> /etc/default/cpufrequtils
systemctl enable cpufrequtils
```

**Current Status (2026-06-14):**
- ✅ Powersave enabled (temporary)
- ⚠️ Not persistent - will revert to schedutil on reboot

**Hardware:**
- CPU: Intel i7-3630QM @ 2.4GHz (4C/8T)
- RAM: 15 GB
- Likely thermal paste degradation or cooling system issue

**Why This Matters:**
- Excessive fan noise in datacenter/office environment
- May indicate thermal management problem
- Server still functional but needs powersave to keep fan reasonable

**Related:** [[reference_distributed_fleet]] - Fleet hardware profiles
