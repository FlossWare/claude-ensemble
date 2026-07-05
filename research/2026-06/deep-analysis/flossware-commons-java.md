# Deep Code Analysis: commons-java

**Analysis Date:** 2026-06-16
**Repository:** flossware/commons-java

## 1. Repository Structure

```
.
├── src
│   ├── main
│   │   └── java
│   ├── site
│   │   ├── markdown
│   │   └── site.xml
│   └── test
│       ├── java
│       └── resources
├── AUTONOMOUS_WORKFLOW_GUIDE.md
├── AUTO_RESOLVE_MODE.md
├── CHANGELOG.md
├── CLAUDE_CODE_GUIDES.md
├── CLAUDE.md
├── CODE_OF_CONDUCT.md
├── CONTINUOUS_REVIEW_GUIDE.md
├── CONTRIBUTING.md
├── dependency-check-suppressions.xml
├── flossware-commons-analysis.md
├── LICENSE
├── LICENSE-HEADER.txt
├── mvnw
├── mvnw.cmd
├── pmd-ruleset.xml
├── pom.xml
├── pom.xml.backup-20260528-181240
├── pom.xml.backup-rename
├── README.md
├── SECURITY.md
├── spotbugs-exclude.xml
└── STATUS.md

9 directories, 23 files
```

**File Statistics:**
- Total files: 75
- Java files: 48
- XML files: 5
- Python files: 0
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**
- Maven (pom.xml found)

**Key Packages/Modules:**
- org.flossware.commons

**Design Patterns Detected:**
- Pattern usage: 84 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 20
- Test directory: src/test/

**Documentation:**
- README.md (269 lines)
- Javadoc annotations: 337

**Code Metrics:**
- Java LOC: 2772

## 4. Key Files Deep Dive

### pom.xml (Maven Configuration)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="https://maven.apache.org/POM/4.0.0" xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.flossware</groupId>
  <artifactId>commons-java</artifactId>
  <version>1.0</version>
  <name>FlossWare Commons</name>
  <description>This project is a collection of shareable Java related functionality.</description>
  <url>https://github.com/FlossWare/commons-java</url>
  <licenses>
    <license>
      <name>GNU General Public License, Version 3</name>
      <url>https://www.gnu.org/licenses/gpl-3.0.txt</url>
      <distribution>repo</distribution>
    </license>
  </licenses>
  <developers>
    <developer>
      <id>sfloess</id>
      <name>Scot P. Floess</name>
      <email>sfloess@redhat.com</email>
      <organization>FlossWare</organization>
      <organizationUrl>https://github.com/FlossWare</organizationUrl>
      <roles>
        <role>architect</role>
        <role>developer</role>
      </roles>
      <timezone>America/Chicago</timezone>
    </developer>
  </developers>
  <organization>
    <name>FlossWare</name>
    <url>https://github.com/FlossWare</url>
  </organization>
  <issueManagement>
    <system>GitHub Issues</system>
    <url>https://github.com/FlossWare/commons-java/issues</url>
  </issueManagement>
  <ciManagement>
    <system>GitHub Actions</system>
    <url>https://github.com/FlossWare/commons-java/actions</url>
  </ciManagement>
  <packaging>jar</packaging>
  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <maven-clean-plugin>3.5.0</maven-clean-plugin>
    <maven-resources-plugin>3.3.1</maven-resources-plugin>
    <maven-compiler-plugin>3.15.0</maven-compiler-plugin>
    <maven-surefire-plugin>3.5.5</maven-surefire-plugin>
    <maven-jar-plugin>3.5.0</maven-jar-plugin>
...
```

**Dependencies:**
- commons-java
- maven-clean-plugin
- maven-resources-plugin
- maven-compiler-plugin
- maven-surefire-plugin
- maven-jar-plugin
- maven-install-plugin
- maven-deploy-plugin
- maven-site-plugin
- maven-project-info-reports-plugin

### README.md
```markdown
# commons-java

Foundation utilities for the [Solenopsis](https://github.com/solenopsis) Salesforce SOAP framework.

[![Build Status](https://github.com/FlossWare/commons-java/workflows/CD-CI/badge.svg)](https://github.com/FlossWare/commons-java/actions)
[![codecov](https://codecov.io/gh/FlossWare/commons-java/branch/main/graph/badge.svg)](https://codecov.io/gh/FlossWare/commons-java)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Security Policy](https://img.shields.io/badge/security-policy-blue)](https://github.com/FlossWare/commons-java/blob/main/SECURITY.md)
[![Maven Central](https://img.shields.io/badge/maven--central-packagecloud-orange)](https://packagecloud.io/flossware/java)
[![Java Version](https://img.shields.io/badge/Java-17%2B-blue)](https://openjdk.org/projects/jdk/17/)
[![Coverage](https://img.shields.io/badge/coverage-93%25-brightgreen)](https://github.com/FlossWare/commons-java/actions)
[![Quality](https://img.shields.io/badge/quality-A%2B-brightgreen)](https://github.com/FlossWare/commons-java/actions)

## Purpose

This library provides low-level utilities used by the Solenopsis framework for Salesforce SOAP operations:
- **[solenopsis/soap](https://github.com/solenopsis/soap)** - Salesforce SOAP client generation (Apex, Metadata, Enterprise, Partner, Tooling APIs)
- **[solenopsis/session](https://github.com/solenopsis/session)** - Salesforce session management and authentication

## Features

### SOAP Utilities (`org.flossware.commons-java.util.SoapUtil`)
Core utilities for Apache CXF SOAP clients:
- Configure SOAP service headers and endpoints
- Compute QNames from `@WebServiceClient` annotations  
- Set custom headers for Salesforce API calls
- Manage SOAP factory instances

### String Utilities (`org.flossware.commons-java.util.StringUtil`)
- String concatenation with separators
...
```

### Top 5 Largest Source Files
- ./src/test/java/org/flossware/commons/util/StringUtilTest.java (598 lines)
- ./src/main/java/org/flossware/commons/util/StringUtil.java (544 lines)
- ./src/test/java/org/flossware/commons/util/FileUtilTest.java (432 lines)
- ./src/main/java/org/flossware/commons/util/FileUtil.java (326 lines)
- ./src/test/java/org/flossware/commons/util/SoapUtilTest.java (280 lines)

---
**Analysis Complete**
