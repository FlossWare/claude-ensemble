#!/usr/bin/env node
/**
 * Populate orchestration queue with current running workflows
 */

const { getOrchestrationQueue } = require('./orchestration-adapter.js');

async function populateCurrentWork() {
  const queue = getOrchestrationQueue();

  // Current running workflows (57 total)
  const tasks = [
    // Code reviews (9)
    { task_id: 'code-review-solenopsis-session', task_type: 'code_review', description: 'Deep code review of solenopsis/session repository with chunking, vectorDB, and graphDB', priority: 70 },
    { task_id: 'code-review-solenopsis-soap', task_type: 'code_review', description: 'Deep code review of solenopsis/soap repository with chunking, vectorDB, and graphDB', priority: 70 },
    { task_id: 'code-review-solenopsis-metadata', task_type: 'code_review', description: 'Deep code review of solenopsis/metadata repository with chunking, vectorDB, and graphDB', priority: 70 },
    { task_id: 'code-review-flossware-collections', task_type: 'code_review', description: 'Deep code review of FlossWare/collections-java repository with chunking, vectorDB, and graphDB', priority: 70 },
    { task_id: 'code-review-flossware-commons', task_type: 'code_review', description: 'Deep code review of FlossWare/commons-java repository with chunking, vectorDB, and graphDB', priority: 70 },
    { task_id: 'code-review-sfdeasy', task_type: 'code_review', description: 'Deep code review of sfdeasy repository with chunking, vectorDB, and graphDB', priority: 70 },
    { task_id: 'code-review-claude-skills', task_type: 'code_review', description: 'Deep code review of claude-global-skills repository with chunking, vectorDB, and graphDB', priority: 70 },
    { task_id: 'code-review-search-engineering', task_type: 'code_review', description: 'Deep code review of search-engineering repository with chunking, vectorDB, and graphDB', priority: 70 },
    { task_id: 'code-review-tower-playbooks', task_type: 'code_review', description: 'Deep code review of tower-playbooks repository with chunking, vectorDB, and graphDB', priority: 70 },

    // AI/ML/Consciousness research (12)
    { task_id: 'research-iit-consciousness', task_type: 'deep_research', description: 'Deep research on Integrated Information Theory (IIT) - Phi calculation, mathematical framework, Tononi and Koch work, blogs, white papers, conference talks 2024-2026', priority: 60 },
    { task_id: 'research-gwt-consciousness', task_type: 'deep_research', description: 'Deep research on Global Workspace Theory (GWT) - Baars and Dehaene work, presentations, conference proceedings 2024-2026', priority: 60 },
    { task_id: 'research-free-energy-principle', task_type: 'deep_research', description: 'Deep research on Free Energy Principle - Karl Friston blogs, tutorials, computational neuroscience talks 2024-2026', priority: 60 },
    { task_id: 'research-transformer-architecture', task_type: 'deep_research', description: 'Deep research on Transformer/Mamba/MoE architectures - Google AI blog, OpenAI talks, NeurIPS/ICML/ICLR proceedings 2024-2026', priority: 60 },
    { task_id: 'research-genetic-algorithms', task_type: 'deep_research', description: 'Deep research on Genetic Algorithms - GECCO/CEC conferences, practical implementation guides 2024-2026', priority: 60 },
    { task_id: 'research-ai-architecture-blogs', task_type: 'deep_research', description: 'Deep research on AI architecture blogs - Karpathy, distill.pub, Lil Log, Jay Alammar industry blogs 2024-2026', priority: 60 },
    { task_id: 'research-llm-reasoning', task_type: 'deep_research', description: 'Deep research on LLM reasoning - Chain-of-thought talks, interpretability research, AI safety discussions 2024-2026', priority: 60 },
    { task_id: 'research-neural-architecture-search', task_type: 'deep_research', description: 'Deep research on Neural architecture search - AutoML white papers, MLOps talks, NAS implementations 2024-2026', priority: 60 },

    // Languages (10)
    { task_id: 'research-openjdk-8', task_type: 'deep_research', description: 'Deep research on OpenJDK 8 internals - JVM architecture, GC algorithms, core libraries, lambdas, streams 2024-2026', priority: 55 },
    { task_id: 'research-openjdk-11', task_type: 'deep_research', description: 'Deep research on OpenJDK 11 LTS - Modules, HTTP/2 client, performance improvements 2024-2026', priority: 55 },
    { task_id: 'research-openjdk-17', task_type: 'deep_research', description: 'Deep research on OpenJDK 17 LTS - Pattern matching, records, sealed classes, modern features 2024-2026', priority: 55 },
    { task_id: 'research-kotlin', task_type: 'deep_research', description: 'Deep research on Kotlin language - Coroutines, null safety, type system, comparison with Java 2024-2026', priority: 55 },
    { task_id: 'research-erlang', task_type: 'deep_research', description: 'Deep research on Erlang/OTP - Actor model, distributed systems, fault tolerance 2024-2026', priority: 55 },
    { task_id: 'research-haskell', task_type: 'deep_research', description: 'Deep research on Haskell - Pure functional programming, type classes, monads, lazy evaluation 2024-2026', priority: 55 },
    { task_id: 'research-python', task_type: 'deep_research', description: 'Deep research on Python - Core language, standard library, ecosystem, asyncio, typing 2024-2026', priority: 55 },
    { task_id: 'research-salesforce-apex', task_type: 'deep_research', description: 'Deep research on Salesforce Apex - Triggers, classes, governors, DML, SOQL/SOSL, integration patterns 2024-2026', priority: 55 },
    { task_id: 'research-salesforce-metadata', task_type: 'deep_research', description: 'Deep research on Salesforce Metadata API - Package.xml, metadata types, deployment, change sets vs source-driven 2024-2026', priority: 55 },
    { task_id: 'research-salesforce-bulk', task_type: 'deep_research', description: 'Deep research on Salesforce Bulk API - Batch processing, CSV vs JSON, performance optimization 2024-2026', priority: 55 },

    // Apache ecosystem (18)
    { task_id: 'research-apache-netbeans', task_type: 'deep_research', description: 'Deep research on Apache NetBeans IDE - Architecture, plugin system, Java development features 2024-2026', priority: 50 },
    { task_id: 'research-apache-kafka', task_type: 'deep_research', description: 'Deep research on Apache Kafka - Distributed streaming, topics, partitions, consumer groups, exactly-once semantics 2024-2026', priority: 50 },
    { task_id: 'research-apache-solr', task_type: 'deep_research', description: 'Deep research on Apache Solr - Full-text search, faceting, indexing, SolrCloud, performance tuning 2024-2026', priority: 50 },
    { task_id: 'research-spring-framework', task_type: 'deep_research', description: 'Deep research on Spring Framework - IoC container, AOP, Spring MVC, Spring Data, modern features 2024-2026', priority: 50 },
    { task_id: 'research-spring-boot', task_type: 'deep_research', description: 'Deep research on Spring Boot - Auto-configuration, starter dependencies, microservices patterns, observability 2024-2026', priority: 50 },
    { task_id: 'research-apache-camel', task_type: 'deep_research', description: 'Deep research on Apache Camel - Enterprise integration patterns, routes, components, transformations 2024-2026', priority: 50 },
    { task_id: 'research-apache-http-server', task_type: 'deep_research', description: 'Deep research on Apache HTTP Server - MPM models, mod_rewrite, virtual hosts, SSL/TLS, security hardening 2024-2026', priority: 50 },
    { task_id: 'research-apache-tomcat', task_type: 'deep_research', description: 'Deep research on Apache Tomcat - Servlet container architecture, connectors, thread pools, clustering, performance 2024-2026', priority: 50 },
    { task_id: 'research-apache-maven', task_type: 'deep_research', description: 'Deep research on Apache Maven - POM structure, dependency management, lifecycle, plugins, Maven vs Gradle 2024-2026', priority: 50 },
    { task_id: 'research-apache-ant', task_type: 'deep_research', description: 'Deep research on Apache Ant - Build files, targets, tasks, Ant vs Maven migration patterns 2024-2026', priority: 50 },
    { task_id: 'research-apache-activemq', task_type: 'deep_research', description: 'Deep research on Apache ActiveMQ - JMS implementation, messaging patterns, broker architecture, clustering 2024-2026', priority: 50 },
    { task_id: 'research-apache-cxf', task_type: 'deep_research', description: 'Deep research on Apache CXF - SOAP and REST web services, JAX-WS, JAX-RS, WSDL-first, interceptors 2024-2026', priority: 50 },
    { task_id: 'research-apache-hadoop', task_type: 'deep_research', description: 'Deep research on Apache Hadoop - HDFS architecture, MapReduce, YARN, Hadoop 3.x features, cloud migration 2024-2026', priority: 50 },
    { task_id: 'research-apache-spark', task_type: 'deep_research', description: 'Deep research on Apache Spark - RDD, DataFrame, Dataset APIs, Spark SQL, Streaming, MLlib, Spark 3.x 2024-2026', priority: 50 },
    { task_id: 'research-apache-cassandra', task_type: 'deep_research', description: 'Deep research on Apache Cassandra - Ring architecture, consistent hashing, CQL, data modeling, Cassandra 4.x/5.x 2024-2026', priority: 50 },
    { task_id: 'research-apache-airflow', task_type: 'deep_research', description: 'Deep research on Apache Airflow - DAG design, task dependencies, executors, XCom, dynamic DAGs, Airflow 2.x 2024-2026', priority: 50 },
    { task_id: 'research-apache-flink', task_type: 'deep_research', description: 'Deep research on Apache Flink - DataStream API, event time, windowing, state management, exactly-once 2024-2026', priority: 50 },
    { task_id: 'research-apache-hbase', task_type: 'deep_research', description: 'Deep research on Apache HBase - Column-family database, RowKey design, regions, coprocessors, HBase 2.x/3.x 2024-2026', priority: 50 },

    // Data/Query technologies (6)
    { task_id: 'research-graph-databases', task_type: 'deep_research', description: 'Deep research on graph databases - Neo4j Cypher, Amazon Neptune, ArangoDB, TigerGraph, property graphs, graph algorithms 2024-2026', priority: 50 },
    { task_id: 'research-document-databases', task_type: 'deep_research', description: 'Deep research on document databases - MongoDB aggregation, CouchDB, Couchbase, RavenDB, document modeling, ACID vs BASE 2024-2026', priority: 50 },
    { task_id: 'research-graphql', task_type: 'deep_research', description: 'Deep research on GraphQL - SDL, resolvers, N+1 problem, federation, subscriptions, DataLoader, Apollo vs Relay 2024-2026', priority: 50 },
    { task_id: 'research-xsd', task_type: 'deep_research', description: 'Deep research on XSD - XML Schema Definition structure, simple/complex types, validation, XSD 1.1 features 2024-2026', priority: 50 },
    { task_id: 'research-xml-ecosystem', task_type: 'deep_research', description: 'Deep research on XML technologies - DOM vs SAX parsing, XPath, XSLT transformations, XML security, modern alternatives 2024-2026', priority: 50 },
    { task_id: 'research-csv-format', task_type: 'deep_research', description: 'Deep research on CSV data format - Parsing challenges, RFC 4180, streaming processing, schema evolution, validation 2024-2026', priority: 50 },
  ];

  console.log(`Enqueueing ${tasks.length} tasks...`);
  for (const task of tasks) {
    const result = await queue.enqueue({
      ...task,
      metadata: {
        session_id: '4d1f43c9-cfc0-4917-a842-a238f5415111',
        orchestrator: 'laptop-01',
        worker_pool: 'fleet-5-nodes',
        storage_pattern: 'chunking + vectorDB + graphDB',
        launched_at: new Date().toISOString()
      }
    });
    console.log(`✓ ${result.task_id} (${result.status})`);
  }

  // Mark all as running (background workflows already launched)
  console.log('\nMarking all tasks as running...');
  for (const task of tasks) {
    await queue.pool.query(`
      UPDATE orchestration.task_queue
      SET status = 'running', started_at = NOW()
      WHERE task_id = $1
    `, [task.task_id]);
  }

  // Export state
  const state = await queue.exportState();
  console.log(`\n✅ Populated ${state.tasks.length} tasks in orchestration queue`);
  console.log(`   Status: ${state.tasks.filter(t => t.status === 'running').length} running`);

  await queue.close();
}

populateCurrentWork().catch(console.error);
