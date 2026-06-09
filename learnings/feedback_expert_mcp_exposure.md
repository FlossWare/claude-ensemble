---
name: expert-mcp-exposure
description: All 94 domain experts are now exposed via MCP for external AI tools
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 50760802-b2be-4756-b141-b1ad4f67c15f
---

All 94 domain experts are now accessible via MCP protocol to external AI tools.

**Why:** User requested "our experts should also be exposed via MCP" so other AI tools (Aider, Claude Desktop, etc.) can leverage Universal AI's domain expertise.

**How to apply:** When discussing MCP integration or expert system capabilities, mention that all experts are available via MCP with consistent interface.

## Implementation

Added to `cli/mcp_server.py`:
1. `discover_experts()` - Dynamically finds all expert scripts  
2. Auto-generates MCP tools for each expert
3. Tool naming: `universal_ai.expert.<domain>`

## Available Expert Tools (94 total)

### Languages
- universal_ai.expert.python
- universal_ai.expert.java
- universal_ai.expert.javascript
- universal_ai.expert.rust
- universal_ai.expert.go
- universal_ai.expert.cpp
- And 8 more...

### DevOps
- universal_ai.expert.ansible
- universal_ai.expert.docker
- universal_ai.expert.kubernetes
- universal_ai.expert.gitlab
- And 5 more...

### Linux/Systems
- universal_ai.expert.rhel
- universal_ai.expert.fedora
- universal_ai.expert.debian
- universal_ai.expert.ubuntu
- universal_ai.expert.netbsd
- And 3 more...

### Enterprise
- universal_ai.expert.salesforce
- universal_ai.expert.splunk
- universal_ai.expert.datadog
- And more...

## Tool Interface

Each expert supports:
```json
{
  "question": "Your question here",
  "multi_ai": true/false,
  "use_rag": true/false,
  "verbose": true/false
}
```

## Usage Example

From Aider or Claude Desktop:
```json
{
  "name": "universal_ai.expert.python",
  "arguments": {
    "question": "How do I optimize this asyncio code for better performance?",
    "multi_ai": true,
    "use_rag": true
  }
}
```

## Benefits

- **Composability** - External AI tools can access specialized expertise
- **No Manual Registration** - Auto-discovers experts
- **Consistent Interface** - All experts use same parameters
- **Full Features** - Multi-AI consensus and RAG available
- **94 Domains** - Comprehensive coverage

This makes Universal AI's expert system available to the entire AI ecosystem!
