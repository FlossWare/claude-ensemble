---
name: gemini-not-redhat-supported
description: "Gemini API key is personal/free tier - exclude from officially supported Red Hat models"
metadata:
  type: feedback
  created: 2026-07-24
---

Exclude Gemini (Google AI Studio) from officially supported Red Hat models. The GOOGLE_API_KEY stored in the orchestrator is a personal free-tier key (prefix AIzaSy..., 39 chars, uses generativelanguage.googleapis.com endpoint with FreeTier quotas).

**Why:** Not an enterprise/Red Hat-provided API key. Free tier has strict daily quotas that get exhausted quickly. Enterprise Google Cloud would use Vertex AI endpoints instead.

**How to apply:** When selecting models for Red Hat work or compliance-sensitive tasks, skip Gemini/Google AI. Use it only for personal/experimental work. For fleet multi-model consensus, prefer: Groq (free), OpenRouter free models (Nemotron, etc.), and Cerebras (free).

Related: [[feedback_gemini_arbiter_fallback]]
