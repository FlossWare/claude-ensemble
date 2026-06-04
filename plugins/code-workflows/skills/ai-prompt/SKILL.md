---
name: ai-prompt
description: This skill should be used when the user asks for "multiple AI perspectives", "consensus opinion", "multi-model answer", or wants diverse AI viewpoints on architecture, design decisions, or technical questions.
version: 1.0.0
---

# AI Prompt - Multi-Model Consensus for Any Question

Get multiple AI perspectives on any question using arbiter/worker consensus pattern.

## Features

- **Multi-Model Responses** - Opus, Sonnet, Haiku respond independently
- **Arbiter Synthesis** - Best answer synthesized from all perspectives
- **Consensus Tracking** - Shows areas of agreement/disagreement
- **Attribution** - See which model contributed what
- **Universal** - Works for ANY prompt/question

## Usage

```bash
# Architecture question
/ai-prompt How should I architect this authentication system?

# Design decision
/ai-prompt Should I use REST or GraphQL for this API?

# Code review question
/ai-prompt Is this approach to caching optimal?
```

## How It Works

1. **Multi-Model Response** - 3 AI models independently answer your question
2. **Arbiter Synthesis** - Opus reviews all answers and synthesizes the best response
3. **Consensus Analysis** - Shows agreement levels and key points
4. **Final Answer** - Unified response incorporating all perspectives

## Consensus Levels

- **HIGH** - All 3 models agree (3/3)
- **MEDIUM** - Majority agree (2/3)
- **LOW** - Models disagree (1/3 or split)

## Use Cases

- **Architecture Decisions** - Get multiple perspectives on design
- **Technical Questions** - Consensus on best practices
- **Code Reviews** - Multiple viewpoints on approach
- **Problem Solving** - Diverse solutions to problems

---

**Version**: 1.0  
**Created**: 2026-06-03
