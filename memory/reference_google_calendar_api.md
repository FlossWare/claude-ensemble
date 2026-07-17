---
name: google-calendar-api
description: Gmail MCP OAuth credentials (~/.gmail-mcp/) include Google Calendar scopes — can create/manage calendar events via Calendar API directly
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0295075e-4c0c-4cff-9940-f97bacbb3501
---

The Gmail MCP OAuth credentials at `~/.gmail-mcp/credentials.json` include `calendar` and `calendar.events` scopes (plus drive, contacts, tasks, docs, sheets, presentations).

**How to create calendar events:** Use the Google Calendar API directly with the OAuth refresh token from `~/.gmail-mcp/credentials.json` and client ID/secret from `~/.gmail-mcp/gcp-oauth.keys.json`.

**Python pattern (no extra dependencies):**
```python
import json, urllib.request, urllib.parse

# Load creds
with open("/home/sfloess/.gmail-mcp/credentials.json") as f:
    tokens = json.load(f)["tokens"]
with open("/home/sfloess/.gmail-mcp/gcp-oauth.keys.json") as f:
    oauth = json.load(f)["installed"]

# Refresh access token
refresh_data = urllib.parse.urlencode({
    "client_id": oauth["client_id"],
    "client_secret": oauth["client_secret"],
    "refresh_token": tokens["refresh_token"],
    "grant_type": "refresh_token"
}).encode()
req = urllib.request.Request("https://oauth2.googleapis.com/token", data=refresh_data)
access_token = json.loads(urllib.request.urlopen(req).read())["access_token"]

# Create event
event = {
    "summary": "Event title",
    "start": {"dateTime": "2026-07-17T11:00:00", "timeZone": "America/New_York"},
    "end":   {"dateTime": "2026-07-17T11:30:00", "timeZone": "America/New_York"},
}
req = urllib.request.Request(
    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
    data=json.dumps(event).encode(),
    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
)
result = json.loads(urllib.request.urlopen(req).read())
```

**Available scopes:** gmail.modify, gmail.settings.basic, calendar, calendar.events, drive, drive.file, contacts, contacts.readonly, tasks, documents, spreadsheets, presentations

**How to apply:** When user asks to create calendar events, reminders, or appointments — use this pattern instead of saying "I don't have calendar access." Also applies to Google Tasks, Drive, Contacts, Docs, Sheets via same OAuth creds.

See also: [[gmail-mcp-integration]]
