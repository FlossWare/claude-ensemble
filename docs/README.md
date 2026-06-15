# Multi-AI Systems Documentation

Welcome to the comprehensive documentation for the Multi-AI consensus and automation systems built in claude-global-skills.

## 🎯 What You'll Find Here

This repository contains **56 workflows** implementing advanced AI patterns:
- Multi-AI consensus with worker/arbiter architecture
- Full SDLC automation (development → testing → security → documentation → release)
- Learning systems (code learning, web learning, memory RAG)
- Supporting infrastructure (arbiter rotation, task routing, cost tracking, performance monitoring)

## 🚀 Quick Start

**First time?** Start here:
1. [5-Minute Quick Start](getting-started/quick-start.md) - Run your first consensus workflow
2. [Core Concepts: Multi-AI Consensus](core-concepts/multi-ai-consensus.md) - Understand the worker/arbiter pattern
3. [Workflow Catalog](reference/workflow-catalog.md) - Browse all 56 workflows

## 📚 Documentation Structure

### Getting Started
- [Quick Start Guide](getting-started/quick-start.md) - 5 minutes to your first workflow
- [Installation](getting-started/installation.md) - Setup and dependencies
- [First Workflow Tutorial](getting-started/first-workflow.md) - Step-by-step guide

### Core Concepts
- [Multi-AI Consensus](core-concepts/multi-ai-consensus.md) - Philosophy and benefits of consensus
- [Worker/Arbiter Pattern](core-concepts/arbiter-worker-pattern.md) - Architecture deep dive
- [Model Selection Guide](core-concepts/model-selection.md) - When to use opus/sonnet/haiku/gemini
- [Cost vs Quality Tradeoffs](core-concepts/cost-vs-quality.md) - Budget management

### Consensus Patterns (6 variants)
- [Pattern Overview & Comparison](consensus-patterns/overview.md) - Which pattern for which scenario
- [Basic Consensus](consensus-patterns/basic-consensus.md) - `ai-consensus` (3 workers + arbiter)
- [Hierarchical Consensus](consensus-patterns/hierarchical.md) - Multi-domain with sub-teams
- [Debate Consensus](consensus-patterns/debate.md) - Adversarial testing
- [Weighted Consensus](consensus-patterns/weighted.md) - Confidence-based synthesis
- [Filtered Consensus](consensus-patterns/filtered.md) - Quality threshold filtering
- [Refinement Consensus](consensus-patterns/refinement.md) - Iterative improvement loops

### Supporting Systems
- [Arbiter Rotation](supporting-systems/arbiter-rotation.md) - Preventing bias with rotation
- [Task Routing](supporting-systems/task-routing.md) - Dynamic model selection
- [Cost Tracking](supporting-systems/cost-tracking.md) - Budget enforcement and reporting
- [Performance Monitoring](supporting-systems/performance-monitoring.md) - Quality metrics over time
- [Confidence Calibration](supporting-systems/confidence-calibration.md) - Platt scaling & isotonic regression
- [Uncertainty Analysis](supporting-systems/uncertainty-analysis.md) - Epistemic vs aleatoric uncertainty

### Session Coordination (NEW)
- **[Session Coordination Guide](SESSION-COORDINATION-COMPLETE.md)** - Fleet-wide conflict prevention ⭐
- [Git LFS Locks Complete Guide](git-lfs-locks-guide.md) - Battle-tested file locking
- [Quick Reference Card](git-lfs-locks-quickref.md) - Daily commands cheat sheet
- [Implementation Journey](../projects/-home-sfloess/learnings/session-orchestration-journey-2026-06-13.md) - Multi-AI consensus process

**What it solves:** Prevent conflicting edits across Claude sessions running on multiple machines.

**Solution:** Git LFS locks (fleet consensus choice after multi-AI review)
- Deployed to all 5 fleet nodes (laptop-01, aio-01, server-01/02/03)
- Opt-in per repository (zero impact on existing workflows)
- Prevention, not just detection

**Quick start:**
```bash
# Enable in a repo
git lfs install && git config lfs.locksverify true

# Lock → Edit → Unlock
claude-lock src/file.ts
vim src/file.ts
git commit -am "changes"
claude-unlock src/file.ts
```

### Learning Systems
- [Learning Overview](learning-systems/overview.md) - Four learning systems architecture
- [Code Learning](learning-systems/code-learning.md) - Extract patterns from repos (`ai-web-code-learn`)
- [Web Learning](learning-systems/web-learning.md) - Learn from documentation (`ai-web-learn`)
- [Production RAG](learning-systems/production-rag.md) - ChromaDB + semantic embeddings
- [Memory RAG](learning-systems/memory-rag.md) - Semantic search across memories

### SDLC Workflows (18 workflows)
- [SDLC Suite Overview](sdlc-workflows/overview.md) - Full automation pipeline
- [Development Phase](sdlc-workflows/development.md) - code-review, code-solve
- [Testing Phase](sdlc-workflows/testing.md) - code-test, code-smoke-test
- [PR Review](sdlc-workflows/pr-review.md) - code-pr-review
- [Security Audit](sdlc-workflows/security.md) - code-security
- [Documentation](sdlc-workflows/documentation.md) - code-doc
- [Release Notes](sdlc-workflows/release.md) - code-release-notes
- [Orchestration](sdlc-workflows/orchestration.md) - code-sdlc meta-workflow
- [Continuous Loop](sdlc-workflows/continuous-loop.md) - code-sdlc-auto-continuous

### Autonomous Workflows
- [Autonomous Overview](autonomous-workflows/overview.md) - Auto vs interactive mode
- [Decision Criteria](autonomous-workflows/decision-criteria.md) - Auto-decision thresholds
- [Safety Gates](autonomous-workflows/safety-gates.md) - Breaking change detection
- [Best Practices](autonomous-workflows/best-practices.md) - When to use autonomous mode

### Integration Patterns
- [Solve-Then-Review](integration-patterns/solve-then-review.md) - Multi-AI with different models
- [Multi-AI Chat](integration-patterns/multi-ai-chat.md) - Interactive consensus chat
- [Parallel Execution](integration-patterns/parallel-execution.md) - Concurrent workers
- [Worktree Isolation](integration-patterns/worktree-isolation.md) - Safe parallel testing

### Advanced Topics
- [Model Extensibility](advanced-topics/model-extensibility.md) - Adding Grok/Ollama/OpenAI/Gemini
- [Local Models](advanced-topics/local-models.md) - Ollama integration
- [Schema Design](advanced-topics/schema-design.md) - Structured output patterns
- [Workflow Composition](advanced-topics/workflow-composition.md) - Calling workflows from workflows
- [Error Handling](advanced-topics/error-handling.md) - Graceful degradation

### Reference
- [Workflow Catalog](reference/workflow-catalog.md) - All 30+ workflows with examples
- [API Reference](reference/api-reference.md) - Arguments and return types
- [Configuration](reference/configuration.md) - Config files and environment variables
- [Permissions](reference/permissions.md) - Claude Code permissions setup
- [Troubleshooting](reference/troubleshooting.md) - Common issues and solutions
- [Testing Status](reference/testing-status.md) - What's tested, what's blocked

### Examples
- [Custom Consensus Workflow](examples/custom-consensus.md) - Build your own from scratch
- [Specialized Arbiter](examples/specialized-arbiter.md) - Domain-specific arbiters
- [Hybrid Patterns](examples/hybrid-patterns.md) - Mixing consensus patterns
- [Production Deployment](examples/production-deployment.md) - CI/CD integration

## 📊 Current Status

**Statistics** (as of 2026-06-13):
- **56 workflows** totaling ~15,500 lines of code
- **15 workflows** proven in production (27%)
- **8 workflows** blocked by dependencies (14%)
- **26 workflows** created but untested (46%)
- **13 advanced AI features** implemented: hierarchical consensus, debate, weighted synthesis, filtering, refinement, calibration, uncertainty analysis, task routing, cost tracking, performance monitoring, AST analysis, semantic search, production code learning
- **NEW:** Fleet-wide session coordination with Git LFS locks (deployed to 5 nodes)

**Known Issues**:
- ✅ All previous issues resolved as of commit 8367cc6
- See [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) for details

## 🎓 Learning Paths

### Beginner Path
1. Read [Multi-AI Consensus](core-concepts/multi-ai-consensus.md)
2. Try [Quick Start](getting-started/quick-start.md)
3. Explore [Workflow Catalog](reference/workflow-catalog.md)

### Intermediate Path
1. Study [Worker/Arbiter Pattern](core-concepts/arbiter-worker-pattern.md)
2. Compare [Consensus Patterns](consensus-patterns/overview.md)
3. Try [SDLC Workflows](sdlc-workflows/overview.md)

### Advanced Path
1. Build [Custom Consensus](examples/custom-consensus.md)
2. Integrate [Local Models](advanced-topics/local-models.md)
3. Deploy to [Production CI/CD](examples/production-deployment.md)

## 🤝 Contributing

Found an issue? Want to improve docs?
- Documentation guidelines in each file
- Report issues with specific workflow names
- See individual docs for contributing notes

## 📖 Version History

- **3** (2026-06-13): Session coordination system (Git LFS locks, fleet consensus process)
- **2** (2026-06-10): Complete multi-AI system with 56 workflows
- **1** (2026-06-09): Initial SDLC workflows

---

**Need help?** Start with [Quick Start](getting-started/quick-start.md) or browse the [Workflow Catalog](reference/workflow-catalog.md).
