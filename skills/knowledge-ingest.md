# Knowledge Ingest - Universal Documentation Learning

Learn from any documentation format using multi-AI consensus.

## Usage

```bash
/knowledge-ingest --source=/path/to/doc.pdf
/knowledge-ingest --source=/path/to/README.md
/knowledge-ingest --source=https://docs.example.com
```

## Concepts Borrowed from knowledge-ai

This workflow **prototypes ideas** from the FlossWare knowledge-ai project:
- Universal format detection (PDF, Markdown, HTML, code)
- Multi-AI fact extraction with consensus validation
- Semantic chunking for retrieval
- Vector-friendly storage in global memory

`.claude` is the **testing ground** - ideas proven here can flow back to knowledge-ai.

## What It Does

1. **Detect** - Identify format and structure automatically
2. **Extract** - Workers (Opus, Sonnet, GPT-4o) extract facts independently
3. **Validate** - Arbiter synthesizes consensus, rejects low-agreement facts
4. **Chunk** - Organize facts into semantic chunks (500-1000 chars)
5. **Store** - Save in global memory with concept tagging

## Output

Knowledge stored in `memory/knowledge-*.md` files:
- Concept-tagged for retrieval
- Markdown-formatted for readability
- Consensus-validated for accuracy
- Vector-friendly chunk sizes

## Testing Ideas

Use this to prototype:
- Chunking strategies
- Fact extraction prompts
- Consensus thresholds
- Storage formats
- RAG retrieval patterns

Learnings feed back into FlossWare AI projects.

## Related

- FlossWare: knowledge-ai (production library)
- FlossWare: consensus-ai (multi-model consensus)
- FlossWare: vectordb-ai (vector storage)
- `/ai-learn` - Extract learnings from sessions
