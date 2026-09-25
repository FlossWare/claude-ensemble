---
name: imperial-temperatures
description: "Always report temperatures in Fahrenheit (imperial), not Celsius"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 641874f2-3be7-45a9-afab-79134d1bba85
  modified: 2026-08-06T18:39:55.152Z
---

Always use Fahrenheit (imperial) when reporting temperatures to the user.

**Why:** User preference — they want imperial units for temperature readings.

**How to apply:** When reading CPU/system temps (which are reported in Celsius by the kernel), convert to Fahrenheit before presenting. Formula: F = C × 9/5 + 32.
