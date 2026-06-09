---
name: feedback-security-approach
description: Use Maven dependencyManagement to override vulnerable transitive dependencies without breaking compatibility
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5069eeef-3c97-47e3-b069-3f9236a0ac7c
---

When fixing security vulnerabilities in transitive dependencies, use Maven's `<dependencyManagement>` section to override specific versions without changing direct dependencies.

**Why:**
The metadata project depends on org.solenopsis:session and org.solenopsis:soap, which in turn depend on older versions of CXF, Jetty, and other libraries with known CVEs. Directly upgrading those dependencies could break compatibility with Session/Soap libraries. Using dependencyManagement allows selective overrides.

**How to apply:**

1. Add `<dependencyManagement>` section in pom.xml before `<build>`
2. List each vulnerable transitive dependency with the fixed version
3. Maven will use these versions instead of what transitive dependencies request
4. Test thoroughly - ensure all tests still pass

**Example:**
```xml
<dependencyManagement>
    <dependencies>
        <!-- Override vulnerable CXF from org.solenopsis:soap -->
        <dependency>
            <groupId>org.apache.cxf</groupId>
            <artifactId>cxf-core</artifactId>
            <version>4.0.11</version>
        </dependency>
        <!-- Override vulnerable Jetty from CXF -->
        <dependency>
            <groupId>org.eclipse.jetty</groupId>
            <artifactId>jetty-server</artifactId>
            <version>11.0.26</version>
        </dependency>
    </dependencies>
</dependencyManagement>
```

**When this was validated:**
Successfully fixed 9+ CVEs in metadata project 2.0 without breaking compatibility with Session 1.16 and Soap 1.11. All 57 tests passed after overrides.

**Research approach used:**
- WebSearch for "package-name version CVE security vulnerabilities 2026"
- Check mvn versions:display-dependency-updates for latest versions
- Verify with mvn dependency:tree that overrides took effect
- Run full test suite to validate compatibility
