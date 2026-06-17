# GitLab AI Agent Task - Deep Research (2026-06-16)

**Repository:** https://gitlab.cee.redhat.com/ccit/agents/gitlab-agent-task  
**Upstream:** https://github.com/redhat-community-ai-tools/cicaddy-gitlab  
**Version:** v2.3.2 (781 commits)  
**License:** Apache 2.0  
**Type:** GitLab CI template wrapper for cicaddy-gitlab AI agent framework

---

## Executive Summary

**gitlab-agent-task** is a **thin wrapper** repository providing internal Red Hat GitLab CI templates for the **cicaddy-gitlab** AI agent framework. The actual Python code lives upstream on GitHub and is installed from PyPI. This repo adds Red Hat-specific infrastructure:

- CentOS Stream 10 base images
- Red Hat SSL certificate handling  
- Internal GitLab runner tags
- MCP server configs for internal tools (Konflux DevLake, DataRouter, Context7)
- Agent skills and prompts for Red Hat workflows

**Core Capability**: AI-powered merge request code review with delegated sub-agent architecture.

---

## Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────┐
│  gitlab-agent-task (Internal Red Hat Wrapper)               │
│  ├─ GitLab CI templates (gitlab/*.yml)                      │
│  ├─ Internal base templates (.gitlab/templates/base/)       │
│  ├─ MCP configs (.gitlab/templates/mcp/)                    │
│  ├─ DSPy task files (.gitlab/prompts/)                      │
│  └─ Agent skills (.agents/skills/gitlab-agent/)             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  cicaddy-gitlab (Upstream - PyPI Package)                   │
│  ├─ GitLab API integration                                  │
│  ├─ MR diff fetching                                        │
│  ├─ Comment posting                                         │
│  ├─ DSPy prompt framework                                   │
│  └─ CI/CD orchestration                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  cicaddy (Core Framework)                                   │
│  ├─ Multi-provider AI (Gemini, OpenAI, Claude, Vertex)     │
│  ├─ Delegated sub-agent orchestration                      │
│  ├─ MCP tool integration                                    │
│  ├─ Token-aware execution                                   │
│  ├─ Prompt injection defense                                │
│  └─ Metadata architecture                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features

### 1. Multi-Provider AI Support

Supported providers:
- **Gemini** (standalone via API key)
- **Gemini Vertex AI** (via GCP service account + ADC)
- **OpenAI** (GPT-4o, GPT-4 Turbo)
- **Claude** (Anthropic API)
- **Claude Vertex AI** (via GCP service account + ADC)

**Vertex AI Advantage**: No API keys needed, uses Application Default Credentials (ADC) with GCP service accounts. Recommended for teams with GCP projects.

### 2. Delegated Sub-Agent Architecture

**Default mode: `DELEGATION_MODE: "auto"`**

A **triage agent** analyzes the MR diff and spawns specialized sub-agents in parallel:

Built-in specialist agents:
- `general-reviewer` - Overall code quality
- `security-reviewer` - Security vulnerabilities  
- `architecture-reviewer` - Design patterns, scalability
- `devops-reviewer` - CI/CD, infrastructure, deployment
- `api-reviewer` - REST/GraphQL API design
- `database-reviewer` - Schema, queries, migrations
- `ui-reviewer` - Frontend, UX, accessibility
- `performance-reviewer` - Performance, resource usage

**Triage intelligence varies by model:**
- Gemini Flash: Selects 4 agents (general, devops, security, architecture)
- Gemini Pro: Selects 2 agents (general, devops) - can miss security
- Claude Sonnet 4.6: Selects 5 agents (all of the above + performance) - most thorough

**Custom sub-agents:** Add YAML files to `.agents/delegation/review/` or JSON via `DELEGATION_AGENTS` CI variable.

### 3. DSPy Task Files (Declarative YAML Prompts)

Structured, reusable prompt definitions with:
- Input/output schemas
- Tool requirements/restrictions
- Constraints and reasoning mode
- Examples

Example: `.gitlab/prompts/mr_code_review.yml`

```yaml
name: mr_code_review
inputs:
  - name: diff_content
    required: true
    format: diff
outputs:
  - name: issues
    format: list
  - name: security_concerns
    format: list
constraints:
  - Focus on actionable feedback
  - Prioritize by severity (Critical > High > Medium > Low)
  - Provide specific line references
```

### 4. MCP Server Integration

**Model Context Protocol (MCP)** for external tool access:

Internal Red Hat MCP servers configured:
- **Konflux DevLake** - DORA metrics, build analytics
- **DataRouter** - Data pipeline monitoring
- **Context7** - Code intelligence

Configuration via `MCP_SERVERS_CONFIG`:

```yaml
MCP_SERVERS_CONFIG: >-
  [{"name": "context7", "protocol": "http",
    "endpoint": "https://mcp.context7.com/mcp",
    "headers": {"CONTEXT7_API_KEY": "$CONTEXT7_API_KEY"},
    "timeout": 300, "idle_timeout": 60,
    "scan_mode": "enforce"}]
```

**Dual timeout strategy:**
- `timeout` (max_tool_timeout): Absolute max per tool (default: 300s)
- `idle_timeout`: Time between progress updates (default: 60s)

### 5. Prompt Injection Defense

**Built-in heuristic scanner** checks content for prompt injection patterns:

**Scan modes:**
- `audit` - Log warnings only
- `enforce` - Block malicious content (default for skills)
- `disabled` - No scanning

**Auto-enabled for:**
- Agent rule files (AGENTS.md, GEMINI.md, CLAUDE.md)
- Skill files
- Local tool outputs

**Opt-in for MCP:** Set `scan_mode: "enforce"` per server in `MCP_SERVERS_CONFIG`.

### 6. Agent Rules System

Auto-loaded files from repo root:
- `AGENTS.md` - Project-wide coding standards, architecture notes
- `GEMINI.md` - Gemini-specific rules (when AI_PROVIDER=gemini)
- `CLAUDE.md` - Claude-specific rules (when AI_PROVIDER=claude)

Agent applies these rules during review automatically.

---

## Delegation Evaluation Results

**Test:** Real infrastructure MR (konflux/infra!611) - 716 lines, 7 files (Terraform, K8s manifests, Lua)

### Performance Comparison

| Model | Mode | Time | Output | Sub-Agents | Verified Issues | Critical Bugs |
|-------|------|------|--------|------------|-----------------|---------------|
| Gemini Flash | none | **16s** | 5.4K | — | 2 | 0 |
| Gemini Flash | auto | 78s | 20.4K | 4 | 5 | 1 |
| Gemini Pro | none | 74s | 5.0K | — | 4 | **1 unique** |
| Gemini Pro | auto | 87s | 10.2K | 2 | 5 | 1 |
| Claude 4.6 | none | 57s | 10.7K | — | 8 | **3 (1 unique)** |
| Claude 4.6 | auto | 173s | **61.8K** | **5** | 9 | 3 |

### Key Findings

**✅ Auto mode strengths:**
- Broader category coverage (HA, monitoring, performance)
- Higher minimum quality floor (Flash auto: 5 issues vs Flash none: 2)
- Only Claude auto activated performance-reviewer

**❌ Auto mode weaknesses:**
- **Missed 2 critical bugs** found exclusively by single-agent:
  - ArgoCD aggregation label wrong prefix (Pro none only)
  - Singular RBAC resource names (Claude none only)
- Triage quality varies (Pro auto: only 2 agents, missed security)
- False positive rate higher (2/3 auto vs 1/3 none)
- Diminishing returns (Claude auto: 6× output, only +1 issue vs Claude none)

**🎯 Optimal configurations:**
- **Speed**: Flash none (16s, catches obvious issues)
- **Balanced**: Claude none (57s, 8 issues, best single-agent)
- **Maximum breadth**: Claude auto (173s, 9 issues, 5 agents, 9 categories)
- **Maximum bug detection**: **Claude none + Pro none** (~75s, 10 issues total - captures all critical bugs)

**Key insight:** No single run catches everything. For high-risk infrastructure changes, running multiple models in single-agent mode may be more effective than delegation with one model.

---

## CI/CD Variable Setup

**Required variables (GitLab Settings > CI/CD > Variables):**

| Variable | Type | Masked | Protected | Expand | Notes |
|----------|------|--------|-----------|--------|-------|
| `GITLAB_TOKEN` | Text | ✓ | ✗ | ✓ | Project/Group Access Token with `api` scope |
| `GEMINI_API_KEY` | Text | ✓ | ✗ | ✓ | For AI_PROVIDER=gemini |
| `OPENAI_API_KEY` | Text | ✓ | ✗ | ✓ | For AI_PROVIDER=openai |
| `ANTHROPIC_API_KEY` | Text | ✓ | ✗ | ✓ | For AI_PROVIDER=claude |
| `GOOGLE_CLOUD_PROJECT` | Text | ✓ | ✗ | ✓ | GCP project ID for Vertex AI Gemini |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Text | ✓ | ✗ | ✓ | GCP project ID for Vertex AI Claude |
| `GOOGLE_APPLICATION_CREDENTIALS` | **File** | ✓ | ✗ | ✓ | GCP service account JSON (base64-encoded) |
| `CONTEXT7_API_KEY` | Text | ✓ | ✗ | ✓ | MCP tool authentication |
| `SLACK_WEBHOOK_URL` | Text | ✓ | Optional | ✓ | Notifications |

**Critical settings:**
- **Protected = No** for MR pipelines (protected variables only work on protected branches)
- **Masked = Yes** for all secrets (hides from logs)
- **Expand = Yes** (default, for variable references)

**Vertex AI setup:**
1. Create GCP service account with "Vertex AI User" role
2. Export JSON key
3. Base64-encode: `base64 < key.json | tr -d '\n'`
4. Store as **File** type CI variable with **Masked** + **Hidden** enabled

See: `docs/vertex-ai-adc-setup.md` for full guide.

---

## Quick Start Examples

### 1. Basic MR Code Review (Gemini Vertex AI)

```yaml
include:
  - project: 'ccit/agents/gitlab-agent-task'
    file: 'gitlab/ai_agent_template.yml'
    ref: 'v2.3.2'

ai_code_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    AI_MODEL: "gemini-3.5-flash"
    DELEGATION_MODE: "auto"  # Default: multi-agent
    SLACK_WEBHOOK_URL: $SLACK_WEBHOOK_URL
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### 2. Claude via Vertex AI

```yaml
ai_code_review_claude:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "anthropic-vertex"
    ANTHROPIC_VERTEX_PROJECT_ID: $ANTHROPIC_VERTEX_PROJECT_ID
    AI_MODEL: "claude-sonnet-4-6"
    DELEGATION_MODE: "auto"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### 3. Custom Review Prompt (Inline)

```yaml
ai_security_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    AI_TASK_PROMPT: |
      Security-focused code review. Prioritize:
      1. Authentication/authorization issues
      2. Input validation and injection vulnerabilities
      3. Data exposure and secrets handling
      4. Dependency security concerns
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### 4. DSPy Task File (Declarative)

```yaml
ai_code_review_dspy:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    AI_TASK_FILE: ".gitlab/prompts/mr_code_review.yml"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### 5. Single-Agent Mode (Opt Out of Delegation)

```yaml
ai_single_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    DELEGATION_MODE: "none"  # Disable sub-agents
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

### 6. Scheduled Analysis with MCP

```yaml
include:
  - project: 'ccit/agents/gitlab-agent-task'
    file: '.gitlab/templates/base/ai_cron_base.yml'
  - project: 'ccit/agents/gitlab-agent-task'
    file: '.gitlab/templates/mcp/konflux_devlake.yml'

weekly_dora_report:
  extends:
    - .ai_cron_base
    - .mcp_konflux_devlake
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    AI_MODEL: "gemini-3.5-flash"
    AI_TASK_FILE: ".gitlab/prompts/dora_metrics.yml"
    SLACK_WEBHOOK_URL: $ANALYSIS_SLACK_WEBHOOK
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

### 7. Custom Sub-Agents (YAML)

`.agents/delegation/review/compliance-reviewer.yaml`:

```yaml
name: compliance-reviewer
agent_type: review
persona: compliance engineer specializing in regulatory requirements
description: Reviews changes for regulatory and compliance impact
categories:
  - security
  - configuration
constraints:
  - Focus on regulatory compliance (SOC2, GDPR, HIPAA)
  - Flag any PII handling changes
  - Check audit logging requirements
output_sections:
  - Compliance Impact
  - Regulatory Risks
  - Required Controls
priority: 15
```

### 8. Multi-Model Review (Maximum Bug Detection)

```yaml
ai_claude_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "anthropic-vertex"
    ANTHROPIC_VERTEX_PROJECT_ID: $ANTHROPIC_VERTEX_PROJECT_ID
    AI_MODEL: "claude-sonnet-4-6"
    DELEGATION_MODE: "none"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

ai_gemini_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    AI_MODEL: "gemini-3.1-pro-preview"
    DELEGATION_MODE: "none"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

---

## Red Hat Internal Customizations

### 1. Base Images
- CentOS Stream 10 (`.gitlab/templates/base/`)
- Red Hat SSL certificates pre-configured

### 2. Internal Runner Tags
- Optimized for internal GitLab infrastructure
- Pre-configured in base templates

### 3. MCP Server Configs

Internal-only MCP servers:
- **Konflux DevLake** (`.gitlab/templates/mcp/konflux_devlake.yml`)
- **DataRouter** (`.gitlab/templates/mcp/datarouter.yml`)

### 4. Child Pipelines
- `.gitlab/child-pipelines/devlake.yml`
- `.gitlab/child-pipelines/datarouter.yml`

### 5. Prompts
- `.gitlab/prompts/konflux_repos/summary_all_repos.yml`
- `.gitlab/prompts/konflux_repos/single_repo_analysis.yml`
- `.gitlab/prompts/datarouter_analysis.yml`

---

## Repository Structure

```
gitlab-agent-task/
├── gitlab/
│   ├── ai_agent_template.yml      # Main MR review template
│   └── ai_cron_template.yml       # Scheduled analysis template
├── .gitlab/
│   ├── templates/
│   │   ├── base/
│   │   │   ├── ai_agent_base.yml  # Base with SSL certs
│   │   │   ├── ai_cron_base.yml   # Cron base
│   │   │   └── ssl_setup.yml      # Red Hat SSL setup
│   │   ├── mcp/
│   │   │   ├── konflux_devlake.yml
│   │   │   └── datarouter.yml
│   │   └── jobs/
│   │       ├── mr_review.yml
│   │       └── datarouter.yml
│   ├── prompts/                   # DSPy task files
│   │   ├── mr_code_review.yml
│   │   ├── branch_review.yml
│   │   ├── datarouter_analysis.yml
│   │   └── konflux_repos/
│   ├── child-pipelines/
│   │   ├── devlake.yml
│   │   └── datarouter.yml
│   └── workflows/
│       ├── mr_pipeline.yml
│       ├── scheduled_analysis.yml
│       └── pages_deployment.yml
├── .agents/
│   └── skills/
│       └── gitlab-agent/
│           └── SKILL.md
├── examples/
│   ├── simple_usage.yml
│   ├── simple_usage_vertex.yml
│   ├── advanced_usage.yml
│   ├── branch_review_usage.yml
│   ├── cron_datarouter_daily.yml
│   ├── datarouter_simple_daily.yml
│   ├── datarouter_statistics_check_fix.yml
│   └── dependency_management_example.yml
├── docs/
│   ├── vertex-ai-adc-setup.md
│   └── delegation-eval.md
├── AGENTS.md                      # Agent rules guide
├── CLAUDE.md -> AGENTS.md         # Symlink
├── README.md
├── CHANGELOG.md                   # 781 commits tracked
├── LICENSE                        # Apache 2.0
├── .gitlab-ci.yml
└── .env.example
```

---

## Upstream Documentation

**cicaddy-gitlab** (GitHub):
- [Configuration](https://github.com/redhat-community-ai-tools/cicaddy-gitlab/blob/main/docs/configuration.md)
- [Cron Jobs](https://github.com/redhat-community-ai-tools/cicaddy-gitlab/blob/main/docs/cron-jobs.md)
- [Development](https://github.com/redhat-community-ai-tools/cicaddy-gitlab/blob/main/docs/development.md)
- [Prompt Engineering Best Practices](https://github.com/redhat-community-ai-tools/cicaddy-gitlab/blob/main/docs/prompt-engineering-best-practices.md)
- [Env Files](https://github.com/redhat-community-ai-tools/cicaddy-gitlab/blob/main/docs/env-file-preparation.md)

**cicaddy core** (GitHub):
- [Architecture](https://github.com/waynesun09/cicaddy/blob/main/docs/architecture.md)
- [Sub-Agent Delegation](https://github.com/waynesun09/cicaddy/blob/main/docs/sub-agent-delegation.md)
- [MCP Integration](https://github.com/waynesun09/cicaddy/blob/main/docs/mcp-integration.md)
- [Token-Aware Execution](https://github.com/waynesun09/cicaddy/blob/main/docs/token-aware-execution.md)
- [Metadata Architecture](https://github.com/waynesun09/cicaddy/blob/main/docs/metadata-architecture.md)

---

## Git Workflow

- Sign commits: `git commit -s`
- Check CI status: `glab ci status`
- Tag releases: `git tag -a v<version> -m "<summary>"`

## Release Process

1. Update `CHANGELOG.md`
2. Update version refs in `README.md`
3. Commit and push to main
4. Tag with semantic versioning
5. Push tag: `git push origin v<version>`

---

## Running Locally

```bash
# MR review
uv run --with cicaddy-gitlab cicaddy run --env-file .env.mr

# Scheduled task
uv run --with cicaddy-gitlab cicaddy run --env-file .env.cron

# Dry-run
uv run --with cicaddy-gitlab cicaddy run --env-file .env.mr --dry-run
```

See: [env file guide](https://github.com/redhat-community-ai-tools/cicaddy-gitlab/blob/main/docs/env-file-preparation.md)

---

## Security Features

### 1. Prompt Injection Defense
- Heuristic scanner checks external content
- Modes: audit (log), enforce (block), disabled
- Auto-enabled for agent rules, skills, local tools
- Opt-in for MCP servers

### 2. Masked CI/CD Variables
- All secrets masked in logs
- Base64-encoded service account keys
- Hidden flag (GitLab 17.6+) for additional protection

### 3. Token Scoping
- `GITLAB_TOKEN` requires `api` scope only
- Project/Group access tokens (not personal)
- Unprotected for MR pipelines (security trade-off)

### 4. MCP Tool Filtering
- Whitelist/blacklist tools per server
- Timeout controls (total + idle)
- Scan mode per server

---

## Limitations & Considerations

### 1. Protected Variables Trade-off
- Must disable "Protect variable" for MR pipelines
- Means any user with push access could potentially access secrets
- Mitigations: Masked variables, group-level secrets, Hidden flag

### 2. Delegation Quality Variance
- Triage agent quality varies by model
- Gemini Pro auto: only 2 agents (missed security)
- Claude auto: 5 agents but slowest (173s)

### 3. No Single Perfect Configuration
- Multi-model approach (Claude + Pro none) captures most bugs
- Auto mode adds breadth, single-agent adds depth
- Trade-offs: speed vs coverage vs cost

### 4. Upstream Sync Maintenance
- Internal templates may diverge from upstream
- Manual sync required on new cicaddy-gitlab releases
- Must preserve internal-only changes (SSL, runners, base image)

---

## Future Research Topics

**Red Hat Source Article:** https://source.redhat.com/projects_and_programs/ai/share_ai/building_ai_blog/gitlab_ai_agent_github_actions_for_ai_powered_devops_workflows

**Status:** Requires Red Hat SSO authentication - could not fetch via WebFetch or curl.

**To access:**
1. Authenticate to Red Hat Source via browser
2. Use browser's network inspector to capture authentication cookies
3. Or use internal tool with Red Hat SSO integration

**Expected content:** GitLab AI agent + GitHub Actions integration patterns, AI-powered DevOps workflows.

---

## Summary

**gitlab-agent-task** is a production-ready AI code review system built on the cicaddy framework, tailored for Red Hat's internal GitLab infrastructure. Its delegated sub-agent architecture, multi-provider AI support, and MCP integration make it a comprehensive DevOps AI platform. The empirical delegation evaluation shows trade-offs between single-agent depth and multi-agent breadth, with optimal strategies depending on risk tolerance and time constraints.

**Recommended for:** Teams wanting AI-powered MR reviews with minimal setup, flexible AI provider options, and integration with internal monitoring tools.

**Best practices:**
- Use Vertex AI (no API keys to manage)
- Start with Claude none for balanced coverage
- Add multi-model reviews (Claude + Pro) for high-risk changes
- Enable delegation auto for infrastructure coverage
- Customize sub-agents for domain-specific needs

---

**Research Date:** 2026-06-16  
**Researcher:** Claude Sonnet 4.5  
**Repo Cloned:** /tmp/gitlab-agent-task  
**Total Analysis:** 781 commits, 17 templates, 8 examples, 2 docs, 4 MCP configs
