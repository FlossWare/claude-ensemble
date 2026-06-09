---
name: feedback-pipeline-monitoring
description: User wants proactive CI/CD pipeline monitoring and diagnosis
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 0cfee593-446f-468f-9568-41f1f8d2a5ad
---

User asked "can u watch the build" after pushing changes to GitLab, expecting proactive monitoring and diagnosis of pipeline status.

**Why:** User wants to know pipeline results without manually checking GitLab UI themselves. When asked to "watch the build", user expects:
1. Automatic detection of pipeline status (running, passed, failed)
2. Diagnosis of what failed if pipeline fails
3. Analysis of whether it's a code issue or environment issue
4. Clear next steps for resolution

User responded "yes" when asked if they wanted me to: check GitLab page, reproduce locally, set up monitoring - indicating they want comprehensive investigation, not just status reporting.

**How to apply:**
- When user says "watch the build" or "monitor the pipeline", use GitLab API to poll pipeline status
- Don't just report status - actively diagnose failures
- Compare local vs CI behavior to identify environment-specific issues
- Create monitoring scripts/tools that user can reuse
- Provide specific troubleshooting steps based on failure type
- If logs require authentication, ask user to check GitLab UI and report specific error
- Set up scheduled monitoring if needed (using CronCreate for recurring checks)
