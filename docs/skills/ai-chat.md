---
name: ai-chat
description: Interactive multi-AI chat session that stays active until you exit
---

# AI Chat - Interactive Multi-Model Conversation

Stay in continuous chat mode with multi-AI consensus responses. Perfect for brainstorming, exploring topics, or having back-and-forth conversations with multiple AI perspectives.

## Features

- **Continuous Mode**: Stays active until you type "exit" - no need to re-invoke
- **Multi-AI Consensus**: Every response synthesized from opus/sonnet/haiku
- **Visible Mode Indicator**: Clear display showing you're in AI chat mode
- **Conversation History**: Maintains context across all turns in the session
- **Attribution Tracking**: See which models contributed what insights
- **Conflict Detection**: Alerts when models disagree on key points

## Usage

```bash
# Start interactive chat
claude run ai-chat

# Start with an initial question
claude run ai-chat "What's the best way to structure a Node.js API?"

# Via skill invocation
/ai-chat
```

## During Chat

- **Ask questions** naturally - just type and press enter
- **See consensus** from all models with attribution
- **Exit commands**: Type `exit`, `quit`, `q`, `bye`, or `done`

## Example Session

```
🤖 AI Chat Mode | Workers: opus, sonnet, haiku (3 models)
📝 Type your questions below. Type "exit" to leave chat mode.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 Turn #1
You: What's the difference between REST and GraphQL?

🔄 Consulting 3 AI models...
✅ Received 3/3 responses

⚖️ Arbiter synthesizing best answer...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI (HIGH consensus from 3 models):

REST and GraphQL are both API architectures but differ fundamentally:

**REST**:
- Multiple endpoints (one per resource)
- Fixed response structure
- Over-fetching common (get full object even if you need 2 fields)
- Under-fetching requires multiple requests
- HTTP verbs (GET, POST, PUT, DELETE)

**GraphQL**:
- Single endpoint
- Client specifies exact fields needed
- No over/under-fetching (request exactly what you need)
- Strongly typed schema
- Real-time subscriptions built-in

**When to use:**
- REST: Simpler APIs, caching is critical, standard CRUD operations
- GraphQL: Complex data requirements, mobile apps (minimize bandwidth), frequent schema changes

📊 Attribution:
  • opus: Schema typing, real-time subscriptions
  • sonnet: Over/under-fetching explanation, use case recommendations
  • haiku: HTTP verbs, endpoint structure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 Turn #2
You: exit

👋 Ending AI chat session after 2 turns.
```

## Modes

### Consensus Levels

- **HIGH**: All models agree on key points (high confidence)
- **MEDIUM**: Majority agreement with some variations
- **LOW**: Significant disagreements between models (shows conflicts)

### Model Rotation

The arbiter role rotates each turn to ensure balanced synthesis:
- Turn 1: Opus arbitrates
- Turn 2: Sonnet arbitrates
- Turn 3: Haiku arbitrates
- Turn 4: Back to Opus...

## Benefits

- **Better answers** through consensus vs single model
- **Diverse perspectives** catch blind spots
- **Context preservation** across conversation
- **Visual mode indicator** so you always know you're in chat mode
- **No repeated invocation** - stays active until you exit

## Comparison to `/ai-prompt`

| Feature | `/ai-prompt` | `/ai-chat` |
|---------|-------------|-----------|
| Mode | Single question | Continuous conversation |
| Context | No history | Full conversation history |
| Exit | Auto-exits after answer | Stays until you type "exit" |
| Indicator | No visible mode | Clear "AI Chat Mode" header |
| Use case | One-off questions | Back-and-forth discussion |

## Technical Details

- Uses arbiter/worker pattern from ai-prompt
- Conversation history limited to last 5 turns (context window management)
- Worker failures handled gracefully (continues with available models)
- Session history returned on exit (can be logged/analyzed)

## Future Enhancements

- [ ] Save conversation history to file
- [ ] Resume previous chat sessions
- [ ] Voice mode integration
- [ ] Custom worker selection per session
- [ ] Export chat as markdown
