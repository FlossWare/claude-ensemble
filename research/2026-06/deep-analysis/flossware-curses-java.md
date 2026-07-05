# Deep Code Analysis: curses-java

**Analysis Date:** 2026-06-16
**Repository:** flossware/curses-java

## 1. Repository Structure

```
.
├── ci
│   └── rev-version.sh
├── docs
│   ├── adr
│   │   ├── 0001-use-foreign-function-api.md
│   │   ├── 0002-automatic-continuous-versioning.md
│   │   └── 0003-thread-safety-with-reentrant-lock.md
│   ├── screenshots
│   │   └── README.md
│   ├── api-improvement-proposals.md
│   ├── cicd.md
│   ├── examples.md
│   ├── maven-central-publishing.md
│   ├── module-system.md
│   ├── readme-claim-verification.md
│   ├── real-world-examples-design.md
│   ├── roadmap.md
│   ├── testing.md
│   └── themes.md
├── examples
│   ├── AdvancedComponentTest.java
│   ├── AllWidgetsTest.java
│   ├── ComprehensiveUITest.java
│   ├── README.md
│   ├── SimpleDemo.java
│   ├── SystemDashboard.java
│   ├── TableTest.java
│   └── TodoListApp.java
├── src
│   ├── main
│   │   └── java
│   ├── site
│   │   ├── markdown
│   │   └── site.xml
│   └── test
│       └── java
├── themes
│   ├── borland3d.json
│   ├── dark.json
│   ├── dbase4-3d.json
│   ├── README.md
│   └── schema.json
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── dependency-check-suppressions.xml
├── LICENSE
├── module-info.java.template
├── mvnw
├── mvnw.cmd
├── pmd-ruleset.xml
├── pom.xml
├── QUICKSTART.txt
├── README.md
├── run-interactive.bat
├── run-interactive.ps1
├── run-interactive.sh
├── SECURITY.md
├── spotbugs-exclude.xml
├── test-interactive.bat
├── test-interactive.ps1
└── test-interactive.sh

14 directories, 49 files
```

**File Statistics:**
- Total files: 247
- Java files: 202
- XML files: 5
- Python files: 0
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**
- Maven (pom.xml found)

**Key Packages/Modules:**
- org.flossware.curses

**Design Patterns Detected:**
- Pattern usage: 24 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 109
- Test directory: src/test/

**Documentation:**
- README.md (556 lines)
- docs/ directory exists
- Javadoc annotations: 219

**Code Metrics:**
- Java LOC: 10261

## 4. Key Files Deep Dive

### pom.xml (Maven Configuration)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="https://maven.apache.org/POM/4.0.0" xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.flossware</groupId>
  <artifactId>curses-java</artifactId>
  <version>1.0</version>
  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <maven.compiler.source>21</maven.compiler.source>
    <maven.compiler.target>21</maven.compiler.target>
    <exec.mainClass>org.flossware.curses.Main</exec.mainClass>
    <junit.version>5.11.0</junit.version>
    <mockito.version>5.14.2</mockito.version>
    <assertj.version>3.27.3</assertj.version>
    <slf4j.version>2.0.9</slf4j.version>
    <message>Automated Version Bump ${project.version} [ci skip]</message>
    <!-- Reproducible builds - https://maven.apache.org/guides/mini/guide-reproducible-builds.html -->
    <project.build.outputTimestamp>2026-05-24T06:34:42Z</project.build.outputTimestamp>
  </properties>
  <dependencies>
    <!-- JUnit 5 -->
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter-api</artifactId>
      <version>${junit.version}</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter-engine</artifactId>
      <version>${junit.version}</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter-params</artifactId>
      <version>${junit.version}</version>
      <scope>test</scope>
    </dependency>
    <!-- Mockito for mocking -->
    <dependency>
      <groupId>org.mockito</groupId>
      <artifactId>mockito-core</artifactId>
      <version>${mockito.version}</version>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.mockito</groupId>
      <artifactId>mockito-junit-jupiter</artifactId>
      <version>${mockito.version}</version>
...
```

**Dependencies:**
- curses-java
- junit-jupiter-api
- junit-jupiter-engine
- junit-jupiter-params
- mockito-core
- mockito-junit-jupiter
- assertj-core
- slf4j-api
- slf4j-simple
- jqwik

### README.md
```markdown
# curses-java

A modern Java terminal UI library that brings AWT-like components to the terminal using ncurses. Built with cutting-edge Java 21 features including Virtual Threads, Foreign Function & Memory API, Record Patterns, and Sealed Interfaces.

![Status](https://img.shields.io/badge/status-working-brightgreen)
![Version](https://img.shields.io/badge/version-1.28-blue)
![Java](https://img.shields.io/badge/java-21-orange)
![License](https://img.shields.io/badge/license-GPL--3.0-blue)

## ✨ Features

- 🎮 **Fully Interactive** - Real keyboard & mouse navigation and widget interaction
- 🖱️ **Window Manipulation** - Drag to move windows, resize by dragging edges and corners
- 🎨 **Color Support** - 8 standard colors with predefined color pairs and 10 built-in themes
- 📝 **Advanced Text Editing** - Selection, cut/copy/paste, undo/redo, word navigation in text fields
- 📜 **Scrollable Views** - JScrollPane with viewport clipping and scrollbar integration
- ☕ **Modern Java 21** - Virtual Threads, Foreign Function API, Record Patterns, Sealed Interfaces
- 🎯 **29 Widgets** - Complete AWT-compatible component set
- 🔒 **Thread-Safe** - ReentrantLock protection for all components
- ⚡ **Fast Rendering** - Differential updates, dirty rectangles, layout caching
- 🎭 **Themes** - 10 built-in themes (modern, retro computing, and classic IDE styles) with pluggable architecture
- 🧩 **Module System** - Java 9+ JPMS support (opt-in via `module-info.java.template`)
- 📦 **Zero Dependencies** - Only ncurses (native) and test libraries
- ✅ **Comprehensive Tests** - 799 tests (766 unit + 33 integration) with 99% coverage

## 🚀 Quick Start

**Linux/macOS:**
```bash
./run-interactive.sh
...
```

### Top 5 Largest Source Files
- ./src/test/java/org/flossware/curses/integration/Rendering3DIT.java (1267 lines)
- ./src/test/java/org/flossware/curses/integration/UIRenderingWithThemesIT.java (837 lines)
- ./src/test/java/org/flossware/curses/integration/ThemeSwitchingIT.java (837 lines)
- ./src/main/java/org/flossware/curses/api/Component.java (777 lines)
- ./src/test/java/org/flossware/curses/theme/Theme3DTest.java (767 lines)

---
**Analysis Complete**
