---
name: feedback-java-version
description: Solenopsis framework must remain on Java 17 due to client base constraints
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

All Solenopsis framework projects (JCommons, SOAP, Session) must remain on Java 17. Do not upgrade to Java 21.

**Why:** The client base is using Java 17. Upgrading to Java 21 would be a breaking change that forces all consumers to upgrade, which is not acceptable.

**How to apply:** When considering new dependencies or features (like jcollections which requires Java 21), reject them if they require Java version upgrades. Keep all three projects aligned on Java 17. This constraint applies to:
- JCommons (currently Java 17)
- SOAP (currently Java 17)
- Session (currently Java 17)

Even if a library like jcollections could provide useful features (persistent file-backed collections for session caching), the Java 21 requirement makes it incompatible with the Solenopsis framework's Java 17 constraint.
