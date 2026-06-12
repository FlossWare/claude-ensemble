# Memory Index

## Feedback
- [ALWAYS Multi-AI](feedback_always_multi_ai.md) — **DEFAULT**: Always use multi-AI with maximum coverage (6 models) for ALL decisions. Quality over cost. No exceptions.
- [No Version Management](feedback_no_version_management.md) — Never create git tags; user handles all versioning
- [Workflow parallel() vs pipeline()](feedback_workflow_parallel_vs_pipeline.md) — Correct semantics: parallel() = concurrent (eliminates waits), pipeline() = sequential (adds waits)
- [Arbiter/Worker Multi-Model](feedback_arbiter_worker_multi_model.md) — Always use different AI models (Fable/Opus/Sonnet/Haiku/GPT-4o/Gemini) for workers to get diverse perspectives
- [Multi-Model Strategy Interface](feedback_multi_model_strategy.md) — 9 strategies: QualityFirst, CostOptimized, Balanced, Quantized (Ollama), QuintupleVerification (5-stage)
- [Gemini Arbiter Fallback](feedback_gemini_arbiter_fallback.md) — Configurable arbiter fallback with priority order (default: Fable → Opus → Sonnet)
- [Multi-Model Shorthand](feedback_multi_model_shorthand.md) — User prefers "multi-ai" → apply multi-model arbiter/worker pattern (also: multi-model, a/w, consensus)

## Project
- [Versioning Policy](project_versioning_policy.md) — X.Y format (not X.Y.Z); every main commit is a release candidate
- [Search Engineering Models](project_search_engineering_models.md) — /search-engineering/ directory restricted to 4 models: Gemini, Opus, Sonnet, Haiku only

## Reference
- [Distributed Fleet](reference_distributed_fleet.md) — How to use personal fleet (aio-01, server-01/02/03) with fleet-utils.js; auto-blocks Red Hat work

## Learnings Archive (Read on demand)

Categorized index of 148 learnings files in `../learnings/` directory. Read relevant files when context requires.

### Core Patterns
- arbiter-worker-pattern.md — Multi-AI consensus architecture
- coordinator-pattern.md — Workflow orchestration patterns
- autonomous-workflow-suite.md — Code SDLC automation workflows
- parallel-by-default.md — Use pipeline() not parallel() by default

### Workflow Implementation
- claude-code-workflows.md — Workflow development guidelines
- no-bash-in-workflows.md — Use execSync not Bash tool in workflows
- workflow-meta-first-requirement.md — Always define meta block first
- workflow-imports-lesson.md — Import/export issues in workflows
- workflow-nesting-workaround.md — How to nest workflows via workflow()

### Project Histories (by name)
- project_jcollections.md — File-backed collections library
- project_solenopsis_*.md — Salesforce metadata tools (architecture, metadata)
- project_jnexus_*.md — Nexus artifact management (architecture, state)
- project_virtos_*.md — Virtual OS proof-of-concept (proof, testing)
- project_sfdeasy*.md — Salesforce deployment (resources, test fixes)
- project_jremote_*.md — Remote execution framework (refactoring)
- project_jsecurity.md — Security framework architecture

### CI/CD & Deployment
- reference_cicd_*.md — CI/CD documentation and troubleshooting
- reference_github_*.md — GitHub Actions and CLI usage
- reference_packagecloud.md — Package deployment reference
- feedback_ci_testing.md — CI testing preferences
- gitlab_ci_cache_fix.md — GitLab CI cache configuration

### Code Quality & Reviews
- code_review_may_2026.md — Major code review session learnings
- pr-review-auto-autonomous.md — Autonomous PR review patterns
- pr-impact-analysis.md — Impact analysis in PR reviews
- toctou-race-condition-fix.md — Time-of-check-time-of-use fixes

### Expert Consultations
- expert_diagnosis_*.md — Expert troubleshooting sessions
- expert_feedback_*.md — Expert recommendations
- expert_reference_*.md — Expert reference material

### Session Summaries
- comprehensive_session_may_2026.md — Major comprehensive work session
- session-*.md — Dated session summaries (learning extraction)
- *_complete.md — Project completion summaries
