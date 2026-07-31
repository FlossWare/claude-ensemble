# Skills Reference - Complete Catalog

**Total Skills:** 104  
**Categories:** AI (27), Code (20), Orchestration (50), Learning (2), Consensus (5)  
**Last Updated:** 2026-07-07

---

## Table of Contents

1. [AI Skills](#ai-skills) - Multi-model consensus, web learning, cost tracking
2. [Code Skills](#code-skills) - Review, testing, documentation, SDLC automation
3. [Orchestration Skills](#orchestration-skills) - Fleet management, distributed execution
4. [Learning Skills](#learning-skills) - Continual learning, monitoring
5. [Consensus Skills](#consensus-skills) - Arbiter rotation, strategy selection
6. [Usage Patterns](#usage-patterns)

---

## AI Skills (27)

### Consensus & Decision Making

#### ai-consensus
**Purpose:** Multi-model consensus for any task  
**Pattern:** 3-6 worker models + arbiter synthesis  
**Usage:**
```javascript
import aiConsensus from './skills/ai/ai-consensus.js';
const result = await aiConsensus({ task: 'Analyze this code for bugs' });
```

#### ai-consensus-weighted
**Purpose:** Weighted consensus based on model confidence  
**Pattern:** Weighted average instead of simple majority  
**Best for:** When some models are more reliable for specific tasks

#### ai-consensus-hierarchical
**Purpose:** Hierarchical consensus with specialized sub-teams  
**Pattern:** Team leaders → sub-team workers → final synthesis  
**Best for:** Complex multi-domain problems

#### ai-consensus-debate
**Purpose:** Adversarial debate between models  
**Pattern:** Propose → exchange critiques → refine → synthesize  
**Best for:** Finding edge cases, challenging assumptions

#### ai-consensus-filtered
**Purpose:** Confidence-filtered consensus  
**Pattern:** Only synthesize responses above confidence threshold  
**Best for:** High-stakes decisions requiring certainty

#### ai-consensus-refinement
**Purpose:** Self-correcting iterative consensus  
**Pattern:** Generate → critique → refine → repeat until convergence  
**Best for:** Improving answer quality through iteration

#### ai-consensus-disagreement
**Purpose:** Analyze model disagreement patterns  
**Pattern:** Track where/why models disagree  
**Best for:** Understanding consensus robustness

### Web Learning

#### ai-web-learn
**Purpose:** Learn from web pages  
**Pattern:** Fetch → extract facts → store embeddings  
**Storage:** PostgreSQL + pgvector

#### ai-web-learn-production
**Purpose:** Production web learning pipeline  
**Pattern:** PostgreSQL + pgvector semantic embeddings  
**Storage:** PostgreSQL + pgvector

#### ai-web-learn-universal-ai
**Purpose:** Web learning using Universal AI RAG  
**Pattern:** PostgreSQL + pgvector + advanced retrieval  
**Best for:** Production-grade knowledge accumulation

#### ai-web-learn-mcp
**Purpose:** Advanced web learning with MCP tool discovery  
**Pattern:** Auto-discovers MCP tools + real embeddings  
**Best for:** Dynamic tool-based web scraping

#### ai-web-code-learn
**Purpose:** Learn from source code repositories  
**Pattern:** Fetch repos → extract patterns → store learnings  
**Storage:** PostgreSQL learning.experiences

#### ai-web-code-learn-production
**Purpose:** Production code learning pipeline  
**Pattern:** Source code analysis with embeddings + graph storage  
**Storage:** PostgreSQL + OrientDB graph

### Research & Analysis

#### ai-pdf-deep-research
**Purpose:** Adversarial verification of PDF content  
**Pattern:** Extract claims → 3-vote refutation → synthesize  
**Best for:** Academic papers, fact-checking documents

#### ai-uncertainty-analysis
**Purpose:** Uncertainty quantification  
**Pattern:** Epistemic (model disagreement) vs aleatoric (inherent randomness)  
**Best for:** Understanding confidence bounds

### Monitoring & Optimization

#### ai-performance-monitor
**Purpose:** Track model performance over time  
**Pattern:** Log accuracy, latency, cost → dashboards  
**Storage:** PostgreSQL monitoring.execution_summary

#### ai-cost-tracker
**Purpose:** Track token usage and enforce budgets  
**Pattern:** Per-agent cost tracking with budget alerts  
**Storage:** PostgreSQL costs.entries

#### ai-confidence-calibration
**Purpose:** Calibrate model confidence scores  
**Pattern:** Track reported vs actual confidence → adjust  
**Best for:** Improving confidence reliability

#### ai-reaction-tracker
**Purpose:** Track AI behavioral reactions during execution  
**Pattern:** Monitor decision patterns, failure modes  
**Best for:** Understanding model behavior

### Routing & Task Management

#### ai-task-router
**Purpose:** Dynamic task routing to optimal models  
**Pattern:** Task analysis → model selection → execution  
**Uses:** Model-capability-matrix.cjs for scoring

#### ai-prompt
**Purpose:** Simple multi-model consensus prompt  
**Pattern:** Quick consensus wrapper for one-off questions  
**Best for:** Simple Q&A without complex setup

#### ai-extract-learning
**Purpose:** Extract learnings from workflow execution  
**Pattern:** Analyze results → extract patterns → store  
**Storage:** PostgreSQL learning.experiences

#### ai-chat
**Purpose:** Interactive multi-AI chat session  
**Pattern:** Stays active until exit, maintains context  
**Best for:** Exploratory conversations

#### ai-cross-validation
**Purpose:** Cross-validation framework for evaluations  
**Pattern:** K-fold validation of model performance  
**Best for:** Benchmarking model accuracy

---

## Code Skills (20)

### Code Review

#### code-review
**Purpose:** Find issues via multi-AI code review  
**Pattern:** Multi-model review → impact analysis → report  
**Interactive:** Prompts before creating issues

#### code-review-auto
**Purpose:** Autonomous brutal code review  
**Pattern:** Auto-creates issues for all findings  
**Best for:** CI/CD pipelines, automated quality gates

### Testing

#### code-test
**Purpose:** Comprehensive application testing  
**Pattern:** Build → unit → integration → smoke → report  
**Interactive:** Prompts before running tests

#### code-test-auto
**Purpose:** Autonomous testing bot  
**Pattern:** Auto-creates issues for all test failures  
**Best for:** Continuous testing, regression detection

#### code-smoke-test
**Purpose:** Auto-detect project type and run smoke tests  
**Pattern:** Detect (npm/python/go/rust) → run basic tests  
**Best for:** Quick sanity checks

### Documentation

#### code-doc
**Purpose:** Interactive documentation generation  
**Pattern:** Analyze code → generate docs → prompt for approval  
**Outputs:** README.md, API docs, inline comments

#### code-doc-auto
**Purpose:** Autonomous documentation generation  
**Pattern:** Auto-creates documentation without prompts  
**Best for:** CI/CD documentation updates

### Security

#### code-security
**Purpose:** Interactive security audit  
**Pattern:** Multi-AI security analysis → prompt before creating issues  
**Checks:** SQL injection, XSS, auth issues, secrets

#### code-security-auto
**Purpose:** Autonomous security audit  
**Pattern:** Auto-creates issues for verified vulnerabilities  
**Best for:** Security-first CI/CD

### Issue Resolution

#### code-solve
**Purpose:** Resolve GitHub/GitLab issues  
**Pattern:** Multi-AI consensus → implement fix → verify  
**Interactive:** Prompts for approval before committing

#### code-solve-auto
**Purpose:** Autonomous issue solver  
**Pattern:** Auto-resolves all open issues without prompts  
**Best for:** Automated maintenance

### SDLC Automation

#### code-sdlc
**Purpose:** Complete SDLC automation  
**Pattern:** Development → testing → review → release  
**Interactive:** Prompts at each phase

#### code-sdlc-auto
**Purpose:** Autonomous SDLC automation  
**Pattern:** Runs entire pipeline end-to-end  
**Best for:** Fully automated delivery

#### code-sdlc-auto-continuous
**Purpose:** Continuous SDLC loop  
**Pattern:** Runs code-sdlc-auto until codebase is clean  
**Best for:** Autonomous code quality improvement

### Pull Requests

#### code-pr-review
**Purpose:** Interactive PR review with multi-AI consensus  
**Pattern:** Review → comment → approve/reject  
**Interactive:** Prompts before posting comments

#### code-pr-review-auto
**Purpose:** Autonomous PR review bot  
**Pattern:** Auto-approves/rejects PRs  
**Best for:** Automated PR gating

### Release Management

#### code-release-notes
**Purpose:** Generate release notes from commits  
**Pattern:** Multi-AI categorization → changelog  
**Interactive:** Prompts before publishing

#### code-release-notes-auto
**Purpose:** Autonomous release notes generation  
**Pattern:** Auto-publishes release notes  
**Best for:** Automated releases

### Code Analysis

#### code-ast-analysis
**Purpose:** Parse code structure via AST  
**Pattern:** Tree-sitter or regex fallback → extract functions/classes  
**Outputs:** Detailed code structure metadata

#### code-semantic-search
**Purpose:** Standalone code embedding and search  
**Pattern:** Embed codebase → semantic similarity search  
**Storage:** PostgreSQL + pgvector

---

## Orchestration Skills (50)

### Fleet Management

#### distributed-orchestrator
**Purpose:** Core distributed fleet orchestration  
**Pattern:** SSH distribution across 8 worker nodes  
**Used by:** All multi-worker workflows

#### distributed-orchestrator-graceful-degradation
**Purpose:** Orchestrator with failure handling  
**Pattern:** Worker failures → auto-reassignment → continue  
**Best for:** Production reliability

#### fleet-agent-dispatcher
**Purpose:** Dispatch agents to fleet workers  
**Pattern:** Task → select worker → SSH execute → collect  
**Used by:** Fleet-based workflows

#### fleet-agent-wrapper
**Purpose:** Wrap agent execution with fleet context  
**Pattern:** Add fleet metadata, logging, error handling  

#### fleet-remote-executor
**Purpose:** Execute commands on remote fleet nodes  
**Pattern:** SSH + result streaming + timeout handling  

#### fleet-utils
**Purpose:** Shared fleet utilities  
**Functions:** Node selection, health checks, load balancing

#### fleet-work-reassignment
**Purpose:** Reassign work when workers fail  
**Pattern:** Detect failure → find healthy worker → retry

#### fleet-telemetry-minimal
**Purpose:** Minimal telemetry for fleet operations  
**Pattern:** Log worker stats without overhead

### Consensus Infrastructure

#### consensus-strategies
**Purpose:** Strategy selection for consensus workflows  
**Pattern:** Thompson Sampling bandit → select best strategy  

#### multi-ai-consensus
**Purpose:** Generic multi-AI consensus wrapper  
**Pattern:** Configurable workers + arbiter + synthesis

#### get-next-arbiter
**Purpose:** Arbiter rotation with task-aware selection  
**Pattern:** Task type → model-capability-matrix → select arbiter  
**Updated:** 2026-07-07 (now uses 445+ models across 21 providers, not 6)

#### update-arbiter-state
**Purpose:** Update arbiter rotation state  
**Pattern:** Track last arbiter → rotate → persist state

### Learning Infrastructure

#### continual-learning-monitor
**Purpose:** Monitor continual learning system  
**Pattern:** Track bandit state, model distribution, alerts

#### background-learner
**Purpose:** Background learning from workflow executions  
**Pattern:** Extract patterns → store → improve routing

#### claude-learning-integration
**Purpose:** Integrate Claude-specific learning hooks  
**Pattern:** Hook into Claude Code workflow completion

#### workflow-cleanup
**Purpose:** Clean up completed workflow artifacts  
**Pattern:** Archive old workflows → free disk space

### Workflow Tools

#### add-workflow-logging
**Purpose:** Add logging to workflow execution  
**Pattern:** Inject logging hooks → track progress

#### workflow-status
**Purpose:** Check workflow execution status  
**Pattern:** Query PostgreSQL → return current state

#### validation-workflow-example
**Purpose:** Example workflow with validation  
**Pattern:** Template for validation-first workflows

#### validation-workflow-wrapper
**Purpose:** Wrap workflows with validation logic  
**Pattern:** Pre-validate inputs → execute → post-validate

### Testing & Validation

#### test-fleet-dynamic-import
**Purpose:** Test dynamic import of fleet modules  
**Pattern:** Verify ES modules load correctly

#### test-hardcoded-models
**Purpose:** Test for hardcoded model references  
**Pattern:** Scan code → flag hardcoded models

#### test-ssh-distribution
**Purpose:** Test SSH distribution to workers  
**Pattern:** Verify connectivity, permissions, execution

#### test-ssh-distribution-advanced
**Purpose:** Advanced SSH distribution tests  
**Pattern:** Test parallel execution, error handling

#### test-phase3-remote-execution
**Purpose:** Test phase 3 remote execution  
**Pattern:** Verify multi-phase distributed workflows

#### test-openclaw-degradation
**Purpose:** Test OpenClaw degradation handling  
**Pattern:** Simulate failures → verify recovery

#### test-openclaw
**Purpose:** Test OpenClaw integration  
**Pattern:** Verify OpenClaw API compatibility

#### test-security-curl-auth
**Purpose:** Test curl authentication  
**Pattern:** Verify auth headers, tokens

#### validation-test
**Purpose:** Generic validation test framework  
**Pattern:** Schema validation, type checking

#### arbiter-rotation.test
**Purpose:** Test arbiter rotation logic  
**Pattern:** Verify rotation sequence, state persistence

#### consensus-strategies.test
**Purpose:** Test consensus strategy selection  
**Pattern:** Verify Thompson Sampling selection

#### consensus-strategies-routing-verification.test
**Purpose:** Verify routing uses consensus strategies  
**Pattern:** End-to-end routing verification

#### fleet-agent-dispatcher.test
**Purpose:** Test fleet agent dispatching  
**Pattern:** Verify task distribution, result collection

#### fleet-remote-executor.test
**Purpose:** Test remote execution  
**Pattern:** Verify SSH commands, result streaming

#### load-multi-ai-config.test
**Purpose:** Test multi-AI config loading  
**Pattern:** Verify config parsing, validation

#### edge-case-tests
**Purpose:** Test edge cases across all systems  
**Pattern:** Boundary conditions, error states

#### hardcoded-thresholds.test
**Purpose:** Test for hardcoded thresholds  
**Pattern:** Flag magic numbers, suggest config

#### issue-98-regression-test
**Purpose:** Regression test for issue #98  
**Pattern:** Prevent specific bug from returning

#### test-issue-97-indexOf-regression
**Purpose:** Regression test for indexOf bug  
**Pattern:** Verify array operations work correctly

#### github-issue-integration.test
**Purpose:** Test GitHub issue integration  
**Pattern:** Verify issue creation, comments, closure

#### recovery-chain-utils.test
**Purpose:** Test recovery chain utilities  
**Pattern:** Verify error recovery, retry logic

### Utilities

#### load-multi-ai-config
**Purpose:** Load multi-AI configuration  
**Pattern:** Parse JSON/YAML → validate → return config

#### enable-local-models
**Purpose:** Enable local model execution  
**Pattern:** Detect local models → configure paths  
**Status:** DEPRECATED/ARCHIVED - Local models removed since 2026-06-28 (API-only fleet)

#### detect-local-models
**Purpose:** Detect available local models  
**Pattern:** Scan system → return model list  
**Status:** DEPRECATED/ARCHIVED - Local models removed since 2026-06-28 (API-only fleet)

#### memory-rag-index
**Purpose:** Index memory files for RAG  
**Pattern:** Chunk → embed → store in vector DB

#### memory-rag-search
**Purpose:** Search memory via RAG  
**Pattern:** Query → semantic search → return results

#### recovery-chain-utils
**Purpose:** Error recovery utilities  
**Pattern:** Retry logic, fallback chains, circuit breakers

#### work-distribution
**Purpose:** Distribute work across workers  
**Pattern:** Load balancing, priority queuing

#### doc-review
**Purpose:** Review documentation for completeness  
**Pattern:** Multi-AI doc review → suggest improvements

#### doc-review-auto
**Purpose:** Autonomous doc review  
**Pattern:** Auto-creates issues for doc gaps

#### orchestrator-brain
**Purpose:** Central orchestration decision engine  
**Pattern:** Routing decisions, worker selection, optimization

#### orchestrator
**Purpose:** Main orchestrator entry point  
**Pattern:** Unified API for all orchestration functions

#### example-active-learning
**Purpose:** Example of active learning pattern  
**Pattern:** Uncertain cases → query oracle → learn

#### examples-agent-execute
**Purpose:** Example agent execution patterns  
**Pattern:** Various agent usage examples

#### model-optimization
**Purpose:** Model performance optimization  
**Pattern:** Profile → identify bottlenecks → optimize

#### index
**Purpose:** Skills index/registry  
**Pattern:** Central export point for all skills

---

## Learning Skills (2)

#### continual-learning-monitor
**Purpose:** Monitor continual learning system health  
**Pattern:** Track bandit state, model diversity, feedback loops  
**Alerts:** Model dominance, reward hacking, concept collapse

#### workflow-cleanup
**Purpose:** Clean up old workflow data  
**Pattern:** Archive completed workflows, free disk space  
**Retention:** Configurable (default: 90 days)

---

## Consensus Skills (5)

#### get-next-arbiter
**Purpose:** Select next arbiter with task-aware routing  
**Pattern:** Task type → capability matrix → select best arbiter  
**Models:** 445+ free models across 21 providers (updated 2026-07-07)

#### update-arbiter-state
**Purpose:** Update arbiter rotation state  
**Pattern:** Track last arbiter → rotate → persist to database

#### consensus-strategies
**Purpose:** Manage consensus strategies  
**Pattern:** Thompson Sampling for strategy selection  
**Storage:** PostgreSQL learning.strategy_performance

#### multi-ai-consensus
**Purpose:** Generic multi-model consensus  
**Pattern:** Configurable workers/arbiter/synthesis

#### arbiter-rotation.test
**Purpose:** Test arbiter rotation logic  
**Pattern:** Verify rotation correctness, state management

---

## Usage Patterns

### Basic Consensus

```javascript
import aiConsensus from './skills/ai/ai-consensus.js';

const result = await aiConsensus({
  task: 'Should we use REST or GraphQL?',
  workers: 6
});

console.log(result.consensus);
console.log(`Confidence: ${result.confidence}`);
```

### Code Review Automation

```javascript
import codeReview from './skills/code/code-review.js';

const issues = await codeReview({
  files: ['src/**/*.js'],
  severity: 'medium',
  autofix: false
});

console.log(`Found ${issues.length} issues`);
```

### Fleet Distribution

```javascript
import { distributedOrchestrator } from './skills/misc/distributed-orchestrator.js';

const result = await distributedOrchestrator({
  task: 'Analyze 1000 files',
  workers: 8,
  strategy: 'parallel'
});
```

### Web Learning

```javascript
import webLearn from './skills/ai/ai-web-learn-production.js';

await webLearn({
  url: 'https://example.com/article',
  store: true,
  embeddings: true
});
```

### Security Audit

```javascript
import codeSecurity from './skills/code/code-security-auto.js';

const vulnerabilities = await codeSecurity({
  autofix: true,
  severity: 'high'
});
```

---

## Skill Categories Summary

| Category | Count | Purpose |
|----------|-------|---------|
| **AI Skills** | 27 | Consensus, learning, research, monitoring |
| **Code Skills** | 20 | Review, testing, docs, security, SDLC |
| **Orchestration** | 50 | Fleet management, distribution, testing |
| **Learning** | 2 | Continual learning, monitoring |
| **Consensus** | 5 | Arbiter rotation, strategy selection |
| **TOTAL** | 104 | Complete skill ecosystem |

---

## Integration Notes

**For Claude Code:**
- Skills are invoked via `Skill` tool
- Format: `/skill-name args`
- Example: `/ai-consensus "Analyze this code"`

**For other AI systems:**
- Import as ES modules
- Call as async functions
- Return structured results

**For orchestrator API:**
- Skills available via `/api/fleet/execute`
- Pass skill name + args as JSON
- Distributed execution automatic

---

**Last Updated:** 2026-07-07  
**Maintained by:** Orchestrator Development Team
