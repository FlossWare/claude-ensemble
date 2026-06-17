# Create Release Notes with Claude

**Published to Confluence:** https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421593810/How+to+Create+Release+Notes+with+Claude

**Last Updated:** 2026-06-16  
**Purpose:** Document the complete process for using Claude to generate and publish release notes

---

## Overview

Complete workflow for creating release notes (e.g., R305, R309) using Claude Code with automated Jira, Confluence, and Gmail integration.

---

## Prerequisites

1. **Jira API Token** - For updating tickets with fix versions
2. **Confluence API Token** - For creating/updating release notes pages (same as Jira token)
3. **Gmail OAuth** - For sending release notifications

See setup guides:
- [Claude + Google Integration](https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421627699)
- [Claude + Atlassian Integration](https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421659743)

---

## Step-by-Step Process

### Step 1: Gather Release Information

Identify what goes into the release:
- Fixed issues/tickets
- New features
- Bug fixes
- Breaking changes (if any)

**Example:**
```
Release: R305
Issues: PROJ-123, PROJ-456, PROJ-789
Date: 2026-06-15
```

---

### Step 2: Update Jira Tickets

Close the Rxyz Jira ticket and update all fixed issues with the release version.

**Via Claude:**
Ask Claude to update Jira:
```
Update these Jira tickets with fix version R305:
- PROJ-123
- PROJ-456
- PROJ-789
```

Claude will use the Jira API to:
1. Update `fixVersions` field for each ticket
2. Optionally transition tickets to Done/Closed

**Manual verification:**
Check https://redhat.atlassian.net to confirm updates

---

### Step 3: Generate Release Notes Content

Ask Claude to generate release notes:

```
Generate release notes for R305 with these tickets:
- PROJ-123: Fixed authentication bug
- PROJ-456: Added new dashboard feature  
- PROJ-789: Performance improvements

Format for Confluence.
```

Claude will create Confluence-formatted HTML with:
- Release date
- List of fixed issues (with hyperlinks)
- Categorized by type (bugs, features, improvements)
- Highlights section

---

### Step 4: Publish to Confluence

**Via Claude:**
```
Create a Confluence page for R305 release notes under the How To parent page
```

Claude will:
1. POST to Confluence API
2. Create page with title "R305 Release Notes"
3. Set parent to How To page (326190622)
4. Add generated HTML content
5. Return the page URL

**Result:** https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/[new-page-id]

---

### Step 5: Send Email Notification

**Via Claude:**
```
Send release notification email for R305 to team@redhat.com with the Confluence link
```

Claude will:
1. Use Gmail API to compose email
2. Include:
   - Release version (R305)
   - Release date
   - Link to Confluence release notes
   - Summary of key changes
3. Send to specified recipients

---

## Complete Automated Workflow

**Single command to Claude:**

```
Close release R305 with these issues:
- PROJ-123: Fixed authentication bug
- PROJ-456: Added dashboard feature
- PROJ-789: Performance improvements

1. Update Jira tickets with fix version R305
2. Create Confluence release notes page
3. Send email to team@redhat.com and stakeholders@redhat.com
```

Claude will execute all steps automatically and report:
- ✅ Jira tickets updated (3)
- ✅ Confluence page created: [URL]
- ✅ Email sent to 2 recipients

---

## Python Code Template

For manual/scripted execution:

```python
#!/usr/bin/env python3
import requests
from requests.auth import HTTPBasicAuth
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
import os
from datetime import datetime

def create_release_notes(release_version, issues):
    """Complete release notes workflow"""
    
    # 1. Update Jira tickets
    jira_auth = HTTPBasicAuth(
        os.environ['JIRA_USER_EMAIL'],
        os.environ['JIRA_API_TOKEN']
    )
    
    for issue_key in issues:
        url = f"{os.environ['JIRA_URL']}/rest/api/3/issue/{issue_key}"
        data = {"fields": {"fixVersions": [{"name": release_version}]}}
        requests.put(url, json=data, auth=jira_auth)
        print(f"✅ Updated {issue_key}")
    
    # 2. Create Confluence page
    conf_auth = HTTPBasicAuth(
        os.environ['CONFLUENCE_USER_EMAIL'],
        os.environ['CONFLUENCE_API_TOKEN']
    )
    
    content = f"""
    <h1>{release_version} Release Notes</h1>
    <p><strong>Release Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>
    
    <h2>Fixed Issues</h2>
    <ul>
    """
    
    for issue in issues:
        content += f'<li><a href="{os.environ["JIRA_URL"]}/browse/{issue}">{issue}</a></li>\n'
    
    content += "</ul>"
    
    url = f"{os.environ['CONFLUENCE_URL']}/rest/api/content"
    data = {
        "type": "page",
        "title": f"{release_version} Release Notes",
        "space": {"key": "DXPIR"},
        "ancestors": [{"id": "326190622"}],
        "body": {"storage": {"value": content, "representation": "storage"}}
    }
    
    response = requests.post(url, json=data, auth=conf_auth)
    page_id = response.json()['id']
    page_url = f"{os.environ['CONFLUENCE_URL']}/spaces/DXPIR/pages/{page_id}"
    print(f"✅ Confluence: {page_url}")
    
    # 3. Send email
    creds = Credentials(
        token=None,
        refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],
        client_id=os.environ['GOOGLE_CLIENT_ID'],
        client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
        token_uri='https://oauth2.googleapis.com/token'
    )
    
    service = build('gmail', 'v1', credentials=creds)
    
    message = MIMEText(f"""
Hi team,

{release_version} has been released!

Release notes: {page_url}

Fixed {len(issues)} issues.

Thanks,
Claude
    """)
    
    message['to'] = 'team@redhat.com'
    message['subject'] = f'{release_version} Release Notification'
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
    print(f"✅ Email sent")

# Usage:
create_release_notes("R305", ["PROJ-123", "PROJ-456", "PROJ-789"])
```

---

## Checklist

- [ ] Gather all fixed issues for the release
- [ ] Ask Claude to update Jira tickets with fix version
- [ ] Ask Claude to generate release notes content
- [ ] Ask Claude to create Confluence page
- [ ] Verify Confluence page looks correct
- [ ] Ask Claude to send email notification
- [ ] Verify email received by stakeholders

---

## Tips

1. **Categorize Issues:** Group by type (bugs, features, improvements)
2. **Add Highlights:** Include a summary of major changes
3. **Use Templates:** Keep consistent format across releases
4. **Test First:** Do a dry-run with a test release to verify workflow
5. **Save Credentials:** Store API tokens/OAuth tokens securely in environment variables

---

## Troubleshooting

**Jira update fails:**
- Check `JIRA_API_TOKEN` is valid
- Verify you have permissions to update tickets

**Confluence page creation fails:**
- Check `CONFLUENCE_API_TOKEN` is valid
- Verify parent page ID (326190622) exists
- Check you have write permissions to DXPIR space

**Email send fails:**
- Verify Google OAuth refresh token is valid
- Check Gmail API is enabled in Google Cloud Console
- Ensure OAuth scopes include `gmail.send`

---

## See Also

- [Claude + Google Integration Guide](https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421627699)
- [Claude + Atlassian Integration Guide](https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421659743)
- [Parent: How To Guides](https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/326190622)

---

**Last Updated:** 2026-06-16  
**Created by:** Claude Code  
**Confluence:** https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421593810
