#!/usr/bin/env python3
"""Baeldung Java/Spring ecosystem scraper.

Covers:
  - Java core (collections, streams, concurrency, IO, generics, annotations)
  - Spring (Boot, MVC, Security, Data, Cloud, Batch, WebFlux)
  - Persistence (JPA, Hibernate, JDBC, MongoDB, Redis)
  - Testing (JUnit, Mockito, integration testing)
  - Kotlin, DevOps, Algorithms
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class BaeldungScraper(BaseScraper):
    """Scrape Baeldung Java/Spring tutorials."""

    SOURCES = {
        "java-core": {
            "pages": {
                # Collections
                "https://www.baeldung.com/java-collections": "Guide to Java Collections",
                "https://www.baeldung.com/java-arraylist": "ArrayList Guide",
                "https://www.baeldung.com/java-linkedlist": "LinkedList Guide",
                "https://www.baeldung.com/java-hashmap": "HashMap Guide",
                "https://www.baeldung.com/java-hashset": "HashSet Guide",
                "https://www.baeldung.com/java-treemap": "TreeMap Guide",
                "https://www.baeldung.com/java-treeset": "TreeSet Guide",
                "https://www.baeldung.com/java-linkedhashmap": "LinkedHashMap Guide",
                "https://www.baeldung.com/java-queue": "Queue Interface Guide",
                "https://www.baeldung.com/java-deque": "Deque Interface Guide",
                "https://www.baeldung.com/java-priority-queue": "PriorityQueue Guide",
                "https://www.baeldung.com/java-concurrent-map": "ConcurrentMap Guide",
                "https://www.baeldung.com/java-concurrenthashmap": "ConcurrentHashMap Guide",
                "https://www.baeldung.com/java-blocking-queue": "BlockingQueue Guide",
                "https://www.baeldung.com/java-concurrent-queues": "Concurrent Queues Guide",
                "https://www.baeldung.com/java-copy-on-write-arraylist": "CopyOnWriteArrayList Guide",
                "https://www.baeldung.com/java-immutable-list": "Immutable List",
                "https://www.baeldung.com/java-list-to-map": "List to Map Conversion",
                "https://www.baeldung.com/java-iterate-map": "Iterate Over a Map",
                "https://www.baeldung.com/java-map-computeifabsent": "Map computeIfAbsent",
                "https://www.baeldung.com/java-sorting": "Sorting in Java",
                "https://www.baeldung.com/java-comparator-comparable": "Comparator and Comparable",
                "https://www.baeldung.com/java-collections-interview-questions": "Collections Interview Questions",
                "https://www.baeldung.com/java-array-to-list": "Array to List Conversion",
                "https://www.baeldung.com/java-list-to-array": "List to Array Conversion",
                "https://www.baeldung.com/java-initialize-hashmap": "Initialize HashMap",
                "https://www.baeldung.com/java-map-entry": "Map.Entry Interface",
                "https://www.baeldung.com/java-enumerate-map": "Enumerate a Map",
                "https://www.baeldung.com/java-weakhashmap": "WeakHashMap Guide",
                "https://www.baeldung.com/java-identityhashmap": "IdentityHashMap Guide",
                "https://www.baeldung.com/java-enummap": "EnumMap Guide",
                "https://www.baeldung.com/java-enumset": "EnumSet Guide",
                # Streams
                "https://www.baeldung.com/java-8-streams": "Java 8 Streams",
                "https://www.baeldung.com/java-8-streams-introduction": "Streams Introduction",
                "https://www.baeldung.com/java-stream-reduce": "Stream reduce()",
                "https://www.baeldung.com/java-stream-collect": "Stream collect()",
                "https://www.baeldung.com/java-groupingby-collector": "groupingBy Collector",
                "https://www.baeldung.com/java-stream-filter-lambda": "Stream filter()",
                "https://www.baeldung.com/java-stream-map": "Stream map()",
                "https://www.baeldung.com/java-stream-flatmap": "Stream flatMap()",
                "https://www.baeldung.com/java-stream-findany-findfirst": "findAny() vs findFirst()",
                "https://www.baeldung.com/java-stream-operations-on-strings": "Stream Operations on Strings",
                "https://www.baeldung.com/java-stream-immutable-collection": "Stream to Immutable Collection",
                "https://www.baeldung.com/java-parallel-streams": "Parallel Streams",
                "https://www.baeldung.com/java-optional": "Optional Guide",
                "https://www.baeldung.com/java-stream-to-list": "Stream to List",
                "https://www.baeldung.com/java-stream-distinct": "Stream distinct()",
                "https://www.baeldung.com/java-stream-peek": "Stream peek()",
                "https://www.baeldung.com/java-stream-sum": "Stream Sum",
                "https://www.baeldung.com/java-stream-toarray": "Stream toArray()",
                "https://www.baeldung.com/java-collectors-tomap": "Collectors.toMap()",
                "https://www.baeldung.com/java-merge-streams": "Merge Streams",
                # Concurrency
                "https://www.baeldung.com/java-concurrency": "Java Concurrency Guide",
                "https://www.baeldung.com/java-executor-service-tutorial": "ExecutorService Tutorial",
                "https://www.baeldung.com/thread-pool-java-and-guava": "Thread Pools",
                "https://www.baeldung.com/java-completablefuture": "CompletableFuture Guide",
                "https://www.baeldung.com/java-future": "Future Interface",
                "https://www.baeldung.com/java-runnable-callable": "Runnable vs Callable",
                "https://www.baeldung.com/java-thread-lifecycle": "Thread Lifecycle",
                "https://www.baeldung.com/java-synchronized": "Synchronized Keyword",
                "https://www.baeldung.com/java-volatile": "Volatile Keyword",
                "https://www.baeldung.com/java-atomic-variables": "Atomic Variables",
                "https://www.baeldung.com/java-countdown-latch": "CountDownLatch",
                "https://www.baeldung.com/java-cyclic-barrier": "CyclicBarrier",
                "https://www.baeldung.com/java-semaphore": "Semaphore",
                "https://www.baeldung.com/java-concurrent-locks": "Concurrent Locks",
                "https://www.baeldung.com/java-reentrant-lock": "ReentrantLock",
                "https://www.baeldung.com/java-daemon-thread": "Daemon Threads",
                "https://www.baeldung.com/java-thread-safety": "Thread Safety",
                "https://www.baeldung.com/java-fork-join": "Fork/Join Framework",
                "https://www.baeldung.com/java-phaser": "Phaser",
                "https://www.baeldung.com/java-virtual-threads": "Virtual Threads",
                "https://www.baeldung.com/java-thread-join": "Thread.join()",
                "https://www.baeldung.com/java-wait-notify": "wait() and notify()",
                "https://www.baeldung.com/java-thread-local": "ThreadLocal",
                "https://www.baeldung.com/java-exchanger": "Exchanger",
                "https://www.baeldung.com/java-scheduled-executor-service": "ScheduledExecutorService",
                # IO
                "https://www.baeldung.com/java-io": "Java IO Guide",
                "https://www.baeldung.com/java-nio-2-file-api": "NIO 2 File API",
                "https://www.baeldung.com/java-nio2-file-visitor": "NIO 2 File Visitor",
                "https://www.baeldung.com/java-write-to-file": "Write to File",
                "https://www.baeldung.com/java-read-file": "Read a File",
                "https://www.baeldung.com/java-io-vs-nio": "IO vs NIO",
                "https://www.baeldung.com/java-path": "Path API",
                "https://www.baeldung.com/java-inputstream": "InputStream Guide",
                "https://www.baeldung.com/java-outputstream": "OutputStream Guide",
                "https://www.baeldung.com/java-buffered-reader": "BufferedReader Guide",
                "https://www.baeldung.com/java-serialization": "Serialization Guide",
                "https://www.baeldung.com/java-nio-selector": "NIO Selector",
                "https://www.baeldung.com/java-nio2-watchservice": "WatchService",
                # Generics
                "https://www.baeldung.com/java-generics": "Java Generics Guide",
                "https://www.baeldung.com/java-type-erasure": "Type Erasure",
                "https://www.baeldung.com/java-generics-interview-questions": "Generics Interview Questions",
                "https://www.baeldung.com/java-super-type-tokens": "Super Type Tokens",
                # Annotations and Reflection
                "https://www.baeldung.com/java-custom-annotation": "Custom Annotations",
                "https://www.baeldung.com/java-default-annotations": "Default Annotations",
                "https://www.baeldung.com/java-reflection": "Reflection Guide",
                "https://www.baeldung.com/java-method-reflection": "Method Reflection",
                # Core fundamentals
                "https://www.baeldung.com/java-string": "String Guide",
                "https://www.baeldung.com/java-string-builder-string-buffer": "StringBuilder vs StringBuffer",
                "https://www.baeldung.com/java-string-pool": "String Pool",
                "https://www.baeldung.com/java-equals-hashcode-contracts": "equals() and hashCode() Contracts",
                "https://www.baeldung.com/java-exceptions": "Exception Handling",
                "https://www.baeldung.com/java-checked-unchecked-exceptions": "Checked vs Unchecked Exceptions",
                "https://www.baeldung.com/java-try-with-resources": "Try-With-Resources",
                "https://www.baeldung.com/java-enum-values": "Enum Values",
                "https://www.baeldung.com/java-lambda-expressions-tips": "Lambda Expressions Tips",
                "https://www.baeldung.com/java-functional-interfaces": "Functional Interfaces",
                "https://www.baeldung.com/java-method-references": "Method References",
                "https://www.baeldung.com/java-record-keyword": "Record Keyword",
                "https://www.baeldung.com/java-sealed-classes-interfaces": "Sealed Classes and Interfaces",
                "https://www.baeldung.com/java-pattern-matching-instanceof": "Pattern Matching instanceof",
                "https://www.baeldung.com/java-switch-pattern-matching": "Switch Pattern Matching",
                "https://www.baeldung.com/java-text-blocks": "Text Blocks",
                "https://www.baeldung.com/java-modules": "Java Modules (JPMS)",
                "https://www.baeldung.com/java-classpath": "Classpath Guide",
                "https://www.baeldung.com/java-classloaders": "ClassLoaders Guide",
                "https://www.baeldung.com/java-immutable-object": "Immutable Objects",
                "https://www.baeldung.com/java-cloneable": "Cloneable Interface",
                "https://www.baeldung.com/java-iterable-to-stream": "Iterable to Stream",
                "https://www.baeldung.com/java-iterator": "Iterator Guide",
                "https://www.baeldung.com/java-type-casting": "Type Casting",
                "https://www.baeldung.com/java-wrapper-classes": "Wrapper Classes",
                "https://www.baeldung.com/java-autoboxing": "Autoboxing and Unboxing",
                "https://www.baeldung.com/java-varargs": "Varargs",
                "https://www.baeldung.com/java-inner-classes": "Inner Classes",
                "https://www.baeldung.com/java-anonymous-classes": "Anonymous Classes",
                "https://www.baeldung.com/java-interfaces": "Interfaces Guide",
                "https://www.baeldung.com/java-abstract-class": "Abstract Classes",
                "https://www.baeldung.com/java-inheritance": "Inheritance Guide",
                "https://www.baeldung.com/java-polymorphism": "Polymorphism",
                "https://www.baeldung.com/java-encapsulation": "Encapsulation",
            },
        },
        "spring": {
            "pages": {
                # Spring Boot
                "https://www.baeldung.com/spring-boot": "Spring Boot Introduction",
                "https://www.baeldung.com/spring-boot-start": "Getting Started with Spring Boot",
                "https://www.baeldung.com/spring-boot-starters": "Spring Boot Starters",
                "https://www.baeldung.com/spring-boot-auto-configuration": "Auto-Configuration",
                "https://www.baeldung.com/spring-boot-actuator": "Spring Boot Actuator",
                "https://www.baeldung.com/spring-boot-testing": "Spring Boot Testing",
                "https://www.baeldung.com/spring-profiles": "Spring Profiles",
                "https://www.baeldung.com/spring-boot-custom-starter": "Custom Starter",
                "https://www.baeldung.com/configuration-properties-in-spring-boot": "Configuration Properties",
                "https://www.baeldung.com/spring-boot-logging": "Logging in Spring Boot",
                "https://www.baeldung.com/spring-boot-embedded-tomcat-logs": "Embedded Tomcat Logs",
                "https://www.baeldung.com/spring-boot-devtools": "DevTools",
                "https://www.baeldung.com/spring-boot-annotations": "Spring Boot Annotations",
                "https://www.baeldung.com/spring-boot-docker": "Spring Boot with Docker",
                "https://www.baeldung.com/spring-boot-3": "Spring Boot 3",
                "https://www.baeldung.com/spring-boot-yaml-vs-properties": "YAML vs Properties",
                "https://www.baeldung.com/spring-boot-command-line-arguments": "Command Line Arguments",
                "https://www.baeldung.com/spring-boot-war-tomcat-deploy": "WAR Deployment",
                "https://www.baeldung.com/spring-boot-shutdown": "Graceful Shutdown",
                "https://www.baeldung.com/spring-boot-custom-error-page": "Custom Error Page",
                # Spring MVC
                "https://www.baeldung.com/spring-mvc-tutorial": "Spring MVC Tutorial",
                "https://www.baeldung.com/spring-controllers": "Controllers Guide",
                "https://www.baeldung.com/spring-controller-vs-restcontroller": "@Controller vs @RestController",
                "https://www.baeldung.com/spring-requestmapping": "@RequestMapping Guide",
                "https://www.baeldung.com/spring-request-response-body": "@RequestBody and @ResponseBody",
                "https://www.baeldung.com/spring-pathvariable": "@PathVariable Guide",
                "https://www.baeldung.com/spring-request-param": "@RequestParam Guide",
                "https://www.baeldung.com/spring-rest-api-with-protocol-buffers": "REST API with Protocol Buffers",
                "https://www.baeldung.com/rest-with-spring-series": "REST with Spring Series",
                "https://www.baeldung.com/spring-rest-openapi-documentation": "OpenAPI Documentation",
                "https://www.baeldung.com/swagger-2-documentation-for-spring-rest-api": "Swagger 2 for REST API",
                "https://www.baeldung.com/spring-cors": "CORS in Spring",
                "https://www.baeldung.com/exception-handling-for-rest-with-spring": "Exception Handling for REST",
                "https://www.baeldung.com/spring-response-entity": "ResponseEntity Guide",
                "https://www.baeldung.com/spring-validate-requestbody": "Validate @RequestBody",
                "https://www.baeldung.com/spring-boot-bean-validation": "Bean Validation",
                "https://www.baeldung.com/spring-mvc-content-negotiation-json-xml": "Content Negotiation",
                "https://www.baeldung.com/spring-mvc-handlerinterceptor": "HandlerInterceptor",
                "https://www.baeldung.com/spring-mvc-custom-data-binder": "Custom Data Binder",
                "https://www.baeldung.com/spring-file-upload": "File Upload",
                "https://www.baeldung.com/spring-mvc-form-tutorial": "Form Handling",
                "https://www.baeldung.com/spring-resttemplate": "RestTemplate Guide",
                # Spring Security
                "https://www.baeldung.com/security-spring": "Spring Security Series",
                "https://www.baeldung.com/spring-security-login": "Spring Security Login",
                "https://www.baeldung.com/spring-security-authentication-and-registration": "Authentication and Registration",
                "https://www.baeldung.com/spring-security-oauth": "OAuth with Spring Security",
                "https://www.baeldung.com/spring-security-oauth2-enable": "OAuth2 Configuration",
                "https://www.baeldung.com/spring-security-jwt": "JWT with Spring Security",
                "https://www.baeldung.com/spring-security-csrf": "CSRF Protection",
                "https://www.baeldung.com/spring-security-method-security": "Method Security",
                "https://www.baeldung.com/spring-security-expressions": "Security Expressions",
                "https://www.baeldung.com/spring-security-cors-preflight": "CORS Preflight",
                "https://www.baeldung.com/spring-security-basic-authentication": "Basic Authentication",
                "https://www.baeldung.com/spring-security-taglibs": "Security Taglibs",
                "https://www.baeldung.com/spring-security-remember-me": "Remember Me",
                "https://www.baeldung.com/spring-security-session": "Session Management",
                "https://www.baeldung.com/spring-security-5-reactive": "Reactive Security",
                "https://www.baeldung.com/spring-security-ldap": "LDAP Authentication",
                "https://www.baeldung.com/spring-security-custom-filter": "Custom Filter",
                "https://www.baeldung.com/spring-security-granted-authority-vs-role": "GrantedAuthority vs Role",
                "https://www.baeldung.com/spring-security-multiple-auth-providers": "Multiple Auth Providers",
                "https://www.baeldung.com/spring-security-logout": "Logout Configuration",
                # Spring Data
                "https://www.baeldung.com/the-persistence-layer-with-spring-data-jpa": "Spring Data JPA Guide",
                "https://www.baeldung.com/spring-data-repositories": "Spring Data Repositories",
                "https://www.baeldung.com/spring-data-jpa-query": "Spring Data JPA Queries",
                "https://www.baeldung.com/spring-data-derived-queries": "Derived Queries",
                "https://www.baeldung.com/spring-data-jpa-pagination-sorting": "Pagination and Sorting",
                "https://www.baeldung.com/spring-data-rest-intro": "Spring Data REST",
                "https://www.baeldung.com/spring-data-mongodb-tutorial": "MongoDB Tutorial",
                "https://www.baeldung.com/spring-data-redis-tutorial": "Redis Tutorial",
                "https://www.baeldung.com/spring-data-elasticsearch-tutorial": "Elasticsearch Tutorial",
                "https://www.baeldung.com/spring-data-cassandra-tutorial": "Cassandra Tutorial",
                "https://www.baeldung.com/spring-data-jpa-modifying-annotation": "@Modifying Annotation",
                "https://www.baeldung.com/spring-data-jpa-projections": "Spring Data JPA Projections",
                "https://www.baeldung.com/spring-data-jpa-delete": "Delete Operations",
                # Spring Cloud
                "https://www.baeldung.com/spring-cloud-series": "Spring Cloud Series",
                "https://www.baeldung.com/spring-cloud-netflix-eureka": "Netflix Eureka",
                "https://www.baeldung.com/spring-cloud-gateway": "Spring Cloud Gateway",
                "https://www.baeldung.com/spring-cloud-config": "Spring Cloud Config",
                "https://www.baeldung.com/spring-cloud-openfeign": "OpenFeign",
                "https://www.baeldung.com/spring-cloud-circuit-breaker": "Circuit Breaker",
                "https://www.baeldung.com/spring-cloud-kubernetes": "Kubernetes Integration",
                "https://www.baeldung.com/spring-cloud-bus": "Spring Cloud Bus",
                "https://www.baeldung.com/spring-cloud-sleuth-single-application": "Spring Cloud Sleuth",
                "https://www.baeldung.com/spring-cloud-vault": "Spring Cloud Vault",
                # Spring WebFlux
                "https://www.baeldung.com/spring-webflux": "WebFlux Introduction",
                "https://www.baeldung.com/spring-5-webclient": "WebClient Guide",
                "https://www.baeldung.com/spring-webflux-concurrency": "WebFlux Concurrency",
                "https://www.baeldung.com/spring-webflux-filters": "WebFlux Filters",
                "https://www.baeldung.com/spring-reactive-sequence": "Reactive Sequence",
                "https://www.baeldung.com/spring-webflux-backpressure": "Backpressure in WebFlux",
                "https://www.baeldung.com/spring-webflux-errors": "Error Handling in WebFlux",
                # Spring Batch
                "https://www.baeldung.com/introduction-to-spring-batch": "Spring Batch Introduction",
                "https://www.baeldung.com/spring-batch-job-parameters": "Job Parameters",
                "https://www.baeldung.com/spring-batch-testing-job": "Testing Batch Jobs",
                "https://www.baeldung.com/spring-batch-tasklet-chunk": "Tasklet vs Chunk",
                "https://www.baeldung.com/spring-batch-skip-logic": "Skip Logic",
                "https://www.baeldung.com/spring-batch-retry-logic": "Retry Logic",
                # Core Spring
                "https://www.baeldung.com/spring-dependency-injection": "Dependency Injection",
                "https://www.baeldung.com/inversion-control-and-dependency-injection-in-spring": "IoC and DI",
                "https://www.baeldung.com/spring-bean-scopes": "Bean Scopes",
                "https://www.baeldung.com/spring-bean-lifecycle": "Bean Lifecycle",
                "https://www.baeldung.com/spring-autowire": "@Autowired Guide",
                "https://www.baeldung.com/spring-qualifier-annotation": "@Qualifier Annotation",
                "https://www.baeldung.com/spring-component-annotation": "@Component Annotation",
                "https://www.baeldung.com/spring-value-annotation": "@Value Annotation",
                "https://www.baeldung.com/spring-events": "Spring Events",
                "https://www.baeldung.com/spring-aop": "Spring AOP",
                "https://www.baeldung.com/spring-aop-pointcut-tutorial": "AOP Pointcuts",
                "https://www.baeldung.com/spring-scheduling-annotations": "Scheduling Annotations",
                "https://www.baeldung.com/spring-async": "@Async Annotation",
                "https://www.baeldung.com/spring-cache-tutorial": "Caching Tutorial",
                "https://www.baeldung.com/spring-postconstruct-predestroy": "@PostConstruct and @PreDestroy",
                "https://www.baeldung.com/spring-conditional-annotations": "Conditional Annotations",
                "https://www.baeldung.com/spring-factorybean": "FactoryBean Guide",
                "https://www.baeldung.com/spring-applicationcontext": "ApplicationContext",
                "https://www.baeldung.com/spring-beanfactory-vs-applicationcontext": "BeanFactory vs ApplicationContext",
                "https://www.baeldung.com/spring-expression-language": "Spring Expression Language (SpEL)",
                "https://www.baeldung.com/spring-data-jpa-named-entity-graphs": "Named Entity Graphs",
                "https://www.baeldung.com/spring-type-conversions": "Type Conversions",
                "https://www.baeldung.com/spring-properties-file-outside-jar": "External Properties",
                "https://www.baeldung.com/spring-yaml": "Spring YAML Configuration",
            },
        },
        "persistence": {
            "pages": {
                # JPA / Hibernate
                "https://www.baeldung.com/learn-jpa-hibernate": "JPA and Hibernate Series",
                "https://www.baeldung.com/jpa-entities": "JPA Entities",
                "https://www.baeldung.com/hibernate-one-to-many": "One-to-Many Mapping",
                "https://www.baeldung.com/hibernate-many-to-many": "Many-to-Many Mapping",
                "https://www.baeldung.com/jpa-one-to-one": "One-to-One Mapping",
                "https://www.baeldung.com/hibernate-inheritance": "Inheritance Mapping",
                "https://www.baeldung.com/jpa-entity-lifecycle-events": "Entity Lifecycle Events",
                "https://www.baeldung.com/hibernate-criteria-queries": "Criteria Queries",
                "https://www.baeldung.com/hibernate-named-query": "Named Queries",
                "https://www.baeldung.com/jpa-join-types": "JPA Join Types",
                "https://www.baeldung.com/jpa-queries": "JPA Queries",
                "https://www.baeldung.com/hibernate-lazy-eager-loading": "Lazy vs Eager Loading",
                "https://www.baeldung.com/jpa-hibernate-projections": "Hibernate Projections",
                "https://www.baeldung.com/hibernate-second-level-cache": "Second Level Cache",
                "https://www.baeldung.com/jpa-entity-graph": "Entity Graph",
                "https://www.baeldung.com/hibernate-identifiers": "Identifier Strategies",
                "https://www.baeldung.com/jpa-composite-primary-keys": "Composite Primary Keys",
                "https://www.baeldung.com/spring-data-jpa-projections": "Spring Data JPA Projections",
                "https://www.baeldung.com/hibernate-save-persist-update-merge-saveorupdate": "save/persist/update/merge",
                "https://www.baeldung.com/jpa-embedded-embeddable": "@Embedded and @Embeddable",
                "https://www.baeldung.com/jpa-attribute-converters": "Attribute Converters",
                "https://www.baeldung.com/hibernate-lob": "LOB Handling",
                "https://www.baeldung.com/jpa-cascade-types": "Cascade Types",
                "https://www.baeldung.com/hibernate-session-object-states": "Session Object States",
                "https://www.baeldung.com/hibernate-detached-entity-passed-to-persist": "Detached Entity Error",
                "https://www.baeldung.com/hibernate-pagination": "Pagination with Hibernate",
                "https://www.baeldung.com/jpa-stored-procedures": "Stored Procedures",
                "https://www.baeldung.com/hibernate-sort": "Sorting with Hibernate",
                "https://www.baeldung.com/jpa-optimistic-locking": "Optimistic Locking",
                "https://www.baeldung.com/jpa-pessimistic-locking": "Pessimistic Locking",
                "https://www.baeldung.com/jpa-hibernate-batch-insert-update": "Batch Insert and Update",
                "https://www.baeldung.com/hibernate-query-plan-cache": "Query Plan Cache",
                "https://www.baeldung.com/hibernate-spatial": "Hibernate Spatial",
                "https://www.baeldung.com/hibernate-types-library": "Hibernate Types Library",
                "https://www.baeldung.com/jpa-criteria-api-in-expressions": "Criteria API In Expressions",
                "https://www.baeldung.com/spring-data-jpa-query-by-example": "Query by Example",
                "https://www.baeldung.com/spring-data-jpa-specifications": "JPA Specifications",
                # Transactions
                "https://www.baeldung.com/transaction-configuration-with-jpa-and-spring": "Transaction Configuration",
                "https://www.baeldung.com/spring-transactional-propagation-isolation": "Propagation and Isolation",
                "https://www.baeldung.com/spring-programmatic-transaction-management": "Programmatic Transactions",
                # JDBC
                "https://www.baeldung.com/java-jdbc": "JDBC Guide",
                "https://www.baeldung.com/spring-jdbc-jdbctemplate": "JdbcTemplate Guide",
                "https://www.baeldung.com/spring-jdbc-autogenerated-keys": "Auto-Generated Keys",
                "https://www.baeldung.com/spring-jdbc-batch-inserts": "Batch Inserts",
                # MongoDB
                "https://www.baeldung.com/java-mongodb": "Java MongoDB",
                "https://www.baeldung.com/queries-in-spring-data-mongodb": "MongoDB Queries",
                "https://www.baeldung.com/spring-data-mongodb-index-annotations-converter": "MongoDB Indexes",
                "https://www.baeldung.com/spring-data-mongodb-reactive": "Reactive MongoDB",
                "https://www.baeldung.com/spring-data-mongodb-transactions": "MongoDB Transactions",
                # Connection/Pools/Migrations
                "https://www.baeldung.com/spring-boot-hikari": "HikariCP Configuration",
                "https://www.baeldung.com/java-connection-pooling": "Connection Pooling",
                "https://www.baeldung.com/spring-data-jpa-multiple-databases": "Multiple Databases",
                "https://www.baeldung.com/liquibase-refactor-schema-of-java-app": "Liquibase Guide",
                "https://www.baeldung.com/database-migrations-with-flyway": "Flyway Migrations",
                "https://www.baeldung.com/spring-boot-h2-database": "H2 Database",
                "https://www.baeldung.com/spring-boot-testcontainers-integration-test": "Testcontainers DB",
                # Redis
                "https://www.baeldung.com/spring-data-redis-tutorial": "Redis Tutorial",
                "https://www.baeldung.com/spring-data-redis-properties": "Redis Properties",
                # Other persistence
                "https://www.baeldung.com/querydsl-with-jpa-tutorial": "Querydsl with JPA",
                "https://www.baeldung.com/java-jooq-intro": "jOOQ Introduction",
                "https://www.baeldung.com/mybatis": "MyBatis with Spring",
                "https://www.baeldung.com/spring-data-r2dbc": "R2DBC Reactive DB",
            },
        },
        "testing": {
            "pages": {
                # JUnit
                "https://www.baeldung.com/junit-5": "JUnit 5 Guide",
                "https://www.baeldung.com/junit-5-test-order": "Test Order",
                "https://www.baeldung.com/junit-5-conditional-test-execution": "Conditional Test Execution",
                "https://www.baeldung.com/junit-5-parameters": "JUnit 5 Parameters",
                "https://www.baeldung.com/parameterized-tests-junit-5": "Parameterized Tests",
                "https://www.baeldung.com/junit-5-extensions": "JUnit 5 Extensions",
                "https://www.baeldung.com/junit-assertions": "JUnit Assertions",
                "https://www.baeldung.com/junit-5-repeated-test": "Repeated Tests",
                "https://www.baeldung.com/junit-5-test-templates": "Test Templates",
                "https://www.baeldung.com/junit-5-lifecycle-methods": "Lifecycle Methods",
                "https://www.baeldung.com/junit-5-nested-test-classes": "Nested Test Classes",
                "https://www.baeldung.com/junit-5-temporary-directory": "Temporary Directory",
                "https://www.baeldung.com/junit-5-migration": "JUnit 4 to 5 Migration",
                "https://www.baeldung.com/junit-5-assumptions": "JUnit 5 Assumptions",
                "https://www.baeldung.com/junit-5-test-interfaces": "Test Interfaces",
                # Mockito
                "https://www.baeldung.com/mockito-series": "Mockito Series",
                "https://www.baeldung.com/mockito-annotations": "Mockito Annotations",
                "https://www.baeldung.com/mockito-verify": "Mockito verify()",
                "https://www.baeldung.com/mockito-behavior": "Mockito Behavior",
                "https://www.baeldung.com/mockito-spy": "Mockito spy()",
                "https://www.baeldung.com/mockito-argumentmatchers": "Argument Matchers",
                "https://www.baeldung.com/mockito-argument-captor": "Argument Captor",
                "https://www.baeldung.com/mockito-mock-methods": "Mock Methods",
                "https://www.baeldung.com/mockito-void-methods": "Void Methods",
                "https://www.baeldung.com/mockito-exceptions": "Mockito Exceptions",
                "https://www.baeldung.com/mockito-final": "Final Classes and Methods",
                "https://www.baeldung.com/mockito-lazy-verification": "Lazy Verification",
                "https://www.baeldung.com/mockito-mock-static-methods": "Mock Static Methods",
                "https://www.baeldung.com/mockito-mock-constructors": "Mock Constructors",
                "https://www.baeldung.com/mockito-bdd": "BDD with Mockito",
                "https://www.baeldung.com/mockito-mocksettings": "MockSettings",
                # Integration
                "https://www.baeldung.com/spring-boot-testing": "Spring Boot Testing",
                "https://www.baeldung.com/spring-boot-testcontainers": "Testcontainers",
                "https://www.baeldung.com/spring-boot-testing-pitfalls": "Testing Pitfalls",
                "https://www.baeldung.com/spring-mock-mvc-rest-assured": "MockMvc with REST Assured",
                "https://www.baeldung.com/integration-testing-in-spring": "Integration Testing",
                "https://www.baeldung.com/spring-test": "@SpringBootTest",
                "https://www.baeldung.com/spring-webflux-testing": "WebFlux Testing",
                "https://www.baeldung.com/spring-boot-test-slices-overview": "Test Slices Overview",
                "https://www.baeldung.com/spring-boot-webmvctest": "@WebMvcTest",
                "https://www.baeldung.com/spring-boot-datajpatest": "@DataJpaTest",
                "https://www.baeldung.com/spring-tests-mockmvcresultmatchers": "MockMvc ResultMatchers",
                "https://www.baeldung.com/spring-mock-mvc": "MockMvc Guide",
                "https://www.baeldung.com/spring-embedded-kafka-testing": "Embedded Kafka Testing",
                # Other
                "https://www.baeldung.com/assertj": "AssertJ Guide",
                "https://www.baeldung.com/hamcrest-collections-arrays": "Hamcrest Guide",
                "https://www.baeldung.com/java-testing-best-practices": "Testing Best Practices",
                "https://www.baeldung.com/rest-assured-tutorial": "REST Assured Tutorial",
                "https://www.baeldung.com/wiremock-tutorial": "WireMock Tutorial",
                "https://www.baeldung.com/cucumber-rest-api-testing": "Cucumber REST Testing",
                "https://www.baeldung.com/java-archunit-intro": "ArchUnit Introduction",
                "https://www.baeldung.com/gatling-jmeter-grinder-comparison": "Performance Testing Comparison",
                "https://www.baeldung.com/java-selenium-with-junit-and-testng": "Selenium with JUnit",
                "https://www.baeldung.com/awaitility-testing": "Awaitility Testing",
                "https://www.baeldung.com/pitest-mutation-testing": "Mutation Testing with PIT",
                "https://www.baeldung.com/jacoco": "JaCoCo Code Coverage",
                "https://www.baeldung.com/spring-boot-embedded-mongodb": "Embedded MongoDB Testing",
                "https://www.baeldung.com/java-testng": "TestNG Guide",
                "https://www.baeldung.com/json-path": "JsonPath for Testing",
                "https://www.baeldung.com/java-spock-tutorial": "Spock Framework",
                "https://www.baeldung.com/spring-jmeter": "JMeter with Spring",
                "https://www.baeldung.com/java-contract-testing-pact": "Contract Testing with Pact",
            },
        },
        "kotlin": {
            "pages": {
                "https://www.baeldung.com/kotlin/overview": "Kotlin Overview",
                "https://www.baeldung.com/kotlin/null-safety": "Null Safety",
                "https://www.baeldung.com/kotlin/coroutines": "Coroutines",
                "https://www.baeldung.com/kotlin/collections-api": "Collections API",
                "https://www.baeldung.com/kotlin/extension-methods": "Extension Functions",
                "https://www.baeldung.com/kotlin/data-classes": "Data Classes",
                "https://www.baeldung.com/kotlin/sealed-classes": "Sealed Classes",
                "https://www.baeldung.com/kotlin/scope-functions": "Scope Functions",
                "https://www.baeldung.com/kotlin/sequences": "Sequences",
                "https://www.baeldung.com/kotlin/channels": "Channels",
                "https://www.baeldung.com/kotlin/flow": "Kotlin Flow",
                "https://www.baeldung.com/kotlin/spring-boot": "Spring Boot with Kotlin",
                "https://www.baeldung.com/kotlin/exposed-persistence": "Exposed Persistence",
                "https://www.baeldung.com/kotlin/ktor": "Ktor Framework",
                "https://www.baeldung.com/kotlin/delegation-pattern": "Delegation Pattern",
                "https://www.baeldung.com/kotlin/inline-functions": "Inline Functions",
                "https://www.baeldung.com/kotlin/reified-types": "Reified Types",
                "https://www.baeldung.com/kotlin/type-aliases": "Type Aliases",
                "https://www.baeldung.com/kotlin/dsl": "Kotlin DSL",
                "https://www.baeldung.com/kotlin/multiplatform": "Kotlin Multiplatform",
                "https://www.baeldung.com/kotlin/generics": "Generics",
                "https://www.baeldung.com/kotlin/lambda-expressions": "Lambda Expressions",
                "https://www.baeldung.com/kotlin/higher-order-functions": "Higher-Order Functions",
                "https://www.baeldung.com/kotlin/operator-overloading": "Operator Overloading",
                "https://www.baeldung.com/kotlin/destructuring-declarations": "Destructuring Declarations",
                "https://www.baeldung.com/kotlin/enum": "Enums",
                "https://www.baeldung.com/kotlin/interfaces": "Interfaces",
                "https://www.baeldung.com/kotlin/companion-object": "Companion Objects",
                "https://www.baeldung.com/kotlin/singleton": "Singletons (object)",
                "https://www.baeldung.com/kotlin/lazy-initialization": "Lazy Initialization",
                "https://www.baeldung.com/kotlin/contracts": "Contracts",
                "https://www.baeldung.com/kotlin/annotations": "Annotations",
                "https://www.baeldung.com/kotlin/properties": "Properties",
                "https://www.baeldung.com/kotlin/constructors": "Constructors",
                "https://www.baeldung.com/kotlin/regular-expressions": "Regular Expressions",
                "https://www.baeldung.com/kotlin/string-templates": "String Templates",
                "https://www.baeldung.com/kotlin/when": "When Expression",
                "https://www.baeldung.com/kotlin/ranges": "Ranges",
                "https://www.baeldung.com/kotlin/maps": "Maps",
                "https://www.baeldung.com/kotlin/lists": "Lists",
                "https://www.baeldung.com/kotlin/sets": "Sets",
                "https://www.baeldung.com/kotlin/exception-handling": "Exception Handling",
                "https://www.baeldung.com/kotlin/return-from-lambda": "Return from Lambda",
                "https://www.baeldung.com/kotlin/variance": "Variance (in/out)",
                "https://www.baeldung.com/kotlin/java-interop": "Java Interoperability",
                "https://www.baeldung.com/kotlin/koin-di": "Koin Dependency Injection",
                "https://www.baeldung.com/kotlin/arrow": "Arrow Library",
                "https://www.baeldung.com/kotlin/kotest": "Kotest Testing",
                "https://www.baeldung.com/kotlin/mockk": "MockK Mocking",
                "https://www.baeldung.com/kotlin/coroutine-context-dispatchers": "Coroutine Context and Dispatchers",
            },
        },
        "devops": {
            "pages": {
                # Docker
                "https://www.baeldung.com/ops/docker-guide": "Docker Guide",
                "https://www.baeldung.com/ops/docker-compose": "Docker Compose",
                "https://www.baeldung.com/ops/dockerfile": "Dockerfile Guide",
                "https://www.baeldung.com/ops/docker-networking": "Docker Networking",
                "https://www.baeldung.com/ops/docker-volumes": "Docker Volumes",
                "https://www.baeldung.com/ops/docker-multi-stage-builds": "Multi-Stage Builds",
                "https://www.baeldung.com/ops/docker-healthcheck": "Docker Healthcheck",
                "https://www.baeldung.com/ops/docker-compose-profiles": "Compose Profiles",
                "https://www.baeldung.com/ops/docker-logs": "Docker Logs",
                "https://www.baeldung.com/ops/docker-container-filesystem": "Container Filesystem",
                # Kubernetes
                "https://www.baeldung.com/ops/kubernetes-guide": "Kubernetes Guide",
                "https://www.baeldung.com/ops/kubernetes-pods": "Kubernetes Pods",
                "https://www.baeldung.com/ops/kubernetes-deployment": "Kubernetes Deployment",
                "https://www.baeldung.com/ops/kubernetes-services": "Kubernetes Services",
                "https://www.baeldung.com/ops/kubernetes-configmap": "ConfigMap",
                "https://www.baeldung.com/ops/kubernetes-secrets": "Kubernetes Secrets",
                "https://www.baeldung.com/ops/kubernetes-helm": "Helm Charts",
                "https://www.baeldung.com/ops/kubernetes-ingress": "Kubernetes Ingress",
                "https://www.baeldung.com/ops/kubernetes-namespaces": "Kubernetes Namespaces",
                "https://www.baeldung.com/ops/kubernetes-persistent-volumes": "Persistent Volumes",
                # CI/CD
                "https://www.baeldung.com/ops/jenkins-pipelines": "Jenkins Pipelines",
                "https://www.baeldung.com/ops/github-actions": "GitHub Actions",
                "https://www.baeldung.com/ops/jenkins-pipeline-stages": "Jenkins Pipeline Stages",
                "https://www.baeldung.com/ops/gitlab-ci-cd": "GitLab CI/CD",
                # Build Tools
                "https://www.baeldung.com/ops/gradle": "Gradle Guide",
                "https://www.baeldung.com/maven": "Maven Guide",
                "https://www.baeldung.com/maven-profiles": "Maven Profiles",
                "https://www.baeldung.com/maven-dependency-scopes": "Maven Dependency Scopes",
                "https://www.baeldung.com/maven-multi-module": "Maven Multi-Module",
                "https://www.baeldung.com/gradle-building-a-java-app": "Gradle Java App",
                "https://www.baeldung.com/gradle-dependencies": "Gradle Dependencies",
                "https://www.baeldung.com/maven-wrapper": "Maven Wrapper",
                "https://www.baeldung.com/maven-plugin": "Maven Plugin Development",
                "https://www.baeldung.com/maven-settings-xml": "Maven settings.xml",
                "https://www.baeldung.com/maven-repository": "Maven Repository",
                # Linux / Ops
                "https://www.baeldung.com/ops/linux-shell-scripting": "Shell Scripting",
                "https://www.baeldung.com/linux/nginx": "Nginx Guide",
                "https://www.baeldung.com/ops/git-guide": "Git Guide",
                "https://www.baeldung.com/ops/linux-systemd": "Systemd",
                "https://www.baeldung.com/ops/linux-cron": "Cron Jobs",
                "https://www.baeldung.com/ops/linux-ssh": "SSH Guide",
                "https://www.baeldung.com/ops/linux-networking": "Linux Networking",
                "https://www.baeldung.com/ops/linux-environment-variables": "Environment Variables",
                # Monitoring
                "https://www.baeldung.com/ops/prometheus-intro": "Prometheus Introduction",
                "https://www.baeldung.com/ops/grafana-intro": "Grafana Introduction",
                "https://www.baeldung.com/ops/elk-stack": "ELK Stack",
                # Cloud
                "https://www.baeldung.com/ops/aws-s3": "AWS S3",
                "https://www.baeldung.com/ops/terraform-intro": "Terraform Introduction",
                "https://www.baeldung.com/ops/ansible-intro": "Ansible Introduction",
            },
        },
        "algorithms": {
            "pages": {
                # Sorting
                "https://www.baeldung.com/java-sorting-algorithms": "Sorting Algorithms Overview",
                "https://www.baeldung.com/java-bubble-sort": "Bubble Sort",
                "https://www.baeldung.com/java-selection-sort": "Selection Sort",
                "https://www.baeldung.com/java-insertion-sort": "Insertion Sort",
                "https://www.baeldung.com/java-merge-sort": "Merge Sort",
                "https://www.baeldung.com/java-quicksort": "Quicksort",
                "https://www.baeldung.com/java-heap-sort": "Heap Sort",
                "https://www.baeldung.com/java-radix-sort": "Radix Sort",
                "https://www.baeldung.com/java-counting-sort": "Counting Sort",
                "https://www.baeldung.com/java-bucket-sort": "Bucket Sort",
                "https://www.baeldung.com/java-timsort": "Timsort",
                # Searching
                "https://www.baeldung.com/java-binary-search": "Binary Search",
                "https://www.baeldung.com/java-interpolation-search": "Interpolation Search",
                "https://www.baeldung.com/java-ternary-search": "Ternary Search",
                # Graph algorithms
                "https://www.baeldung.com/java-depth-first-search": "Depth-First Search",
                "https://www.baeldung.com/java-breadth-first-search": "Breadth-First Search",
                "https://www.baeldung.com/java-dijkstra": "Dijkstra's Algorithm",
                "https://www.baeldung.com/java-a-star-pathfinding": "A* Pathfinding",
                "https://www.baeldung.com/java-graphs": "Graphs in Java",
                "https://www.baeldung.com/java-graph-has-a-cycle": "Cycle Detection",
                "https://www.baeldung.com/java-topological-sort": "Topological Sort",
                "https://www.baeldung.com/java-prim-algorithm": "Prim's Algorithm",
                "https://www.baeldung.com/java-kruskal-algorithm": "Kruskal's Algorithm",
                "https://www.baeldung.com/java-bellman-ford": "Bellman-Ford Algorithm",
                "https://www.baeldung.com/java-floyd-warshall": "Floyd-Warshall Algorithm",
                # Data Structures
                "https://www.baeldung.com/java-tree-structure": "Tree Structure",
                "https://www.baeldung.com/java-binary-tree": "Binary Tree",
                "https://www.baeldung.com/java-balanced-binary-tree": "Balanced Binary Tree",
                "https://www.baeldung.com/java-avl-trees": "AVL Trees",
                "https://www.baeldung.com/java-red-black-trees": "Red-Black Trees",
                "https://www.baeldung.com/java-trie": "Trie Data Structure",
                "https://www.baeldung.com/java-linked-list": "Linked List Implementation",
                "https://www.baeldung.com/java-stack": "Stack Implementation",
                "https://www.baeldung.com/java-hash-table": "Hash Table",
                "https://www.baeldung.com/java-lru-cache": "LRU Cache",
                "https://www.baeldung.com/java-bloom-filter": "Bloom Filter",
                "https://www.baeldung.com/java-skip-list": "Skip List",
                "https://www.baeldung.com/java-circular-linked-list": "Circular Linked List",
                "https://www.baeldung.com/java-doubly-linked-list": "Doubly Linked List",
                # Dynamic Programming
                "https://www.baeldung.com/java-dynamic-programming": "Dynamic Programming",
                "https://www.baeldung.com/java-knapsack": "Knapsack Problem",
                "https://www.baeldung.com/java-longest-common-subsequence": "Longest Common Subsequence",
                "https://www.baeldung.com/java-longest-increasing-subsequence": "Longest Increasing Subsequence",
                "https://www.baeldung.com/java-edit-distance": "Edit Distance",
                "https://www.baeldung.com/java-coin-change-problem": "Coin Change Problem",
                "https://www.baeldung.com/java-matrix-chain-multiplication": "Matrix Chain Multiplication",
                # Algorithmic Techniques
                "https://www.baeldung.com/java-greedy-algorithms": "Greedy Algorithms",
                "https://www.baeldung.com/java-backtracking": "Backtracking",
                "https://www.baeldung.com/java-permutations": "Permutations",
                "https://www.baeldung.com/java-combinations": "Combinations",
                "https://www.baeldung.com/java-fibonacci": "Fibonacci Sequence",
                "https://www.baeldung.com/java-two-pointer-technique": "Two Pointer Technique",
                "https://www.baeldung.com/java-sliding-window": "Sliding Window",
                # Complexity and Theory
                "https://www.baeldung.com/cs/big-o-notation": "Big O Notation",
                "https://www.baeldung.com/java-algorithm-complexity": "Algorithm Complexity",
                "https://www.baeldung.com/cs/time-vs-space-complexity": "Time vs Space Complexity",
                "https://www.baeldung.com/cs/p-np-np-hard-np-complete": "P, NP, NP-Hard, NP-Complete",
                # String Algorithms
                "https://www.baeldung.com/java-string-search-algorithms": "String Search Algorithms",
                "https://www.baeldung.com/java-kmp-algorithm": "KMP Algorithm",
                "https://www.baeldung.com/java-rabin-karp-algorithm": "Rabin-Karp Algorithm",
                "https://www.baeldung.com/java-anagram-check": "Anagram Check",
                "https://www.baeldung.com/java-palindrome-check": "Palindrome Check",
                # Math
                "https://www.baeldung.com/java-gcd-algorithm": "GCD Algorithm",
                "https://www.baeldung.com/java-sieve-of-eratosthenes": "Sieve of Eratosthenes",
                "https://www.baeldung.com/java-modular-exponentiation": "Modular Exponentiation",
                "https://www.baeldung.com/java-matrix-multiplication": "Matrix Multiplication",
                "https://www.baeldung.com/java-power-set": "Power Set",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"baeldung-{source_key}" if source_key else "baeldung"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' | Baeldung', ' - Baeldung']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})
        for url, title in pages.items():
            if not self.running:
                break
            item_id = self.make_id(url)
            content = self.fetch_url(url)
            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)
                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"baeldung-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")
            time.sleep(2.0)
        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0
        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(f"Unknown source key: {self.source_key}. Available: {list(self.SOURCES.keys())}")
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES
        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping baeldung/{key} ===")
            total += self._scrape_source(key, config)
        return total


if __name__ == "__main__":
    import os
    import sys
    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    BaeldungScraper(base, source_key).run()
