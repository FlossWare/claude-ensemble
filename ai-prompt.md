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

# Technical decision
/ai-prompt What's the best way to handle real-time updates?
```

## How It Works

1. **Multi-Model Response** - 3 AI models independently answer your question
2. **Arbiter Synthesis** - Opus reviews all answers and synthesizes the best response
3. **Consensus Analysis** - Shows agreement levels and key points
4. **Final Answer** - Unified response incorporating all perspectives

## Output Format

```
📊 Multi-Model Consensus Results

Consensus Level: HIGH (3/3 models agreed)
Final Confidence: 95%

## Synthesized Answer
[Unified answer incorporating all models]

## Areas of Agreement
1. Use JWT tokens for authentication
2. Implement refresh token rotation
3. Store sessions in Redis

## Individual Model Contributions
Opus contributed:
  - Detailed security considerations
  - Token expiration strategy

Sonnet contributed:
  - Implementation patterns
  - Edge case handling

Haiku contributed:
  - Performance optimization
  - Concise best practices
```

## Example

```bash
$ /ai-prompt How should I structure this microservices architecture?

🤖 Getting responses from Opus, Sonnet, Haiku...
✅ Received responses from 3 models

⚖️ Arbiter synthesizing best answer...
✅ Synthesis complete (high consensus)

📊 Results:
Consensus: HIGH (3/3 agreed)
Confidence: 92%

Synthesized Answer:
Based on consensus from all models, here's the recommended structure:

1. API Gateway pattern (all 3 models agreed)
2. Event-driven communication via message queue
3. Separate databases per service
4. Centralized logging and monitoring
...
```

## Use Cases

- **Architecture Decisions** - Get multiple perspectives on design
- **Technical Questions** - Consensus on best practices
- **Code Reviews** - Multiple viewpoints on approach
- **Problem Solving** - Diverse solutions to problems
- **Learning** - See how different models approach same question

## Consensus Levels

- **HIGH** - All 3 models agree (3/3)
- **MEDIUM** - Majority agree (2/3)
- **LOW** - Models disagree (1/3 or split)

## Benefits vs Single Model

**Single Model**:
- One perspective
- May miss edge cases
- Potential bias

**Multi-Model Consensus**:
- Multiple perspectives
- More comprehensive
- Catches edge cases
- Higher confidence
- Shows areas of disagreement

## Files

- `~/.claude/workflows/ai-prompt.js`
- `~/.claude/skills/ai-prompt.md`
- Uses `~/.claude/workflows/shared/consensus-engine.js`

---

**Version**: 1.0  
**Created**: 2026-06-03  
**Global**: Works for any question
