---
name: project-notion2config
description: notion2config project - System configs from Notion databases (GitLab repository)
metadata: 
  node_type: memory
  type: project
  originSessionId: 97e2ffe0-6678-42c0-bb00-b637160800ac
---

# notion2config Project

**Repository:** https://github.com/FlossWare/notion2config (GitHub)
**Location:** `~/Development/github/FlossWare/notion2config/`
**Purpose:** Generate infrastructure configuration files from Notion databases

## Overview

System configs from Notion databases. Keep infrastructure inventory in Notion and automatically generate config files for various services.

**Tagline:** *Infrastructure as data, configs as code.*

## Current Tools

### notion-dnsmasq.sh ✅ Complete
- Generates dnsmasq configuration (DHCP + DNS) from Notion database
- Handles pagination for large databases
- Auto-reloads dnsmasq service
- Backs up existing configs
- FreeBSD compatible

**Database Requirements:**
- **Name** (Title) - Hostname
- **IP** (Text) - IPv4 address  
- **MAC** (Text, optional) - MAC address for DHCP

**Usage:**
```bash
export NOTION_TOKEN=secret_xxx
./converters/notion-dnsmasq.sh --dry-run
./converters/notion-dnsmasq.sh -o /etc/dnsmasq.d/hosts.conf
```

## Planned Tools

- **notion-ansible.sh** - Ansible inventory generator
- **notion-hosts.sh** - /etc/hosts file generator
- **notion-nginx.sh** - nginx reverse proxy configs
- **notion-docker.sh** - Docker Compose generator
- **notion-terraform.sh** - Terraform variables

## Project Structure

```
notion2config/
├── converters/
│   └── notion-dnsmasq.sh
├── docs/
│   └── notion-dnsmasq.md
├── examples/
│   ├── compute-database-template.md
│   └── dnsmasq-output.conf
└── tests/
    └── validate-notion-access.sh
```

## Notion Setup

1. Create integration at https://www.notion.so/my-integrations
2. Share database with integration
3. Get database ID from URL
4. Set `NOTION_TOKEN` environment variable

## Security

- Store tokens in environment variables or secure credential managers
- Use read-only integration permissions
- Never commit tokens to git

## How to Apply

When working on Notion → config automation tasks:
- Use this project for generating system configs from Notion
- Follow the pattern established by notion-dnsmasq.sh
- All tools should support dry-run mode
- Include validation scripts
- Document database schema requirements
- Support FreeBSD paths
