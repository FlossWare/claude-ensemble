#!/usr/bin/env node
/**
 * Fleet Orchestrator HTTP Service (ENHANCED with AI Learning)
 *
 * Runs on pi-02 as centralized routing service with:
 * - Thompson Sampling model selection (AI-driven)
 * - Quality feedback recording (learns from outcomes)
 * - Adaptive routing (improves over time)
 * - PostgreSQL learning database integration
 */

import { createServer } from 'http';
import { ProductionFleetRouter } from './production-router.mjs';
import { OrchestratorLearningAdapter } from '../shared/orchestrator-learning-adapter.js';
import { sanitizeHtml, validateModelInput, parseAndValidateBody, validateQueryParam } from '../shared/input-validator.js';

const PORT = process.env.PORT || 8888;
const HOST = process.env.HOST || '0.0.0.0';
const REFRESH_INTERVAL = parseInt(process.env.REFRESH_INTERVAL || '300000'); // 5 minutes

class OrchestratorService {
  constructor() {
    this.router = null;
    this.learning = null;
    this.lastRefresh = null;
    this.requestCount = 0;
    this.errorCount = 0;
    this.feedbackCount = 0;
  }

  async initialize() {
    console.log('[orchestrator] Initializing production router...');
    this.router = new ProductionFleetRouter({ maxConcurrent: 1 });

    console.log('[orchestrator] Connecting to learning database...');
    this.learning = new OrchestratorLearningAdapter();
    await this.learning.connect();

    await this.refreshRegistry();

    // Auto-refresh registry periodically
    setInterval(() => {
      this.refreshRegistry().catch(err => {
        console.error('[orchestrator] Auto-refresh failed:', err.message);
      });
    }, REFRESH_INTERVAL);

    console.log('[orchestrator] Initialized successfully');
  }

  async refreshRegistry() {
    console.log('[orchestrator] Refreshing model registry...');
    try {
      await this.router.refreshRegistry({ useCache: false });
      this.lastRefresh = new Date().toISOString();
      console.log(`[orchestrator] Registry refreshed: ${Object.keys(this.router.registry).length} models`);
    } catch (err) {
      console.error('[orchestrator] Refresh failed:', err.message);
      throw err;
    }
  }

  async handleRequest(req, res) {
    this.requestCount++;

    const url = new URL(req.url, `http://${req.headers.host}`);
    const path = url.pathname;

    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
      res.writeHead(200);
      res.end();
      return;
    }

    try {
      switch (path) {
        case '/':
        case '/health':
          this.handleHealth(req, res);
          break;

        case '/route':
          await this.handleRoute(req, res);
          break;

        case '/route-thompson':
          await this.handleRouteThompson(req, res);
          break;

        case '/feedback':
          await this.handleFeedback(req, res);
          break;

        case '/models':
          this.handleModels(req, res);
          break;

        case '/rankings':
          await this.handleRankings(req, res);
          break;

        case '/utilization':
          this.handleUtilization(req, res);
          break;

        case '/stats':
          this.handleStats(req, res);
          break;

        case '/refresh':
          await this.handleRefresh(req, res);
          break;

        default:
          res.writeHead(404, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Not found' }));
      }
    } catch (err) {
      this.errorCount++;
      console.error('[orchestrator] Request error:', err.message);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  handleHealth(req, res) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      service: 'fleet-orchestrator',
      version: '2.0-learning',
      uptime: process.uptime(),
      last_refresh: this.lastRefresh,
      request_count: this.requestCount,
      error_count: this.errorCount,
      feedback_count: this.feedbackCount,
      models_available: Object.keys(this.router.registry).length,
      learning_enabled: this.learning?.connected || false
    }));
  }

  /**
   * NEW: Thompson Sampling route (AI-driven model selection)
   */
  async handleRouteThompson(req, res) {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const payload = JSON.parse(body);
        const {
          taskType = 'general',
          task = '',
          count = 3,
          constraints = {}
        } = payload;

        // Input validation
        const sanitizedTaskType = sanitizeHtml(taskType, { maxLength: 100, allowNewlines: false });
        const sanitizedTask = sanitizeHtml(task, { maxLength: 5000 });

        // Get available models from registry
        const availableModels = Object.keys(this.router.registry);

        if (availableModels.length === 0) {
          res.writeHead(503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'No models available' }));
          return;
        }

        // Use Thompson Sampling to select best models
        const selectedModels = await this.learning.selectModelsThompson(
          taskType,
          availableModels,
          count
        );

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          method: 'thompson-sampling',
          models: selectedModels,
          taskType,
          count: selectedModels.length,
          reasoning: `Selected via Thompson Sampling from ${availableModels.length} available models`
        }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
  }

  /**
   * Legacy route handler (static routing)
   */
  async handleRoute(req, res) {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const model = url.searchParams.get('model');

    if (!model) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Missing model parameter' }));
      return;
    }

    try {
      // Validate model name input
      const validatedModel = validateModelInput(model);
      const selectedHost = this.router.selectHostForModel(validatedModel);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        selectedModel: model,
        selectedHost,
        method: 'static-routing'
      }));
    } catch (err) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  /**
   * NEW: Record feedback from task execution
   */
  async handleFeedback(req, res) {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const feedback = JSON.parse(body);
        const {
          model,
          success = false,
          quality = 0.5,
          cost = 0,
          duration = 0,
          taskType = 'general'
        } = feedback;

        if (!model) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'Missing model parameter' }));
          return;
        }

        // Input validation
        const validatedModel = validateModelInput(model);
        const sanitizedTaskType = sanitizeHtml(taskType, { maxLength: 100, allowNewlines: false });

        // Record feedback in learning database
        await this.learning.recordFeedback(validatedModel, {
          success,
          quality,
          cost,
          duration,
          taskType
        });

        this.feedbackCount++;

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'recorded',
          model,
          feedback_count: this.feedbackCount
        }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
    });
  }

  /**
   * NEW: Get model rankings (by quality)
   */
  async handleRankings(req, res) {
    try {
      const url = new URL(req.url, `http://${req.headers.host}`);
      const taskType = url.searchParams.get('taskType');

      const rankings = await this.learning.getModelRankings(taskType);

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        rankings,
        count: rankings.length,
        taskType: taskType || 'all'
      }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }

  handleModels(req, res) {
    const models = Object.entries(this.router.registry).map(([name, hosts]) => ({
      name,
      hosts: hosts.length,
      category: this.categorizeModel(name),
      size_gb: this.estimateSize(name)
    }));

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ models }));
  }

  categorizeModel(name) {
    if (name.includes('code') || name.includes('coder')) return 'coding';
    if (name.includes('math')) return 'reasoning';
    if (name.includes('sql')) return 'coding';
    return 'general';
  }

  estimateSize(name) {
    if (name.includes('70b') || name.includes('72b')) return 40;
    if (name.includes('33b') || name.includes('34b')) return 20;
    if (name.includes('13b') || name.includes('14b')) return 8;
    if (name.includes('7b') || name.includes('8b')) return 4;
    if (name.includes('3b') || name.includes('4b')) return 2;
    return 4;
  }

  handleUtilization(req, res) {
    const utilization = {};
    for (const [host, count] of this.router.inFlight) {
      utilization[host] = {
        in_flight: count,
        max_concurrent: this.router.maxConcurrent
      };
    }

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ utilization }));
  }

  handleStats(req, res) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      requests: this.requestCount,
      errors: this.errorCount,
      feedback_count: this.feedbackCount,
      models: Object.keys(this.router.registry).length,
      learning_enabled: this.learning?.connected || false,
      uptime: process.uptime()
    }));
  }

  async handleRefresh(req, res) {
    try {
      await this.refreshRegistry();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        status: 'refreshed',
        models: Object.keys(this.router.registry).length,
        timestamp: this.lastRefresh
      }));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    }
  }
}

// Start service
const service = new OrchestratorService();
await service.initialize();

const server = createServer((req, res) => service.handleRequest(req, res));
server.listen(PORT, HOST, () => {
  console.log(`[orchestrator] Listening on http://${HOST}:${PORT}`);
  console.log(`[orchestrator] Learning-enhanced routing enabled`);
  console.log(`[orchestrator] Thompson Sampling endpoint: POST /route-thompson`);
  console.log(`[orchestrator] Feedback endpoint: POST /feedback`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('[orchestrator] Shutting down...');
  await service.learning.close();
  server.close(() => process.exit(0));
});
