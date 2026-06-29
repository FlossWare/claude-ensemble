/**
 * Tests for cost-tracker module
 *
 * Tests pricing calculations, cost aggregation, and database tracking
 */

import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import { CostTracker, getCostTracker, MODEL_PRICING } from '../lib/cost-tracker.js';

describe('CostTracker', () => {
  let tracker;

  beforeAll(() => {
    tracker = new CostTracker({
      host: process.env.PG_HOST || 'localhost',
      port: process.env.PG_PORT || 5432,
      database: process.env.PG_DB || 'learning_test',
      user: process.env.PG_USER || 'postgres',
      password: process.env.PG_PASSWORD,
      ssl: process.env.PG_SSL === 'true'
    });
  });

  afterAll(async () => {
    await tracker.close();
  });

  describe('getPricingInfo', () => {
    it('should return pricing for known models', () => {
      const pricing = tracker.getPricingInfo('sonnet');
      expect(pricing).toHaveProperty('provider');
      expect(pricing).toHaveProperty('input_cost_per_1m');
      expect(pricing).toHaveProperty('output_cost_per_1m');
      expect(pricing.provider).toBe('anthropic');
      expect(pricing.input_cost_per_1m).toBe(3000); // $3.00
      expect(pricing.output_cost_per_1m).toBe(15000); // $15.00
    });

    it('should return fallback pricing for unknown models', () => {
      const pricing = tracker.getPricingInfo('unknown-model-xyz');
      expect(pricing).toHaveProperty('provider');
      expect(pricing.provider).toBe('anthropic');
      expect(pricing.input_cost_per_1m).toBe(800); // Haiku fallback
    });

    it('should handle case-insensitive model names', () => {
      const pricing = tracker.getPricingInfo('SONNET');
      expect(pricing.input_cost_per_1m).toBe(3000);
    });

    it('should resolve aliases', () => {
      const alias = tracker.getPricingInfo('opus');
      const full = tracker.getPricingInfo('claude-opus-4');
      expect(alias.input_cost_per_1m).toBe(full.input_cost_per_1m);
      expect(alias.output_cost_per_1m).toBe(full.output_cost_per_1m);
    });
  });

  describe('calculateCost', () => {
    it('should calculate cost for tokens', () => {
      const cost = tracker.calculateCost('sonnet', 1000000, 1000000);
      expect(cost).toHaveProperty('total_cost_usd');
      expect(cost).toHaveProperty('input_cost_usd');
      expect(cost).toHaveProperty('output_cost_usd');
      // 1M input @ $3/1M = $3, 1M output @ $15/1M = $15, total = $18
      expect(cost.input_cost_usd).toBe(3);
      expect(cost.output_cost_usd).toBe(15);
      expect(cost.total_cost_usd).toBe(18);
    });

    it('should handle zero tokens', () => {
      const cost = tracker.calculateCost('sonnet', 0, 0);
      expect(cost.total_cost_usd).toBe(0);
    });

    it('should calculate partial token costs', () => {
      const cost = tracker.calculateCost('haiku', 100000, 50000);
      // 100k input @ $0.80/1M = $0.08, 50k output @ $4/1M = $0.20
      expect(cost.total_cost_usd).toBeCloseTo(0.28, 6);
    });

    it('should track correct provider in cost calculation', () => {
      const cost = tracker.calculateCost('gpt-4o', 1000, 1000);
      expect(cost.provider).toBe('openai');
    });

    it('should return precision with 6 decimal places', () => {
      const cost = tracker.calculateCost('sonnet', 1, 1);
      const totalStr = cost.total_cost_usd.toString();
      const decimals = totalStr.split('.')[1];
      expect(decimals).toBeDefined();
      expect(decimals.length).toBeLessThanOrEqual(6);
    });
  });

  describe('Pricing database coverage', () => {
    it('should have pricing for major providers', () => {
      const providers = new Set(
        Object.values(MODEL_PRICING).map(p => p.provider)
      );
      expect(providers.has('anthropic')).toBe(true);
      expect(providers.has('openai')).toBe(true);
      expect(providers.has('google')).toBe(true);
      expect(providers.has('mistral')).toBe(true);
    });

    it('should have context window for all models', () => {
      Object.entries(MODEL_PRICING).forEach(([model, pricing]) => {
        expect(pricing.context_window).toBeGreaterThan(0);
      });
    });
  });

  describe('Free tier models', () => {
    it('should track free models with zero cost', () => {
      const cost = tracker.calculateCost('llama-3.3-70b-versatile', 1000000, 1000000);
      expect(cost.total_cost_usd).toBe(0);
    });

    it('should support multiple free providers', () => {
      const groq = tracker.calculateCost('mixtral-8x7b-32768', 100000, 100000);
      const mistral = tracker.calculateCost('mistral-large-latest', 100000, 100000);

      expect(groq.total_cost_usd).toBe(0);
      expect(mistral.total_cost_usd).toBeGreaterThan(0);
    });
  });

  describe('Model comparison', () => {
    it('should show cost differences between models', () => {
      const haiku = tracker.calculateCost('haiku', 1000000, 1000000);
      const sonnet = tracker.calculateCost('sonnet', 1000000, 1000000);
      const opus = tracker.calculateCost('opus', 1000000, 1000000);

      expect(haiku.total_cost_usd).toBeLessThan(sonnet.total_cost_usd);
      expect(sonnet.total_cost_usd).toBeLessThan(opus.total_cost_usd);
    });
  });

  describe('Singleton pattern', () => {
    it('should return same instance from getCostTracker', () => {
      const tracker1 = getCostTracker();
      const tracker2 = getCostTracker();
      expect(tracker1).toBe(tracker2);
    });
  });
});

describe('CostTracker Database Operations', () => {
  let tracker;

  beforeAll(async () => {
    tracker = new CostTracker({
      host: process.env.PG_HOST || 'localhost',
      port: process.env.PG_PORT || 5432,
      database: process.env.PG_DB || 'learning_test',
      user: process.env.PG_USER || 'postgres',
      password: process.env.PG_PASSWORD,
      ssl: process.env.PG_SSL === 'true'
    });

    // Skip database tests if PostgreSQL not available
    try {
      await tracker.initialize();
    } catch (error) {
      console.warn('Skipping database tests - PostgreSQL not available:', error.message);
    }
  });

  afterAll(async () => {
    await tracker.close();
  });

  describe('trackCost', () => {
    it('should track cost without database if not initialized', async () => {
      const tracker2 = new CostTracker({
        host: 'invalid-host',
        port: 9999,
        database: 'invalid',
        user: 'invalid'
      });

      const result = await tracker2.trackCost({
        model: 'sonnet',
        input_tokens: 1000,
        output_tokens: 500
      });

      expect(result).toHaveProperty('total_cost_usd');
      expect(result.total_cost_usd).toBeGreaterThan(0);
      expect(result.database_tracked).toBe(false);
    });
  });

  describe('getAggregate', () => {
    it('should handle aggregation without data', async () => {
      // This test just verifies aggregation doesn't crash
      const result = await tracker.getAggregate({ since_hours: 1, groupBy: 'model' });
      expect(result).toHaveProperty('period');
      expect(result).toHaveProperty('group_by');
    });
  });
});
