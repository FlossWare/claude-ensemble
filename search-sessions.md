---
description: Search all Claude Code sessions using semantic vector search
---

# Search Sessions Skill

Search through all your Claude Code sessions using local embeddings (Red Hat compliant).

## Usage

When the user asks to search sessions, run the search and present results in a clear format.

## Steps

1. Extract the search query from the user's request
2. Run the search using the local search script
3. Parse and present results in a readable format
4. Offer to open specific sessions if requested

## Search Command

```bash
HF_HOME=/exports/ai-models/huggingface ~/bin/search-sessions-local.py "<query>" [limit] [field]
```

Parameters:
- `<query>`: The semantic search query
- `limit`: Number of results (default: 10)
- `field`: Which field to search (title, summary, content)

## Example Searches

```bash
# Basic search
HF_HOME=/exports/ai-models/huggingface ~/bin/search-sessions-local.py "postgres setup" 10

# Title search
HF_HOME=/exports/ai-models/huggingface ~/bin/search-sessions-local.py "API integration" 10 title

# Deep content search
HF_HOME=/exports/ai-models/huggingface ~/bin/search-sessions-local.py "backup disaster recovery" 20 content
```

## Output Format

Present results as:

```
Found X sessions matching "query":

1. [Similarity: 0.850] 2026-06-15 14:30
   Session: abc123...
   Title: Setup PostgreSQL database
   Summary: User asked about setting up PostgreSQL with vector extensions...
   
2. [Similarity: 0.720] 2026-06-10 09:15
   Session: def456...
   Title: Database backup strategy
   Summary: Discussion about automated backups to NAS...
```

Then offer: "Would you like me to open any of these sessions or search for something else?"

## Notes

- All searches use LOCAL embeddings (no API calls)
- Red Hat compliant (Anthropic only on laptop-01)
- Model: all-MiniLM-L6-v2 (384 dims)
- Storage: /exports/ai-models/huggingface/
