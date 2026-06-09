---
name: feedback-versioning-format
description: User wants X.Y versioning format (not X.Y.Z semver) for Solenopsis projects
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5069eeef-3c97-47e3-b069-3f9236a0ac7c
---

Use X.Y versioning format for version numbers, not X.Y.Z semantic versioning.

**Why:**
When asked to use "X.Y as versioning" and then to "make this 2.0", user confirmed the version should be "2.0" not "2.0.0". This is a deliberate choice for simpler version numbering.

**How to apply:**
- Version numbers: 2.0, 2.1, 3.0 (not 2.0.0, 2.1.0, 3.0.0)
- In Maven POM: `<version>2.0</version>`
- In documentation: Refer to "version 2.0" not "2.0.0"
- For minor updates: increment second digit (2.0 → 2.1)
- For major updates: increment first digit (2.1 → 3.0)

**Example:**
```xml
<version>2.0</version>  <!-- Correct -->
<version>2.0.0</version>  <!-- Incorrect -->
```
