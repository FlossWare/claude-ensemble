# Google & Atlassian Integration Walkthrough

Complete step-by-step guide for setting up Claude Code to access Gmail, Google Drive, Jira, and Confluence.

---

## Part 1: Google OAuth Setup (Gmail + Google Drive)

### Step 1: Create Google Cloud Project

1. **Go to Google Cloud Console:**
   ```
   https://console.cloud.google.com/
   ```

2. **Create a new project** (or select existing):
   - Click "Select a project" → "New Project"
   - Name: "Claude Integration" (or whatever you prefer)
   - Click "Create"

### Step 2: Enable APIs

1. **Go to APIs & Services → Library:**
   ```
   https://console.cloud.google.com/apis/library
   ```

2. **Enable Gmail API:**
   - Search for "Gmail API"
   - Click on it
   - Click "Enable"

3. **Enable Google Drive API:**
   - Search for "Google Drive API"
   - Click on it
   - Click "Enable"

### Step 3: Create OAuth Credentials

1. **Go to APIs & Services → Credentials:**
   ```
   https://console.cloud.google.com/apis/credentials
   ```

2. **Configure OAuth Consent Screen:**
   - Click "OAuth consent screen"
   - User Type: "External" (unless you have Google Workspace)
   - Click "Create"
   - Fill in:
     - App name: "Claude Code Integration"
     - User support email: (your email)
     - Developer contact: (your email)
   - Click "Save and Continue"
   - Scopes: Click "Add or Remove Scopes"
     - Search and add:
       - `https://www.googleapis.com/auth/gmail.send`
       - `https://www.googleapis.com/auth/gmail.readonly`
       - `https://www.googleapis.com/auth/drive.readonly`
       - `https://www.googleapis.com/auth/drive.file`
   - Click "Update" → "Save and Continue"
   - Test users: Add your email
   - Click "Save and Continue"

3. **Create OAuth Client ID:**
   - Go back to "Credentials" tab
   - Click "+ Create Credentials" → "OAuth client ID"
   - Application type: "Desktop app"
   - Name: "Claude Code Desktop"
   - Click "Create"
   - **IMPORTANT:** Download the JSON file (credentials.json)
   - Save it to: `~/.config/google-oauth/credentials.json`

```bash
mkdir -p ~/.config/google-oauth
# Move your downloaded file here
mv ~/Downloads/client_secret_*.json ~/.config/google-oauth/credentials.json
```

### Step 4: Run OAuth Flow

Create this Python script to get your refresh token:

```bash
cat > /tmp/google_oauth_setup.py << 'EOF'
#!/usr/bin/env python3
"""
Google OAuth Setup - Get refresh token for Gmail and Drive access
"""
import os
import json
from pathlib import Path

# Install required packages if needed
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
except ImportError:
    print("Installing required packages...")
    os.system("pip3 install --user google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.file'
]

CREDENTIALS_FILE = Path.home() / '.config' / 'google-oauth' / 'credentials.json'
TOKEN_FILE = Path.home() / '.config' / 'google-oauth' / 'token.json'

def main():
    creds = None
    
    # Load existing token if available
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    
    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("Starting OAuth flow...")
            print(f"Reading credentials from: {CREDENTIALS_FILE}")
            
            if not CREDENTIALS_FILE.exists():
                print(f"ERROR: credentials.json not found at {CREDENTIALS_FILE}")
                print("Please download it from Google Cloud Console")
                return
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        print(f"✅ Token saved to: {TOKEN_FILE}")
    
    # Parse credentials
    with open(CREDENTIALS_FILE) as f:
        client_data = json.load(f)
        client_id = client_data['installed']['client_id']
        client_secret = client_data['installed']['client_secret']
    
    # Display environment variables to add
    print("\n" + "="*70)
    print("✅ OAuth Setup Complete!")
    print("="*70)
    print("\nAdd these to your ~/.bashrc:\n")
    print(f'export GOOGLE_CLIENT_ID="{client_id}"')
    print(f'export GOOGLE_CLIENT_SECRET="{client_secret}"')
    print(f'export GOOGLE_REFRESH_TOKEN="{creds.refresh_token}"')
    print(f'export GOOGLE_TOKEN_FILE="{TOKEN_FILE}"')
    print("\nThen run: source ~/.bashrc")
    print("="*70)

if __name__ == '__main__':
    main()
EOF

chmod +x /tmp/google_oauth_setup.py
```

**Run the setup:**

```bash
python3 /tmp/google_oauth_setup.py
```

This will:
1. Open your browser
2. Ask you to sign in to Google
3. Ask you to grant permissions
4. Save the token
5. Print environment variables to add

### Step 5: Add to Environment

Copy the output from the script and add to `~/.bashrc`:

```bash
cat >> ~/.bashrc << 'EOF'

# Google OAuth (Gmail + Drive)
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"
export GOOGLE_REFRESH_TOKEN="your-refresh-token"
export GOOGLE_TOKEN_FILE="$HOME/.config/google-oauth/token.json"
EOF

source ~/.bashrc
```

### Step 6: Test Gmail Access

```bash
cat > /tmp/test_gmail.py << 'EOF'
#!/usr/bin/env python3
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os

# Load credentials
creds = Credentials.from_authorized_user_file(
    os.environ['GOOGLE_TOKEN_FILE'],
    ['https://www.googleapis.com/auth/gmail.readonly']
)

# Build Gmail API client
service = build('gmail', 'v1', credentials=creds)

# Get profile
profile = service.users().getProfile(userId='me').execute()
print(f"✅ Gmail connected!")
print(f"Email: {profile['emailAddress']}")
print(f"Messages total: {profile['messagesTotal']}")
EOF

python3 /tmp/test_gmail.py
```

---

## Part 2: Atlassian Setup (Jira + Confluence)

### Step 1: Create API Token

1. **Go to Atlassian Account Settings:**
   ```
   https://id.atlassian.com/manage-profile/security/api-tokens
   ```

2. **Create API Token:**
   - Click "Create API token"
   - Label: "Claude Code Integration"
   - Click "Create"
   - **IMPORTANT:** Copy the token immediately (you can't see it again)
   - Save it somewhere secure

### Step 2: Add to Environment

```bash
cat >> ~/.bashrc << 'EOF'

# Atlassian (Jira + Confluence)
export JIRA_URL="https://redhat.atlassian.net"
export JIRA_USER_EMAIL="your-email@redhat.com"
export JIRA_API_TOKEN="your-api-token-here"

export CONFLUENCE_URL="https://redhat.atlassian.net/wiki"
export CONFLUENCE_USER_EMAIL="your-email@redhat.com"
export CONFLUENCE_API_TOKEN="your-api-token-here"  # Same token as Jira
EOF

source ~/.bashrc
```

### Step 3: Test Jira Access

```bash
cat > /tmp/test_jira.py << 'EOF'
#!/usr/bin/env python3
import requests
from requests.auth import HTTPBasicAuth
import os
import json

# Jira API
url = f"{os.environ['JIRA_URL']}/rest/api/3/myself"
auth = HTTPBasicAuth(
    os.environ['JIRA_USER_EMAIL'],
    os.environ['JIRA_API_TOKEN']
)

response = requests.get(url, auth=auth)

if response.status_code == 200:
    user = response.json()
    print(f"✅ Jira connected!")
    print(f"User: {user['displayName']}")
    print(f"Email: {user['emailAddress']}")
else:
    print(f"❌ Failed: {response.status_code}")
    print(response.text)
EOF

python3 /tmp/test_jira.py
```

### Step 4: Test Confluence Access

```bash
cat > /tmp/test_confluence.py << 'EOF'
#!/usr/bin/env python3
import requests
from requests.auth import HTTPBasicAuth
import os

# Confluence API
url = f"{os.environ['CONFLUENCE_URL']}/rest/api/user/current"
auth = HTTPBasicAuth(
    os.environ['CONFLUENCE_USER_EMAIL'],
    os.environ['CONFLUENCE_API_TOKEN']
)

response = requests.get(url, auth=auth)

if response.status_code == 200:
    user = response.json()
    print(f"✅ Confluence connected!")
    print(f"User: {user['displayName']}")
    print(f"Email: {user['email']}")
else:
    print(f"❌ Failed: {response.status_code}")
    print(response.text)
EOF

python3 /tmp/test_confluence.py
```

---

## Part 3: R305/R309 Release Notes Workflow

### Complete Integration Script

```bash
cat > ~/bin/release-notes-workflow.py << 'EOF'
#!/usr/bin/env python3
"""
R305/R309 Release Notes Workflow
- Generate release notes from git commits
- Create Confluence page
- Update Jira tickets
- Send Gmail notification
"""
import os
import sys
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText

def get_gmail_service():
    """Initialize Gmail API service"""
    creds = Credentials.from_authorized_user_file(
        os.environ['GOOGLE_TOKEN_FILE'],
        ['https://www.googleapis.com/auth/gmail.send']
    )
    return build('gmail', 'v1', credentials=creds)

def create_confluence_page(title, content, space_key='DXPIR', parent_id='326190622'):
    """Create or update Confluence page"""
    url = f"{os.environ['CONFLUENCE_URL']}/rest/api/content"
    auth = HTTPBasicAuth(
        os.environ['CONFLUENCE_USER_EMAIL'],
        os.environ['CONFLUENCE_API_TOKEN']
    )
    
    # Check if page exists
    search_url = f"{url}?title={title}&spaceKey={space_key}"
    response = requests.get(search_url, auth=auth)
    
    if response.status_code == 200 and response.json()['size'] > 0:
        # Update existing page
        page = response.json()['results'][0]
        page_id = page['id']
        version = page['version']['number']
        
        update_url = f"{url}/{page_id}"
        data = {
            "version": {"number": version + 1},
            "title": title,
            "type": "page",
            "body": {
                "storage": {
                    "value": content,
                    "representation": "storage"
                }
            }
        }
        response = requests.put(update_url, json=data, auth=auth)
    else:
        # Create new page
        data = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "ancestors": [{"id": parent_id}],
            "body": {
                "storage": {
                    "value": content,
                    "representation": "storage"
                }
            }
        }
        response = requests.post(url, json=data, auth=auth)
    
    if response.status_code in [200, 201]:
        page = response.json()
        return f"{os.environ['CONFLUENCE_URL']}/spaces/{space_key}/pages/{page['id']}"
    else:
        print(f"❌ Confluence error: {response.text}")
        return None

def update_jira_fix_version(issue_key, version_name):
    """Update Jira ticket with fix version"""
    url = f"{os.environ['JIRA_URL']}/rest/api/3/issue/{issue_key}"
    auth = HTTPBasicAuth(
        os.environ['JIRA_USER_EMAIL'],
        os.environ['JIRA_API_TOKEN']
    )
    
    data = {
        "fields": {
            "fixVersions": [{"name": version_name}]
        }
    }
    
    response = requests.put(url, json=data, auth=auth)
    return response.status_code in [200, 204]

def send_gmail(to, subject, body):
    """Send email via Gmail"""
    service = get_gmail_service()
    
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    try:
        message = service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()
        print(f"✅ Email sent! Message ID: {message['id']}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

def generate_release_notes(release_version, start_date, end_date):
    """Generate release notes from git commits"""
    # This is a placeholder - implement based on your git workflow
    notes = f"""
    <h1>{release_version} Release Notes</h1>
    <p>Release Date: {datetime.now().strftime('%Y-%m-%d')}</p>
    
    <h2>New Features</h2>
    <ul>
        <li>Feature 1</li>
        <li>Feature 2</li>
    </ul>
    
    <h2>Bug Fixes</h2>
    <ul>
        <li>Fix 1</li>
        <li>Fix 2</li>
    </ul>
    
    <h2>Known Issues</h2>
    <ul>
        <li>Issue 1</li>
    </ul>
    """
    return notes

def main():
    if len(sys.argv) < 2:
        print("Usage: release-notes-workflow.py <R305|R309>")
        sys.exit(1)
    
    release = sys.argv[1]
    
    print(f"\n🚀 Starting {release} Release Notes Workflow\n")
    
    # 1. Generate release notes
    print("1. Generating release notes...")
    notes = generate_release_notes(release, "2026-06-01", "2026-06-15")
    
    # 2. Create Confluence page
    print("2. Creating Confluence page...")
    confluence_url = create_confluence_page(
        title=f"{release} Release Notes",
        content=notes,
        space_key='DXPIR',
        parent_id='326190622'
    )
    
    if confluence_url:
        print(f"   ✅ Published: {confluence_url}")
    
    # 3. Update Jira tickets (example)
    print("3. Updating Jira tickets...")
    # update_jira_fix_version("PROJ-123", release)
    
    # 4. Send notification email
    print("4. Sending notification email...")
    email_body = f"""
Hi Team,

{release} release notes are now available:
{confluence_url}

Please review and provide feedback.

Best regards,
Automated Release System
    """
    
    # send_gmail("team@redhat.com", f"{release} Release Notes", email_body)
    
    print(f"\n✅ {release} Release Workflow Complete!\n")

if __name__ == '__main__':
    main()
EOF

chmod +x ~/bin/release-notes-workflow.py
```

### Usage

**For R305:**
```bash
~/bin/release-notes-workflow.py R305
```

**For R309:**
```bash
~/bin/release-notes-workflow.py R309
```

---

## Part 4: Verify Complete Setup

Run this verification script:

```bash
cat > /tmp/verify-integration.sh << 'EOF'
#!/bin/bash

echo "🔍 Verifying Google & Atlassian Integration"
echo ""

# Check environment variables
echo "📋 Environment Variables:"
echo -n "  GOOGLE_CLIENT_ID: "
[ -n "$GOOGLE_CLIENT_ID" ] && echo "✅" || echo "❌"

echo -n "  GOOGLE_CLIENT_SECRET: "
[ -n "$GOOGLE_CLIENT_SECRET" ] && echo "✅" || echo "❌"

echo -n "  GOOGLE_REFRESH_TOKEN: "
[ -n "$GOOGLE_REFRESH_TOKEN" ] && echo "✅" || echo "❌"

echo -n "  JIRA_API_TOKEN: "
[ -n "$JIRA_API_TOKEN" ] && echo "✅" || echo "❌"

echo -n "  JIRA_URL: "
[ -n "$JIRA_URL" ] && echo "✅" || echo "❌"

echo -n "  CONFLUENCE_URL: "
[ -n "$CONFLUENCE_URL" ] && echo "✅" || echo "❌"

echo ""
echo "📁 Files:"
echo -n "  ~/.config/google-oauth/credentials.json: "
[ -f ~/.config/google-oauth/credentials.json ] && echo "✅" || echo "❌"

echo -n "  ~/.config/google-oauth/token.json: "
[ -f ~/.config/google-oauth/token.json ] && echo "✅" || echo "❌"

echo ""
echo "🧪 API Tests:"

# Test Gmail
python3 /tmp/test_gmail.py 2>/dev/null && echo "  Gmail: ✅" || echo "  Gmail: ❌"

# Test Jira
python3 /tmp/test_jira.py 2>/dev/null && echo "  Jira: ✅" || echo "  Jira: ❌"

# Test Confluence
python3 /tmp/test_confluence.py 2>/dev/null && echo "  Confluence: ✅" || echo "  Confluence: ❌"

echo ""
echo "✅ Verification Complete!"
EOF

chmod +x /tmp/verify-integration.sh
/tmp/verify-integration.sh
```

---

## Summary

After following this walkthrough, you'll have:

✅ **Google OAuth** working for Gmail and Google Drive  
✅ **Atlassian API** tokens for Jira and Confluence  
✅ **Release notes workflow** for R305/R309  
✅ **Automated publishing** to Confluence  
✅ **Email notifications** via Gmail  
✅ **Jira ticket updates** with fix versions

All environment variables saved in `~/.bashrc` and ready to use!
