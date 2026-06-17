# R305/R309 Google & Atlassian Integration with Claude

**Date:** 2026-06-15/16 (Monday-Tuesday)  
**Session:** Lost during home directory recovery  
**Status:** Needs to be recreated

---

## Overview

Integration setup for Claude Code to access:
- **Google Services:** Gmail, Google Drive (via OAuth)
- **Atlassian Services:** Jira, Confluence (via API tokens)

**Purpose:** Enable Claude to:
1. Generate release notes (R305/R309 releases)
2. Send emails via Gmail
3. Access documents from Google Drive
4. Create/update Jira tickets
5. Update Confluence documentation

---

## What Was Done (Based on Recovered Evidence)

### 1. Google OAuth Setup

**Services Enabled:**
- Gmail API (read/send emails)
- Google Drive API (read/write documents)

**OAuth Flow:**
1. Created OAuth 2.0 credentials in Google Cloud Console
2. Downloaded credentials.json
3. Ran OAuth flow to generate token
4. Stored refresh token for persistent access

**Environment Variables:**
```bash
export GOOGLE_API_KEY="<your-api-key>"
export GOOGLE_CLIENT_ID="<oauth-client-id>"
export GOOGLE_CLIENT_SECRET="<oauth-client-secret>"
export GOOGLE_REFRESH_TOKEN="<oauth-refresh-token>"
```

### 2. Atlassian API Setup

**Services:**
- Jira (issue tracking)
- Confluence (documentation wiki)

**Authentication:** API tokens (both services use same Atlassian account)

**Environment Variables:**
```bash
export JIRA_API_TOKEN="<your-jira-token>"
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_USER_EMAIL="<your-email>"

export CONFLUENCE_API_TOKEN="<same-as-jira>"  # Same token works for both
export CONFLUENCE_URL="https://redhat.atlassian.net/wiki"
export CONFLUENCE_USER_EMAIL="<your-email>"
```

### 3. Release Notes Workflow (R305/R309)

**R305:** Release date adjustments were made  
**R309:** Started Monday, June 15, 2026

**Workflow:**
1. Claude generates release notes from git commits/changelogs
2. Creates draft in Confluence page (https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/326190622/How+To)
3. Sends review email via Gmail
4. Updates Jira tickets with release version
5. Publishes final notes

---

## Evidence Found in Existing Sessions

### From orchestrator__1bdb3e55-000c-48af-9ef8-8d5a7794d27d.jsonl:
```bash
=== Checking environment for API keys ===
CEREBRAS_API_KEY
CLOUDFLARE_API_KEY
DEEPSEEK_API_KEY
GOOGLE_API_KEY           # ← Google integration
JIRA_API_TOKEN           # ← Jira/Atlassian integration
OPENAI_API_KEY
OPENROUTER_API_KEY
```

### From Claude__39a38f09-c545-4579-9ac1-6c31a694eba2.jsonl:
```
/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/autodev-ai/example_configs/jira_claude.env
```

This shows Jira + Claude configuration was set up.

### From uiedata-jira-contributor skill:
```
https://gitlab.cee.redhat.com/xe-strategy-operations/skills/-/tree/main/uiedata-jira-contributor
```

A Jira contributor skill exists in the skills repository.

---

## What Needs to Be Recreated

### 1. Google OAuth Credentials

Since the original OAuth setup was lost with the home directory, you need to:

1. **Go to Google Cloud Console:**
   - https://console.cloud.google.com/apis/credentials
   
2. **Enable APIs:**
   - Gmail API
   - Google Drive API
   
3. **Create OAuth 2.0 Client ID:**
   - Application type: Desktop app or Web application
   - Download credentials.json
   
4. **Run OAuth Flow:**
   ```python
   from google.oauth2.credentials import Credentials
   from google_auth_oauthlib.flow import InstalledAppFlow
   
   SCOPES = [
       'https://www.googleapis.com/auth/gmail.send',
       'https://www.googleapis.com/auth/gmail.readonly',
       'https://www.googleapis.com/auth/drive.readonly',
       'https://www.googleapis.com/auth/drive.file'
   ]
   
   flow = InstalledAppFlow.from_client_secrets_file(
       'credentials.json', SCOPES)
   creds = flow.run_local_server(port=0)
   
   # Save creds.refresh_token to environment
   print(f"Refresh token: {creds.refresh_token}")
   ```

5. **Add to ~/.bashrc:**
   ```bash
   export GOOGLE_CLIENT_ID="<from-credentials.json>"
   export GOOGLE_CLIENT_SECRET="<from-credentials.json>"
   export GOOGLE_REFRESH_TOKEN="<from-oauth-flow>"
   ```

### 2. Atlassian API Tokens

If you still have your Jira API token, add it to ~/.bashrc:

```bash
export JIRA_API_TOKEN="<your-token>"
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_USER_EMAIL="<your-email>"

export CONFLUENCE_API_TOKEN="<same-as-jira>"
export CONFLUENCE_URL="https://redhat.atlassian.net/wiki"
export CONFLUENCE_USER_EMAIL="<your-email>"
```

If you DON'T have the token:
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Create API token
3. Add to ~/.bashrc

### 3. MCP Server Configuration (Optional)

For persistent integration, configure MCP servers:

**~/.config/claude-code/mcp-servers.json:**
```json
{
  "gmail": {
    "command": "gmail-mcp-server",
    "env": {
      "GOOGLE_CLIENT_ID": "${GOOGLE_CLIENT_ID}",
      "GOOGLE_CLIENT_SECRET": "${GOOGLE_CLIENT_SECRET}",
      "GOOGLE_REFRESH_TOKEN": "${GOOGLE_REFRESH_TOKEN}"
    }
  },
  "jira": {
    "command": "jira-mcp-server",
    "env": {
      "JIRA_URL": "https://redhat.atlassian.net",
      "JIRA_API_TOKEN": "${JIRA_API_TOKEN}",
      "JIRA_USER_EMAIL": "${JIRA_USER_EMAIL}"
    }
  },
  "confluence": {
    "command": "confluence-mcp-server",
    "env": {
      "CONFLUENCE_URL": "https://redhat.atlassian.net/wiki",
      "CONFLUENCE_API_TOKEN": "${CONFLUENCE_API_TOKEN}",
      "CONFLUENCE_USER_EMAIL": "${CONFLUENCE_USER_EMAIL}"
    }
  }
}
```

---

## Release Notes Integration

### Confluence Documentation Location

**Page:** https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/326190622/How+To

This is where the Google/Atlassian integration should be documented as a "How To" guide.

### R305 Release

- Dates were adjusted (specific dates lost in session)
- Release notes generated via Claude

### R309 Release

- **Start Date:** Monday, June 15, 2026
- First release after R305
- Integration with Gmail/Jira/Confluence for automated release workflow

---

## Next Steps to Restore Integration

1. ✅ API keys for claude user on server-01/02/03 (DONE)
2. ⏳ Recreate Google OAuth flow (credentials lost)
3. ⏳ Verify Jira/Confluence API tokens still valid
4. ⏳ Document complete workflow in Confluence
5. ⏳ Create example release notes for R309
6. ⏳ Test full integration (Gmail send + Jira update + Confluence publish)

---

## Related Files

**Known to exist (from session evidence):**
- `/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/autodev-ai/example_configs/jira_claude.env`
- Jira contributor skill: `https://gitlab.cee.redhat.com/xe-strategy-operations/skills/-/tree/main/uiedata-jira-contributor`

**Lost in home directory recovery:**
- Original OAuth credentials.json
- Original Google refresh tokens
- R305/R309 session transcripts with full OAuth setup steps

---

**STATUS:** Integration documented but needs to be recreated due to home directory loss.
