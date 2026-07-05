# Deep Code Analysis: metadata

**Analysis Date:** 2026-06-16
**Repository:** solenopsis/metadata

## 1. Repository Structure

```
.
├── src
│   └── main
│       └── java
├── CODE_OF_CONDUCT.md
├── LICENSE
├── pom.xml
└── README.md

4 directories, 4 files
```

**File Statistics:**
- Total files: 11
- Java files: 7
- XML files: 1
- Python files: 0
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**
- Maven (pom.xml found)

**Key Packages/Modules:**
- org.solenopsis.metadata

**Design Patterns Detected:**
- Pattern usage: 0 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 0

**Documentation:**
- README.md (20 lines)
- Javadoc annotations: 0

**Code Metrics:**
- Java LOC: 664

## 4. Key Files Deep Dive

### pom.xml (Maven Configuration)
```xml
<project xmlns="https://maven.apache.org/POM/4.0.0" xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/POM/4.0.0 https://maven.apache.org/maven-v4_0_0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>org.solenopsis</groupId>
    <artifactId>metadata</artifactId>
    <version>1.0.0</version>
    <url>https://github.com/solenopsis/Metadata</url>

    <packaging>jar</packaging>

    <name>Metadata Application Library</name>
    <description>Provides useful metata applications.</description>

    <licenses>
        <license>
            <name>GNU General Public License, Version 3</name>
            <url>https://www.gnu.org/licenses/gpl-3.0.txt</url>
            <distribution>repo</distribution>
        </license>
    </licenses>

    <properties>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

        <java>1.8</java>

        <com.github.github_site-maven-plugin>0.12</com.github.github_site-maven-plugin>
        <org.apache.maven.plugins_maven-compiler-plugin>3.6.1</org.apache.maven.plugins_maven-compiler-plugin>
        <org.apache.maven.plugins_maven-surefire-plugin>2.19.1</org.apache.maven.plugins_maven-surefire-plugin>
        <org.apache.maven.plugins_maven-project-info-reports-plugin>2.9</org.apache.maven.plugins_maven-project-info-reports-plugin>
        <org.apache.maven.plugins_maven-javadoc-plugin>2.10.4</org.apache.maven.plugins_maven-javadoc-plugin>
        <org.apache.maven.plugins_maven-surefire-report-plugin>2.19.1</org.apache.maven.plugins_maven-surefire-report-plugin>
        <org.codehaus.mojo_cobertura-maven-plugin>2.7</org.codehaus.mojo_cobertura-maven-plugin>
        <org.apache.maven.plugins_maven-pmd-plugin>3.7</org.apache.maven.plugins_maven-pmd-plugin>
        <org.apache.maven.plugins_maven-jxr-plugin>2.5</org.apache.maven.plugins_maven-jxr-plugin>
        <org.codehaus.mojo_findbugs-maven-plugin>3.0.4</org.codehaus.mojo_findbugs-maven-plugin>
        <net.sourceforge.cobertura_cobertura>2.1.1</net.sourceforge.cobertura_cobertura>

        <org.apache.httpcomponents_httpclient>4.5.13</org.apache.httpcomponents_httpclient>
        <commons-io_commons-io>2.7</commons-io_commons-io>

        <org.solenopsis_keraiai>3.0.8</org.solenopsis_keraiai>

        <junit_junit>4.12</junit_junit>

        <github.global.server>github</github.global.server>
    </properties>

    <developers>
        <developer>
...
```

**Dependencies:**
- metadata
- site-maven-plugin
- maven-compiler-plugin
- maven-surefire-plugin
- maven-javadoc-plugin
- cobertura-maven-plugin
- maven-pmd-plugin
- httpclient
- commons-io
- cobertura-maven-plugin

### README.md
```markdown
# Metadata

This project contains various metadata related applications.

## Retrieving WSDLs

You can automagically download all API and custom WSDLs for your org.

### To Run

We support the following application args:
* --solenopsis [name of env]
* --cred [fully qualified path to a credentials property file]
* --prefix [prefix for each wsdl file]
* --dir [fully qualified path to store downloads WSDLs]

Notes:
* If you do not provide a `--dir` option, your home directory will be the output directory.
* You need to provide either a `--solenopsis` or `--cred` params.

`mvn clean install exec:java -Dexec.mainClass=org.solenopsis.metadata.wsdl.RetrieveWsdls -Dexec.args="[aforementioned parameters]"`...
```

### Top 5 Largest Source Files
- ./src/main/java/org/solenopsis/metadata/wsdl/RetrieveWsdls.java (184 lines)
- ./src/main/java/org/solenopsis/metadata/WildcardEnum.java (158 lines)
- ./src/main/java/org/solenopsis/metadata/wsdl/Context.java (84 lines)
- ./src/main/java/org/solenopsis/metadata/xml/Types.java (74 lines)
- ./src/main/java/org/solenopsis/metadata/xml/Package.java (69 lines)

---
**Analysis Complete**
