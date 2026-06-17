# How to Close a Release (Rxyz)

**Process for closing releases like R305, R309, etc.**

**Published to Confluence:** Part of How To guides at https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/326190622

---

## Overview

Standard workflow for closing a release (e.g., R305, R309):

1. Close the Rxyz Jira ticket
2. Update Confluence with release notes
3. Send email notification to stakeholders

---

## Step 1: Close Jira Ticket (Rxyz)

### Via Jira Web UI:
1. Go to https://redhat.atlassian.net
2. Search for ticket (e.g., "R305")
3. Update **Fix Version** field
4. Transition to **Done/Closed**

### Via Claude/API:
```python
import requests
from requests.auth import HTTPBasicAuth
import os

issue_key = "PROJ-305"  # Your Rxyz ticket
url = f"{os.environ['JIRA_URL']}/rest/api/3/issue/{issue_key}"
auth = HTTPBasicAuth(
    os.environ['JIRA_USER_EMAIL'],
    os.environ['JIRA_API_TOKEN']
)

# Update fix version
data = {
    "fields": {
        "fixVersions": [{"name": "R305"}]
    }
}
requests.put(url, json=data, auth=auth)

# Transition to Done
transitions_url = f"{url}/transitions"
response = requests.get(transitions_url, auth=auth)
done_id = [t['id'] for t in response.json()['transitions'] 
           if t['name'] == 'Done'][0]

requests.post(transitions_url, 
              json={"transition": {"id": done_id}},
              auth=auth)
```

---

## Step 2: Update Confluence

### Create Release Notes Page:

1. **Manually:**
   - Go to https://redhat.atlassian.net/wiki/spaces/DXPIR
   - Create page under "How To" parent (326190622)
   - Title: "R305 Release Notes"
   - Add release date, fixed issues, highlights

2. **Via Claude/API:**
```python
url = f"{os.environ['CONFLUENCE_URL']}/rest/api/content"
auth = HTTPBasicAuth(
    os.environ['CONFLUENCE_USER_EMAIL'],
    os.environ['CONFLUENCE_API_TOKEN']
)

from datetime import datetime

data = {
    "type": "page",
    "title": "R305 Release Notes",
    "space": {"key": "DXPIR"},
    "ancestors": [{"id": "326190622"}],  # Parent: How To
    "body": {
        "storage": {
            "value": f"""
                <h1>R305 Release Notes</h1>
                <p><strong>Release Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>
                
                <h2>Fixed Issues</h2>
                <ul>
                    <li><a href='https://redhat.atlassian.net/browse/PROJ-123'>PROJ-123</a> - Bug fix</li>
                    <li><a href='https://redhat.atlassian.net/browse/PROJ-456'>PROJ-456</a> - Feature</li>
                </ul>
                
                <h2>Highlights</h2>
                <p>Summary of major changes...</p>
            """,
            "representation": "storage"
        }
    }
}

response = requests.post(url, json=data, auth=auth)
page_id = response.json()['id']
print(f"Created: https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/{page_id}")
```

---

## Step 3: Send Email Notification

### Via Gmail:

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

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

R305 has been released!

Release notes: https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/{page_id}

Fixed issues:
- PROJ-123: Bug fix
- PROJ-456: New feature

Thanks,
Claude
""")

message['to'] = 'team@redhat.com'
message['subject'] = 'R305 Release Notification'

raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
service.users().messages().send(
    userId='me',
    body={'raw': raw}
).execute()

print("✅ Email sent")
```

---

## Complete Automated Workflow

Put it all together:

```python
def close_release(release_version, issues_list, stakeholder_emails):
    """
    Complete release closing workflow
    
    Args:
        release_version: e.g., "R305"
        issues_list: ["PROJ-123", "PROJ-456"]
        stakeholder_emails: ["team@redhat.com"]
    """
    from datetime import datetime
    
    # 1. Update Jira tickets
    for issue in issues_list:
        update_jira_fix_version(issue, release_version)
    
    # 2. Create Confluence page
    page_id = create_confluence_release_notes(
        release_version, 
        issues_list
    )
    
    # 3. Send notification email
    send_release_email(
        release_version,
        page_id,
        issues_list,
        stakeholder_emails
    )
    
    print(f"✅ {release_version} closed successfully!")
    print(f"   Confluence: https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/{page_id}")

# Usage:
close_release(
    "R305",
    ["PROJ-123", "PROJ-456", "PROJ-789"],
    ["team@redhat.com", "stakeholders@redhat.com"]
)
```

---

## Checklist

Release closing checklist:

- [ ] All issues resolved in Jira
- [ ] Jira ticket (Rxyz) updated with fix version
- [ ] Jira ticket transitioned to Done/Closed
- [ ] Confluence release notes page created
- [ ] Release notes include: date, fixed issues, highlights
- [ ] Email sent to stakeholders
- [ ] Git tags created (if applicable)
- [ ] Documentation updated

---

## Required Environment Variables

Make sure these are set in `~/.bashrc`:

```bash
# Jira
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_USER_EMAIL="your-email@redhat.com"
export JIRA_API_TOKEN="your-token"

# Confluence (same token as Jira)
export CONFLUENCE_URL="https://redhat.atlassian.net/wiki"
export CONFLUENCE_USER_EMAIL="your-email@redhat.com"
export CONFLUENCE_API_TOKEN="your-token"

# Gmail
export GOOGLE_CLIENT_ID="your-client-id"
export GOOGLE_CLIENT_SECRET="your-secret"
export GOOGLE_REFRESH_TOKEN="your-refresh-token"
```

---

## See Also

- [Claude + Google Integration](https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421627699)
- [Claude + Atlassian Integration](https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421659743)
- [R305/R309 Integration Example](R305-R309-google-atlassian-integration.md)

---

**Last Updated:** 2026-06-16  
**Created by:** Claude Code
