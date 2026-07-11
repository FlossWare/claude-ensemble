---
name: intelligent-search-api
description: "REST API endpoints for intelligent multi-source search (PostgreSQL → Vector → Graph)"
metadata:
  type: reference
  date: 2026-07-10
---

# Intelligent Search REST API

**Base URL:** `http://aio-01:5000`

## Available Endpoints

### 1. Direct Database Queries

**PostgreSQL (Memories):**
```bash
GET /learning/memory/search?q=query&limit=10
```

**Vector Search (Semantic Similarity):**
```bash
GET /learning/experiences/similar?query=query&limit=10
```

**Graph Database (Relationships):**
```bash
POST /graph/query
Content-Type: application/json
{"query": "SELECT FROM V WHERE name LIKE '%query%'"}
```

### 2. Unified Search (All Three)

**Cascading search** - queries all three in parallel:
```bash
GET /search/unified?q=query&limit=10
```

Returns:
```json
{
  "query": "your query",
  "sources": {
    "postgresql": {"status": "success", "results": [...]},
    "vector": {"status": "success", "results": [...]},
    "graph": {"status": "success", "results": [...]}
  },
  "combined": [
    {"source": "postgresql", "type": "memory", "score": 1.0, "data": {...}},
    ...
  ]
}
```

### 3. Intelligent Search (Adaptive Order)

**Intelligent search** - chooses order based on query type:
```bash
GET /search/intelligent?q=query&limit=10
```

**Query Classification:**

| Query Type | Example | Search Order | Why |
|------------|---------|--------------|-----|
| **Factual** | "What is laptop-01's IP?" | PostgreSQL → Vector → Graph | Structured data first |
| **Semantic** | "Similar to fleet optimization" | Vector → PostgreSQL → Graph | Similarity first |
| **Relationship** | "What depends on aio-01?" | Graph → PostgreSQL → Vector | Relationships first |
| **Mixed** | General queries | All three equally weighted | Balanced search |

**Keywords that trigger each type:**

- **Factual:** "what is", "where is", "how many", "list", "show me", "find"
- **Semantic:** "similar to", "like", "explain", "concept", "idea"
- **Relationship:** "related to", "connected to", "depends on", "impact of"

**Response includes query classification:**
```json
{
  "query": "What is aio-01's role?",
  "query_type": "factual",
  "search_order": ["postgresql", "vector", "graph"],
  "sources": {...},
  "combined": [...]
}
```

## When to Use Which Endpoint

**Use direct endpoints when:**
- You know exactly which database has the data
- You want only one type of result (e.g., only relationships)
- You need raw database access

**Use `/search/unified` when:**
- You want comprehensive results from all sources
- You don't know where the data might be
- You want to see all possible matches

**Use `/search/intelligent` when:**
- You want optimal results with minimal response time
- The query type is clear (factual/semantic/relationship)
- You want adaptive search based on query intent

## Priority Weighting

Intelligent search uses priority multipliers:

**Factual queries:**
- PostgreSQL: 3.0× (highest priority)
- Vector: 2.0×
- Graph: 1.0×

**Semantic queries:**
- Vector: 3.0×
- PostgreSQL: 2.0×
- Graph: 1.0×

**Relationship queries:**
- Graph: 3.0×
- PostgreSQL: 2.0×
- Vector: 1.0×

Results are scored and ranked by: `priority × relevance`

## Examples

**Find a specific fact:**
```bash
curl "http://aio-01:5000/search/intelligent?q=What%20is%20PostgreSQL%20port"
# → Factual query → PostgreSQL searched first
```

**Find similar concepts:**
```bash
curl "http://aio-01:5000/search/intelligent?q=Similar%20to%20autostorage"
# → Semantic query → Vector DB searched first
```

**Find relationships:**
```bash
curl "http://aio-01:5000/search/intelligent?q=What%20depends%20on%20aio-01"
# → Relationship query → Graph DB searched first
```

## How Claude Should Use This

**Instead of reading memory files:**
```python
# OLD (reading files)
memory_file = Path("memory/some_memory.md").read_text()

# NEW (intelligent search)
response = requests.get(
    "http://aio-01:5000/search/intelligent",
    params={"q": "fleet architecture", "limit": 5}
)
results = response.json()
```

**Search order:**
1. Try `/search/intelligent` first (adaptive)
2. If API is down, fall back to reading memory files

## Related

- [[feedback_autostorage_expanded]] - How data gets into databases
- [[feedback_always_unified_rest_api]] - Always use REST API
- [[reference_home_network_AUTHORITATIVE]] - PostgreSQL on aio-01:5433
