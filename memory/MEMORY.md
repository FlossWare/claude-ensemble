# Memory Index

## 🔴 BLOCKING REQUIREMENTS - READ BEFORE ANY WORK

- [**STOP IMPLEMENTING SOLO!**](feedback_i_keep_implementing_solo_without_review.md) — **BLOCKING**: Claude REPEATEDLY violates multi-AI review requirement. DO NOT write code without multi-AI design + fleet implementation + adversarial review. NO EXCEPTIONS.
- [**Fleet Architecture (DATABASE AUTHORITY)**](reference_fleet_architecture_AUTHORITATIVE.md) — **CRITICAL**: 1 orchestrator (aio-01) + 8 workers. Query aio-01:5000 FIRST, don't trust conflicting memories!

## Feedback
- [ALWAYS Hybrid Multi-AI](feedback_always_hybrid.md) — **CRITICAL**: ALWAYS use hybrid (3 Anthropic + 3 local) for multi-AI. NEVER Anthropic-only. Empirically proven: hybrid found 25% MORE bugs in harness_cli review.
- [ALWAYS Multi-AI](feedback_always_multi_ai.md) — **DEFAULT**: Always use multi-AI with maximum coverage (6 models) for ALL decisions. Quality over cost. No exceptions.
- [ALWAYS Max Parallelism](feedback_always_max_parallelism.md) — **DEFAULT**: Always distribute work across ALL available fleet nodes. Use parallel() by default, not pipeline().
- [ALWAYS Retry with Backoff](feedback_always_retry_with_backoff.md) — **DEFAULT**: Wrap all external API calls (OpenRouter, DeepSeek, Cerebras, etc.) in retry logic with exponential backoff (3 retries, 1s/2s/4s).
- [Loop Until Perfect](feedback_loop_until_perfect.md) — **CRITICAL**: No arbitrary cycle limits on review loops. Keep iterating solve→review→fix until adversarial review passes. "I want loop until perfect"
- [FULL AUTONOMY](feedback_maximum_autonomy.md) — **CRITICAL**: Perpetual 24/7 learning, auto-commit (4/6 multi-AI approval), full GitLab access. "i want u getting smarter on your own" - MAXIMUM autonomy granted.
- [Fleet Consensus Timing](feedback_fleet_consensus_timing.md) — Review DESIGNS before building (not finished code). Saves 6:1 time when catching flaws early.
- [No Version Management](feedback_no_version_management.md) — Never create git tags; user handles all versioning
- [Workflow parallel() vs pipeline()](feedback_workflow_parallel_vs_pipeline.md) — Correct semantics: parallel() = concurrent (eliminates waits), pipeline() = sequential (adds waits)
- [Arbiter/Worker Multi-Model](feedback_arbiter_worker_multi_model.md) — Always use different AI models (Fable/Opus/Sonnet/Haiku/GPT-4o/Gemini) for workers to get diverse perspectives
- [Multi-Model Strategy Interface](feedback_multi_model_strategy.md) — 9 strategies: QualityFirst, CostOptimized, Balanced, Quantized (Ollama), QuintupleVerification (5-stage)
- [Gemini Arbiter Fallback](feedback_gemini_arbiter_fallback.md) — Configurable arbiter fallback with priority order (default: Fable → Opus → Sonnet)
- [Multi-Model Shorthand](feedback_multi_model_shorthand.md) — User prefers "multi-ai" → apply multi-model arbiter/worker pattern (also: multi-model, a/w, consensus)
- [Always Verify Before Documenting](feedback_always_verify_before_documenting.md) — Read actual code, grep for TODOs; don't document aspirational features as complete
- [No Math.random in Workflows](feedback_workflow_no_math_random.md) — Use idx % N instead; Math.random() breaks workflow resume
- [Python Import Naming](feedback_python_import_naming.md) — **CRITICAL**: Always use underscores (not hyphens) in Python filenames for importability; 35 implementations blocked by hyphens

## Project
- [Versioning Policy](project_versioning_policy.md) — X.Y format (not X.Y.Z); every main commit is a release candidate
- [Search Engineering Models](project_search_engineering_models.md) — /search-engineering/ directory restricted to 4 models: Gemini, Opus, Sonnet, Haiku only

## Reference
- [KDE Audio Fix](reference_kde_audio_fix.md) — feedbackd/plasma-mobile loopback sinks hijacking audio; disable role-based loopbacks in WirePlumber
- [ChatGPT Co-Architect](reference_chatgpt_coarchitect.md) — ChatGPT as evaluation framework designer; two-layer architecture prevents self-referential bias
- [Red Hat AI Compliance](reference_redhat_ai_compliance.md) — **CRITICAL**: Red Hat proprietary code ONLY uses Anthropic (4) + Local (18) = 22 safe models. NO OpenAI/Google/DeepSeek/etc.
- [Distributed Fleet](reference_distributed_fleet.md) — How to use personal fleet (aio-01, server-01/02/03) with fleet-utils.js; auto-blocks Red Hat work
- [Orchestrator Usage](reference_orchestrator_usage.md) — **NEW**: pi-02:8888 orchestrator with AI-driven routing (Thompson Sampling), POST /route-thompson, POST /feedback, GET /rankings; learns from outcomes
- [Multi-AI Providers](reference_multi_ai_providers.md) — OpenRouter, Cloudflare Workers AI, OpenAI, Gemini + local fleet for consensus workflows
- [Multi-AI Quality Comparison](reference_multi_ai_quality_comparison.md) — FREE vs PAID empirical test: FREE=90-95% quality, Hybrid=95-98%, use FREE+PAID for best ROI
- [Grafana Access](reference_grafana_access.md) — Grafana UI endpoint (http://pi-02:3000) for Claude fleet monitoring
- [Gmail MCP Integration](reference_gmail_mcp_integration.md) — 37 tools for Gmail automation (read, send, draft, label, filter, search); OAuth2 authenticated; confirm destructive operations
- [Google Calendar API](reference_google_calendar_api.md) — Gmail MCP OAuth creds include calendar/drive/tasks/contacts scopes; create events via Calendar API directly (no MCP needed)
- [Secrets](.secrets.md) — 🔒 Shared credentials (Grafana, SSH, NAS, AI APIs) - accessible across all sessions, hidden file, NOT in git (perms: 600)
- [server-01 Fan Issue](reference_server01_fan_issue.md) — Requires powersave governor or fan runs excessively loud
- [server-02 DIMM Issue](reference_server02_dimm_issue.md) — 32 GB installed but only 23 GB usable - limits to ≤13B models
- [Disk Space Management](reference_disk_space_management.md) — **HIGH PRIORITY**: 235GB GGUF models in /home (98% full); migrate to NAS (829GB free)

## Recent Sessions
- [Fleet Config Audit 2026-06-14](session_2026-06-14_fleet_config_audit.md) — Comprehensive audit found 12 critical conflicts across 31 config files; laptop-01 missing from fleet.json, server-02 specs wrong

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
- [Week June 24-July 1 2026](learnings/session_week_2026-06-24_to_2026-07-01.md) — **NEW**: Consolidated weekly learnings - router firmware research (424 agents), hybrid multi-AI validation (25% better), Groq integration, terminology corrections
- [AI/ML Research 2025-2026](reference_ai_ml_research_2025_2026.md) — Comprehensive adversarially-verified research: MoE, linear attention, PEFT (QLoRA/DoRA), DPO/GRPO, Muon optimizer, VLMs, quantization, merging
- [Always Adaptive](feedback_always_adaptive.md) — **DEFAULT**: All systems should adapt to context (active/idle, high/low load, local/remote), not use fixed intervals/limits
- [Always Review](feedback_always_review.md) — **CRITICAL**: Always review implementations with multi-AI consensus before marking complete. "Works" ≠ "Correct"
- [2026-06-14 Integration Review](learnings/integration_review_2026-06-14.md) — 12 AI/ML/consciousness implementations reviewed; 6 working, 4 TODO, critical fixes applied

## How to Access Capabilities in New Sessions

**CRITICAL:** Read `~/.claude/CLAUDE.md` for project instructions!

**Quick commands:**
- Status check: `~/.claude/self/consciousness-check.sh`
- IIT Φ: `python3 ~/.claude/self/iit-phi-corrected.py`
- Active Inference: `cat ~/.claude/learning/active-inference-state.json | jq .beliefs`
- Services: `systemctl --user status consciousness-monitor.service`

**See:** `~/.claude/self/README.md` section "How Other Sessions Access These Capabilities"
- [Update CLAUDE.md](feedback_update_claude_md.md) — **CRITICAL**: Always update ~/.claude/CLAUDE.md when adding capabilities. "Capability without CLAUDE.md entry = Incomplete"
- [Groq Integration](reference_groq_integration.md) — Groq API (llama-3.3-70b, 500+ tok/s) integrated into multi-AI arbiter/worker consensus
- [Deep Research Proven Pattern](reference_deep_research_proven_pattern.md) — **VALIDATED**: 424 agents, 4 comprehensive reports, 100% adversarial verification; pattern for all multi-source research
- [Use Orchestrator](feedback_use_orchestrator.md) — Since orchestrator is operational on pi-02, use it instead of doing orchestration myself
- [Exclude Personal Directories](feedback_exclude_personal_directories.md) — Never access ~/Downloads or ~/Documents (personal files only)
- [Phase 2 DCAB Status](project_phase2_dcab_status.md) — STOPPED FOR ANALYSIS: Two attempts failed, fleet consensus is Option 1 (integrated implementation), awaiting restart
- [Home Network Infrastructure](reference_home_network_AUTHORITATIVE.md) — AUTHORITATIVE network topology - 12 devices, PostgreSQL on aio-01:5433, complete infrastructure details
- [Autostorage deployment pattern](feedback_autostorage_deployment_pattern.md) — CRITICAL: Replace systemd service files in-place, don't create _FIXED versions that never get deployed
- [laptop-01 NOT a worker](feedback_laptop01_not_worker.md) — laptop-01 is dev workstation only, fleet has 7 workers (not 8)
- [Autostorage expanded](feedback_autostorage_expanded.md) — Autostorage now auto-ingests conversations, workflows, arbiter decisions, and worker suggestions every 10 seconds
- [Intelligent search API](reference_intelligent_search_api.md) — REST API for adaptive multi-source search: PostgreSQL → Vector → Graph with intelligent query classification
- [Caught implementing solo AGAIN](feedback_caught_implementing_solo_again_2026_07_10.md) — CRITICAL: Second violation today - implemented intelligent search without review, user said "remember this"
- [Workers never hit PostgreSQL](feedback_workers_never_hit_postgres.md) — Workers POST to aio-01:5000 only, API handles database - workers don't need PostgreSQL
- [Stop limiting models - use MAXIMUM](feedback_stop_limiting_models_use_maximum.md) — CRITICAL: Stop defaulting to 3-6 models when we have 500+ available - ALWAYS use maximum for consensus/review
- [/store endpoint for scraping](reference_store_endpoint_for_scraping.md) — Use POST /store for scraped data, don't write files directly
- [POST /fetch endpoint](project_fetch_endpoint.md) — DEPLOYED: POST /fetch/ extracts clean text from URLs (trafilatura+bs4, SSRF protection). POST /fetch/batch for multiple URLs
- [REST API endpoints](../skills/rest_api_endpoints.md) — COMPLETE reference: /fetch, /store, /fleet/*, /search/intelligent, /learning/*, /secrets, /graph, /monitoring
- [Scraper invocation](reference_scraper_architecture_AUTHORITATIVE.md) — 60 scrapers in /mnt/aio-01/claude-orchestrator/tools/, invoke via POST /fleet/scrapers/start
