# Deep Code Analysis: Keraiai

**Analysis Date:** 2026-06-16
**Repository:** solenopsis/Keraiai

## 1. Repository Structure

```
.
├── jaxws
│   └── binding.xml
├── src
│   ├── 2017-01-02_14-11_bak
│   │   ├── main
│   │   └── test
│   ├── 2017-04-08_05-33_bak
│   │   └── test
│   ├── 2017-05-28_11-33_bak
│   │   └── main
│   ├── main
│   │   ├── java
│   │   └── resources
│   └── test
│       └── java
├── CODE_OF_CONDUCT.md
├── LICENSE.md
├── logSoap.txt
├── pom.xml
├── README.md
└── workToDo.txt

15 directories, 7 files
```

**File Statistics:**
- Total files: 111
- Java files: 97
- XML files: 2
- Python files: 0
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**
- Maven (pom.xml found)

**Key Packages/Modules:**
- org.solenopsis.keraiai

**Design Patterns Detected:**
- Pattern usage: 100 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 39
- Test directory: src/test/

**Documentation:**
- README.md (175 lines)
- Javadoc annotations: 463

**Code Metrics:**
- Java LOC: 3051

## 4. Key Files Deep Dive

### pom.xml (Maven Configuration)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="https://maven.apache.org/POM/4.0.0" xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="https://maven.apache.org/POM/4.0.0 https://maven.apache.org/maven-v4_0_0.xsd">
	<modelVersion>4.0.0</modelVersion>
	<groupId>org.solenopsis</groupId>
	<artifactId>keraiai</artifactId>
	<version>4.0.8</version>
    <url>https://github.com/solenopsis/Keraiai</url>
    
    <licenses>
        <license>
            <name>GNU General Public License, Version 3</name>
            <url>https://www.gnu.org/licenses/gpl-3.0.txt</url>
            <distribution>repo</distribution>
        </license>
    </licenses>

	<packaging>jar</packaging>

    <name>Keraiai SFDC Communication Library</name>
    <description>This project is a Java communication library for SFDC.</description>

    <properties>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

        <java_version>1.7</java_version>

        <com.github.github_site-maven-plugin_version>0.12</com.github.github_site-maven-plugin_version>
        <org.apache.maven.plugins_maven-compiler-plugin_version>3.6.1</org.apache.maven.plugins_maven-compiler-plugin_version>
        <org.apache.maven.plugins_maven-surefire-plugin_version>3.0.0-M3</org.apache.maven.plugins_maven-surefire-plugin_version>
        <org.apache.maven.plugins_maven-project-info-reports-plugin_version>2.9</org.apache.maven.plugins_maven-project-info-reports-plugin_version>
        <org.apache.maven.plugins_maven-javadoc-plugin_version>2.10.4</org.apache.maven.plugins_maven-javadoc-plugin_version>
        <org.apache.maven.plugins_maven-surefire-report-plugin_version>2.19.1</org.apache.maven.plugins_maven-surefire-report-plugin_version>
        <org.codehaus.mojo_cobertura-maven-plugin_version>2.7</org.codehaus.mojo_cobertura-maven-plugin_version>
        <org.apache.maven.plugins_maven-pmd-plugin_version>3.7</org.apache.maven.plugins_maven-pmd-plugin_version>
        <org.apache.maven.plugins_maven-jxr-plugin_version>2.5</org.apache.maven.plugins_maven-jxr-plugin_version>
        <org.codehaus.mojo_findbugs-maven-plugin_version>3.0.4</org.codehaus.mojo_findbugs-maven-plugin_version>
        <org.jvnet.jax-ws-commons_jaxws-maven-plugin_version>2.3</org.jvnet.jax-ws-commons_jaxws-maven-plugin_version>
        <net.sourceforge.cobertura_cobertura_version>2.1.1</net.sourceforge.cobertura_cobertura_version>
        <org.flossware_jCore_version>1.0.52</org.flossware_jCore_version>

        <junit_junit_version>4.12</junit_junit_version>

		<base.package>org.solenopsis.keraiai.wsdl</base.package>

        <github.global.server>github</github.global.server>
    </properties>

    <developers>
        <developer>
...
```

**Dependencies:**
- keraiai
- site-maven-plugin
- maven-compiler-plugin
- maven-surefire-plugin
- jaxws-maven-plugin
- maven-javadoc-plugin
- cobertura-maven-plugin
- maven-pmd-plugin
- maven-project-info-reports-plugin
- maven-javadoc-plugin

### README.md
```markdown
# Keraiai

Welcome to Keraiai - a Java communication library for SFDC.

![Build Status](https://flossware.no-ip.org:58080/buildStatus/icon?job=Solenopsis-Keraiai&style=plastic)

## Keraiai vs Lasius?

Currently, [Lasius](https://github.com/solenopsis/Lasius) contains WSDLs for the Enterprise, Partner, Metadata and Tooling APIs...as well as similar communications functionality as found here.  However, we decided to simplifiy the libraries:
* Keraiai will provide all communications related functionality.
* [Lasius](https://github.com/solenopsis/Lasius) will provide other general utility functionality.

## What Does Keraiai Mean?

Like all [Solenopsis](https://github.com/solenopsis) themes, we wanted to choose a Latin or Greek word related to ants.  Since this is project is for SFDC communication, we considered an ant's antenna.  The word [keraiai](https://dictionary.reference.com/browse/antennae) is actually Greek and refers to an insect's horns.

## Design Decisions

### Interfaces Located Within Parent Packages

When an interface can be shared across sub-packages, we chose to define those interfaces in parent packages.

### Enums

#### Implement Interfaces

If you browse the source code, you will note we make heavy use of enums which implement interfaces.  Doing so allows us to more naturally decouple and allows us to mock implementations in our unit tests.

#### Declarative Model

...
```

### Top 5 Largest Source Files
- ./src/2017-04-08_05-33_bak/test/java/org/solenopsis/keraiai/soap/port/PortUtilsTest.java (682 lines)
- ./src/2017-04-08_05-33_bak/test/java/org/solenopsis/keraiai/credentials/CredentialsUtilsTest.java (522 lines)
- ./src/2017-05-28_11-33_bak/main/java/zzzz/org/solenopsis/keraiai/soap/oldport/OldPortUtils.java (474 lines)
- ./src/2017-01-02_14-11_bak/test/java/org/solenopsis/keraiai/soap/AbstractSoapMgrTest.java (432 lines)
- ./src/2017-05-28_11-33_bak/main/java/zzzz/org/solenopsis/keraiai/soap/oldport/PortUtils.java (428 lines)

---
**Analysis Complete**
