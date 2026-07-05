# Connect PDFs to workflows that used their knowledge

**Status:** Open  
**Priority:** Medium  
**Created:** 2026-07-04  

## Goal

Track which PDFs were referenced/used during workflow execution to build a knowledge provenance graph.

## Context

When workflows research topics or solve problems, they may reference PDFs from the library. Currently there's no tracking of which PDFs influenced which decisions.

## Implementation

- Extend workflow storage to track PDF references
- Add relationship in Neo4j: `(Workflow)-[:REFERENCED]->(PDFDocument)`
- Capture PDF usage during workflow execution
- Add metadata: when referenced, how used (background reading vs. direct citation)

## Benefits

- "Which PDFs helped solve similar problems?"
- "What workflows benefited from this book?"
- Knowledge reuse tracking
- Citation graph for research workflows

## Related

- Workflow storage: `shared/workflow-storage-adapter.js`
- Neo4j sync: `shared/neo4j-realtime-sync.cjs`
- Workflow executions table: `workflow.executions`

## Example Queries

```cypher
// Workflows that used Kubernetes books
MATCH (w:Workflow)-[:REFERENCED]->(p:PDFDocument)-[:ABOUT]->(t:Topic {name: 'kubernetes'})
RETURN w.workflow_name, p.filename

// Most referenced PDFs
MATCH (p:PDFDocument)<-[:REFERENCED]-(w:Workflow)
RETURN p.filename, COUNT(w) as times_referenced
ORDER BY times_referenced DESC
LIMIT 10
```

## Acceptance Criteria

- [ ] Workflow execution captures PDF references
- [ ] Neo4j relationship created: `REFERENCED`
- [ ] Metadata includes: timestamp, usage_type
- [ ] Query showing "PDFs used by successful workflows"
