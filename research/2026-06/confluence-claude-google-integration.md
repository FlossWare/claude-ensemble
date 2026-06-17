# Claude Integration with Google (Gmail + Drive)

**Published to Confluence:** https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421627699

**Last Updated:** 2026-06-16  
**Purpose:** Enable Claude Code to access Gmail and Google Drive for automated workflows

## Overview

OAuth 2.0 setup guide for Claude to access:
- Gmail - Read, send, and search emails
- Google Drive - Read and create files

## Setup Steps

1. Create GCP Project and Enable APIs (Gmail API, Google Drive API)
2. Create OAuth 2.0 Credentials (Desktop application)
3. Configure OAuth scopes: gmail.send, gmail.readonly, drive.readonly, drive.file
4. Add environment variables (GOOGLE_OAUTH_CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
5. Test Gmail and Drive access with Python

## Use Cases
- Automated email notifications (release announcements, CI/CD alerts)
- Documentation updates to Google Drive
- Integration with CI/CD workflows

## Security
- Never commit OAuth credentials to git
- Store tokens in environment variables
- Regularly rotate refresh tokens (every 90 days)

**Full guide:** https://redhat.atlassian.net/wiki/spaces/DXPIR/pages/421627699
