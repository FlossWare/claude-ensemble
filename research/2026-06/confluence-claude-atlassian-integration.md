# Claude Integration with Atlassian (Jira + Confluence)

**Published to Confluence:** https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421659743

**Last Updated:** 2026-06-16  
**Purpose:** Enable Claude Code to access Jira and Confluence for automated workflows

## Overview

API token authentication guide for Claude to access:
- Jira - Create, update, and query issues/tickets
- Confluence - Create, update, and read wiki pages

## Setup Steps

1. Create Atlassian API Token (Settings → Access tokens)
2. Add environment variables (JIRA_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN)
3. Same token works for Confluence
4. Test Jira and Confluence access with Python

## Use Cases
- Automated release notes publishing (R305, R309)
- Jira ticket updates with fix versions
- Documentation generation and updates
- Integration with CI/CD workflows

## R305/R309 Release Workflow
Complete automated workflow:
1. Generate HTML release notes with issue links
2. Create Confluence page
3. Update all Jira tickets with fix version

## Security
- Never commit API tokens to git
- Store tokens in environment variables
- Regularly rotate tokens (every 90 days)

**Full guide:** https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421659743
