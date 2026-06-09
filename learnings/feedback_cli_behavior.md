---
name: feedback-cli-behavior
description: Command-line argument parsing should allow flexible option ordering
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b8036c51-08a6-48f2-aa1c-41877b100b83
---

The jsecurity CLI accepts options anywhere in the argument list, not just before directories.

**Why:** User confirmed flexible ordering is desired behavior when asked about failing test that expected strict ordering. Both `jsecurity -t 4 /path` and `jsecurity /path -t 4` should work.

**How to apply:**
- Don't enforce that all options must come before directory arguments
- CleanDisk argument parser allows interspersed options and directories
- Tests should not expect failure when options appear after directories
