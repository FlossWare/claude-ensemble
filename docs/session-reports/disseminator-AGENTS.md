# Disseminator Agent Rules

## Project Overview

Disseminator is a Java-based content distribution and search platform using:
- **Java 21** (primary runtime)
- **Maven** for build management
- **Apache Solr 9.3.0** for search functionality
- **Apache Camel** for integration routes
- **Red Hat internal infrastructure**

## Code Review Guidelines

### Architecture
- This is a microservices architecture with Solr plugins and Camel routes
- Changes affecting search indexing must consider Solr schema compatibility
- Integration routes should follow Camel best practices

### Java Standards
- Target Java 21 features and patterns
- Follow Red Hat Java coding standards
- Maintain timezone handling (EST) consistency
- Use proper resource management (try-with-resources)

### Maven & Dependencies
- Maven repository is pre-populated in base image at `/opt/maven-repository`
- Verify dependency versions against `dependencies.lock`
- Security: Flag any new dependencies or version changes for review
- No cache usage (ephemeral Kubernetes pods)

### Solr & Search
- Solr is pre-installed at `/opt/solr/solr-9.3.0`
- Plugin changes require thorough testing with configsets
- Consider impact on existing indexes and queries
- Performance: Review query complexity and indexing patterns

### Security & Compliance
- All secrets must use CI/CD variables, never hardcoded
- Red Hat certificates must be properly imported
- SSH keys managed via `create_ssh.sh` script
- Review any authentication/authorization changes carefully

### Testing
- Integration tests should cover Solr and Camel components
- QE tests run in dedicated stage
- Consider impact on deployed environments (qa/stage/prod)

### CI/CD
- Build artifacts and deployment follow strict stage progression
- Changes to `.gitlab-ci.yml` require extra scrutiny
- JIRA integration is automated - verify ticket references
- Base image sync is automated via scheduled jobs

## Focus Areas for Review

1. **Java Code Quality**: Thread safety, resource management, exception handling
2. **Solr Integration**: Schema changes, query performance, plugin compatibility
3. **Camel Routes**: Route definitions, error handling, message transformations
4. **Maven Configuration**: Dependencies, plugins, build lifecycle
5. **Security**: Secrets management, certificate handling, input validation
6. **Performance**: Query optimization, memory usage, caching strategies
7. **Deployment Impact**: Changes affecting qa/stage/prod deployments
