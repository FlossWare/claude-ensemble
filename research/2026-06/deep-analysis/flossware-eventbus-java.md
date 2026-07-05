# Deep Code Analysis: eventbus-java

**Analysis Date:** 2026-06-16
**Repository:** flossware/eventbus-java

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
│       └── java
├── AUTONOMOUS_WORKFLOW_GUIDE.md
├── AUTO_RESOLVE_MODE.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTINUOUS_REVIEW_GUIDE.md
├── dependency-check-suppressions.xml
├── LICENSE
├── pmd-ruleset.xml
├── pom.xml
├── pom.xml.backup
├── pom.xml.backup-20260528-181240
├── pom.xml.backup-rename
├── pom.xml.bak
├── README.md
└── spotbugs-exclude.xml

8 directories, 16 files
```

**File Statistics:**
- Total files: 171
- Java files: 13
- XML files: 13
- Python files: 0
- JavaScript files: 12

## 2. Architecture & Code Patterns

**Build System:**
- Maven (pom.xml found)

**Key Packages/Modules:**
- org.flossware.eventbus

**Design Patterns Detected:**
- Pattern usage: 16 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 6
- Test directory: src/test/

**Documentation:**
- README.md (359 lines)
- Javadoc annotations: 69

**Code Metrics:**
- Java LOC: 832

## 4. Key Files Deep Dive

### pom.xml (Maven Configuration)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="https://maven.apache.org/POM/4.0.0" xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.flossware</groupId>
  <artifactId>eventbus-java</artifactId>
  <version>1.3</version>
  <packaging>jar</packaging>
  <name>FlossWare Eventbus</name>
  <description>Event bus and service registry for inter-application communication</description>
  <url>https://github.com/FlossWare/eventbus-java</url>
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
    </developer>
  </developers>
  <scm>
    <connection>scm:git:https://github.com/FlossWare/eventbus-java.git</connection>
    <developerConnection>scm:git:https://github.com/FlossWare/eventbus-java.git</developerConnection>
    <url>https://github.com/FlossWare/eventbus-java</url>
  </scm>
  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <maven.compiler.release>21</maven.compiler.release>
    <slf4j.version>2.0.9</slf4j.version>
    <junit.version>6.1.0</junit.version>
    <gpg.skip>true</gpg.skip>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.slf4j</groupId>
      <artifactId>slf4j-api</artifactId>
      <version>${slf4j.version}</version>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>${junit.version}</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>ch.qos.logback</groupId>
      <artifactId>logback-classic</artifactId>
...
```

**Dependencies:**
- eventbus-java
- slf4j-api
- junit-jupiter
- logback-classic
- maven-compiler-plugin
- maven-surefire-plugin
- jacoco-maven-plugin
- maven-source-plugin
- maven-javadoc-plugin
- maven-gpg-plugin

### README.md
```markdown
# JEventBus

[![Maven Central](https://img.shields.io/maven-central/v/org.flossware/eventbus-java.svg?label=Maven%20Central)](https://central.sonatype.com/artifact/org.flossware/eventbus-java)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Event bus and service registry for inter-application communication in Java.

## Features

- **Message Bus**: Topic-based publish/subscribe messaging
- **Service Registry**: Type-safe service discovery and lookup
- **Asynchronous Delivery**: Non-blocking message dispatch
- **Thread-Safe**: Concurrent operations with CopyOnWriteArrayList
- **Flexible Messages**: Support for headers, custom payloads, and metadata
- **Multiple Subscribers**: Broadcast messages to all interested parties
- **Exception Isolation**: Handler exceptions don't affect other subscribers

## Installation

### Maven

```xml
<dependency>
    <groupId>org.flossware</groupId>
    <artifactId>eventbus-java</artifactId>
    <version>1.0</version>
</dependency>
```

### Gradle
...
```

### Top 5 Largest Source Files
- ./target/site/jacoco/jacoco-resources/prettify.js (1510 lines)
- ./target/apidocs/search.js (458 lines)
- ./target/apidocs/search-page.js (284 lines)
- ./src/test/java/org/flossware/eventbus/api/MessageTest.java (256 lines)
- ./target/apidocs/script.js (253 lines)

---
**Analysis Complete**
