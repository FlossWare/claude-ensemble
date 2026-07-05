# Build a personal tech library assistant: "What should I read about X?"

**Status:** Open  
**Priority:** High  
**Created:** 2026-07-04  

## Goal

Create an intelligent assistant that recommends PDFs from your library based on learning goals, current knowledge level, and context.

## Context

With 849 PDFs in the library, finding the right book to read for a specific goal is challenging. An assistant should recommend based on:
- What you already know (from past workflows)
- What you're trying to learn
- Difficulty level
- Relevance to current projects

## Implementation

### Core Features

1. **Recommendation Engine**
   - Query: "What should I read about Kubernetes?"
   - Returns: Ordered list with rationale
   - Considers: your experience level, related topics, PDF complexity

2. **Learning Path Builder**
   - Input: Goal (e.g., "learn data engineering")
   - Output: Ordered reading list from beginner → advanced
   - Uses PDF relationships and prerequisites

3. **Context-Aware Suggestions**
   - "I'm working on X, what would help?"
   - Analyzes current workflow context
   - Suggests relevant PDFs

### Technical Stack

```javascript
// API endpoint
POST /api/library-assistant/recommend
{
  "query": "What should I read about Kubernetes?",
  "context": {
    "current_project": "microservices migration",
    "skill_level": "intermediate",
    "time_available": "2 hours"
  }
}

// Response
{
  "recommendations": [
    {
      "pdf": "Kubernetes Best Practices.pdf",
      "relevance": 0.95,
      "rationale": "Matches your intermediate level and covers production patterns",
      "estimated_time": "1.5 hours",
      "prerequisites_met": true
    }
  ]
}
```

### Integration Points

- Semantic search (Issue #001) for concept matching
- Workflow history for skill level inference
- Neo4j for topic relationships
- PDF metadata for complexity estimation

## Example Interactions

**Query:** "I need to learn about distributed systems"

**Response:**
1. **Start with:** "Distributed Systems Fundamentals" (2h read)
   - Why: Covers basics, no prerequisites
2. **Then:** "CAP Theorem in Practice" (1h read)
   - Why: Builds on fundamentals
3. **Advanced:** "Consensus Algorithms Deep Dive" (3h read)
   - Why: After understanding basics

**Query:** "Working on Kafka integration, what should I read?"

**Response:**
1. **"Apache Kafka Essentials"** - Most relevant (0.92 match)
   - Covers integration patterns you'll need
2. **"Event Streaming Architecture"** - Contextual (0.85 match)
   - Background on event-driven design

## Acceptance Criteria

- [ ] Recommendation API endpoint created
- [ ] Query handling with context awareness
- [ ] Learning path builder for multi-PDF sequences
- [ ] Integration with semantic search
- [ ] Rationale provided for each recommendation
- [ ] Skill level detection from workflow history
- [ ] CLI command: `./scripts/library-recommend "topic"`

## Future Enhancements

- Track reading progress
- "Mark as read" to improve future recommendations
- Reading time estimates based on page count
- Prerequisite chains ("read X before Y")
- Integration with workflow execution ("before starting this task, read...")
