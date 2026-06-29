#!/usr/bin/env node
export const meta = {
  name: 'close-issues-and-push',
  description: 'Close completed GitLab issues and push all changes to remote',
  phases: [
    { title: 'Review Completed Work', detail: 'Identify what issues can be closed' },
    { title: 'Commit Changes', detail: 'Commit new providers and updates' },
    { title: 'Close Issues', detail: 'Close completed GitLab issues' },
    { title: 'Push Remote', detail: 'Push everything to GitLab' }
  ]
};

phase('Review Completed Work');

const review = await agent(`Review completed work and identify closable issues:

Check git status to see what changed since last commit:
- New API providers added (DeepSeek, Cerebras, OpenRouter, Cloudflare)
- Updated fleet-utils.js with 4 new providers
- Tested and verified error handling
- All credentials distributed

List GitLab issues with 'gl issue list' and identify which are complete:
- Distribution issues (workers now execute)
- API provider issues (4 new providers added)
- Error handling issues (verified working)

Return JSON:
{
  "files_changed": [],
  "issues_to_close": [],
  "commit_message": "..."
}`,
{ label: 'Review completed work', model: 'sonnet', effort: 'medium' });

log('Review complete');

phase('Commit Changes');

const commit = await agent(`Commit recent changes:

1. Check git status
2. Stage relevant files:
   - shared/fleet-utils.js (4 new providers)
   - Any updated scripts
   - New documentation if any

3. Create commit:
   "feat: Add 4 new API providers (DeepSeek, Cerebras, OpenRouter, Cloudflare)

   - Add DeepSeek support (deepseek-chat, deepseek-coder)
   - Add Cerebras support (llama-3.3-70b, zai-glm-4.7) - VERY FAST (183ms)
   - Add OpenRouter support (meta-llama/llama-3.3-70b-instruct)
   - Add Cloudflare Workers AI support
   - Update mapModelToProvider with new model mappings
   - Distribute credentials to all 8 workers
   - Verify error handling (backoff, circuit breaker, jitter)

   Working APIs: Groq, Cerebras, Google, Cohere (6 total)
   Needs funding: DeepSeek, OpenRouter

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

Return JSON:
{
  "committed": true/false,
  "commit_hash": "...",
  "files_committed": []
}`,
{ label: 'Commit changes', model: 'opus', effort: 'high' });

log('Changes committed');

phase('Close Issues');

const closeIssues = await agent(`Close completed GitLab issues:

Use 'gl issue list' to see open issues, then close relevant ones:

Close issues related to:
1. Fleet distribution (workers now execute API calls via SSH)
2. API provider expansion (4 new providers added)
3. Credential distribution (done on all 8 workers)
4. Error handling verification (confirmed working)

For each issue to close:
gl issue close <issue-id> -m "Completed: [brief description of fix]"

Example:
gl issue close 42 -m "Completed: Workers now execute API calls via SSH. Tested on all 8 workers with 6 working APIs."

Return JSON:
{
  "issues_closed": [],
  "close_messages": {}
}`,
{ label: 'Close issues', model: 'haiku', effort: 'medium' });

log('Issues closed');

phase('Push Remote');

const push = await agent(`Push all changes to GitLab:

1. Verify we're on main branch: git branch
2. Pull latest (in case of conflicts): git pull origin main
3. Push commits: git push origin main
4. Verify push succeeded

Return JSON:
{
  "pushed": true/false,
  "branch": "main",
  "commits_pushed": [],
  "error": null
}`,
{ label: 'Push to remote', model: 'sonnet', effort: 'medium' });

log('Pushed to remote');

return {
  review,
  commit,
  issues_closed: closeIssues,
  push,
  success: commit?.committed && push?.pushed
};
