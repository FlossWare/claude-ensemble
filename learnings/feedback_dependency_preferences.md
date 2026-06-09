---
name: feedback-dependency-preferences
description: User explicitly does not want jCore or Keraiai dependencies - use Session/Soap/jcommons instead
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5069eeef-3c97-47e3-b069-3f9236a0ac7c
---

Do not use jCore or Keraiai dependencies in Solenopsis projects. Use the newer Session, Soap, and jcommons libraries instead.

**Why:**
User explicitly stated "please do not use jCode nor Keraiai" when asked to update the metadata project. These are deprecated/older libraries that have been replaced with better-maintained alternatives.

**How to apply:**
For Solenopsis projects needing:
- **Salesforce session management**: Use `org.solenopsis:session`
- **Salesforce SOAP APIs**: Use `org.solenopsis:soap`
- **Common utilities**: Use `org.flossware:jcommons`

**Migration Pattern:**
```xml
<!-- OLD - Don't use -->
<dependency>
    <groupId>org.solenopsis</groupId>
    <artifactId>keraiai</artifactId>
</dependency>

<!-- NEW - Use instead -->
<dependency>
    <groupId>org.solenopsis</groupId>
    <artifactId>session</artifactId>
</dependency>
<dependency>
    <groupId>org.solenopsis</groupId>
    <artifactId>soap</artifactId>
</dependency>
<dependency>
    <groupId>org.flossware</groupId>
    <artifactId>jcommons</artifactId>
</dependency>
```
