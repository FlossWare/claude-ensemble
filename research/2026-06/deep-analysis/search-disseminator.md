# Deep Code Analysis: disseminator

**Analysis Date:** 2026-06-16
**Repository:** search-engineering/disseminator

## 1. Repository Structure

```
.
├── ansible
│   ├── deploy.yml
│   └── stop_indexing.yml
├── ci
│   ├── scripts
│   │   ├── addVersionToJira.sh
│   │   ├── build_secrets.sh
│   │   ├── build_tower_secrets.sh
│   │   ├── call-tower.sh
│   │   ├── commentOnJiras.sh
│   │   ├── compute_pom_version.sh
│   │   ├── compute_values.sh
│   │   ├── compute_version.sh
│   │   ├── create_ssh.sh
│   │   ├── delete-tag.sh
│   │   ├── deploy_solr_artifact.sh
│   │   ├── generate-dependency-cache-key.sh
│   │   ├── getJiras.sh
│   │   ├── oc_setup.sh
│   │   ├── post_to_jira.sh
│   │   ├── solr.sh
│   │   ├── updateJiraStatus.sh
│   │   └── upload2nexus.sh
│   ├── git_config
│   ├── secret.yml
│   ├── ssh_config
│   └── vars.yml
├── data
│   └── CatalogPage.json
├── infra
│   ├── inventory
│   │   ├── aws-prod-disseminator
│   │   ├── aws-qa-disseminator
│   │   ├── aws-stage-disseminator
│   │   └── psi
│   ├── local_setup_templates
│   │   ├── solr.in.sh
│   │   └── solr.xml
│   ├── roles
│   │   ├── destroy-solr
│   │   ├── destroy-zk
│   │   ├── java
│   │   ├── solr
│   │   └── zookeeper
│   ├── configure-java.yml
│   ├── configure-solr.yml
│   ├── configure-zk.yml
│   ├── destroy-solr.yml
│   ├── destroy-zk.yml
│   ├── restart-solr.yml
│   ├── restart-zk.yml
│   └── stop-solr.yml
├── load_test
│   ├── test-data
│   │   ├── comet_search_with_query_string - comet_search_with_query_string.csv.csv
│   │   ├── connect_search_traffic_with_query_string.csv
│   │   ├── docs_search_query_string.csv
│   │   ├── kbe_search_params_with_query_string.csv
│   │   ├── rs_search_cases_accounts_with_query_string.csv
│   │   ├── rs_search_platform_access_connect_recommendation_with_query_string.csv
│   │   ├── rs_search_recommendations_with_query_string.csv
│   │   └── rs_search_traffic_without_any_specific_redhat_client_modified.csv
│   ├── DisseminatorLoadTest.jmx
│   └── README.md
├── mindmaps
│   ├── Re-architecture.mm
│   ├── ROSA.mm
│   └── Search Routes.mm
├── scripts
│   ├── psi
│   │   ├── application.properties
│   │   ├── deploy-psi.sh
│   │   └── deploy-psi-solr.sh
│   ├── python
│   │   ├── CamelRouteStatus
│   │   └── eolDocumentation
│   ├── backup.sh
│   ├── camel-util.sh
│   ├── create-collection.sh
│   ├── deleteOldBackup.sh
│   ├── evaluate_test_set.py
│   ├── properties.sh
│   ├── run-disseminator.sh
│   ├── run-disseminator-standalone.sh
│   ├── solr-util.sh
│   ├── ssh-aws.sh
│   ├── ssh.sh
│   ├── status-collector.py
│   ├── upload-configs.sh
│   └── util.sh
├── src
│   ├── main
│   │   ├── java
│   │   └── resources
│   └── test
│       ├── java
│       └── resources
├── tests
│   └── functional-tests
```

**File Statistics:**
- Total files: 2684
- Java files: 1376
- XML files: 209
- Python files: 4
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**
- Maven (pom.xml found)

**Key Packages/Modules:**
- com.redhat.disseminator

**Design Patterns Detected:**
- Pattern usage: 312 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 429
- Test directory: src/test/
- CI/CD: GitLab CI configured

**Documentation:**
- README.md (100 lines)
- Javadoc annotations: 400

**Code Metrics:**
- Java LOC: 52958

## 4. Key Files Deep Dive

### pom.xml (Maven Configuration)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
	xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
	xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
	<modelVersion>4.0.0</modelVersion>

	<parent>
		<groupId>org.springframework.boot</groupId>
		<artifactId>spring-boot-starter-parent</artifactId>
		<version>3.4.3</version>
		<relativePath />
	</parent>

	<groupId>com.redhat</groupId>
	<artifactId>disseminator</artifactId>
	<version>2.495</version>
    <name>Search Engineering:  Disseminator</name>
    <description>The Search Engineering Disseminator project</description>

	<url>https://redhat.com</url>

	<scm>
        <connection>scm:git:git@gitlab.cee.redhat.com:search-engineering/disseminator.git</connection>
        <developerConnection>scm:git:git@gitlab.cee.redhat.com:search-engineering/disseminator.git</developerConnection>
		<url>https://gitlab.cee.redhat.com/search-engineering/disseminator</url>
	</scm>

	<distributionManagement>
		<repository>
			<id>nexus</id>
			<name>nexus</name>
			<url>https://nexus.corp.redhat.com/repository/information-retrieval-maven2-releases/</url>
		</repository>
	</distributionManagement>

	<properties>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>

		<java.version>21</java.version>
        <maven.compiler.source>21</maven.compiler.source>
        <maven.compiler.target>21</maven.compiler.target>

        <org.codehaus.mojo_rpm-maven-plugin>2.3.0</org.codehaus.mojo_rpm-maven-plugin>
        <org.apache.maven.plugins_maven-jar-plugin>3.3.0</org.apache.maven.plugins_maven-jar-plugin>
		<org.apache.maven.plugins_maven-scm-plugin>2.0.1</org.apache.maven.plugins_maven-scm-plugin>

        <org.springdoc_springdoc-openapi-starter-webmvc-ui>2.6.0</org.springdoc_springdoc-openapi-starter-webmvc-ui>

        <camel.version>4.10.2</camel.version>
		<log4j.version>2.21.1</log4j.version>
...
```

**Dependencies:**
- spring-boot-starter-parent
- disseminator
- dependency-check-maven
- maven-surefire-plugin
- maven-resources-plugin
- spring-boot-maven-plugin
- camel-maven-plugin
- maven-assembly-plugin
- maven-jar-plugin
- maven-surefire-plugin

### README.md
```markdown
# [Disseminator](https://gitlab.cee.redhat.com/search-engineering/disseminator)

## Requirements

### [Java 17](https://openjdk.org/projects/jdk/17/)
[Java 17](https://openjdk.org/projects/jdk/17/) is the required version for [Disseminator](https://gitlab.cee.redhat.com/search-engineering/disseminator).  It is recommended to use [SdkMan!](https://sdkman.io) for managing your JVMs.

### [Maven](https://maven.apache.org)
[Disseminator](https://gitlab.cee.redhat.com/search-engineering/disseminator) uses [Maven](https://maven.apache.org) for building.  You can use [SdkMan!](https://sdkman.io) to install or leverage the script [mvnw](https://gitlab.cee.redhat.com/search-engineering/disseminator/-/blob/main/mvnw) which is a [Maven Wrapper](https://maven.apache.org/wrapper/).

### Importing Certs for Your JVM

A number of certs are required when building and running [Disseminator](https://gitlab.cee.redhat.com/search-engineering/disseminator):
* [Nexus](https://nexus.corp.redhat.com)
* [Downloads](https://downloads.corp.qa.redhat.com)

_Please refer to your browser's documentation to download certs._

To import a key:

`keytool -importcert -file [Fully Qualified Path to the Downloaded PEM file] -alias [Something Meaningful] -keystore ${JAVA_HOME}/lib/security/cacerts`

Examples:

| Host | Command |
|-----------|-----------|
| [Nexus](https://nexus.corp.redhat.com) | `keytool -importcert -file ~/Downloads/nexus.corp.redhat.pem -alias nexus -keystore ${JAVA_HOME}/lib/security/cacerts` |
| [Downloads](https://downloads.corp.qa.redhat.com) | `keytool -importcert -file ~/Downloads/downloads.corp.preprod.redhat.pem -alias downloads -keystore ${JAVA_HOME}/lib/security/cacerts` |

The passwords for both are `changeit`.
...
```

### Top 5 Largest Source Files
- total (5571 lines)
- ./tests/functional-tests/src/test/java/com/redhat/disseminator/functional/tests/diagNodeTests/CaseSearchTest.java (990 lines)
- ./tests/functional-tests/src/test/java/com/redhat/disseminator/functional/tests/kcsRecommendations/KcsRecommendationsTest.java (872 lines)
- ./tests/functional-tests/src/test/java/com/redhat/disseminator/functional/tests/solr/CollectionFieldsTest.java (810 lines)
- ./tests/functional-tests/src/test/java/com/redhat/disseminator/functional/tests/sanityTests/SanityTestsForSearchRoutes.java (760 lines)

---
**Analysis Complete**
