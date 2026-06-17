# Deep Code Analysis: sf-precise-deploy

**Analysis Date:** 2026-06-16
**Repository:** solenopsis/sf-precise-deploy

## 1. Repository Structure

```
.
├── messages
│   ├── precise.delta.md
│   ├── precise.deploy.md
│   └── precise.git-delta.md
├── src
│   ├── commands
│   │   └── precise
│   ├── lib
│   │   ├── destructive-changes-generator.ts
│   │   ├── field-diff-engine.ts
│   │   ├── git-integration.ts
│   │   └── metadata-parser.ts
│   └── index.ts
├── test
│   └── lib
│       ├── destructive-changes-generator.test.ts
│       ├── error-handling.test.ts
│       ├── field-diff-engine.test.ts
│       ├── git-integration.test.ts
│       └── metadata-parser.test.ts
├── test-data
│   ├── source
│   │   ├── classes
│   │   ├── flows
│   │   ├── objects
│   │   └── workflows
│   └── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── DEVELOPMENT.md
├── LICENSE
├── package.json
├── QUICKSTART.md
├── README.md
├── SUMMARY.md
└── tsconfig.json

14 directories, 23 files
```

**File Statistics:**
- Total files: 35
- Java files: 0
- XML files: 2
- Python files: 0
- JavaScript files: 13

## 2. Architecture & Code Patterns

**Build System:**
- npm/Node.js (package.json found)

**Key Packages/Modules:**
- src/commands
- src/commands/precise
- src/lib

**Design Patterns Detected:**
- Pattern usage: 0 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 0

**Documentation:**
- README.md (147 lines)
- Javadoc annotations: 0

**Code Metrics:**

## 4. Key Files Deep Dive

### README.md
```markdown
# sf-precise-deploy

[![CI](https://github.com/solenopsis/sf-precise-deploy/actions/workflows/ci.yml/badge.svg)](https://github.com/solenopsis/sf-precise-deploy/actions/workflows/ci.yml)
[![npm version](https://badge.fury.io/js/%40flossware%2Fsf-precise-deploy.svg)](https://www.npmjs.com/package/@flossware/sf-precise-deploy)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Salesforce CLI plugin for surgical deployments with field-level delta detection.

## Why?

Modern Salesforce deployment tools (SF CLI, sfdx-git-delta) detect changes at the **file level**. If you modify one field in an object with 200 fields, you deploy the entire object file.

**sf-precise-deploy** analyzes metadata at the **field level**, enabling surgical deployments:
- 🎯 Deploy only the fields that changed
- 🔪 Generate field-level destructive changes
- ⚡ Reduce deployment conflicts and time
- 🔄 Git-based or directory-based comparison
- 🛡️ Comprehensive error handling

## Features

### 🎯 Field-Level Delta Detection
Parses metadata XML to detect changes within files:
- CustomField
- ValidationRule
- RecordType
- WorkflowRule
- And more...

### 🔪 Surgical Destructive Changes
...
```

### Top 5 Largest Source Files
-  (0 lines)

---
**Analysis Complete**
