---
name: pxeos-tftpos-decomposition
description: "pxe-os decomposition — tftp-os is the standalone base, pxe-os decorates it (has-a, not siblings sharing a library)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 87f86bea-63f4-4075-afa5-1899ccbce831
  modified: 2026-07-29T01:29:11.505Z
---

## pxe-os → tftp-os + pxe-os Decomposition

pxe-os should decompose into tftp-os (standalone) and pxe-os (decorator on tftp-os).

**Why:** PXE literally starts with TFTP (DHCP → TFTP → iPXE → HTTP). tftp-os is the foundation, not a sibling. pxe-os depends on tftp-os, not the other way around. tftp-os also works standalone for router firmware flashing (OpenWRT, DD-WRT, FreshTomato).

**How to apply:**
- tftp-os owns: TFTP serving, MAC matching, config/profiles, state tracking, plugin base, webhooks, audit, metrics
- pxe-os decorates tftp-os with: iPXE script generation, HTTP boot assets, autoinstall configs, OS installer plugins
- Decorator pattern — has-a relationship, NOT inheritance, NOT a shared third library
- tftp-os standalone: serves firmware images to routers
- pxe-os standalone: full PXE provisioning (depends on tftp-os)
- Stacking both decorators on one server is valid

Related: [[feedback_always_review]]
