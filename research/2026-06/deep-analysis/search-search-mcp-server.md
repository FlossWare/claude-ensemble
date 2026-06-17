# Deep Code Analysis: search-mcp-server

**Analysis Date:** 2026-06-16
**Repository:** search-engineering/search-mcp-server

## 1. Repository Structure

```
.
├── deployment
│   └── openshift
│       ├── buildconfig.yaml
│       ├── configmap.yaml
│       ├── deployment.yaml
│       ├── imagestream.yaml
│       ├── kustomization.yaml
│       ├── route.yaml
│       ├── secret.yaml
│       └── service.yaml
├── docs
│   ├── architecture.md
│   ├── authentication.md
│   ├── ci-cd.md
│   ├── deployment.md
│   ├── development.md
│   └── tutorial.md
├── examples
│   ├── fastmcp_client.py
│   └── README.md
├── template_mcp_server
│   ├── src
│   │   ├── assets
│   │   ├── clients
│   │   ├── config
│   │   ├── models
│   │   ├── oauth
│   │   ├── storage
│   │   ├── tools
│   │   ├── api.py
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── mcp.py
│   │   ├── README.md
│   │   ├── search_settings.py
│   │   ├── settings.py
│   │   └── validators.py
│   ├── utils
│   │   ├── __init__.py
│   │   └── pylogger.py
│   ├── __init__.py
│   └── py.typed
├── tests
│   ├── conftest.py
│   ├── README.md
│   ├── test_api.py
│   ├── test_basic.py
│   ├── test_compliance_search_tool.py
│   ├── test_cve_filters_tool.py
│   ├── test_cve_search_tool.py
│   ├── test_docs_search_tool.py
│   ├── test_errata_filters_tool.py
│   ├── test_errata_search_tool.py
│   ├── test_hydra_client.py
│   ├── test_kbase_search_tool.py
│   ├── test_lifecycle_search_tool.py
│   ├── test_main.py
│   ├── test_mcp.py
│   ├── test_oauth_controller.py
│   ├── test_oauth_handler.py
│   ├── test_oauth_service.py
│   ├── test_product_aliases.py
│   ├── test_search_unified_tool.py
│   ├── test_settings.py
│   ├── test_solr_client.py
│   ├── test_storage_init.py
│   ├── test_storage_service.py
│   ├── test_utils.py
│   ├── test_validators.py
│   └── test_vector_client.py
├── catalog-info.yaml
├── CHANGELOG.md
├── compose.yaml
├── Containerfile
├── CONTRIBUTING.md
├── LICENSE
├── Makefile
├── pyproject.toml
├── README.md
├── SEARCH_ARCHITECTURE.md
├── SECURITY.md
├── TEAM_WORKFLOW.md
└── UPSTREAM_TEMPLATE.md

16 directories, 68 files
```

**File Statistics:**
- Total files: 98
- Java files: 0
- XML files: 0
- Python files: 63
- JavaScript files: 0

## 2. Architecture & Code Patterns

**Build System:**

**Key Packages/Modules:**

**Design Patterns Detected:**
- Pattern usage: 0 occurrences

## 3. Code Quality Analysis

**Testing:**
- Test files: 25

**Documentation:**
- README.md (327 lines)
- docs/ directory exists
- Javadoc annotations: 0

**Code Metrics:**

## 4. Key Files Deep Dive

### README.md
```markdown
# Search MCP Server

A Search MCP Server that exposes Red Hat search capabilities as MCP tools backed by Apache Solr. Built on the [Red Hat template MCP server](https://github.com/redhat-data-and-ai/template-mcp-server) ([upstream template docs](UPSTREAM_TEMPLATE.md)), it adds a shared Solr client, query validation, standardized response models, and optional vector reranking.

## Current MCP Tools

| Tool                    | Description                                                                                                                                       |
|-------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| **`search_unified`**    | Unified cross-type search across all Red Hat content (edismax, optional semantic reranking, documentKind filtering, faceted discovery)            |
| **`search_kbase`**      | Search Red Hat Knowledge Base articles and solutions (edismax, optional semantic reranking, product filtering, faceted product discovery)         |
| **`search_docs`**       | Search Red Hat product documentation, English multipage only (edismax, optional semantic reranking, product filtering, faceted product discovery) |
| **`search_cve`**        | Search Red Hat CVE records (edismax, optional semantic reranking, severity filtering, product/fix-state filtering, faceted severity discovery, sort by severity/date)          |
| **`get_cve_filters`**   | Discover available product names and fix states for CVE searches (facets from platform_state_string on CVE documents). Accepts optional `product_search` with alias expansion from `product_aliases.yaml` (e.g. "rhel" → "Red Hat Enterprise Linux", "ocp" → "OpenShift Container Platform") |
| **`search_errata`**     | Search Red Hat Errata records (edismax, optional semantic reranking, `portal_product_filter` segment fields with `*`-style wildcards: product/product_variant/product_version/product_architecture, plus advisory/severity/publication, faceted discovery)  |
| **`get_errata_filters`**| Facets for the four `portal_product_filter` segment labels (`product`, variant, version, arch) from PortalProduct. Accepts optional `product_search` with alias expansion from `product_aliases.yaml` |
| **`search_lifecycle`**  | Search product lifecycle events — support phases, release dates, end-of-life (EOL) schedules, version timelines, retirement dates (edismax with PLC-specific field boosts, product filtering, faceted product discovery) |
| **`search_compliance`** | Search Red Hat Compliance records (edismax, optional semantic reranking, product/region/industry filtering, faceted discovery)                    |


## Local Development Setup

### Prerequisites

- Python 3.12.x (tested with 3.12.11)
- [`uv`](https://docs.astral.sh/uv/) package manager (or `pip` if preferred)

### Step 1: Clone the repo and enter the directory

```bash
cd /path/to/search-mcp-server
...
```

### Top 5 Largest Source Files
- ./tests/test_oauth_controller.py (1284 lines)
- ./tests/test_oauth_service.py (1115 lines)
- ./tests/test_storage_service.py (1040 lines)
- ./template_mcp_server/src/oauth/controller.py (598 lines)
- ./tests/test_utils.py (580 lines)

---
**Analysis Complete**
