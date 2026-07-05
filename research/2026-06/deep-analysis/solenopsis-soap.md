# Deep Code Analysis: soap

**Analysis Date:** 2026-06-16
**Repository:** solenopsis/soap

## 1. Repository Structure

```
.
├── src
│   ├── main
│   │   ├── java
│   │   └── resources
│   └── test
│       └── java
├── API.md
├── ARCHITECTURE.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── LICENSE
├── pom.xml
└── README.md

7 directories, 7 files
```

**File Statistics:**
- Total files: 48
- Java files: 34
- XML files: 3
- Python files: 0
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**
- Maven (pom.xml found)

**Key Packages/Modules:**
- org.solenopsis.soap

**Design Patterns Detected:**
- Pattern usage: 164 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 11
- Test directory: src/test/

**Documentation:**
- README.md (230 lines)
- Javadoc annotations: 44

**Code Metrics:**
- Java LOC: 1142

## 4. Key Files Deep Dive

### pom.xml (Maven Configuration)
```xml
<?xml version="1.0" encoding="UTF-8"?>

<project xmlns="https://maven.apache.org/POM/4.0.0" xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>org.solenopsis</groupId>
    <artifactId>soap</artifactId>
    <version>1.22</version>

    <name>Solenopsis:  Salesforce SOAP Library</name>
    <description>This project is a Java SOAP library for SFDC.</description>

    <url>https://github.com/solenopsis/soap</url>

    <licenses>
        <license>
            <name>GNU General Public License, Version 3</name>
            <url>https://www.gnu.org/licenses/gpl-3.0.txt</url>
            <distribution>repo</distribution>
        </license>
    </licenses>

    <packaging>jar</packaging>

    <properties>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>

        <org.apache.maven.plugins_maven-scm-plugin>2.0.1</org.apache.maven.plugins_maven-scm-plugin>

        <org.apache.commons_commons-lang3>3.20.0</org.apache.commons_commons-lang3>

        <org.flossware_jcommons>1.21</org.flossware_jcommons>

        <cxf.version>4.0.9</cxf.version>

        <org.junit.jupiter_junit-jupiter-api>5.11.4</org.junit.jupiter_junit-jupiter-api>
        <org.mockito_mockito-core>5.14.2</org.mockito_mockito-core>
        <slf4j.version>2.0.16</slf4j.version>
        <logback.version>1.5.12</logback.version>

        <message>Automated Version Bump ${project.version} [ci skip]</message>
    </properties>

    <scm>
        <connection>scm:git:https://github.com/solenopsis/soap.git</connection>
        <developerConnection>scm:git:https://github.com/solenopsis/soap.git</developerConnection>
        <url>https://github.com/solenopsis/soap</url>
...
```

**Dependencies:**
- soap
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
# Solenopsis SOAP

Java library containing Salesforce SOAP web service clients for all major Salesforce APIs.

[![Build Status](https://github.com/solenopsis/soap/workflows/CD-CI/badge.svg)](https://github.com/solenopsis/soap/actions)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## Overview

This library provides pre-generated SOAP clients for Salesforce APIs using Apache CXF. It automatically generates Java classes from Salesforce WSDL files for:

- **Apex API** - Execute anonymous Apex code and manage logs
- **Enterprise API** - Full-featured data API with strong typing
- **Metadata API** - Deploy and retrieve metadata (custom objects, Apex classes, etc.)
- **Partner API** - Flexible data API with dynamic typing
- **Tooling API** - Developer tools and schema introspection

## Features

- Pre-generated SOAP clients from official Salesforce WSDLs
- Factory pattern for easy service/port creation
- Enum-based API for type-safe service selection
- QName management for web service endpoints
- Built on [FlossWare JCommons](https://github.com/FlossWare/jcommons) for SOAP utilities

## Installation

### Maven

```xml
...
```

### Top 5 Largest Source Files
- ./src/test/java/org/solenopsis/soap/service/ServiceWsdlEnumTest.java (161 lines)
- ./src/main/java/org/solenopsis/soap/port/factory/PortFactoryEnum.java (129 lines)
- ./src/test/java/org/solenopsis/soap/port/factory/PortFactoryEnumTest.java (125 lines)
- ./src/test/java/org/solenopsis/soap/port/PortMethodEnumTest.java (120 lines)
- ./src/test/java/org/solenopsis/soap/service/ServiceEnumTest.java (115 lines)

---
**Analysis Complete**
