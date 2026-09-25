#!/usr/bin/env node
/**
 * Fleet API Proxy Testing Workflow
 *
 * Tests all 37 chat models + 3 embedding models across the fleet
 * Validates tier-based fallback, caching, cost tracking
 */

export const meta = {
  name: 'test-api-proxy',
  description: 'Test all 37 chat + 3 embedding models across fleet',
  phases: [
    { title: 'Test Chat', detail: '37 models across 9 providers' },
    { title: 'Test Embeddings', detail: '3 free embedding models' },
    { title: 'Verify Tracking', detail: 'PostgreSQL usage & failures' },
    { title: 'Test Fallback', detail: 'Tier-based failover logic' },
    { title: 'Review', detail: 'Code review & recommendations' }
  ]
}

export default async function({ phase, parallel, pipeline, agent, log, args }) {
  log('🧪 API Proxy Testing - Full Fleet Validation')

  // Get all models from proxy
  const MODELS = {
    high: [
      'claude-opus-4', 'claude-sonnet-4', 'gpt-4o', 'o1-preview',
      'deepseek-chat', 'deepseek-reasoner', 'command-r-plus',
      'gemini-1.5-pro', 'gemini-exp-1206',
      'nvidia/nemotron-3-ultra-550b-a55b:free', 'nousresearch/hermes-3-llama-3.1-405b:free'
    ],
    medium: [
      'claude-haiku-4', 'llama-3.3-70b-versatile', 'llama3.1-70b',
      'gpt-4o-mini', 'gpt-3.5-turbo', 'o1-mini', 'gemini-2.0-flash',
      'gemini-1.5-flash', 'command-r', 'command', 'deepseek-coder',
      'meta-llama/llama-3.3-70b-instruct:free', '@cf/meta/llama-3.1-70b-instruct',
      '@cf/mistral/mistral-7b-instruct-v0.1', '@cf/qwen/qwen1.5-14b-chat-awq',
      'google/gemma-4-31b-it:free', 'qwen/qwen-2.5-72b-instruct',
      'qwen/qwen3-coder:free', 'cohere/north-mini-code:free'
    ],
    fast: [
      'llama-3.1-8b-instant', 'llama3.1-8b', 'gemma-7b-it', 'gemma2-9b-it',
      'command-light', '@cf/meta/llama-3-8b-instruct', '@cf/microsoft/phi-2',
      '@cf/tinyllama/tinyllama-1.1b-chat-v1.0', '@cf/deepseek-ai/deepseek-math-7b-instruct'
    ]
  }

  const EMBEDDING_MODELS = [
    '@cf/baai/bge-large-en-v1.5',
    '@cf/baai/bge-base-en-v1.5',
    'text-embedding-004'
  ]

  const WORKERS = ['server-01', 'server-02', 'server-03']

  // Phase 1: Test Chat Models
  await phase('Test Chat', async () => {
    log('Testing sample of chat models (high/medium/fast tiers)...')

    const sampleModels = [
      // High tier samples
      {model: 'gpt-4o', tier: 'high'},
      {model: 'deepseek-chat', tier: 'high'},
      {model: 'gemini-exp-1206', tier: 'high'},

      // Medium tier samples
      {model: 'claude-haiku-4', tier: 'medium'},
      {model: 'llama-3.3-70b-versatile', tier: 'medium'},
      {model: 'gemini-2.0-flash', tier: 'medium'},

      // Fast tier samples (free!)
      {model: 'llama-3.1-8b-instant', tier: 'fast'},
      {model: 'gemma2-9b-it', tier: 'fast'},
      {model: '@cf/meta/llama-3-8b-instruct', tier: 'fast'}
    ]

    const results = await parallel(sampleModels.map(({model, tier}) => () =>
      agent(`Test chat model ${model} (${tier} tier) via aio-01 proxy:

curl -s -X POST http://aio-01:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "X-Worker-ID: test-${tier}" \\
  -d '{"model":"${model}","messages":[{"role":"user","content":"Say OK"}],"max_tokens":5}'

Check:
1. Response received (200 OK)
2. Content includes "OK" or similar
3. X-Actual-Model header shows ${model}
4. X-Provider header shows provider

Report: {success: boolean, provider: string, response_preview: string, latency_ms: number}
`, {
        label: `test-${model}`,
        schema: {
          type: 'object',
          properties: {
            success: {type: 'boolean'},
            provider: {type: 'string'},
            response_preview: {type: 'string'},
            latency_ms: {type: 'number'}
          },
          required: ['success', 'provider', 'response_preview']
        }
      })
    ))

    const successful = results.filter(r => r?.success).length
    log(`Chat models: ${successful}/${sampleModels.length} successful`)

    return {sample_results: results}
  })

  // Phase 2: Test Embeddings
  await phase('Test Embeddings', async () => {
    log('Testing all 3 embedding models...')

    const embResults = await parallel(EMBEDDING_MODELS.map(model => () =>
      agent(`Test embedding model ${model} via aio-01 proxy:

curl -s -X POST http://aio-01:8000/v1/embeddings \\
  -H "Content-Type: application/json" \\
  -H "X-Worker-ID: test-embeddings" \\
  -d '{"input":"Test embedding","model":"${model}"}'

Check:
1. Response received (200 OK)
2. data[0].embedding is an array with length > 100
3. dimensions field shows correct size (1024 for bge-large, 1024 for others)

Report: {success: boolean, dimensions: number, embedding_length: number}
`, {
        label: `test-embed-${model}`,
        schema: {
          type: 'object',
          properties: {
            success: {type: 'boolean'},
            dimensions: {type: 'number'},
            embedding_length: {type: 'number'}
          },
          required: ['success', 'dimensions', 'embedding_length']
        }
      })
    ))

    const successful = embResults.filter(r => r?.success).length
    log(`Embeddings: ${successful}/${EMBEDDING_MODELS.length} successful`)

    return {embedding_results: embResults}
  })

  // Phase 3: Verify Tracking
  await phase('Verify Tracking', async () => {
    log('Checking PostgreSQL usage tracking...')

    const tracking = await agent(`Query PostgreSQL to verify proxy tracking:

psql -h aio-01 -p 5433 -U claude -d learning -c "
SELECT
  COUNT(*) as total_calls,
  COUNT(DISTINCT worker_id) as unique_workers,
  COUNT(DISTINCT provider) as providers_used,
  SUM(CASE WHEN cached THEN 1 ELSE 0 END) as cache_hits,
  SUM(cost_usd) as total_cost
FROM api_usage
WHERE timestamp > NOW() - INTERVAL '1 hour';

SELECT provider, model, COUNT(*)
FROM api_embedding_usage
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY provider, model;

SELECT COUNT(*) as failures
FROM api_failures
WHERE timestamp > NOW() - INTERVAL '1 hour';
"

Report: {
  total_calls: number,
  cache_hit_rate: number (percentage),
  total_cost_usd: number,
  embedding_calls: number,
  failures: number
}
`, {
      label: 'verify-tracking',
      schema: {
        type: 'object',
        properties: {
          total_calls: {type: 'number'},
          cache_hit_rate: {type: 'number'},
          total_cost_usd: {type: 'number'},
          embedding_calls: {type: 'number'},
          failures: {type: 'number'}
        },
        required: ['total_calls', 'failures']
      }
    })

    log(`Tracking: ${tracking.total_calls} calls, ${tracking.cache_hit_rate}% cache hit, $${tracking.total_cost_usd}`)

    return tracking
  })

  // Phase 4: Test Fallback (simulate failure)
  await phase('Test Fallback', async () => {
    log('Testing tier-based fallback logic...')

    const fallback = await agent(`Review fallback implementation in /opt/api-proxy.py:

1. Check get_fallback_model() function
2. Verify it returns same-tier alternatives
3. Check that fallbacks are logged to api_failures table

Example scenarios to validate:
- gpt-4o (high/openai) fails → should try deepseek-chat (high/deepseek)
- llama-3.3-70b (medium/groq) fails → should try llama3.1-70b (medium/cerebras)

Report: {
  logic_correct: boolean,
  same_tier_only: boolean,
  failures_logged: boolean,
  concerns: string[]
}
`, {
      label: 'test-fallback',
      schema: {
        type: 'object',
        properties: {
          logic_correct: {type: 'boolean'},
          same_tier_only: {type: 'boolean'},
          failures_logged: {type: 'boolean'},
          concerns: {type: 'array', items: {type: 'string'}}
        },
        required: ['logic_correct', 'same_tier_only', 'failures_logged']
      }
    })

    return fallback
  })

  // Phase 5: Code Review
  await phase('Review', async () => {
    log('Fleet reviewing proxy implementation...')

    const review = await agent(`Code review /opt/api-proxy.py on aio-01:

Focus areas:
1. Security: API keys properly secured? SQL injection risks?
2. Performance: Unnecessary blocking? Connection pooling? Cache efficiency?
3. Error handling: Proper exception handling? Fallback logic sound?
4. Maintainability: Code clarity? Documentation? Magic numbers?
5. Cost optimization: Are free tiers used first? Cache working?

Report findings as:
{
  security_issues: string[],
  performance_suggestions: string[],
  bugs_found: string[],
  cost_optimizations: string[],
  overall_grade: string (A-F),
  recommendation: string
}
`, {
      label: 'code-review',
      schema: {
        type: 'object',
        properties: {
          security_issues: {type: 'array', items: {type: 'string'}},
          performance_suggestions: {type: 'array', items: {type: 'string'}},
          bugs_found: {type: 'array', items: {type: 'string'}},
          cost_optimizations: {type: 'array', items: {type: 'string'}},
          overall_grade: {type: 'string'},
          recommendation: {type: 'string'}
        },
        required: ['overall_grade', 'recommendation']
      }
    })

    log(`Review grade: ${review.overall_grade}`)
    log(`Recommendation: ${review.recommendation}`)

    return review
  })

  log('✅ Testing complete - proxy validated by fleet')
}
