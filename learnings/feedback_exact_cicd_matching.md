---
name: feedback_exact_cicd_matching
description: CI/CD pipelines must match exactly across FlossWare projects
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f26c00bc-2e0f-4df4-8b1f-d7888af7de1f
---

When user requests CI/CD to be "the same as" another project, they mean exactly identical, including typos and formatting.

**Why:** User asked "do we have the same CI-CD as ../jcollections" and then later "please make the ci-cd process the saeme as ../jcollections1". When I matched the workflow, even the intentional typo "latests depenendencies" (instead of "latest dependencies") was preserved to maintain exact consistency with jcollections.

**How to apply:** 
- When copying CI/CD between FlossWare projects, use exact text matching
- Don't "fix" typos or improve formatting - preserve exactly as-is
- Use `diff` to verify workflows are identical
- Only change repository-specific values (artifact names, SCM URLs)
