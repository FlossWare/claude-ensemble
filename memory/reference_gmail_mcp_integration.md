---
name: gmail-mcp-integration
description: "Gmail MCP server integration - available tools, configuration, and authentication for Google Workspace email automation"
metadata: 
  node_type: memory
  type: reference
  originSessionId: ebaffba0-c338-48a6-a611-40d7a528db3a
---

# Gmail MCP Integration

**Server:** `gmail-mcp` v1.2.0  
**Executable:** `/home/sfloess/.npm-global/bin/gmail-mcp`  
**Configuration:** `~/.claude/settings.json` → `mcpServers.gmail`  
**Credentials:** `~/.gmail-mcp/credentials.json` + `gcp-oauth.keys.json`  
**Scopes:** Default = `gmail.modify` + `gmail.settings.basic`

## Available Tools (37 total)

### Email Reading
- **read_email** - Retrieve full message by messageId (headers, body, attachments)
  - Formats: `full`, `summary`, `headers_only`
  - Default maxBodyLength: 104,448 bytes (Gmail web UI clipping threshold)
  
- **search_emails** - Gmail query syntax search (e.g., `from:foo@bar.com after:2024/01/01`)
  - Returns flat message list (not thread-grouped)
  - Max results: 1-500 (default 10)

- **get_thread** - Retrieve all messages in thread (chronological order)
  - Formats: `full`, `metadata`, `minimal`
  
- **list_inbox_threads** - Thread-level view with snippets + message count
  - Max results: 1-500 (default 50)
  - Default query: `in:inbox`
  
- **get_inbox_with_threads** - Bulk-read threads with expanded content
  - Max 500 threads (lightweight) or 100 (expandThreads=true)

- **download_email** - Save message to file (json/eml/txt/html)
  - Does NOT load into LLM context (good for large messages)

- **download_attachment** - Download attachment to filesystem
  - Filename sanitized (path-traversal blocked)

### Email Modification
- **modify_email** - Change labels on single message (archive, trash, read/unread)
  - Reversible (invert addLabelIds/removeLabelIds)
  - Idempotent
  
- **batch_modify_emails** - Bulk label changes (up to 1,000 messages)
  - Cheaper than calling modify_email N times
  - All messages get same label changes
  
- **modify_thread** - Atomic label change on ALL thread messages
  - Reversible, idempotent

### Email Sending
- **send_email** - Send new email immediately
  - **CONFIRM with user before calling**
  - Subject to recipient pairing if enabled
  - Supports attachments, cc, bcc, threading
  
- **reply_to_email** - Reply to sender ONLY
  - Preserves subject (adds "Re:" if missing)
  - Sets In-Reply-To/References headers automatically
  
- **reply_all** - Reply to all recipients (To + CC)
  - **CONFIRM recipients with user** (can broadcast widely)
  - Sets threading headers automatically
  
- **forward_email** - Forward to new recipients (new thread)
  - Gmail-style quoted body with separator
  - Attachments NOT auto-attached (download + attach manually)

### Draft Management
- **draft_email** - Create draft (NO mail sent)
  - Good for human review before sending
  
- **list_drafts** - List drafts (paginated, 1-500 per page)
  - Optional query filter (same syntax as search_emails)
  
- **get_draft** - Retrieve draft by ID
  - Formats: `full`, `metadata`, `minimal`, `raw`
  
- **update_draft** - Replace draft contents (FULL overwrite)
  - Preserves draft ID, new messageId
  
- **send_draft** - Send existing draft immediately
  - **CONFIRM with user before calling**
  
- **delete_draft** - Permanently delete draft
  - **IRREVERSIBLE** (no trash for drafts)

### Label Management
- **list_email_labels** - List all labels (system + user-defined)
  
- **create_label** - Create new user label
  - Returns 409 on duplicate names
  
- **get_or_create_label** - Idempotent label lookup-or-create
  - Safe to call repeatedly
  
- **update_label** - Rename or change label visibility/color
  - Existing messages keep same label ID
  
- **delete_label** - **Permanently delete** label
  - **CONFIRM with user before calling**
  - System labels (INBOX, SENT, etc.) cannot be deleted

### Filter Management
- **list_filters** - List all configured filters
  
- **get_filter** - Retrieve specific filter by ID
  
- **create_filter** - Create custom filter (criteria + actions)
  - Applies to FUTURE messages only
  - NOT idempotent (calling twice creates duplicates)
  - `action.forward` gated by recipient pairing
  
- **create_filter_from_template** - Create from pre-defined template
  - Templates: `fromSender`, `withSubject`, `withAttachments`, `largeEmails`, `containingText`, `mailingList`
  - Safer than free-form filter creation
  
- **delete_filter** - **Permanently delete** filter
  - **CONFIRM with user before calling**
  - No undo, stops processing future messages

### Recipient Pairing (when GMAIL_MCP_RECIPIENT_PAIRING enabled)
- **pair_recipient** - Manage allowlist (~/.gmail-mcp/paired.json)
  - Actions: `add`, `remove`, `list`
  - Pre-approve To/Cc/Bcc addresses
  - **CONFIRM with user before adding**

## Scopes Available

| Short Name | Full URL |
|-----------|----------|
| gmail.readonly | https://www.googleapis.com/auth/gmail.readonly |
| gmail.modify | https://www.googleapis.com/auth/gmail.modify |
| gmail.compose | https://www.googleapis.com/auth/gmail.compose |
| gmail.send | https://www.googleapis.com/auth/gmail.send |
| gmail.labels | https://www.googleapis.com/auth/gmail.labels |
| gmail.settings.basic | https://www.googleapis.com/auth/gmail.settings.basic |
| gmail.settings.sharing | https://www.googleapis.com/auth/gmail.settings.sharing |
| mail.google.com | https://mail.google.com/ |

## Security Gates

**Recipient Pairing** (when enabled):
- Affects: `send_email`, `reply_all`, `draft_email`, `create_filter` (forward action)
- Unpaired recipients are rejected at call time
- Pair addresses via `pair_recipient` tool first

**Destructive Operations** (always confirm with user):
- Sending email (`send_email`, `reply_all`, `forward_email`, `send_draft`)
- Deleting labels (`delete_label`)
- Deleting filters (`delete_filter`)
- Deleting drafts (`delete_draft`)

## Common Patterns

**Inbox Triage:**
```javascript
// 1. List threads
const threads = await list_inbox_threads({ maxResults: 50 });

// 2. Read specific thread
const thread = await get_thread({ threadId: threads[0].id });

// 3. Archive thread
await modify_thread({
  threadId: threads[0].id,
  removeLabelIds: ['INBOX']
});
```

**Search and Label:**
```javascript
// 1. Search for messages
const messages = await search_emails({
  query: 'from:newsletter@example.com',
  maxResults: 100
});

// 2. Create/get label
const label = await get_or_create_label({
  name: 'Newsletters'
});

// 3. Bulk apply label
await batch_modify_emails({
  messageIds: messages.map(m => m.id),
  addLabelIds: [label.id],
  removeLabelIds: ['INBOX']
});
```

**Auto-Filter Setup:**
```javascript
// Create filter from template
await create_filter_from_template({
  template: 'fromSender',
  parameters: {
    senderEmail: 'newsletter@example.com',
    labelIds: [newsletterLabelId],
    archive: true,
    markAsRead: true
  }
});
```

## Authentication Flow

1. OAuth2 credentials in `~/.gmail-mcp/gcp-oauth.keys.json`
2. User consent flow generates `credentials.json`
3. MCP server uses credentials for all API calls
4. Scopes: `gmail.modify` + `gmail.settings.basic` by default

## Integration with Claude Code

**Configuration in settings.json:**
```json
{
  "mcpServers": {
    "gmail": {
      "command": "/home/sfloess/.npm-global/bin/gmail-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

**Tool Usage:**
- All tools available via MCP protocol
- Use ToolSearch to discover available tools at runtime
- Most tools have `readOnlyHint`, `destructiveHint`, `idempotentHint` annotations
- All tools have `execution.taskSupport: "forbidden"` (require synchronous execution)

## Performance Considerations

- **Batch operations** (`batch_modify_emails`) cheaper than loops
- **Format selection** (`summary`, `headers_only`) reduces context usage
- **maxBodyLength** (default 102KB) mirrors Gmail web UI clipping
- **Thread expansion** (`get_inbox_with_threads`) capped at 100 threads when expandThreads=true
- **Pagination** available for `list_inbox_threads`, `search_emails`, `list_drafts`

## Related Memory
- [[feedback_exclude_personal_directories]] - Don't access ~/Downloads or ~/Documents
- User prefers automation over manual email management
