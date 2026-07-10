/**
 * Smart Bandit Adapter - Unified Multi-Algorithm Model Selection
 * ==============================================================
 *
 * Intelligently routes between 4 bandit algorithms based on task characteristics:
 * - LinUCB: Context-aware (rich features available)
 * - UCB1: Deterministic (reproducible behavior needed)
 * - Exp3: Adversarial (non-stationary environment)
 * - Thompson Sampling: Baseline (proven, simple)
 *
 * Usage:
 *   const { smartSelectModel, smartUpdateModel } = require('./shared/smart-bandit-adapter.js');
 *
 *   const context = {
 *     task_type: 'code_review',
 *     quality_requirement: 0.9,
 *     prefer_deterministic: false,  // Set true for reproducibility
 *     suspect_drift: false           // Set true if model performance varying
 *   };
 *
 *   const model = await smartSelectModel(context, availableModels);
 *   // ... execute task ...
 *   await smartUpdateModel(model, context, reward);
 *
 * Auto-routing Logic:
 * 1. If context has rich features (>5 properties) → LinUCB
 * 2. If prefer_deterministic=true → UCB1
 * 3. If suspect_drift=true → Exp3
 * 4. Otherwise → Thompson Sampling (baseline)
 */

const { execSync } = require('child_process');

// Lazy-load to avoid circular dependencies
let getWorkflowStorage, getDB;

function loadDependencies() {
  if (!getWorkflowStorage) {
    try {
      const workflowAdapter = require('./workflow-storage-adapter.cjs');
      getWorkflowStorage = workflowAdapter.getWorkflowStorage;
    } catch (e) {
      console.warn('workflow-storage-adapter not available:', e.message);
      getWorkflowStorage = () => ({ query: async () => {} });
    }
  }

  if (!getDB) {
    try {
      const pgAdapter = require('../learning/postgres-adapter.js');
      getDB = pgAdapter.getDB;
    } catch (e) {
      console.warn('postgres-adapter not available:', e.message);
      getDB = () => ({ query: async () => [] });
    }
  }

  return { getWorkflowStorage, getDB };
}

// Track algorithm performance for meta-learning
let algorithmStats = {
  linucb: { uses: 0, total_reward: 0, avg_reward: 0 },
  ucb1: { uses: 0, total_reward: 0, avg_reward: 0 },
  exp3: { uses: 0, total_reward: 0, avg_reward: 0 },
  thompson: { uses: 0, total_reward: 0, avg_reward: 0 }
};

/**
 * Intelligently select which bandit algorithm to use based on context.
 *
 * @param {Object} context - Task context
 * @returns {string} Algorithm to use ('linucb', 'ucb1', 'exp3', 'thompson')
 */
function selectAlgorithm(context) {
  // Rule 1: Prefer deterministic if explicitly requested
  if (context.prefer_deterministic === true) {
    return 'ucb1';
  }

  // Rule 2: Use Exp3 if concept drift suspected
  if (context.suspect_drift === true || context.non_stationary === true) {
    return 'exp3';
  }

  // Rule 3: Count rich features (exclude flags)
  const featureKeys = Object.keys(context).filter(k =>
    !k.startsWith('prefer_') && !k.startsWith('suspect_') &&
    k !== 'non_stationary'
  );

  const hasRichFeatures = featureKeys.length >= 5;

  // Rule 4: Use LinUCB if rich features available
  if (hasRichFeatures &&
      context.task_type &&
      (context.quality_requirement !== undefined || context.complexity !== undefined)) {
    return 'linucb';
  }

  // Default: Thompson Sampling (proven baseline)
  return 'thompson';
}

/**
 * Select model using automatically chosen bandit algorithm.
 *
 * @param {Object} context - Task context
 * @param {Array<string>} availableModels - List of available model IDs
 * @returns {Promise<string>} Selected model ID
 */
async function smartSelectModel(context, availableModels) {
  // Auto-select algorithm
  const algorithm = selectAlgorithm(context);

  console.log(`[SmartBandit] Selected algorithm: ${algorithm} (based on context)`);

  try {
    let selectedModel;

    switch (algorithm) {
      case 'linucb':
        selectedModel = await selectWithLinUCB(context, availableModels);
        break;

      case 'ucb1':
        selectedModel = await selectWithUCB1(availableModels);
        break;

      case 'exp3':
        selectedModel = await selectWithExp3(availableModels);
        break;

      case 'thompson':
      default:
        selectedModel = await selectWithThompson(availableModels);
        break;
    }

    // Track selection
    algorithmStats[algorithm].uses++;

    // Log to database
    const deps = loadDependencies();
    const db = deps.getWorkflowStorage();
    await db.query(`
      INSERT INTO monitoring.model_selections
      (model, selection_method, context, timestamp)
      VALUES ($1, $2, $3, NOW())
    `, [selectedModel, algorithm, JSON.stringify(context)]);

    return selectedModel;

  } catch (error) {
    console.error(`[SmartBandit] ${algorithm} failed, falling back to Thompson:`, error.message);
    return await selectWithThompson(availableModels);
  }
}

/**
 * Update model performance using the same algorithm.
 *
 * @param {string} modelId - Model that was selected
 * @param {Object} context - Task context that was used
 * @param {number} reward - Observed reward (0-1)
 * @returns {Promise<void>}
 */
async function smartUpdateModel(modelId, context, reward) {
  const algorithm = selectAlgorithm(context);

  try {
    switch (algorithm) {
      case 'linucb':
        await updateLinUCB(modelId, context, reward);
        break;

      case 'ucb1':
        await updateUCB1(modelId, reward);
        break;

      case 'exp3':
        await updateExp3(modelId, reward, context.last_probability || 0.1);
        break;

      case 'thompson':
      default:
        await updateThompson(modelId, reward);
        break;
    }

    // Track reward
    algorithmStats[algorithm].total_reward += reward;
    algorithmStats[algorithm].avg_reward =
      algorithmStats[algorithm].total_reward / algorithmStats[algorithm].uses;

  } catch (error) {
    console.error(`[SmartBandit] Update failed for ${algorithm}:`, error.message);
  }
}

/**
 * Get statistics for all algorithms.
 *
 * @returns {Object} Algorithm performance stats
 */
function getAlgorithmStats() {
  return { ...algorithmStats };
}

// ============================================================================
// Algorithm-Specific Implementations
// ============================================================================

async function selectWithLinUCB(context, availableModels) {
  const pythonCode = `
import sys, json
sys.path.insert(0, '/tmp')
import importlib.util
spec = importlib.util.spec_from_file_location("linucb", "/tmp/linucb-contextual-bandit.py")
linucb_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linucb_module)

bandit = linucb_module.LinUCBContextualBandit(feature_dim=20, alpha=1.5)
try:
    bandit.load_from_database()
except:
    pass

context = json.loads('${JSON.stringify(context).replace(/'/g, "\\'")}')
models = json.loads('${JSON.stringify(availableModels).replace(/'/g, "\\'")}')

model, ucb_score = bandit.select_arm(context, models)
print(json.dumps({'model': model, 'score': float(ucb_score)}))
`;

  const result = execSync(`python3 -c "${pythonCode.replace(/"/g, '\\"')}"`, {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024
  });

  return JSON.parse(result.trim()).model;
}

async function updateLinUCB(modelId, context, reward) {
  const pythonCode = `
import sys, json
sys.path.insert(0, '/tmp')
import importlib.util
spec = importlib.util.spec_from_file_location("linucb", "/tmp/linucb-contextual-bandit.py")
linucb_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linucb_module)

bandit = linucb_module.LinUCBContextualBandit(feature_dim=20, alpha=1.5)
try:
    bandit.load_from_database()
except:
    pass

context = json.loads('${JSON.stringify(context).replace(/'/g, "\\'")}')
bandit.update_arm('${modelId}', context, ${reward})
bandit.save_to_database()
print("OK")
`;

  execSync(`python3 -c "${pythonCode.replace(/"/g, '\\"')}"`, {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024
  });
}

async function selectWithUCB1(availableModels) {
  const pythonCode = `
import sys, json
sys.path.insert(0, '/tmp')
from ucb1_bandit import UCB1Bandit

ucb1 = UCB1Bandit(c=2.0)
try:
    ucb1.load_from_database()
except:
    pass

models = json.loads('${JSON.stringify(availableModels).replace(/'/g, "\\'")}')
model, ucb_score = ucb1.select_arm(models)
print(json.dumps({'model': model, 'score': float(ucb_score) if ucb_score != float('inf') else 999}))
`;

  const result = execSync(`python3 -c "${pythonCode.replace(/"/g, '\\"')}"`, {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024
  });

  return JSON.parse(result.trim()).model;
}

async function updateUCB1(modelId, reward) {
  const pythonCode = `
import sys
sys.path.insert(0, '/tmp')
from ucb1_bandit import UCB1Bandit

ucb1 = UCB1Bandit(c=2.0)
try:
    ucb1.load_from_database()
except:
    pass

ucb1.update_arm('${modelId}', ${reward})
ucb1.save_to_database()
print("OK")
`;

  execSync(`python3 -c "${pythonCode.replace(/"/g, '\\"')}"`, {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024
  });
}

async function selectWithExp3(availableModels) {
  const pythonCode = `
import sys, json
sys.path.insert(0, '/tmp')
from exp3_bandit import Exp3Bandit

exp3 = Exp3Bandit(gamma=0.3)
try:
    exp3.load_from_database()
except:
    pass

models = json.loads('${JSON.stringify(availableModels).replace(/'/g, "\\'")}')
model, prob = exp3.select_arm(models)
print(json.dumps({'model': model, 'probability': float(prob)}))
`;

  const result = execSync(`python3 -c "${pythonCode.replace(/"/g, '\\"')}"`, {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024
  });

  return JSON.parse(result.trim()).model;
}

async function updateExp3(modelId, reward, probability) {
  const pythonCode = `
import sys
sys.path.insert(0, '/tmp')
from exp3_bandit import Exp3Bandit

exp3 = Exp3Bandit(gamma=0.3)
try:
    exp3.load_from_database()
except:
    pass

exp3.update_arm('${modelId}', ${reward}, ${probability})
exp3.save_to_database()
print("OK")
`;

  execSync(`python3 -c "${pythonCode.replace(/"/g, '\\"')}"`, {
    encoding: 'utf8',
    maxBuffer: 10 * 1024 * 1024
  });
}

async function selectWithThompson(availableModels) {
  const deps = loadDependencies();
  const db = deps.getDB();

  const strategies = await db.query(`
    SELECT strategy, alpha, beta
    FROM learning.strategy_performance
    WHERE strategy = ANY($1)
  `, [availableModels]);

  if (strategies.length === 0) {
    // No data yet, return random
    return availableModels[Math.floor(Math.random() * availableModels.length)];
  }

  // Thompson Sampling: sample from Beta(alpha, beta) and pick max
  let bestModel = null;
  let bestSample = -1;

  for (const row of strategies) {
    const { strategy, alpha, beta } = row;

    // Sample from Beta distribution (approximation using gamma)
    const sample = Math.random(); // Simplified - use beta distribution in production

    if (sample > bestSample) {
      bestSample = sample;
      bestModel = strategy;
    }
  }

  return bestModel || availableModels[0];
}

async function updateThompson(modelId, reward) {
  const deps = loadDependencies();
  const db = deps.getDB();

  // Binary feedback: success if reward > 0.7
  const success = reward > 0.7;

  await db.query(`
    INSERT INTO learning.strategy_performance
    (strategy, successes, failures, alpha, beta, total_reward, avg_reward)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (strategy) DO UPDATE SET
      successes = strategy_performance.successes + $2,
      failures = strategy_performance.failures + $3,
      alpha = strategy_performance.alpha + $2,
      beta = strategy_performance.beta + $3,
      total_reward = strategy_performance.total_reward + $6,
      avg_reward = (strategy_performance.total_reward + $6) /
                   (strategy_performance.successes + strategy_performance.failures + $2 + $3)
  `, [
    modelId,
    success ? 1 : 0,
    success ? 0 : 1,
    success ? 1 : 0,
    success ? 0 : 1,
    reward,
    reward
  ]);
}

module.exports = {
  smartSelectModel,
  smartUpdateModel,
  selectAlgorithm,
  getAlgorithmStats
};
