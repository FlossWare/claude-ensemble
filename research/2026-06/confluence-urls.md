# Confluence Pages Published (2026-06-15/16)

## Integration Guides

### 1. Claude Integration with Google (Gmail + Drive)
- **URL**: https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421627699
- **File**: /tmp/confluence-claude-google-integration.html
- **Content**: OAuth 2.0 setup, Gmail/Drive API access, example code

### 2. Claude Integration with Atlassian (Jira + Confluence)
- **URL**: https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421659743
- **File**: /tmp/confluence-claude-atlassian-integration.html
- **Content**: API token setup, Jira/Confluence access, release workflow

### 3. Parent Page: How To
- **URL**: https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/326190622
- **Purpose**: Container page for all how-to guides

### 4. How to Create Release Notes with Claude
- **URL**: https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421593810
- **Note**: Page ID found in session but content unknown

## Supporting Documentation

- `/tmp/google-atlassian-integration-walkthrough.md` - Complete walkthrough (17K)
- `/tmp/R305-R309-google-atlassian-integration.md` - Release workflow example (6.9K)

## Created
2026-06-15/16 during integration setup session

---

## Release Workflow Documentation

### How to Do Releases (R305/R309 Example)

**Documentation:** [R305-R309-google-atlassian-integration.md](R305-R309-google-atlassian-integration.md)

**Complete workflow for publishing release notes:**

1. **Close Jira tickets** - Update fix version via API
2. **Update Confluence** - Create release notes page  
3. **Send email** - Gmail API notification

**Automated workflow steps:**
```python
def publish_release_notes(release_version, issues_list):
    # 1. Generate HTML with issue links
    # 2. POST to Confluence API (create page)
    # 3. PUT to Jira API (update fix versions)
    # 4. POST to Gmail API (send announcement)
```

**APIs used:**
- Jira REST API - Update issue.fixVersions
- Confluence REST API - Create/update pages
- Gmail API - Send release emails

**Example:** See R305-R309-google-atlassian-integration.md for complete code

---

**Last Updated:** 2026-06-16
