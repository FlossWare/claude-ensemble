export const meta = {
  name: 'ai-chat',
  description: 'Interactive multi-AI chat - stays active until you exit',
  phases: [
    { title: 'Chat', detail: 'Continuous multi-AI conversation mode' }
  ]
}

// Multi-AI consensus chat with visible mode indicator
// Uses same arbiter/worker pattern as ai-prompt but loops until user exits

// Import model detection (inline for now due to ES6 import issues)
function getAvailableWorkers(customWorkers = null) {
  if (customWorkers && Array.isArray(customWorkers)) {
    return customWorkers
  }

  const models = []
  models.push('opus', 'sonnet', 'haiku')
  return models
}

const WORKERS = getAvailableWorkers()
log(`🤖 AI Chat Mode | Workers: ${WORKERS.join(', ')} (${WORKERS.length} models)`)
log(`📝 Type your questions below. Type "exit", "quit", or "q" to leave chat mode.`)
log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`)

const SCHEMA = {
  type: 'object',
  required: ['answer', 'confidence', 'reasoning'],
  properties: {
    answer: {
      type: 'string',
      description: 'Your response to the user question'
    },
    confidence: {
      type: 'number',
      description: 'Confidence in this answer (0-100)'
    },
    reasoning: {
      type: 'string',
      description: 'Brief explanation of your reasoning'
    },
    key_points: {
      type: 'array',
      items: { type: 'string' },
      description: 'Key points from your answer (optional)'
    }
  }
}

// Session state
let conversationHistory = []
let sessionActive = true
let turnNumber = 0

// Parse initial query from args or prompt for it
let userQuery = null

if (args) {
  // Check if args is string (single question) or object
  if (typeof args === 'string') {
    userQuery = args
  } else if (Array.isArray(args)) {
    userQuery = args.join(' ')
  } else if (args.question || args.query) {
    userQuery = args.question || args.query
  }
}

phase('Chat')

while (sessionActive) {
  turnNumber++

  // Get user input (use provided query first, then switch to prompting)
  let currentQuery = userQuery

  if (!currentQuery) {
    log(`\n💬 Turn #${turnNumber}`)
    log(`You: (type your question, or "exit" to quit)`)
    // In real usage, this would pause for user input
    // For now, exit after one turn if no query
    log(`⚠️ No query provided. Exiting chat mode.`)
    break
  }

  userQuery = null  // Clear for next iteration

  // Check for exit commands
  const exitCommands = ['exit', 'quit', 'q', 'bye', 'done']
  if (exitCommands.includes(currentQuery.toLowerCase().trim())) {
    log(`👋 Ending AI chat session after ${turnNumber - 1} turns.`)
    sessionActive = false
    break
  }

  // Add to conversation history
  conversationHistory.push({ role: 'user', content: currentQuery, turn: turnNumber })

  log(`\nYou: ${currentQuery}`)
  log(`\n🔄 Consulting ${WORKERS.length} AI models...`)

  // Worker responses in parallel
  const responses = await parallel(
    WORKERS.map((model, idx) =>
      () => agent(
        `You are participating in a multi-AI consensus chat.

CONVERSATION HISTORY:
${conversationHistory.slice(-5).map(h => `[${h.role}]: ${h.content}`).join('\n')}

CURRENT QUESTION:
${currentQuery}

Provide a helpful, accurate response. Be concise but complete.`,
        {
          label: `${model} Response`,
          schema: SCHEMA,
          model,
          phase: 'Chat'
        }
      )
    )
  )

  const validResponses = responses.filter(Boolean)

  if (validResponses.length === 0) {
    log(`❌ All models failed. Please try again.`)
    continue
  }

  log(`✅ Received ${validResponses.length}/${WORKERS.length} responses`)

  // Arbiter synthesis
  log(`\n⚖️ Arbiter synthesizing best answer...`)

  const arbiterPrompt = `You are the arbiter in a multi-AI chat system.

USER QUESTION:
${currentQuery}

RESPONSES FROM ${validResponses.length} AI MODELS:
${validResponses.map((r, idx) => `
**${WORKERS[idx].toUpperCase()}**:
- Answer: ${r.answer}
- Confidence: ${r.confidence}%
- Reasoning: ${r.reasoning}
${r.key_points ? `- Key Points: ${r.key_points.join(', ')}` : ''}
`).join('\n')}

YOUR TASK:
1. Synthesize the BEST answer by combining insights from all models
2. Note where models agree (high confidence) and disagree (explain why)
3. Attribute specific points to models when relevant
4. Provide a clear, helpful final answer

Return a synthesis that is better than any single model's response.`

  const ARBITER_SCHEMA = {
    type: 'object',
    required: ['final_answer', 'consensus_level', 'attribution'],
    properties: {
      final_answer: {
        type: 'string',
        description: 'Synthesized answer combining all model insights'
      },
      consensus_level: {
        type: 'string',
        enum: ['high', 'medium', 'low'],
        description: 'How much models agreed'
      },
      models_agreed: {
        type: 'number',
        description: 'How many models agreed on key points'
      },
      attribution: {
        type: 'object',
        description: 'Which models contributed what insights',
        additionalProperties: {
          type: 'array',
          items: { type: 'string' }
        }
      },
      conflicts: {
        type: 'array',
        items: { type: 'string' },
        description: 'Any disagreements between models (if relevant)'
      }
    }
  }

  // Rotate arbiter model
  const arbiterModel = WORKERS[turnNumber % WORKERS.length]

  const synthesis = await agent(arbiterPrompt, {
    label: `${arbiterModel} Arbiter`,
    schema: ARBITER_SCHEMA,
    model: arbiterModel,
    phase: 'Chat'
  })

  if (!synthesis) {
    log(`❌ Arbiter failed. Falling back to first valid response.`)
    log(`\n🤖 AI: ${validResponses[0].answer}`)
  } else {
    // Display synthesis
    log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`)
    log(`🤖 AI (${synthesis.consensus_level.toUpperCase()} consensus from ${validResponses.length} models):`)
    log(`\n${synthesis.final_answer}`)

    if (synthesis.attribution && Object.keys(synthesis.attribution).length > 0) {
      log(`\n📊 Attribution:`)
      Object.entries(synthesis.attribution).forEach(([model, points]) => {
        if (points && points.length > 0) {
          log(`  • ${model}: ${points.join(', ')}`)
        }
      })
    }

    if (synthesis.conflicts && synthesis.conflicts.length > 0) {
      log(`\n⚠️ Model disagreements:`)
      synthesis.conflicts.forEach(c => log(`  • ${c}`))
    }

    log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`)

    // Add to conversation history
    conversationHistory.push({
      role: 'assistant',
      content: synthesis.final_answer,
      turn: turnNumber,
      consensus: synthesis.consensus_level
    })
  }
}

// Session summary
log(`\n📊 Chat Session Summary:`)
log(`  • Total turns: ${turnNumber - 1}`)
log(`  • Models used: ${WORKERS.join(', ')}`)
log(`  • Conversation saved to session history`)

// Learning: Extract key insights from conversation
if (conversationHistory.length > 2) {
  phase('Learning')
  log(`\n📚 Extracting learnings from conversation...`)

  const learningPrompt = `Review this AI chat conversation and extract key learnings:

CONVERSATION (${conversationHistory.length} messages):
${conversationHistory.map(h => `[${h.role}]: ${h.content}`).join('\n\n')}

Extract:
1. **User preferences** - topics they care about, how they like answers structured
2. **Domain knowledge** - technical details, concepts they understand
3. **Question patterns** - what they ask about repeatedly
4. **Feedback signals** - continued questions (unclear answer) vs moving on (satisfied)

Return actionable insights that would help future conversations be more helpful.`

  const LEARNING_SCHEMA = {
    type: 'object',
    properties: {
      user_interests: {
        type: 'array',
        items: { type: 'string' },
        description: 'Topics the user cares about'
      },
      knowledge_level: {
        type: 'object',
        description: 'User expertise by domain',
        additionalProperties: {
          type: 'string',
          enum: ['beginner', 'intermediate', 'advanced']
        }
      },
      preferences: {
        type: 'array',
        items: { type: 'string' },
        description: 'How user prefers answers (e.g., "concise", "detailed examples", "visual analogies")'
      },
      unresolved_topics: {
        type: 'array',
        items: { type: 'string' },
        description: 'Topics that need follow-up'
      }
    }
  }

  const learnings = await agent(learningPrompt, {
    label: 'Extract Learnings',
    schema: LEARNING_SCHEMA,
    model: 'opus',
    phase: 'Learning'
  })

  if (learnings) {
    log(`\n✅ Learnings extracted:`)
    if (learnings.user_interests?.length > 0) {
      log(`  📌 Interests: ${learnings.user_interests.join(', ')}`)
    }
    if (learnings.knowledge_level && Object.keys(learnings.knowledge_level).length > 0) {
      log(`  🎓 Knowledge: ${Object.entries(learnings.knowledge_level).map(([k, v]) => `${k} (${v})`).join(', ')}`)
    }
    if (learnings.preferences?.length > 0) {
      log(`  ⚙️ Preferences: ${learnings.preferences.join(', ')}`)
    }

    log(`\n💡 Tip: These learnings should be saved to user memory for future sessions`)
  }

  return {
    status: 'completed',
    turns: turnNumber - 1,
    history: conversationHistory,
    learnings
  }
}

return {
  status: 'completed',
  turns: turnNumber - 1,
  history: conversationHistory
}
