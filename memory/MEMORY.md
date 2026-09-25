# Memory Index — Red Hat Work Only

**Personal discoveries:** See `~/.FlossWare/claude/memory/MEMORY.md`

---

## 🔴 CRITICAL RH REQUIREMENTS

- [Always review with multi-AI before marking complete](feedback_always_review.md) — Use fleet consensus for production changes
- [Stop automatically pushing to git](feedback_stop_auto_push.md) — Always ask user before git push operations

---

## Feedback (Red Hat)
- [Always cheapest model](feedback_always_cheapest_model.md) — Default to cheapest capable model (RH: Haiku 4.5), escalate only when needed
- [RH approved models only](feedback_rh_approved_models_only.md) — All RH work uses only Claude/Cursor/Gemini via official (non-personal) API keys
- [Always use worktrees](feedback_always_use_worktrees.md) — Use git worktrees for branch work, keep main repo clean
- [Release fix version scope](feedback_release_fix_version_scope.md) — Only tag Disseminator-related issues, not all resolved CPSEARCH issues
- [Deployment gating timing](feedback_deployment_gating.md) — Manual gates appear after stage completes, not during execution
- [Headroom critical for Red Hat](feedback_headroom_redhat_critical.md) — Token compression critical for RH paid models (Vertex Claude, Cursor, Gemini API) — saves real money
- [MR comments show all phases](feedback_mr_comments_all_phases.md) — Include every phase (Phase 1 + Phase 2 + beyond) with all workers and arbiters, in order
- [Parallel phase launches](feedback_parallel_phase_launches.md) — Launch Phase N+1 for finding X as soon as Phase N completes, don't wait for all Phase N

---

## Project (Red Hat)
- [Disseminator deployment modes](project_disseminator_deployment_modes.md) — starting_at_qa vs only_qa behavior
- [AWX connectivity issues](project_awx_connectivity.md) — NetworkPolicy blocks GitLab pods from AAP
- [Release note email format](project_release_note_format.md) — Bi-weekly R-release announcement format with hyperlinks and Jira integration
- [Team timezones](project_team_timezones.md) — EST: csanders, loleary, grgardne; IST: ypant, rghandi, vmhaskar
- [CPSEARCH-9479 integration diagrams](project_cpsearch_9479.md) — Implement UXE AP-ADR0003: integration architecture diagrams in XE Compass
- [Arbiter-worker pattern](project_mr1087_arbiter_worker_pattern.md) — Two-phase review for MR analysis (Phase 1: 4 workers + Opus 5 arbiter, Phase 2: 4 different workers + GPT-5.4-medium arbiter)

---

## Reference (Red Hat)
- [GitLab API spec.inputs limitation](reference_gitlab_spec_inputs.md) — API variables parameter doesn't populate spec.inputs
- [Sumo Logic indexes](reference_sumologic_indexes.md) — Index names for Solr/Zookeeper (rh_LUCI-003) and Camel nodes (rh_CPAV-001)
- [Sumo Logic API integration](reference_sumologic_integration.md) — Complete integration guide with Python examples, endpoint (api.sumologic.com), cookie handling requirements
- [Catchpoint API integration](reference_catchpoint_integration.md) — Synthetic monitoring data access via REST API with OAuth2 authentication
- [Google APIs integration](reference_google_apis.md) — Token locations (~/.gmail-mcp, ~/.google-docs-api, ~/.config/google-workspace-mcp), refresh procedure, API usage
- [Accomplishments doc updates](reference_accomplishments_doc.md) — How to add entries to Scot's bi-weekly accomplishments Google Doc (doc ID, formatting rules, code examples)
- [Email writing style](reference_email_writing_style.md) — Scot's email tone, structure, phrases, and signature for drafting communications
- [Deployment spreadsheet](reference_deployment_spreadsheet.md) — IR Platform Continuous Delivery sheet tracking every deploy by date/release/version/env
- [Confluence Sumo Logic pages](reference_confluence_sumologic.md) — Page IDs for alerts, dashboards, reports, GitOps docs in DXPIR space
- [Google Service Account setup](reference_google_service_account.md) — How to create, share with Google Sheets, encode for GitLab CI, store in Bitwarden
