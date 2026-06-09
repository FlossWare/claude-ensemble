# Memory Index

## Feedback
- [No Version Management](feedback_no_version_management.md) — Never create git tags; user handles all versioning
- [Workflow parallel() vs pipeline()](feedback_workflow_parallel_vs_pipeline.md) — Correct semantics: parallel() = concurrent (eliminates waits), pipeline() = sequential (adds waits)
- [Arbiter/Worker Multi-Model](feedback_arbiter_worker_multi_model.md) — Always use different AI models (Opus/Sonnet/Haiku/GPT-4o/Gemini) for workers to get diverse perspectives
- [Gemini Arbiter Fallback](feedback_gemini_arbiter_fallback.md) — Gemini can be arbiter but must have fallback logic if it fails (select new arbiter from workers and re-run)
- [Multi-Model Shorthand](feedback_multi_model_shorthand.md) — User prefers "multi-ai" → apply multi-model arbiter/worker pattern (also: multi-model, a/w, consensus)

## Project
- [Versioning Policy](project_versioning_policy.md) — X.Y format (not X.Y.Z); every main commit is a release candidate
