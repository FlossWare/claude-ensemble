/**
 * CommonJS export wrapper for cost-tracker
 * Allows require() usage in mixed ES6/CommonJS codebases
 */

const { Pool } = require('pg');

/**
 * Model pricing database - input/output cost per 1M tokens
 */
const MODEL_PRICING = {
  // Anthropic Claude API
  'claude-opus-4': {
    provider: 'anthropic',
    input_cost_per_1m: 15000,      // $15.00
    output_cost_per_1m: 75000,     // $75.00
    context_window: 200000
  },
  'claude-sonnet-4.5': {
    provider: 'anthropic',
    input_cost_per_1m: 3000,       // $3.00
    output_cost_per_1m: 15000,     // $15.00
    context_window: 200000
  },
  'claude-haiku-4': {
    provider: 'anthropic',
    input_cost_per_1m: 800,        // $0.80
    output_cost_per_1m: 4000,      // $4.00
    context_window: 200000
  },
  // Shorthand aliases
  'opus': {
    provider: 'anthropic',
    input_cost_per_1m: 15000,
    output_cost_per_1m: 75000,
    context_window: 200000,
    alias_for: 'claude-opus-4'
  },
  'sonnet': {
    provider: 'anthropic',
    input_cost_per_1m: 3000,
    output_cost_per_1m: 15000,
    context_window: 200000,
    alias_for: 'claude-sonnet-4.5'
  },
  'haiku': {
    provider: 'anthropic',
    input_cost_per_1m: 800,
    output_cost_per_1m: 4000,
    context_window: 200000,
    alias_for: 'claude-haiku-4'
  },
  // OpenAI GPT Models
  'gpt-4o': {
    provider: 'openai',
    input_cost_per_1m: 2500,       // $2.50
    output_cost_per_1m: 10000,     // $10.00
    context_window: 128000
  },
  'gpt-4-turbo': {
    provider: 'openai',
    input_cost_per_1m: 10000,      // $10.00
    output_cost_per_1m: 30000,     // $30.00
    context_window: 128000
  },
  'gpt-3.5-turbo': {
    provider: 'openai',
    input_cost_per_1m: 500,        // $0.50
    output_cost_per_1m: 1500,      // $1.50
    context_window: 16384
  },
  // Google Gemini API
  'gemini-2.0-flash-exp': {
    provider: 'google',
    input_cost_per_1m: 75000,      // $0.075
    output_cost_per_1m: 300000,    // $0.30
    context_window: 1000000
  },
  'gemini-1.5-pro': {
    provider: 'google',
    input_cost_per_1m: 1250,       // $1.25
    output_cost_per_1m: 5000,      // $5.00
    context_window: 1000000
  },
  'gemini': {
    provider: 'google',
    input_cost_per_1m: 1250,
    output_cost_per_1m: 5000,
    context_window: 1000000,
    alias_for: 'gemini-1.5-pro'
  },
  // Free APIs (tracked for metrics)
  'llama-3.3-70b-versatile': {
    provider: 'groq',
    input_cost_per_1m: 0,
    output_cost_per_1m: 0,
    context_window: 8000
  },
  'llama-3.1-8b-instant': {
    provider: 'groq',
    input_cost_per_1m: 0,
    output_cost_per_1m: 0,
    context_window: 8000
  },
  'mixtral-8x7b-32768': {
    provider: 'groq',
    input_cost_per_1m: 0,
    output_cost_per_1m: 0,
    context_window: 32768
  },
  'mistral-large-latest': {
    provider: 'mistral',
    input_cost_per_1m: 2000,       // $2.00
    output_cost_per_1m: 6000,      // $6.00
    context_window: 128000
  },
  'mistral-small-latest': {
    provider: 'mistral',
    input_cost_per_1m: 140,        // $0.14
    output_cost_per_1m: 420,       // $0.42
    context_window: 32000
  },
  'command-r-plus': {
    provider: 'cohere',
    input_cost_per_1m: 3000,       // $3.00
    output_cost_per_1m: 15000,     // $15.00
    context_window: 128000
  },
  'jamba-1.5-large': {
    provider: 'ai21',
    input_cost_per_1m: 200,        // $0.20
    output_cost_per_1m: 600,       // $0.60
    context_window: 256000
  },
  'jamba-1.5-mini': {
    provider: 'ai21',
    input_cost_per_1m: 20,         // $0.02
    output_cost_per_1m: 60,        // $0.06
    context_window: 256000
  }
};

class CostTracker {
  constructor(pgConfig = null) {
    this.pgConfig = pgConfig || {
      host: process.env.PG_HOST || 'laptop-01',
      port: process.env.PG_PORT || 5432,
      database: process.env.PG_DB || 'learning',
      user: process.env.PG_USER || process.env.USER || 'sfloess',
      password: process.env.PG_PASSWORD || null,
      ssl: process.env.PG_SSL === 'true'
    };

    this.pool = new Pool(this.pgConfig);
    this.initialized = false;
  }

  async initialize() {
    if (this.initialized) return;

    try {
      const client = await this.pool.connect();
      try {
        await client.query(`CREATE SCHEMA IF NOT EXISTS costs;`);
        await client.query(`
          CREATE TABLE IF NOT EXISTS costs.entries (
            id SERIAL PRIMARY KEY,
            model VARCHAR(255) NOT NULL,
            provider VARCHAR(100),
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_cost NUMERIC(12, 6) NOT NULL DEFAULT 0,
            worker_id VARCHAR(255),
            workflow_id VARCHAR(255),
            task_hash VARCHAR(64),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
          );
        `);
        await client.query(`CREATE INDEX IF NOT EXISTS idx_costs_model ON costs.entries(model);`);
        await client.query(`CREATE INDEX IF NOT EXISTS idx_costs_created ON costs.entries(created_at);`);
        await client.query(`CREATE INDEX IF NOT EXISTS idx_costs_provider ON costs.entries(provider);`);
        this.initialized = true;
      } finally {
        client.release();
      }
    } catch (error) {
      console.error('Failed to initialize cost tracking schema:', error.message);
    }
  }

  getPricingInfo(model) {
    let pricing = MODEL_PRICING[model];

    if (!pricing && model) {
      const lowerModel = model.toLowerCase();
      for (const [key, value] of Object.entries(MODEL_PRICING)) {
        if (key.toLowerCase() === lowerModel) {
          pricing = value;
          break;
        }
      }
    }

    if (!pricing) {
      pricing = {
        provider: 'anthropic',
        input_cost_per_1m: 800,
        output_cost_per_1m: 4000,
        context_window: 200000,
        notes: 'Unknown model - using Haiku fallback pricing'
      };
    }

    return pricing;
  }

  calculateCost(model, inputTokens, outputTokens) {
    const pricing = this.getPricingInfo(model);

    const inputCost = (inputTokens / 1000000) * pricing.input_cost_per_1m;
    const outputCost = (outputTokens / 1000000) * pricing.output_cost_per_1m;
    const totalCost = inputCost + outputCost;

    return {
      model,
      provider: pricing.provider,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      input_cost_usd: Math.round(inputCost * 1000000) / 1000000,
      output_cost_usd: Math.round(outputCost * 1000000) / 1000000,
      total_cost_usd: Math.round(totalCost * 1000000) / 1000000,
      pricing_ref: pricing
    };
  }

  async trackCost(data) {
    const {
      model,
      input_tokens = 0,
      output_tokens = 0,
      worker_id = null,
      workflow_id = null,
      task_hash = null,
      metadata = null
    } = data;

    const costData = this.calculateCost(model, input_tokens, output_tokens);
    await this.initialize();

    try {
      const client = await this.pool.connect();
      try {
        const result = await client.query(
          `INSERT INTO costs.entries
           (model, provider, input_tokens, output_tokens, total_cost, worker_id, workflow_id, task_hash, metadata)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           RETURNING id, created_at`,
          [
            model,
            costData.provider,
            input_tokens,
            output_tokens,
            costData.total_cost_usd,
            worker_id,
            workflow_id,
            task_hash,
            metadata ? JSON.stringify(metadata) : null
          ]
        );

        return {
          ...costData,
          id: result.rows[0].id,
          created_at: result.rows[0].created_at,
          database_tracked: true
        };
      } finally {
        client.release();
      }
    } catch (error) {
      console.warn('Failed to track cost in database:', error.message);
      return {
        ...costData,
        database_tracked: false,
        error: error.message
      };
    }
  }

  async getAggregate(options = {}) {
    const { since_hours = 24, groupBy = 'model' } = options;
    await this.initialize();

    try {
      const client = await this.pool.connect();
      try {
        let query;

        if (groupBy === 'model') {
          query = `
            SELECT
              model,
              provider,
              COUNT(*) as request_count,
              SUM(input_tokens) as total_input_tokens,
              SUM(output_tokens) as total_output_tokens,
              SUM(total_cost) as total_cost_usd,
              AVG(total_cost) as avg_cost_per_request,
              MIN(created_at) as first_request,
              MAX(created_at) as last_request
            FROM costs.entries
            WHERE created_at > NOW() - INTERVAL '${since_hours} hours'
            GROUP BY model, provider
            ORDER BY total_cost_usd DESC;
          `;
        } else if (groupBy === 'provider') {
          query = `
            SELECT
              provider,
              COUNT(*) as request_count,
              SUM(input_tokens) as total_input_tokens,
              SUM(output_tokens) as total_output_tokens,
              SUM(total_cost) as total_cost_usd,
              AVG(total_cost) as avg_cost_per_request
            FROM costs.entries
            WHERE created_at > NOW() - INTERVAL '${since_hours} hours'
            GROUP BY provider
            ORDER BY total_cost_usd DESC;
          `;
        } else if (groupBy === 'hour') {
          query = `
            SELECT
              DATE_TRUNC('hour', created_at) as hour,
              COUNT(*) as request_count,
              SUM(input_tokens) as total_input_tokens,
              SUM(output_tokens) as total_output_tokens,
              SUM(total_cost) as total_cost_usd
            FROM costs.entries
            WHERE created_at > NOW() - INTERVAL '${since_hours} hours'
            GROUP BY DATE_TRUNC('hour', created_at)
            ORDER BY hour DESC;
          `;
        }

        const result = await client.query(query);
        return {
          period: `${since_hours} hours`,
          group_by: groupBy,
          results: result.rows,
          timestamp: new Date().toISOString()
        };
      } finally {
        client.release();
      }
    } catch (error) {
      console.error('Failed to get aggregate:', error.message);
      return {
        error: error.message,
        period: `${since_hours} hours`,
        group_by: groupBy
      };
    }
  }

  async close() {
    if (this.pool) {
      await this.pool.end();
    }
  }
}

let instance = null;

function getCostTracker(pgConfig = null) {
  if (!instance) {
    instance = new CostTracker(pgConfig);
  }
  return instance;
}

module.exports = {
  CostTracker,
  getCostTracker,
  MODEL_PRICING
};
