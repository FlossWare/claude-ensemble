---
name: project-search-platform-architecture
description: Red Hat search platform consists of disseminator (indexing) and search-mcp-server (query API)
metadata: 
  node_type: memory
  type: project
  originSessionId: 0e2e63e4-4450-4158-8d71-c4ca64dd77f4
---

The user's search platform has two main components:

1. **disseminator** (Java/Spring Boot/Camel) - Data ingestion and Solr indexing service
   - Manages 40+ Solr collections
   - Writes to Solr access collection
   - Production service

2. **search-mcp-server** (Python/FastMCP) - Read-only search API for AI/LLM integration
   - Exposes 10 MCP tools for Claude
   - Queries Solr access collection (read-only)
   - Optional vector reranking
   - Version 0.1.9

**Why:** Disseminator writes data, search-mcp-server provides AI-friendly query interface. They share the same Solr backend.

**How to apply:** When discussing search features, understand disseminator handles indexing/ETL while search-mcp-server is the consumption layer.
