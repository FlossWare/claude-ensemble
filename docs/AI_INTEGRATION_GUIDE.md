# AI Integration Guide - Multi-Model Orchestration System

**Version:** 1.0.0  
**Last Updated:** 2026-07-07  
**Purpose:** Enable any AI system (GPT-4, Gemini, Claude, custom models) to use this distributed orchestration infrastructure

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Quick Start](#quick-start)
3. [API Reference](#api-reference)
4. [Database Schema](#database-schema)
5. [Workflow Patterns](#workflow-patterns)
6. [Model Routing](#model-routing)
7. [Learning System](#learning-system)
8. [Example Integrations](#example-integrations)
9. [Troubleshooting](#troubleshooting)

---

## System Overview

### Architecture

```
┌─────────────────────────────────────────┐
│ AI Client (You)                         │
│  - Send HTTP requests                   │
│  - Query PostgreSQL                     │
│  - Parse JSON responses                 │
└─────────────────────────────────────────┘
           ↓ REST API
┌─────────────────────────────────────────┐
│ Orchestrator (aio-01:5000)              │
│  - Receives workflow requests           │
│  - Routes to 204 free models            │
│  - Distributes across 8 worker nodes    │
│  - Returns aggregated results           │
└─────────────────────────────────────────┘
           ↓ SSH Distribution
┌─────────────────────────────────────────┐
│ Worker Fleet (8 nodes)                  │
│  - server-01, server-02, server-03      │
│  - laptop-01, desktop-ap, server-ap     │
│  - pi-01, pi-02                         │
│  - Execute API calls to LLM providers   │
└─────────────────────────────────────────┘
           ↓ Results Storage
┌─────────────────────────────────────────┐
│ Learning Database (PostgreSQL)          │
│  - aio-01:5433                          │
│  - Model capabilities & performance     │
│  - Workflow history & patterns          │
│  - Embeddings (pgvector)                │
└─────────────────────────────────────────┘
```

### Key Components

1. **Orchestrator API** - `http://aio-01:5000`
2. **Learning Database** - `postgresql://aio-01:5433/learning`
3. **8 Worker Nodes** - SSH-accessible execution fleet
4. **204 Free Models** - Across 15+ providers (Anthropic, OpenAI, Google, Groq, Cerebras, DeepSeek, etc.)

### What This System Does

- ✅ **Multi-model consensus** - Query 3-8 models, get synthesized answer
- ✅ **Task-aware routing** - Automatically selects best models for task type
- ✅ **Distributed execution** - Parallelizes work across 8 nodes
- ✅ **Adversarial verification** - 3-vote refutation system for facts
- ✅ **Continual learning** - Improves routing based on past performance
- ✅ **Cost optimization** - Uses only free models, zero API costs

---

## Quick Start

### Prerequisites

- Network access to `aio-01:5000` (orchestrator API)
- PostgreSQL client or connection library
- Ability to make HTTP POST requests
- JSON parsing capability

### Your First Request

```bash
curl -X POST http://aio-01:5000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Explain quantum entanglement in simple terms",
    "workflow": "ai-consensus",
    "models": ["opus", "sonnet", "gpt-4o"],
    "phases": ["execute", "synthesize"]
  }'
```

**Response:**
```json
{
  "status": "success",
  "workflow_id": "wf_abc123",
  "result": {
    "consensus": "Quantum entanglement is when two particles...",
    "confidence": 0.92,
    "models_used": ["opus", "sonnet", "gpt-4o"],
    "arbiter": "fable",
    "duration_ms": 4523
  }
}
```

---

## API Reference

### Base URL
```
http://aio-01:5000
```

### Endpoints

#### 1. Execute Workflow

**POST** `/execute`

Execute a multi-agent workflow with distributed execution.

**Request Body:**
```json
{
  "task": "string (required) - The task/question to execute",
  "workflow": "string (optional) - Workflow pattern name (default: ai-consensus)",
  "models": ["array (optional) - Model names to use (default: task-aware selection)"],
  "taskType": "string (optional) - Task category for routing (auto-detected if omitted)",
  "phases": ["array (optional) - Workflow phases to execute"],
  "options": {
    "maxWorkers": "number (optional) - Max parallel workers (default: 6)",
    "minConfidence": "number (optional) - Minimum confidence threshold (default: 0.7)",
    "adversarialVerify": "boolean (optional) - Enable 3-vote verification (default: false)",
    "storeResults": "boolean (optional) - Save to learning DB (default: true)"
  }
}
```

**Response:**
```json
{
  "status": "success|error",
  "workflow_id": "wf_xxxxx",
  "result": {
    "consensus": "string - Synthesized answer",
    "confidence": "number - 0.0 to 1.0",
    "models_used": ["array - Models that contributed"],
    "arbiter": "string - Model that synthesized consensus",
    "worker_results": [
      {
        "model": "string",
        "response": "string",
        "confidence": "number",
        "tokens": "number",
        "duration_ms": "number"
      }
    ],
    "duration_ms": "number - Total workflow time"
  },
  "metadata": {
    "task_type": "string - Detected task category",
    "routing_strategy": "string - How models were selected",
    "phases_completed": ["array - Workflow phases executed"]
  }
}
```

**Example - Deep Research:**
```json
{
  "task": "What are the latest breakthroughs in quantum computing in 2026?",
  "workflow": "deep-research",
  "options": {
    "adversarialVerify": true,
    "maxWorkers": 8
  }
}
```

#### 2. Query Model Capabilities

**GET** `/models/capabilities?taskType={type}`

Get best models for a specific task type.

**Parameters:**
- `taskType` - One of: code_generation, code_review, bug_detection, security_audit, architecture_review, research, fact_checking, consensus, creative_writing, math_reasoning, documentation, testing, optimization, refactoring, data_analysis

**Response:**
```json
{
  "task_type": "code_review",
  "models": [
    {
      "model": "opus",
      "capability_score": 0.94,
      "avg_confidence": 0.89,
      "success_rate": 0.92,
      "avg_tokens": 1523
    },
    {
      "model": "sonnet",
      "capability_score": 0.91,
      "avg_confidence": 0.87,
      "success_rate": 0.89,
      "avg_tokens": 1342
    }
  ]
}
```

#### 3. List Available Models

**GET** `/models/available`

Get all 204 available free models.

**Response:**
```json
{
  "total": 204,
  "providers": {
    "anthropic": ["opus", "sonnet", "haiku", "fable"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    "google": ["gemini-pro", "gemini-flash", "gemini-nano"],
    "groq": ["llama-3.1-405b", "llama-3.1-70b", "mixtral-8x7b"],
    "cerebras": ["llama-3.1-70b", "llama-3.1-8b"],
    "deepseek": ["deepseek-chat", "deepseek-coder"]
  },
  "models": [
    {
      "name": "opus",
      "provider": "anthropic",
      "context_window": 200000,
      "cost_per_1m_tokens": 0.0,
      "strengths": ["code", "reasoning", "complex_analysis"]
    }
  ]
}
```

#### 4. Get Workflow Status

**GET** `/workflow/{workflow_id}`

Check status of a running workflow.

**Response:**
```json
{
  "workflow_id": "wf_abc123",
  "status": "running|completed|failed",
  "progress": {
    "current_phase": "verify",
    "total_phases": 5,
    "completed_workers": 6,
    "total_workers": 8,
    "elapsed_ms": 3421
  },
  "partial_results": {
    "completed_phases": ["scope", "search", "fetch"]
  }
}
```

---

## Database Schema

### Connection

```python
import psycopg2

conn = psycopg2.connect(
    host="aio-01",
    port=5433,
    database="learning",
    user="claude",
    password="<see credentials.json>"
)
```

### Key Tables

#### 1. `learning.model_capabilities`

Model performance by task type.

```sql
CREATE TABLE learning.model_capabilities (
    id SERIAL PRIMARY KEY,
    model VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    capability_score DECIMAL(5,4),  -- 0.0 to 1.0
    avg_confidence DECIMAL(5,4),
    success_rate DECIMAL(5,4),
    total_executions INTEGER,
    avg_tokens INTEGER,
    avg_duration_ms INTEGER,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(model, task_type)
);
```

**Query best model for task:**
```sql
SELECT model, capability_score, success_rate
FROM learning.model_capabilities
WHERE task_type = 'code_review'
ORDER BY capability_score DESC
LIMIT 5;
```

#### 2. `workflow.executions`

Workflow execution history.

```sql
CREATE TABLE workflow.executions (
    id SERIAL PRIMARY KEY,
    workflow_id VARCHAR(50) UNIQUE NOT NULL,
    workflow_name VARCHAR(100),
    task_description TEXT,
    task_embedding vector(384),  -- pgvector for similarity search
    total_workers INTEGER,
    total_duration_ms INTEGER,
    outcome VARCHAR(20),  -- success, error, timeout
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Query similar past workflows:**
```sql
SELECT workflow_id, task_description, outcome
FROM workflow.executions
ORDER BY task_embedding <=> '[0.123, 0.456, ...]'::vector
LIMIT 10;
```

#### 3. `workflow.worker_results`

Individual worker outputs.

```sql
CREATE TABLE workflow.worker_results (
    id SERIAL PRIMARY KEY,
    workflow_execution_id INTEGER REFERENCES workflow.executions(id),
    worker_id VARCHAR(50),
    model VARCHAR(100),
    task_assigned TEXT,
    result TEXT,
    result_embedding vector(384),
    confidence DECIMAL(5,4),
    duration_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd DECIMAL(10,6),
    outcome VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 4. `learning.strategy_performance`

Thompson Sampling bandit state for routing strategies.

```sql
CREATE TABLE learning.strategy_performance (
    strategy VARCHAR(100) PRIMARY KEY,
    successes INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    alpha DECIMAL(10,6),  -- Beta distribution parameters
    beta DECIMAL(10,6),
    total_reward DECIMAL(10,6),
    avg_reward DECIMAL(10,6),
    last_updated TIMESTAMP DEFAULT NOW()
);
```

---

## Workflow Patterns

### Available Workflows

#### 1. `ai-consensus` (Default)

Multi-model consensus for any question.

**Pattern:**
1. Execute: 3-8 models respond independently
2. Synthesize: Arbiter merges best answers
3. Quality score: Confidence calibration

**Best for:** General questions, fact-checking, analysis

**Example:**
```json
{
  "task": "Should we use REST or GraphQL for this API?",
  "workflow": "ai-consensus",
  "models": ["opus", "sonnet", "gpt-4o", "gemini-pro"]
}
```

#### 2. `deep-research`

Multi-source fact-checked research with adversarial verification.

**Pattern:**
1. Scope: Decompose into 5 search angles
2. Search: 5 parallel web searches
3. Fetch: URL-dedup, top 15 sources
4. Verify: 3-vote adversarial refutation (need 2/3 to kill claim)
5. Synthesize: Merge, rank by confidence, cite sources

**Best for:** Research questions, fact verification, literature review

**Example:**
```json
{
  "task": "What are proven treatments for long COVID as of 2026?",
  "workflow": "deep-research",
  "options": {
    "adversarialVerify": true,
    "maxWorkers": 8
  }
}
```

#### 3. `fleet-review`

Adversarial code review across multiple models.

**Pattern:**
1. Audit: Check what's wired vs dormant
2. Review: Multi-model quality assessment
3. Verify: Try to break it (adversarial testing)
4. Grade: A/B/C/D scoring

**Best for:** Code review, architecture validation, security audit

**Example:**
```json
{
  "task": "Review this authentication system for security issues",
  "workflow": "fleet-review",
  "options": {
    "adversarialVerify": true
  }
}
```

#### 4. `learn-and-apply`

Learn from past similar tasks and apply patterns.

**Pattern:**
1. Query: Find similar past tasks (embedding search)
2. Extract: Get successful reasoning patterns
3. Apply: Use pattern on current task
4. Store: Save new pattern if successful

**Best for:** Repetitive tasks, pattern-based work

**Example:**
```json
{
  "task": "Optimize this database query",
  "workflow": "learn-and-apply",
  "options": {
    "storeResults": true
  }
}
```

---

## Model Routing

### Task Types (15 categories)

The system automatically detects task type and routes to best models:

1. **code_generation** - Writing new code
2. **code_review** - Reviewing existing code
3. **bug_detection** - Finding bugs/issues
4. **security_audit** - Security analysis
5. **architecture_review** - System design review
6. **research** - Information gathering
7. **fact_checking** - Verification of claims
8. **consensus** - Multi-perspective synthesis
9. **creative_writing** - Content creation
10. **math_reasoning** - Mathematical problem solving
11. **documentation** - Writing docs/explanations
12. **testing** - Test case creation
13. **optimization** - Performance improvement
14. **refactoring** - Code restructuring
15. **data_analysis** - Data interpretation

### Manual Model Selection

You can override auto-routing:

```json
{
  "task": "Explain quantum computing",
  "models": ["opus", "gpt-4o", "gemini-pro"],
  "taskType": "research"
}
```

### Model Pool (204 models)

**Top performers by category:**

| Task Type | Best Models |
|-----------|-------------|
| code_generation | opus, deepseek-coder, gpt-4o |
| code_review | opus, sonnet, claude-3.5 |
| research | gpt-4o, opus, gemini-pro |
| math_reasoning | gpt-4o, opus, gemini-pro |
| creative_writing | fable, gpt-4o, gemini-pro |
| security_audit | opus, sonnet, deepseek-coder |

**All providers:**
- Anthropic (Claude Opus, Sonnet, Haiku, Fable)
- OpenAI (GPT-4o, GPT-4o-mini, GPT-3.5-turbo)
- Google (Gemini Pro, Flash, Nano)
- Groq (Llama 3.1 405B/70B/8B, Mixtral)
- Cerebras (Llama 3.1 70B/8B)
- DeepSeek (DeepSeek-Chat, DeepSeek-Coder)
- Qwen (26 models)
- Nvidia (12 models)
- And 138 more...

---

## Learning System

### Thompson Sampling Bandit

The system learns which routing strategies work best using Thompson Sampling.

**How it works:**
1. Try strategy (e.g., "use opus for code_review")
2. Measure success (task completed, high confidence, user satisfied)
3. Update Beta distribution parameters (α, β)
4. Sample from distribution for next decision

**Query current state:**
```sql
SELECT strategy, alpha, beta, avg_reward, total_reward
FROM learning.strategy_performance
ORDER BY avg_reward DESC;
```

**Manual update (if you have ground truth):**
```sql
-- Success case
UPDATE learning.strategy_performance
SET successes = successes + 1,
    alpha = alpha + 1,
    total_reward = total_reward + 1.0,
    avg_reward = total_reward / (successes + failures)
WHERE strategy = 'opus_for_code_review';

-- Failure case
UPDATE learning.strategy_performance
SET failures = failures + 1,
    beta = beta + 1,
    avg_reward = total_reward / (successes + failures)
WHERE strategy = 'opus_for_code_review';
```

### Continual Learning Flow

```
┌─────────────┐
│ New Task    │
└──────┬──────┘
       ↓
┌─────────────────────────────────┐
│ Query Similar Tasks             │
│ (embedding similarity search)   │
└──────┬──────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Select Models                   │
│ (Thompson Sampling + history)   │
└──────┬──────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Execute Workflow                │
└──────┬──────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Measure Success                 │
│ (confidence, tokens, duration)  │
└──────┬──────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Update Learning Database        │
│ (capabilities, bandit state)    │
└─────────────────────────────────┘
```

---

## Example Integrations

### Python

```python
import requests
import psycopg2
from sentence_transformers import SentenceTransformer

class OrchestratorClient:
    def __init__(self):
        self.base_url = "http://aio-01:5000"
        self.db = psycopg2.connect(
            host="aio-01",
            port=5433,
            database="learning",
            user="claude"
        )
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def execute_workflow(self, task, workflow="ai-consensus", **options):
        """Execute a workflow and return results."""
        response = requests.post(
            f"{self.base_url}/execute",
            json={
                "task": task,
                "workflow": workflow,
                "options": options
            }
        )
        return response.json()
    
    def find_similar_tasks(self, task, limit=10):
        """Find similar past tasks using embedding search."""
        embedding = self.embedder.encode(task).tolist()
        
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT workflow_id, task_description, outcome
            FROM workflow.executions
            ORDER BY task_embedding <=> %s::vector
            LIMIT %s
        """, (embedding, limit))
        
        return cursor.fetchall()
    
    def get_best_models(self, task_type):
        """Get best models for a task type."""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT model, capability_score, success_rate
            FROM learning.model_capabilities
            WHERE task_type = %s
            ORDER BY capability_score DESC
            LIMIT 5
        """, (task_type,))
        
        return cursor.fetchall()

# Usage
client = OrchestratorClient()

# Execute consensus
result = client.execute_workflow(
    "Explain blockchain in simple terms",
    workflow="ai-consensus",
    maxWorkers=6
)
print(result['result']['consensus'])

# Find similar past work
similar = client.find_similar_tasks("Explain distributed systems")
print(f"Found {len(similar)} similar tasks")

# Get best models for code review
models = client.get_best_models("code_review")
print(f"Best models: {[m[0] for m in models]}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');
const { Client } = require('pg');

class OrchestratorClient {
  constructor() {
    this.baseUrl = 'http://aio-01:5000';
    this.db = new Client({
      host: 'aio-01',
      port: 5433,
      database: 'learning',
      user: 'claude'
    });
    this.db.connect();
  }
  
  async executeWorkflow(task, workflow = 'ai-consensus', options = {}) {
    const response = await axios.post(`${this.baseUrl}/execute`, {
      task,
      workflow,
      options
    });
    return response.data;
  }
  
  async findSimilarTasks(task, limit = 10) {
    // Assuming you have an embedding service
    const embedding = await this.generateEmbedding(task);
    
    const result = await this.db.query(`
      SELECT workflow_id, task_description, outcome
      FROM workflow.executions
      ORDER BY task_embedding <=> $1::vector
      LIMIT $2
    `, [embedding, limit]);
    
    return result.rows;
  }
  
  async getBestModels(taskType) {
    const result = await this.db.query(`
      SELECT model, capability_score, success_rate
      FROM learning.model_capabilities
      WHERE task_type = $1
      ORDER BY capability_score DESC
      LIMIT 5
    `, [taskType]);
    
    return result.rows;
  }
}

// Usage
const client = new OrchestratorClient();

(async () => {
  // Execute deep research
  const result = await client.executeWorkflow(
    'What are the latest AI breakthroughs in 2026?',
    'deep-research',
    { adversarialVerify: true, maxWorkers: 8 }
  );
  
  console.log(result.result.consensus);
  
  // Get best models for security audit
  const models = await client.getBestModels('security_audit');
  console.log('Best models:', models.map(m => m.model));
})();
```

### REST API (Generic)

```bash
# Execute consensus
curl -X POST http://aio-01:5000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Compare Rust vs Go for systems programming",
    "workflow": "ai-consensus",
    "models": ["opus", "gpt-4o", "gemini-pro"]
  }'

# Get model capabilities
curl http://aio-01:5000/models/capabilities?taskType=code_review

# Check workflow status
curl http://aio-01:5000/workflow/wf_abc123
```

---

## Troubleshooting

### Common Issues

#### 1. Connection Refused (aio-01:5000)

**Problem:** Can't reach orchestrator API

**Solutions:**
- Check network: `ping aio-01`
- Check orchestrator running: `ssh root@aio-01 'systemctl status orchestrator'`
- Check firewall: Port 5000 must be open

#### 2. Database Connection Failed (aio-01:5433)

**Problem:** PostgreSQL connection refused

**Solutions:**
- Check PostgreSQL running: `ssh root@aio-01 'systemctl status postgresql'`
- Verify port: `telnet aio-01 5433`
- Check credentials in `~/.claude/credentials.json`

#### 3. Workflow Timeout

**Problem:** Workflow doesn't complete

**Solutions:**
- Check worker fleet: `ssh root@aio-01 'systemctl status claude-worker@*'`
- Reduce maxWorkers: Use 3-4 instead of 8
- Increase timeout in options: `{ "timeout_ms": 60000 }`

#### 4. Low Confidence Results

**Problem:** Consensus confidence < 0.7

**Solutions:**
- Use more models: Increase from 3 to 6-8
- Enable adversarial verification: `{ "adversarialVerify": true }`
- Use task-specific models instead of generic

#### 5. Model Not Found

**Problem:** Requested model doesn't exist

**Solutions:**
- List available models: `GET /models/available`
- Let system auto-select: Omit `models` field, provide `taskType` instead
- Check model name spelling (case-sensitive)

### Logging

**Check orchestrator logs:**
```bash
ssh root@aio-01 'tail -f /var/log/orchestrator/api.log'
```

**Check worker logs:**
```bash
ssh root@server-01 'tail -f /var/log/claude-worker/worker.log'
```

**Check database logs:**
```bash
ssh root@aio-01 'tail -f /var/log/postgresql/postgresql-16-main.log'
```

### Health Checks

**API health:**
```bash
curl http://aio-01:5000/health
# Expected: {"status": "healthy", "workers": 8, "database": "connected"}
```

**Database health:**
```sql
SELECT COUNT(*) as total_executions 
FROM workflow.executions 
WHERE created_at > NOW() - INTERVAL '24 hours';
```

**Fleet health:**
```bash
ssh root@aio-01 'systemctl status claude-worker@{server-01,server-02,server-03,laptop-01,pi-01,pi-02,desktop-ap,server-ap}'
```

---

## Advanced Features

### 1. Adversarial Verification

For fact-checking, use 3-vote adversarial refutation:

```json
{
  "task": "Verify: The speed of light is 300,000 km/s",
  "workflow": "deep-research",
  "options": {
    "adversarialVerify": true,
    "refutationThreshold": 0.66  // 2 out of 3 votes needed to kill claim
  }
}
```

**How it works:**
1. Extract falsifiable claims
2. Spawn 3 independent "skeptic" models
3. Each tries to REFUTE the claim
4. If ≥2 refute successfully → claim rejected
5. Only confirmed claims make it to synthesis

### 2. Semantic Deduplication

Merge similar results using embedding similarity:

```json
{
  "task": "Research quantum computing applications",
  "workflow": "deep-research",
  "options": {
    "semanticDedup": true,
    "similarityThreshold": 0.90  // Merge if >90% similar
  }
}
```

### 3. Knowledge Transfer

Share discoveries between workers mid-workflow:

```json
{
  "task": "Analyze this codebase for bugs",
  "workflow": "fleet-review",
  "options": {
    "knowledgeSharing": true,
    "shareInterval": 5000  // Share every 5 seconds
  }
}
```

**How it works:**
1. Worker A finds a critical issue
2. Broadcast to all other workers
3. Workers B-H can build on that discovery
4. Prevents duplicate work

### 4. Consensus Replay

Debug past consensus decisions:

```json
{
  "workflow_id": "wf_abc123",
  "action": "replay",
  "options": {
    "explainDecisions": true
  }
}
```

**Output:**
```json
{
  "replay": {
    "original_consensus": "Rust is better for systems programming",
    "worker_votes": [
      {"model": "opus", "choice": "Rust", "reasoning": "Memory safety without GC"},
      {"model": "gpt-4o", "choice": "Rust", "reasoning": "Zero-cost abstractions"},
      {"model": "gemini", "choice": "Go", "reasoning": "Simpler syntax, faster compilation"}
    ],
    "arbiter_logic": "Weighted 2/3 toward Rust due to safety + performance alignment",
    "why_gemini_lost": "Single vote vs majority, lower technical depth in reasoning"
  }
}
```

---

## Performance Metrics

### Expected Latencies

| Workflow | Workers | Avg Duration | Token Usage |
|----------|---------|--------------|-------------|
| ai-consensus | 3 | 2-4s | 2K-5K |
| ai-consensus | 6 | 3-6s | 5K-10K |
| deep-research | 8 | 15-30s | 20K-40K |
| fleet-review | 6 | 10-20s | 15K-30K |
| learn-and-apply | 1-3 | 1-3s | 1K-3K |

### Cost (All Free!)

- **API costs:** $0.00 (only free models used)
- **Infrastructure:** Self-hosted on existing hardware
- **Scaling:** Linear with worker count (8 workers = 8× throughput)

### Throughput

- **Single workflow:** 1-30s depending on complexity
- **Concurrent workflows:** Limited by worker pool (8 concurrent max)
- **Queue depth:** Unlimited (tasks queue if workers busy)

---

## Future Roadiness

**Next features (planned):**

1. **Multi-modal support** - Images, audio, video analysis
2. **Long-running tasks** - Workflows >1 hour with checkpointing
3. **Custom workflow DSL** - Define workflows in YAML/JSON
4. **A/B testing framework** - Compare routing strategies automatically
5. **Fine-tuning integration** - Train custom models on workflow results

---

## Contact & Support

**Documentation:** `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/docs/`

**Database Schema:** See `docs/DATABASE_SCHEMA.md`

**API Changelog:** See `CHANGELOG.md`

**Issues:** Report bugs via GitLab issues

---

## License

MIT License - See LICENSE file

---

**Last Updated:** 2026-07-07  
**Version:** 1.0.0  
**Maintained by:** Orchestrator Development Team
