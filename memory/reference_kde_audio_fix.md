---
name: kde-audio-fix
description: KDE Plasma audio routing fix - feedbackd/plasma-mobile loopback sinks hijacking audio output
metadata: 
  node_type: memory
  type: reference
  created: 2026-07-13
  originSessionId: b7d676e2-a262-49e6-b80b-d648b0c73c02
---

# KDE Audio Routing Fix (2026-07-13)

**Problem:** Per-app audio output stopped working in Vivaldi and Jellyfin after Plasma 6.7.0 + PipeWire 1.6.7 update (June 19 transaction 53).

**Root cause:** `plasma-mobile` package requires `feedbackd`, which installs `/usr/share/wireplumber/wireplumber.conf.d/media-role-nodes.conf`. This creates 6 loopback sinks (multimedia, notification, phone, alarm, ringtone, alert) that intercept audio streams by role. Multimedia audio was routed to a virtual loopback sink instead of real HDMI output.

**Fix:** User override that disables role-based loopback routing:
`~/.config/wireplumber/wireplumber.conf.d/99-disable-media-role-loopbacks.conf`

```conf
wireplumber.profiles = {
  main = {
    policy.linking.role-based.loopbacks = disabled
  }
}
```

**Packages involved:**
- `plasma-mobile-6.7.2-1.fc44` → requires `feedbackd-0.8.9-2.fc44` → installs media-role-nodes.conf
- `plasma-desktop-6.7.2-1.fc44` (both installed)
- `pipewire-1.6.8`, `wireplumber-0.5.14`

**How to apply:** If audio routing breaks again after updates, check if loopback sinks reappeared with `pactl list sinks short`. The override file should persist across updates.
