# Apache Solr Codebase Patterns & Architecture

## Repository Overview
**URL**: https://github.com/apache/solr
**Type**: Enterprise search platform built in Java using Apache Lucene
**Build System**: Gradle
**Key Language**: Java

## Core Architecture

### 1. Request Handler Pattern (Handler Architecture)
**Location**: `/solr/core/src/java/org/apache/solr/handler/`

**Base Class**: `RequestHandlerBase`
- Implements `SolrRequestHandler`, `SolrInfoBean`, `ApiSupport`, `PermissionNameProvider`
- Manages request/response lifecycle
- Handles parameter merging (defaults, appends, invariants)
- Integrates OpenTelemetry metrics
- CPU time tracking and query limits enforcement

**Key Handlers**:
- `UpdateRequestHandler`: Handles document updates/indexing
- `SearchHandler`: Processes search queries
- `PingRequestHandler`: Health checks
- `V2UpdateRequestHandler`: REST API v2 for updates

**Metrics Integration**:
- `HandlerMetrics` for tracking performance
- `AttributedLongCounter` and `AttributedLongTimer` for OpenTelemetry
- Query limits and CPU usage monitoring

### 2. Search Engine Core (`/solr/core/src/java/org/apache/solr/search/`)

**Key Components**:
- `SolrIndexSearcher`: Wraps Lucene IndexSearcher, manages search execution
- `SolrQueryParser`: Parses Solr query syntax
- `SolrQueryBuilder`: Builds Lucene Query objects
- `QueryResult`/`QueryResultKey`: Caching query results
- `RankQuery`: Ranking/relevance computation
- `QueryLimits`: Enforces query execution constraints (timeout, memory, CPU)

### 3. Modular Architecture (`/solr/modules/`)

**Core Modules**:
- **analysis-extras**: Advanced text analysis components
- **clustering**: Clustering and faceting algorithms
- **cross-dc**: Cross-datacenter replication
- **cuvs**: Vector search capabilities
- **extraction**: Content extraction (Tika integration)
- **gcs-repository**: Google Cloud Storage integration
- **jwt-auth**: JWT authentication
- **langid**: Language identification
- **language-models**: ML model integration
- **ltr**: Learning to Rank
- **opentelemetry**: Distributed tracing
- **s3-repository**: AWS S3 storage backend
- **scripting**: Script execution (Groovy, etc.)
- **sql**: SQL query interface

### 4. Client Library (`/solr/solrj/`)
- Pure Java client library for Solr
- JSON parser/writer (Noggit)
- Request building APIs
- Response parsing

### 5. Update Pipeline (`/solr/core/src/java/org/apache/solr/update/`)
- `DistributedUpdateProcessor`: Handles distributed indexing
- Update chain processing
- Document routing

### 6. Configuration Management
- `SolrCore`: Represents a search index
- `CoreContainer`: Manages multiple cores
- `PluginBag`/`PluginInfo`: Plugin discovery and initialization
- ZooKeeper integration for distributed coordination

## Key Design Patterns

### Plugin Architecture
- Uses `PluginBag` and `PluginInfo` for loose coupling
- Plugins loaded dynamically from configuration
- Component initialization through `init()` methods

### Parameter Management
- Three-level parameter system:
  - **defaults**: Applied when not explicitly set
  - **appends**: Added to user parameters
  - **invariants**: Cannot be overridden by users
- Implemented via `SolrParams` hierarchy

### Metrics & Observability
- OpenTelemetry integration for distributed tracing
- Attributed counters and timers
- Request-level metrics collection
- CPU and memory limits tracking

### Query Processing Pipeline
1. Parse query string → `SolrQueryParser`
2. Build Lucene query → `SolrQueryBuilder`
3. Execute search → `SolrIndexSearcher`
4. Apply ranking → `RankQuery`
5. Enforce limits → `QueryLimits`

## Module Organization

```
/solr
├── api/                 # REST API definitions
├── core/               # Core search engine
├── solrj/              # Java client library
├── solrj-jetty/        # Jetty servlet container
├── solrj-streaming/    # Streaming API
├── solrj-zookeeper/    # ZK client wrapper
├── modules/            # Feature modules
├── server/             # Embedded server
├── ui/                 # Web UI
├── test-framework/     # Testing utilities
└── docker/             # Containerization
```

## Technology Stack
- **Core**: Apache Lucene for indexing/searching
- **Distributed**: Apache ZooKeeper for coordination
- **Metrics**: OpenTelemetry (OTEL)
- **Serialization**: JSON (Noggit), binary formats
- **Build**: Gradle
- **Language**: Java 11+

## Notable Implementation Details

### Request Lifecycle
1. HTTP request → `RequestHandler`
2. Parameter processing → merge defaults/appends/invariants
3. Query execution with limits/monitoring
4. Response serialization (JSON/XML)

### Security Integration
- `PermissionNameProvider` interface for RBAC
- JWT authentication support
- SSL/TLS support in server configuration

### Vector Search
- `cuvs` module provides vector similarity search
- Integrates with modern embedding models

### Performance Features
- Query result caching (`QueryResult`)
- CPU time tracking (`ThreadCpuTimer`)
- Memory-aware query limits
- Timeout mechanisms

## Development Notes
- Extensive use of interfaces for extensibility
- Configuration-driven plugin loading
- Comprehensive metrics collection
- Support for both embedded and distributed deployments
