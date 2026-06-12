---
name: search-engineering-models
description: search-engineering directory must only use 4 specific models (Gemini, Opus, Sonnet, Haiku)
metadata:
  type: project
  originSessionId: 39a38f09-c545-4579-9ac1-6c31a694eba2
---

For any work in `/home/sfloess/Development/redhat/scm/gitlab/search-engineering/` directory and all subdirectories, restrict AI model usage to exactly 4 models:

**Allowed models:**
1. Gemini (Google)
2. Opus (Claude)
3. Sonnet (Claude)
4. Haiku (Claude)

**Excluded models:**
- Fable (do not use)
- GPT-4o (do not use)
- DeepSeek (do not use)
- Grok (do not use)
- Mistral (do not use)
- Any other models (do not use)

**Why:** This is Red Hat work. Only Gemini, Opus, Sonnet, and Haiku are within Red Hat's accepted models list. Fable, GPT-4o, and other models are not approved for Red Hat projects.

**How to apply:**

When working in `/home/sfloess/Development/redhat/scm/gitlab/search-engineering/`:
- Override default maximum-coverage strategy
- Use custom 4-model worker array: `['gemini', 'opus', 'sonnet', 'haiku']`
- Set arbiter fallback: `['opus', 'sonnet', 'haiku', 'gemini']`
- Ignore global "always multi-AI with 6 models" policy for this directory

**Implementation:**

For workflows, detect path and override:
```javascript
const isSearchEngineering = process.cwd().includes('/search-engineering/')
const workers = isSearchEngineering 
  ? ['gemini', 'opus', 'sonnet', 'haiku']
  : ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']  // default
```

For skill invocations, pass explicit model list:
```bash
/code-review --models=gemini,opus,sonnet,haiku
```

**Applies to:**
- All subdirectories: ai-sdlc, disseminator, search-mcp-server, etc.
- All workflows: code-review, code-solve, code-test, etc.
- All multi-AI consensus operations

---

## **Red Hat Compliance Boundary**

**CRITICAL: Infrastructure Restrictions**

Red Hat work must stay on approved infrastructure with strict compliance controls:

**✅ Approved for Red Hat Work:**
- Corporate workstations (this machine for `/home/sfloess/Development/redhat/`)
- Red Hat approved servers and infrastructure
- Corporate network storage
- Company audit/logging systems

**❌ NEVER Use for Red Hat Work:**
- Personal servers (aio-01, server-01, server-02, server-03)
- Raspberry Pis (coordination, monitoring, file watching)
- Personal NFS/shared storage
- Home lab infrastructure
- Unapproved cloud services
- Personal AI infrastructure

**Why:**
- Red Hat compliance requirements (FIPS, data residency, audit trails)
- Corporate security policies
- Approved hardware/infrastructure only
- No data leakage to personal systems

**How to apply:**

**Red Hat Partition** (approved infrastructure only):
```bash
~/Development/redhat/          # Red Hat work - local only
  - No distributed execution
  - No Raspberry Pi coordination
  - Approved models only (Gemini, Opus, Sonnet, Haiku)
  - Stays on this corporate workstation
```

**Personal Partition** (full distributed fleet allowed):
```bash
~/Development/github/          # Personal/FlossWare/Open-source
~/Development/personal/
  - CAN use aio-01, server-01/02/03
  - CAN use Raspberry Pis
  - CAN use all 6 models
  - CAN use distributed workflows
  - Your infrastructure, your rules
```

**Summary:** Keep Red Hat work isolated on approved infrastructure. Distributed fleet (aio-01, servers, Pis) is for personal projects only.
