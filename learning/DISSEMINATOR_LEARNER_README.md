# Disseminator Autonomous Learning System

**Fully autonomous knowledge extraction from 144+ disseminator conversations**

## Overview

This system continuously learns from conversations about the disseminator codebase, extracting technical patterns, deployment workflows, and architectural knowledge without requiring human approval.

## Features

- **Autonomous Extraction**: No human approval needed for extraction decisions
- **Thompson Sampling**: Intelligent model selection based on performance
- **Cost Control**: Enforces $50/day budget limit
- **Vector Search**: Semantic search over extracted knowledge
- **Quality Filtering**: Only stores high-confidence learnings (≥0.7)
- **Multi-Model**: Uses Opus, Sonnet, Haiku, GPT-4o, Gemini, Fable

## Architecture

```
disseminator-learner.js
  ├─ Discovers conversation logs (144 .jsonl files)
  ├─ Parses conversations (messages, tools, files)
  ├─ Selects model (Thompson Sampling via model-selector.js)
  ├─ Extracts knowledge (10 categories)
  ├─ Filters quality (confidence ≥ 0.7)
  ├─ Stores knowledge (JSONL + vectors)
  ├─ Updates metrics (learning.db)
  └─ Enforces budget (cost-enforcer.js)
```

## Extraction Categories

1. **ifd_endpoint_patterns** - IFD endpoint configurations
2. **deployment_workflows** - Deployment procedures
3. **cicd_pipeline_knowledge** - GitLab CI/CD patterns
4. **kubernetes_deployments** - K8s deployment configs
5. **gitlab_ci_patterns** - GitLab CI best practices
6. **ansible_playbooks** - Ansible automation patterns
7. **troubleshooting_solutions** - Problem solutions
8. **architecture_decisions** - Design decisions
9. **api_endpoints** - API endpoint definitions
10. **configuration_patterns** - Config file patterns

## Usage

### Initial Extraction (Process all 144 conversations)

```bash
cd ~/.claude/learning
node disseminator-learner.js --initial-run
```

### Incremental Processing (New conversations only)

```bash
node disseminator-learner.js --incremental
```

### Continuous Mode (Systemd service)

```bash
# Install service
sudo cp disseminator-learner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable disseminator-learner
sudo systemctl start disseminator-learner

# Check status
sudo systemctl status disseminator-learner

# View logs
tail -f ~/.claude/learning/logs/disseminator-learner.log
```

### Status Dashboard

```bash
# One-time view
node disseminator-status.js

# Watch mode (updates every 5s)
node disseminator-status.js --watch
```

### Search Knowledge Base

```bash
# Simple search
node disseminator-search.js "IFD endpoint configuration"

# Filter by type
node disseminator-search.js --type=cicd_pipeline_knowledge "gitlab"

# Filter by confidence
node disseminator-search.js --min-confidence=0.8 "deployment"

# Vector-only search
node disseminator-search.js --method=vector "kubernetes"

# Text-only search
node disseminator-search.js --method=text "ansible"

# Hybrid search (default)
node disseminator-search.js --method=hybrid "troubleshooting"
```

## Data Files

| File | Purpose | Format |
|------|---------|--------|
| `disseminator-knowledge.jsonl` | Knowledge base | JSONL (one item per line) |
| `disseminator-vectors.jsonl` | Vector embeddings | JSONL (100-dim embeddings) |
| `disseminator-index.json` | Vector index metadata | JSON |
| `disseminator-learner-state.json` | Processing state | JSON |
| `db/costs.db` | Cost tracking | SQLite |
| `db/learning.db` | Model performance | SQLite |

## Knowledge Schema

```json
{
  "id": "dk_1718298765432_abc123",
  "type": "ifd_endpoint_patterns",
  "title": "IFD Endpoint Configuration Pattern",
  "content": "Detailed technical knowledge...",
  "confidence": 0.85,
  "entities": ["IFD", "endpoint", "disseminator"],
  "source_conversation": "c58f1ee3624c460385358",
  "source_path": "/path/to/conversation.jsonl",
  "model_used": "opus",
  "extracted_at": "2026-06-13T14:30:00.000Z",
  "quality_score": 0.87
}
```

## Cost Control

- **Daily Limit**: $50.00 (configurable)
- **Per-Conversation Limit**: $0.50 (configurable)
- **Budget Enforcement**: Hard rejection when limits reached
- **Cost Tracking**: SQLite database with daily/monthly aggregates

## Model Selection (Thompson Sampling)

The system uses Thompson Sampling to select the best model for each extraction:

1. **Beta Distribution**: Each model has `Beta(alpha, beta)` posterior
2. **Sliding Window**: Only recent 100 executions count
3. **Exploration Bonus**: Under-explored models get small boost
4. **Quality Feedback**: Updates posteriors based on extraction quality

## Monitoring

### View Status
```bash
node disseminator-status.js
```

### Check Logs
```bash
tail -f logs/disseminator-learner.log
tail -f logs/disseminator-learner.error.log
```

### Message Bus Channels
```bash
# View budget alerts
node -e "const mb=require('./shared/message-bus.js'); console.log(mb.readMessages('budget-alerts'))"

# View extraction events
node -e "const mb=require('./shared/message-bus.js'); console.log(mb.readMessages('knowledge-extracted'))"
```

### Cost Report
```bash
node shared/cost-enforcer.js
```

## Troubleshooting

### No conversations found
Check that disseminator project directory exists:
```bash
ls -la /home/sfloess/.claude/projects/-home-sfloess-Development-redhat-scm-gitlab-search-engineering-disseminator/
```

### Budget exceeded
Reset daily budget (only if needed):
```bash
node -e "
const {CostDatabase,CostEnforcer}=require('./shared/cost-enforcer.js');
(async()=>{
  const db=new CostDatabase('./db/costs.db');
  await db.init();
  const e=new CostEnforcer(db);
  await e.initialize();
  await e.setBudgetLimits(100,2000,50); // daily, monthly, session
  await db.close();
})()
"
```

### Vector search not working
Rebuild vector index:
```bash
node -e "
const fs=require('fs');
const vecs=fs.readFileSync('./disseminator-vectors.jsonl','utf8').trim().split('\n');
console.log('Vectors:', vecs.length);
"
```

## Integration with Claude Code

The knowledge base is automatically available to Claude Code sessions via:

1. **Memory System**: High-quality learnings (≥0.9) auto-indexed
2. **Vector Search**: Semantic search via MCP tools
3. **Message Bus**: Real-time notifications of new knowledge

## Performance

- **Processing Speed**: ~5 conversations/minute
- **Cost per Conversation**: ~$0.05 (with Sonnet)
- **Total Time (144 conversations)**: ~30 minutes
- **Total Cost (initial run)**: ~$7.20
- **Daily Incremental**: ~$1-2 (for new conversations)

## Continuous Learning Loop

In continuous mode, the system:

1. Checks for new conversations every 1 hour
2. Processes only new/unprocessed conversations
3. Updates knowledge base incrementally
4. Respects daily budget limits
5. Publishes events to message bus
6. Logs all activity

## Security

- **No Remote Access**: All processing local
- **No Credentials**: Uses local conversation logs only
- **Cost Protection**: Hard budget limits prevent runaway costs
- **Quality Gates**: Low-quality extractions filtered out

## Future Enhancements

- [ ] Real embedding model (sentence-transformers)
- [ ] Redis message bus (replace JSONL)
- [ ] Grafana dashboard integration
- [ ] Active learning (query user for clarification)
- [ ] Transfer learning across codebases
- [ ] Automated PR suggestions based on learnings

## License

Internal use only - Red Hat Search Engineering

## Contact

For questions or issues, contact the Claude Code team.
