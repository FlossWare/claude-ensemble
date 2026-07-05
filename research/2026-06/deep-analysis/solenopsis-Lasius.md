# Deep Code Analysis: Lasius

**Analysis Date:** 2026-06-16
**Repository:** solenopsis/Lasius

## 1. Repository Structure

```
.
├── common
│   ├── src
│   │   ├── main
│   │   └── test
│   └── pom.xml
├── mindmaps
│   └── SFDC Web Service Interaction.mm
├── wsutils
│   ├── common
│   │   ├── src
│   │   └── pom.xml
│   ├── custom
│   │   ├── src
│   │   └── pom.xml
│   ├── enterprise
│   │   ├── src
│   │   └── pom.xml
│   ├── metadata
│   │   ├── src
│   │   └── pom.xml
│   ├── partner
│   │   ├── src
│   │   └── pom.xml
│   ├── tooling
│   │   ├── src
│   │   └── pom.xml
│   ├── wsdls
│   │   ├── src
│   │   └── pom.xml
│   └── pom.xml
├── CallDecoration.txt
├── CODE_OF_CONDUCT.md
├── LICENSE.md
├── pom.xml
└── README.md

21 directories, 15 files
```

**File Statistics:**
- Total files: 78
- Java files: 50
- XML files: 13
- Python files: 0
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**
- Maven (pom.xml found)

**Key Packages/Modules:**

**Design Patterns Detected:**
- Pattern usage: 14 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 4

**Documentation:**
- README.md (229 lines)
- Javadoc annotations: 643

**Code Metrics:**

## 4. Key Files Deep Dive

### pom.xml (Maven Configuration)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="https://maven.apache.org/POM/4.0.0" xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://maven.apache.org/POM/4.0.0 https://maven.apache.org/maven-v4_0_0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>org.solenopsis.lasius</groupId>
    <artifactId>lasius-parent</artifactId>
    <version>3.0.39</version>
    <packaging>pom</packaging>

    <name>Lasius</name>

    <properties>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

        <org.apache.maven.plugins_maven-compiler-plugin_version>3.6.1</org.apache.maven.plugins_maven-compiler-plugin_version>
        <org.apache.maven.plugins_maven-surefire-plugin_version>3.0.0-M3</org.apache.maven.plugins_maven-surefire-plugin_version>

        <org.flossware.core_version>2.1.17</org.flossware.core_version>

        <com.fasterxml.jackson.core_jackson-core_version>2.5.2</com.fasterxml.jackson.core_jackson-core_version>
        <commons-collections_commons-collections_version>3.2.1</commons-collections_commons-collections_version>
        <commons-configuration_commons-configuration_version>1.10</commons-configuration_commons-configuration_version>
        <log4j_log4j_version>1.2.17</log4j_log4j_version>
        <junit_junit_version>4.12</junit_junit_version>
        <org.mockito_mockito-all_version>2.0.2-beta</org.mockito_mockito-all_version>
    </properties>

    <developers>
        <developer>
            <name>Scot P. Floess</name>
            <id>flossy</id>
            <email>flossware@gmail.com</email>
            <organization>Solenopsis</organization>
            <roles>
                <role>Developer</role>
            </roles>
            <timezone>-4</timezone>
        </developer>
    </developers>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>${org.apache.maven.plugins_maven-surefire-plugin_version}</version>
            </plugin>

            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
...
```

**Dependencies:**
- lasius-parent
- maven-surefire-plugin
- maven-compiler-plugin
- common
- utils
- wsutils-service
- wsutils-soap
- jackson-core
- commons-configuration
- commons-collections

### README.md
```markdown
# Lasius

Welcome to Lasius - a Java utility framework for SFDC.

_Please be aware we will be phasing out much of the present functionality found in version 3.x.y.  Subsequent versions (4.0.0 and beyond) will resemble the new next-gen subproject.  A major refactoring has been written containing much of the connection like functionality now found in project [Keraiai](https://github.com/solenopsis/Keraiai)._

![Build Status](https://flossware.no-ip.org:58080/buildStatus/icon?job=Solenopsis-Lasius&style=plastic)

## 3.x.y Versions (and Prior)

This project contains many useful features, but chief among them is automatic session management to your SFDC web services ([custom](https://developer.salesforce.com/page/Apex_Web_Services_and_Callouts), [enterprise](https://github.com/solenopsis/Lasius/blob/master/wsutils/wsdls/src/main/resources/wsdl/Lasius-enterprise.wsdl), [metadata](https://github.com/solenopsis/Lasius/blob/master/wsutils/wsdls/src/main/resources/wsdl/Lasius-metadata.wsdl), [partner](https://github.com/solenopsis/Lasius/blob/master/wsutils/wsdls/src/main/resources/wsdl/Lasius-partner.wsdl),  and [tooling](https://github.com/solenopsis/Lasius/blob/master/wsutils/wsdls/src/main/resources/wsdl/Lasius-tooling.wsdl)).  By this we mean using credentials (user name, password, security token SFDC API version, and URL), we can provide:
* Automatic login.
* Automatic re-login should a session id become invalid.
* Concurrent threaded access to SFDC per session id.
* Multiplexed session ids for scaling up simultaneous concurrent calls to SFDC.

The most interesting thing to consider in the aforementioned statements is there is nothing special you must do other than have your SFDC WSDL and use [wsimport](https://docs.oracle.com/javase/6/docs/technotes/tools/share/wsimport.html) to generate your client Java code.  Once you've done this, in a matter of a few lines of code, you can leverage the above bullet points.  The following sections will show you all that's involved.

### Credentials

[Credentials](https://github.com/solenopsis/Lasius/blob/master/common/src/main/java/org/solenopsis/lasius/credentials/Credentials.java) are nothing more than a user name, password, security token, API version and URL (the  SFDC URL to use when we login - ie https://test.salesforce.com or https://login.salesforce.com).  There exists an interface aptly entitled [Credentials](https://github.com/solenopsis/Lasius/blob/master/common/src/main/java/org/solenopsis/lasius/credentials/Credentials.java) and a few implementations:
* [Default Credentials](https://github.com/solenopsis/Lasius/blob/master/common/src/main/java/org/solenopsis/lasius/credentials/DefaultCredentials.java):  simple holder of the aforementioned items such as user name, password, etc.
* [Properties Credentials](https://github.com/solenopsis/Lasius/blob/master/common/src/main/java/org/solenopsis/lasius/credentials/PropertiesCredentials.java):  uses a [property manager](https://github.com/FlossWare/java/tree/master/utils/src/main/java/org/flossware/util/properties), from the [FlossWare java library](https://github.com/FlossWare/java), to load properties containing the aforementioned items such as user name, password, etc.

#### Example

##### /tmp/myuser/creds/single/lone-user.properties

```properties
username = loneuser@some.company.com
...
```

### Top 5 Largest Source Files
- ./wsutils/common/src/main/java/org/solenopsis/lasius/wsimport/common/util/SalesforceWebServiceUtil.java (450 lines)
- ./wsutils/tooling/src/main/java/org/solenopsis/lasius/wsimport/tooling/util/ToolingWebServiceUtil.java (262 lines)
- ./wsutils/custom/src/main/java/org/solenopsis/lasius/wsimport/custom/util/CustomWebServiceUtil.java (262 lines)
- ./wsutils/partner/src/main/java/org/solenopsis/lasius/wsimport/partner/util/PartnerWebServiceUtil.java (261 lines)
- ./wsutils/metadata/src/main/java/org/solenopsis/lasius/wsimport/metadata/util/MetadataWebServiceUtil.java (261 lines)

---
**Analysis Complete**
