name: pdf-research-Kubernetes-best-practices
description: Adversarial verification of PDF content for: Kubernetes best practices
metadata:
  node_type: memory
  type: research
  pdfs_count: 1
  claims_extracted: 0
  claims_verified: 0
  claims_killed: 0
  models_used: fable, opus, sonnet, haiku, gpt-4o, gemini
  verification_votes: 3
  refute_threshold: 2
---

# PDF Research: Kubernetes best practices

**PDFs:** Kubernetes Best Practices.pdf
**Models:** fable, opus, sonnet, haiku, gpt-4o, gemini
**Verification:** 3-vote adversarial, 2/3 threshold
**Arbiters:** Extraction=fable, Verification=opus, Synthesis=sonnet

## Summary

No claims survived adversarial verification.

## Verified Findings

## Methodology

- **Worker models:** fable, opus, sonnet, haiku, gpt-4o, gemini
- **Extraction arbiter:** fable
- **Verification arbiter:** opus
- **Synthesis arbiter:** sonnet
- **Adversarial protocol:** 3 voters per claim, 2/3 refutations to kill
- **Challenger exclusion:** Proposing models excluded from voting on their own claims
- **Max claims verified:** 25 (ranked by importance then confidence)
