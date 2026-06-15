#!/usr/bin/env node
/**
 * AI Cost Tracker HTTP Service
 *
 * Standalone HTTP wrapper around the ai-cost-tracker logic.
 * Provides REST API for tracking token costs, enforcing budgets,
 * and generating cost reports.
 *
 * Usage:
 *   node monitoring/ai-cost-tracker-service.js [--port 9094]
 *
 * Endpoints:
 *   POST /track           - Track a model call (model, input_tokens, output_tokens, workflow_id?, label?)
 *   GET  /cost            - Get session cost (?workflow_id=X)
 *   GET  /budget          - Get remaining budget (?workflow_id=X)
 *   POST /check-budget    - Check if a call would exceed budget
 *   GET  /report          - Generate cost report
 *   POST /reset           - Reset session tracking
 *   GET  /pricing         - Current model pricing
 *   GET  /health          - Health check
 */

import fs from 'fs';
import path from 'path';
import http from 'http';
import os from 'os';

// ============================================================================
// CONFIGURATION
// ============================================================================

const HOME = process.env.HOME || os.homedir();
const DATA_DIR = path.join(HOME, '.claude', 'learning', 'cost-tracking');
const DATA_FILE = path.join(DATA_DIR, 'cost-tracking.json');

const DEFAULT_PRICING = {
  opus: { cost_per_1k_input: 0.015, cost_per_1k_output: 0.075 },
  fable: { cost_per_1k_input: 0.015, cost_per_1k_output: 0.075 },
  sonnet: { cost_per_1k_input: 0.003, cost_per_1k_output: 0.015 },
  haiku: { cost_per_1k_input: 0.00025, cost_per_1k_output: 0.00125 },
  gemini: { cost_per_1k_input: 0.00035, cost_per_1k_output: 0.0014 },
  'gpt-4o': { cost_per_1k_input: 0.005, cost_per_1k_output: 0.015 },
};

const DEFAULT_BUDGET = {
  per_workflow_max_dollars: 5.00,
  per_session_max_dollars: 25.00,
  warn_at_percent: 80,
};

// ============================================================================
// PRICING LOADER
// ============================================================================

function loadModelPricing() {
  const pricing = {};
  for (const [k, v] of Object.entries(DEFAULT_PRICING)) {
    pricing[k] = { ...v };
  }

  try {
    const configPaths = [
      path.join(HOME, '.claude', 'model-config.json'),
      path.join(HOME, 'Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/model-config.json'),
    ];

    for (const configPath of configPaths) {
      try {
        const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        if (config.models) {
          for (const [id, modelCfg] of Object.entries(config.models)) {
            if (!pricing[id]) pricing[id] = {};
            if (modelCfg.cost_per_1k_input !== undefined) pricing[id].cost_per_1k_input = modelCfg.cost_per_1k_input;
            if (modelCfg.cost_per_1k_output !== undefined) pricing[id].cost_per_1k_output = modelCfg.cost_per_1k_output;
            if (modelCfg.cost_per_1k_tokens !== undefined) {
              pricing[id].cost_per_1k_input = pricing[id].cost_per_1k_input || modelCfg.cost_per_1k_tokens;
              pricing[id].cost_per_1k_output = pricing[id].cost_per_1k_output || modelCfg.cost_per_1k_tokens;
            }
          }
        }
        if (config.budget) {
          return { pricing, budget: { ...DEFAULT_BUDGET, ...config.budget } };
        }
        break;
      } catch (_e) { continue; }
    }
  } catch (_err) { /* use defaults */ }

  return { pricing, budget: { ...DEFAULT_BUDGET } };
}

// ============================================================================
// DATA STORE
// ============================================================================

function loadCostStore() {
  try {
    if (fs.existsSync(DATA_FILE)) {
      return JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'));
    }
  } catch (_err) { /* fall through */ }

  return {
    session_id: `session_${Date.now()}`,
    started_at: new Date().toISOString(),
    entries: [],
    workflow_totals: {},
    session_total_usd: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
  };
}

function saveCostStore(store) {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    store.updated_at = new Date().toISOString();
    fs.writeFileSync(DATA_FILE, JSON.stringify(store, null, 2), 'utf-8');
  } catch (err) {
    console.error(`Warning: Could not persist cost data: ${err.message}`);
  }
}

// ============================================================================
// COST CALCULATION
// ============================================================================

function calculateCost(model, inputTokens, outputTokens, pricing) {
  const modelPricing = pricing[model] || pricing[model.toLowerCase()];

  if (!modelPricing) {
    const fallback = pricing.sonnet || { cost_per_1k_input: 0.003, cost_per_1k_output: 0.015 };
    const inputCost = (inputTokens / 1000) * fallback.cost_per_1k_input;
    const outputCost = (outputTokens / 1000) * fallback.cost_per_1k_output;
    return { input_cost: inputCost, output_cost: outputCost, total_cost: inputCost + outputCost, pricing_source: 'fallback (sonnet)' };
  }

  const inputCost = (inputTokens / 1000) * (modelPricing.cost_per_1k_input || 0);
  const outputCost = (outputTokens / 1000) * (modelPricing.cost_per_1k_output || 0);
  return { input_cost: inputCost, output_cost: outputCost, total_cost: inputCost + outputCost, pricing_source: 'config' };
}

function checkBudgetLimit(store, workflowId, additionalCost, budgetConfig) {
  const result = { allowed: true, warnings: [], session_spent: store.session_total_usd, workflow_spent: 0 };

  if (workflowId) {
    const workflowSpent = (store.workflow_totals[workflowId] || { total_usd: 0 }).total_usd;
    result.workflow_spent = workflowSpent;
    const projected = workflowSpent + additionalCost;
    if (projected > budgetConfig.per_workflow_max_dollars) {
      result.allowed = false;
      result.warnings.push(`Workflow "${workflowId}" would exceed budget: $${projected.toFixed(4)} > $${budgetConfig.per_workflow_max_dollars}`);
    } else if (projected > budgetConfig.per_workflow_max_dollars * (budgetConfig.warn_at_percent / 100)) {
      result.warnings.push(`Workflow "${workflowId}" approaching budget: ${(projected / budgetConfig.per_workflow_max_dollars * 100).toFixed(1)}%`);
    }
  }

  const sessionProjected = store.session_total_usd + additionalCost;
  if (sessionProjected > budgetConfig.per_session_max_dollars) {
    result.allowed = false;
    result.warnings.push(`Session would exceed budget: $${sessionProjected.toFixed(4)} > $${budgetConfig.per_session_max_dollars}`);
  }

  result.session_remaining = Math.max(0, budgetConfig.per_session_max_dollars - sessionProjected);
  result.workflow_remaining = workflowId ? Math.max(0, budgetConfig.per_workflow_max_dollars - (result.workflow_spent + additionalCost)) : null;

  return result;
}

function trackCall(store, model, inputTokens, outputTokens, workflowId, label, pricing, budgetConfig) {
  const cost = calculateCost(model, inputTokens, outputTokens, pricing);
  const budgetCheck = checkBudgetLimit(store, workflowId, cost.total_cost, budgetConfig);

  const entry = {
    timestamp: new Date().toISOString(),
    model, label: label || null, workflow_id: workflowId || null,
    input_tokens: inputTokens, output_tokens: outputTokens,
    input_cost: cost.input_cost, output_cost: cost.output_cost,
    total_cost: cost.total_cost, pricing_source: cost.pricing_source,
    budget_allowed: budgetCheck.allowed,
  };

  store.entries.push(entry);
  store.session_total_usd += cost.total_cost;
  store.total_input_tokens += inputTokens;
  store.total_output_tokens += outputTokens;

  if (workflowId) {
    if (!store.workflow_totals[workflowId]) {
      store.workflow_totals[workflowId] = { total_usd: 0, calls: 0, input_tokens: 0, output_tokens: 0, first_call: entry.timestamp };
    }
    const wf = store.workflow_totals[workflowId];
    wf.total_usd += cost.total_cost;
    wf.calls += 1;
    wf.input_tokens += inputTokens;
    wf.output_tokens += outputTokens;
    wf.last_call = entry.timestamp;
  }

  saveCostStore(store);

  return { entry, budget: budgetCheck, session_total_usd: store.session_total_usd };
}

// ============================================================================
// HTTP SERVER
// ============================================================================

function startServer(port = 9094) {
  const { pricing, budget: budgetConfig } = loadModelPricing();
  let store = loadCostStore();

  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://localhost:${port}`);
    const respond = (code, body) => {
      res.writeHead(code, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(body, null, 2));
    };

    try {
      store = loadCostStore();

      if (req.method === 'GET' && url.pathname === '/health') {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end('OK');
        return;
      }

      if (req.method === 'POST' && url.pathname === '/track') {
        let body = '';
        for await (const chunk of req) body += chunk;
        const payload = JSON.parse(body);
        if (!payload.model) { respond(400, { error: 'model is required' }); return; }
        const result = trackCall(store, payload.model, payload.input_tokens || 0, payload.output_tokens || 0, payload.workflow_id, payload.label, pricing, budgetConfig);
        respond(200, result);
        return;
      }

      if (req.method === 'GET' && url.pathname === '/cost') {
        const workflowId = url.searchParams.get('workflow_id');
        if (workflowId) {
          const wfData = store.workflow_totals[workflowId];
          respond(200, {
            workflow_id: workflowId,
            total_usd: wfData ? wfData.total_usd : 0,
            calls: wfData ? wfData.calls : 0,
            input_tokens: wfData ? wfData.input_tokens : 0,
            output_tokens: wfData ? wfData.output_tokens : 0,
          });
        } else {
          respond(200, {
            session_total_usd: store.session_total_usd,
            total_calls: store.entries.length,
            total_input_tokens: store.total_input_tokens,
            total_output_tokens: store.total_output_tokens,
            workflows: Object.keys(store.workflow_totals),
          });
        }
        return;
      }

      if (req.method === 'GET' && url.pathname === '/budget') {
        const workflowId = url.searchParams.get('workflow_id');
        const sessionRemaining = Math.max(0, budgetConfig.per_session_max_dollars - store.session_total_usd);
        const result = {
          session_remaining_usd: sessionRemaining,
          session_budget_usd: budgetConfig.per_session_max_dollars,
          session_used_usd: store.session_total_usd,
          session_used_percent: (store.session_total_usd / budgetConfig.per_session_max_dollars) * 100,
        };
        if (workflowId) {
          const wfSpent = (store.workflow_totals[workflowId] || { total_usd: 0 }).total_usd;
          result.workflow_id = workflowId;
          result.workflow_remaining_usd = Math.max(0, budgetConfig.per_workflow_max_dollars - wfSpent);
          result.workflow_budget_usd = budgetConfig.per_workflow_max_dollars;
          result.workflow_used_usd = wfSpent;
        }
        respond(200, result);
        return;
      }

      if (req.method === 'POST' && url.pathname === '/check-budget') {
        let body = '';
        for await (const chunk of req) body += chunk;
        const payload = JSON.parse(body);
        const estCost = calculateCost(payload.model || 'sonnet', payload.estimated_input_tokens || 0, payload.estimated_output_tokens || 0, pricing);
        const result = checkBudgetLimit(store, payload.workflow_id, estCost.total_cost, budgetConfig);
        result.estimated_cost = estCost.total_cost;
        respond(200, result);
        return;
      }

      if (req.method === 'GET' && url.pathname === '/report') {
        const modelBreakdown = {};
        for (const entry of store.entries) {
          if (!modelBreakdown[entry.model]) modelBreakdown[entry.model] = { total_usd: 0, calls: 0, input_tokens: 0, output_tokens: 0 };
          modelBreakdown[entry.model].total_usd += entry.total_cost;
          modelBreakdown[entry.model].calls += 1;
          modelBreakdown[entry.model].input_tokens += entry.input_tokens;
          modelBreakdown[entry.model].output_tokens += entry.output_tokens;
        }

        respond(200, {
          session_id: store.session_id,
          started_at: store.started_at,
          session_total_usd: store.session_total_usd,
          total_calls: store.entries.length,
          total_input_tokens: store.total_input_tokens,
          total_output_tokens: store.total_output_tokens,
          budget: {
            per_workflow_max: budgetConfig.per_workflow_max_dollars,
            per_session_max: budgetConfig.per_session_max_dollars,
            session_remaining: Math.max(0, budgetConfig.per_session_max_dollars - store.session_total_usd),
            session_used_percent: (store.session_total_usd / budgetConfig.per_session_max_dollars) * 100,
          },
          per_workflow: store.workflow_totals,
          per_model: modelBreakdown,
          recent_entries: store.entries.slice(-20),
        });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/reset') {
        store = {
          session_id: `session_${Date.now()}`,
          started_at: new Date().toISOString(),
          entries: [],
          workflow_totals: {},
          session_total_usd: 0,
          total_input_tokens: 0,
          total_output_tokens: 0,
        };
        saveCostStore(store);
        respond(200, { status: 'reset', session_id: store.session_id });
        return;
      }

      if (req.method === 'GET' && url.pathname === '/pricing') {
        respond(200, { pricing, budget: budgetConfig });
        return;
      }

      // Default
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end([
        'AI Cost Tracker Service',
        '',
        'Endpoints:',
        '  POST /track           - Track call (JSON: model, input_tokens, output_tokens, workflow_id?, label?)',
        '  GET  /cost            - Session cost (?workflow_id=X)',
        '  GET  /budget          - Remaining budget (?workflow_id=X)',
        '  POST /check-budget    - Pre-check budget (JSON: model, estimated_input_tokens, estimated_output_tokens)',
        '  GET  /report          - Full cost report',
        '  POST /reset           - Reset session',
        '  GET  /pricing         - Current model pricing',
        '  GET  /health          - Health check',
      ].join('\n'));
    } catch (err) {
      respond(500, { error: err.message });
    }
  });

  server.listen(port, () => {
    console.log(`[ai-cost-tracker] HTTP service on http://localhost:${port}`);
    console.log(`[ai-cost-tracker] Health: http://localhost:${port}/health`);
    console.log(`[ai-cost-tracker] Data: ${DATA_FILE}`);
    console.log(`[ai-cost-tracker] Models: ${Object.keys(pricing).join(', ')}`);
    console.log(`[ai-cost-tracker] Budget: $${budgetConfig.per_workflow_max_dollars}/wf, $${budgetConfig.per_session_max_dollars}/session`);
  });

  const shutdown = () => {
    console.log('[ai-cost-tracker] Shutting down...');
    server.close(() => process.exit(0));
  };
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);

  return server;
}

// ============================================================================
// CLI
// ============================================================================

const args = process.argv.slice(2);
let port = 9094;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--port' && args[i + 1]) {
    port = parseInt(args[i + 1], 10);
    i++;
  }
}

startServer(port);
