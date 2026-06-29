# AI Prompt - Multi-Model Consensus for Any Question

Get multiple AI perspectives on any question using arbiter/worker consensus pattern.

## Features

- **Multi-Model Responses** - Opus, Sonnet, Haiku, Gemini respond independently in parallel
- **Graceful Fallback** - If Gemini fails or is unavailable, continues with Claude models
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

1. **Multi-Model Response** - Up to 4 AI models (Opus, Sonnet, Haiku, Gemini) independently answer your question in parallel
2. **Graceful Degradation** - If any model fails (e.g., Gemini unavailable), continues with successful models
3. **Arbiter Synthesis** - Opus reviews all answers and synthesizes the best response
4. **Consensus Analysis** - Shows agreement levels and key points from all responding models
5. **Final Answer** - Unified response incorporating all perspectives

## Output Format

```
📊 Multi-Model Consensus Results

Consensus Level: HIGH (4/4 models agreed)
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

Gemini contributed:
  - Alternative approaches
  - Integration considerations
```

## Example

```bash
$ /ai-prompt How should I structure this microservices architecture?

🤖 Getting responses from Opus, Sonnet, Haiku, Gemini...
✅ Received responses from all 4 models

⚖️ Arbiter synthesizing best answer...
✅ Synthesis complete (high consensus)

📊 Results:
Consensus: HIGH (4/4 agreed)
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

- **HIGH** - All responding models agree (4/4 or 3/3)
- **MEDIUM** - Majority agree (3/4, 2/3)
- **LOW** - Models disagree (split or 1/4, 1/3)

Note: If Gemini is unavailable, consensus is calculated from the 3 Claude models that respond.

## Benefits vs Single Model

**Single Model**:
- One perspective
- May miss edge cases
- Potential bias

**Multi-Model Consensus (4 models)**:
- Multiple perspectives (Opus, Sonnet, Haiku, Gemini)
- More comprehensive coverage
- Catches edge cases from different model architectures
- Higher confidence through consensus
- Shows areas of disagreement
- Gracefully handles model unavailability

## Files

- `~/.claude/workflows/ai-prompt.js`
- `~/.claude/skills/ai-prompt.md`
- Uses `~/.claude/workflows/shared/consensus-engine.js`

## Model Availability

- **Claude Models (Opus, Sonnet, Haiku)**: Always available
- **Gemini**: Optional - gracefully skipped if unavailable
  - Requires Google AI API or MCP configuration
  - If it fails, workflow continues with 3 Claude models
  - No error thrown, just logged as unavailable

---

**Version**: 2.0  
**Created**: 2026-06-03  
**Updated**: 2026-06-08 - Added Gemini support with graceful fallback  
**Global**: Works for any question
