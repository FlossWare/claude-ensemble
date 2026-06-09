---
name: reference-repositories
description: GitHub repositories and package management for Solenopsis/FlossWare projects
metadata: 
  node_type: memory
  type: reference
  originSessionId: a575e68b-00c2-4b26-9226-a3cc67abcc1d
---

**GitHub Repositories:**
- FlossWare JCommons: https://github.com/FlossWare/jcommons (renamed from commons)
- Solenopsis SOAP: https://github.com/solenopsis/soap
- Solenopsis Session: https://github.com/solenopsis/session

**Local Paths:**
- JCommons: `/home/sfloess/Development/github/FlossWare/jcommons` (renamed from commons)
- SOAP: `/home/sfloess/Development/github/solenopsis/soap`
- Session: `/home/sfloess/Development/github/solenopsis/session`

**Package Distribution:**
- Maven repository: https://packagecloud.io/flossware/java/maven2
- Deployed automatically via GitHub Actions on push to main
- CI/CD auto-bumps minor version and creates git tags

**GitHub Actions:**
- Workflow file: `.github/workflows/main.yml` (all projects)
- Secrets: `PACKAGECLOUD_TOKEN` (JCommons), `FLOSSWARE_PACKAGECLOUD_TOKEN` (SOAP, Session)
- Auto-commit email: version-bump@flossware.org (JCommons), version-bump@solenopsis.org (SOAP, Session)

**Documentation:**
- Each project has comprehensive README.md and CHANGELOG.md
- READMEs include installation, usage examples, architecture, requirements
- CHANGELOGs follow Keep a Changelog format with upgrade guides
