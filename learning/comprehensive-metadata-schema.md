# Comprehensive Metadata Schema for Orchestration Queue

**Purpose:** Track ALL execution details across 100+ metadata fields for complete auditability and recovery

## Core Metadata Fields (Already in Schema)

### Task Identification
- `id` (SERIAL PRIMARY KEY)
- `task_id` (TEXT UNIQUE)
- `task_type` (TEXT) - 'code_review', 'deep_research', 'pdf_analysis', etc.
- `description` (TEXT)
- `embedding` (vector(384))

### Assignment & Status
- `assigned_worker` (TEXT) - Worker hostname
- `workflow_run_id` (TEXT) - Actual workflow execution ID
- `status` (TEXT) - 'queued', 'running', 'completed', 'failed', 'paused'
- `priority` (INTEGER 0-100)

### Dependencies
- `depends_on` (INTEGER[]) - Task IDs that must complete first
- `blocks` (INTEGER[]) - Task IDs waiting on this

### Progress Tracking
- `progress_percent` (INTEGER 0-100)
- `current_phase` (TEXT)
- `phases_total` (INTEGER)
- `phases_completed` (INTEGER)

### Timing
- `created_at` (TIMESTAMPTZ)
- `started_at` (TIMESTAMPTZ)
- `completed_at` (TIMESTAMPTZ)
- `estimated_duration_ms` (BIGINT)
- `actual_duration_ms` (BIGINT)

### Resource Tracking
- `input_tokens` (BIGINT)
- `output_tokens` (BIGINT)
- `cost_usd` (NUMERIC(10,6))

### Result Storage
- `result_path` (TEXT) - Path to output file
- `result_summary` (TEXT)
- `outcome` (TEXT) - 'success', 'error', 'timeout', 'user_cancelled'
- `error_message` (TEXT)

---

## Extended Metadata (JSONB) - 100+ Fields

The `metadata` JSONB field should contain comprehensive execution context:

### Session Context
```json
{
  "session": {
    "session_id": "4d1f43c9-cfc0-4917-a842-a238f5415111",
    "user": "sfloess",
    "orchestrator": "laptop-01",
    "launched_at": "2026-06-19T15:30:00Z",
    "launched_by": "claude-code"
  }
}
```

### Worker Pool Configuration
```json
{
  "worker_pool": {
    "pool_name": "fleet-5-nodes",
    "worker_count": 5,
    "total_cores": 32,
    "total_ram_gb": 107,
    "workers": ["server-01", "server-02", "server-03", "pi-02", "laptop-02"],
    "orchestrator_excluded": true
  }
}
```

### Storage Configuration
```json
{
  "storage": {
    "pattern": "chunking + vectorDB + graphDB",
    "database": {
      "host": "laptop-01",
      "name": "learning",
      "schema": "code_analysis",
      "table": "chunks"
    },
    "vector": {
      "model": "sentence-transformers/all-MiniLM-L6-v2",
      "dimensions": 384,
      "index_type": "HNSW"
    },
    "graph": {
      "type": "Neo4j",
      "host": "laptop-01",
      "sync_enabled": true
    },
    "filesystem": {
      "base_path": "/exports/code-review",
      "output_format": "json"
    }
  }
}
```

### Task Scope (Repository/Research Topic)
```json
{
  "scope": {
    "type": "repository" | "research_topic" | "pdf_analysis" | "firmware",
    "repository": {
      "url": "https://gitlab.com/...",
      "path": "/home/sfloess/Development/...",
      "branch": "main",
      "commit": "a51c08b"
    },
    "research_topic": {
      "category": "AI/ML/consciousness",
      "subtopic": "Integrated Information Theory",
      "keywords": ["IIT", "Phi", "consciousness", "Tononi"],
      "time_range": "2024-2026"
    },
    "pdf_analysis": {
      "pdf_path": "/mnt/nas/media/books/...",
      "page_count": 250,
      "file_size_mb": 12.5,
      "categories": ["methodology", "leadership"]
    }
  }
}
```

### Chunking Strategy
```json
{
  "chunking": {
    "strategy": "ast_based" | "semantic" | "fixed_size" | "sliding_window",
    "granularity": "function" | "class" | "method" | "file" | "section",
    "chunk_size_target": 1000,
    "overlap_tokens": 100,
    "ast_parser": "tree-sitter" | "babel" | "pdfplumber",
    "language": "java" | "python" | "javascript" | "pdf_text"
  }
}
```

### Embedding Configuration
```json
{
  "embeddings": {
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "dimensions": 384,
    "batch_size": 32,
    "normalization": "l2",
    "total_chunks_processed": 1250,
    "total_embeddings_generated": 1250,
    "embedding_generation_time_ms": 45000
  }
}
```

### Workflow Execution Details
```json
{
  "workflow": {
    "name": "deep-research" | "code-review-auto" | "pdf-analysis",
    "script_path": "/home/sfloess/.claude/.../workflows/scripts/...",
    "run_id": "wf_d9b60074-d43",
    "task_id": "wu333mreg",
    "phases": [
      {
        "name": "Scope",
        "order": 1,
        "duration_ms": 5000,
        "outcome": "success"
      },
      {
        "name": "Search",
        "order": 2,
        "duration_ms": 12000,
        "outcome": "success"
      }
    ]
  }
}
```

### Model Usage
```json
{
  "models": {
    "primary": "claude-opus-4",
    "workers": [
      {
        "worker_id": "worker-1",
        "model": "opus",
        "provider": "anthropic",
        "api_tier": "paid",
        "input_tokens": 5000,
        "output_tokens": 2500,
        "cost_usd": 0.15
      }
    ],
    "arbiter": {
      "model": "sonnet",
      "consensus_method": "weighted_vote",
      "confidence": 0.92
    }
  }
}
```

### Performance Metrics
```json
{
  "performance": {
    "total_duration_ms": 45000,
    "phases": {
      "search_ms": 12000,
      "fetch_ms": 8000,
      "verify_ms": 15000,
      "synthesize_ms": 10000
    },
    "parallelism": {
      "max_concurrent": 5,
      "avg_concurrent": 3.8,
      "wall_clock_savings_percent": 68
    },
    "throughput": {
      "chunks_per_second": 27.8,
      "tokens_per_second": 1250,
      "embeddings_per_second": 27.8
    }
  }
}
```

### Quality Metrics
```json
{
  "quality": {
    "worker_consensus": {
      "agreement_rate": 0.85,
      "diversity_score": 0.72,
      "models_in_consensus": 5
    },
    "verification": {
      "claims_verified": 42,
      "claims_refuted": 3,
      "confidence_avg": 0.88
    },
    "output_quality": {
      "completeness_score": 0.92,
      "accuracy_score": 0.89,
      "relevance_score": 0.94
    }
  }
}
```

### Resource Consumption
```json
{
  "resources": {
    "cpu": {
      "total_cpu_seconds": 1250,
      "peak_cpu_percent": 85,
      "avg_cpu_percent": 62
    },
    "memory": {
      "peak_mb": 4500,
      "avg_mb": 2800
    },
    "disk": {
      "reads_mb": 250,
      "writes_mb": 125,
      "output_size_mb": 12.5
    },
    "network": {
      "api_calls": 25,
      "bytes_sent": 125000,
      "bytes_received": 450000
    }
  }
}
```

### Error Handling
```json
{
  "errors": {
    "total_retries": 2,
    "retry_reasons": ["rate_limit", "timeout"],
    "partial_failures": [
      {
        "phase": "fetch",
        "url": "https://...",
        "error": "404 Not Found"
      }
    ],
    "warnings": [
      "Embedding generation took 2× expected time"
    ]
  }
}
```

### Output Artifacts
```json
{
  "artifacts": {
    "files_generated": [
      "/exports/code-review/research-iit-consciousness/report.json",
      "/exports/code-review/research-iit-consciousness/embeddings.jsonl",
      "/exports/code-review/research-iit-consciousness/citations.bib"
    ],
    "database_records": {
      "chunks_inserted": 1250,
      "relationships_created": 450,
      "embeddings_stored": 1250
    },
    "graph_nodes": {
      "concepts": 42,
      "citations": 28,
      "relationships": 85
    }
  }
}
```

### Integration Points
```json
{
  "integrations": {
    "grafana": {
      "dashboard_url": "http://pi-02:3000/d/...",
      "metrics_exported": true
    },
    "prometheus": {
      "metrics_endpoint": "http://laptop-01:9100/metrics",
      "scrape_interval_seconds": 15
    },
    "neo4j": {
      "sync_completed": true,
      "nodes_created": 127,
      "relationships_created": 450
    }
  }
}
```

### Provenance & Lineage
```json
{
  "provenance": {
    "parent_task_id": "master-research-ai-ml",
    "child_tasks": ["research-iit-details", "research-iit-implementations"],
    "derived_from": ["paper-tononi-2016", "paper-koch-2019"],
    "influences": ["previous-consciousness-research"],
    "lineage_depth": 3
  }
}
```

### Audit Trail
```json
{
  "audit": {
    "created_by": "orchestrator:laptop-01",
    "modified_at": ["2026-06-19T15:30:00Z", "2026-06-19T15:45:00Z"],
    "modified_by": ["system:auto-recovery", "user:manual-priority-bump"],
    "state_transitions": [
      {"from": "queued", "to": "running", "at": "2026-06-19T15:30:00Z"},
      {"from": "running", "to": "paused", "at": "2026-06-19T15:40:00Z", "reason": "user_requested"},
      {"from": "paused", "to": "running", "at": "2026-06-19T15:45:00Z"}
    ]
  }
}
```

### Recovery Information
```json
{
  "recovery": {
    "checkpoint_enabled": true,
    "last_checkpoint_at": "2026-06-19T15:40:00Z",
    "checkpoint_path": "/tmp/.../checkpoint-phase-2.json",
    "resumable": true,
    "resume_from_phase": "verify"
  }
}
```

### Related Work
```json
{
  "related": {
    "similar_tasks": ["research-gwt-consciousness", "research-fep"],
    "similarity_scores": [0.85, 0.72],
    "duplicate_check": false,
    "builds_on": ["foundational-ai-research"],
    "blocks": ["consciousness-synthesis-report"]
  }
}
```

---

## Total Metadata Fields: 150+

**Categories:**
- Session Context: 5 fields
- Worker Pool: 10 fields
- Storage Configuration: 15 fields
- Task Scope: 20 fields
- Chunking Strategy: 8 fields
- Embedding Configuration: 7 fields
- Workflow Execution: 15 fields
- Model Usage: 20 fields
- Performance Metrics: 15 fields
- Quality Metrics: 12 fields
- Resource Consumption: 12 fields
- Error Handling: 8 fields
- Output Artifacts: 10 fields
- Integration Points: 8 fields
- Provenance & Lineage: 8 fields
- Audit Trail: 10 fields
- Recovery Information: 6 fields
- Related Work: 8 fields

**Total: 197 metadata fields** across all categories

---

## Implementation Strategy

1. **Automatic Capture** - All fields populated by orchestrator automatically
2. **Worker Reporting** - Workers report back metrics to orchestrator
3. **Progressive Enhancement** - Start with core fields, add extended as needed
4. **Query Optimization** - JSONB GIN indexes for fast metadata queries
5. **Compression** - Compress large metadata blobs after 30 days
