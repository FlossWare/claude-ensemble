---
name: multi-model-strategy
description: Strategy interface for multi-model arbiter/worker fallback behavior
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 39a38f09-c545-4579-9ac1-6c31a694eba2
---

**Strategy interface for configurable multi-model behavior in arbiter/worker patterns.**

**Why:** Different scenarios need different model selection and fallback strategies:
- Production: Quality-first (Fable → Opus → Sonnet)
- Development: Cost-optimized (Sonnet → Haiku → Opus)
- Rapid prototyping: Speed-first (Haiku → Sonnet → Opus)
- Free tier: Limited model access

**How to apply:**

## Strategy Interface

```javascript
/**
 * Multi-model selection strategy
 */
class ModelStrategy {
  constructor(availableModels = null) {
    this.availableModels = availableModels;
  }
  
  /**
   * Get worker models for parallel analysis
   * @returns {string[]} Array of model names
   */
  getWorkerModels() {
    throw new Error('Must implement getWorkerModels()');
  }
  
  /**
   * Get arbiter fallback chain (priority order)
   * @returns {string[]} Array of model names to try in order
   */
  getArbiterFallback() {
    throw new Error('Must implement getArbiterFallback()');
  }
  
  /**
   * Get preferred arbiter model
   * @returns {string} Model name
   */
  getPreferredArbiter() {
    return this.getArbiterFallback()[0];
  }
  
  /**
   * Filter models to only those available in current subscription
   * @param {string[]} models - Desired models
   * @returns {string[]} Available models from the list
   */
  filterAvailable(models) {
    if (!this.availableModels) return models;
    return models.filter(m => this.availableModels.includes(m));
  }
}

/**
 * Discover available models dynamically (cloud + local/Ollama)
 * @returns {Promise<string[]>} Available model names
 */
async function discoverAvailableModels() {
  const CLOUD_MODELS = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
  const OLLAMA_MODELS = ['ollama:llama3', 'ollama:mistral', 'ollama:codellama', 'ollama:qwen'];
  const available = [];
  
  // Check cloud models
  for (const model of CLOUD_MODELS) {
    try {
      await agent('test', {
        model,
        schema: {type: 'object', properties: {ok: {type: 'boolean'}}, required: ['ok']}
      });
      available.push(model);
      log(`✓ ${model} available`);
    } catch (e) {
      log(`✗ ${model} unavailable`);
    }
  }
  
  // Check Ollama models (if Ollama is running)
  try {
    const ollamaCheck = await agent('Check if Ollama is running: curl -s http://localhost:11434/api/tags', {
      label: 'Check Ollama',
      schema: {type: 'object', properties: {running: {type: 'boolean'}, models: {type: 'array'}}}
    });
    
    if (ollamaCheck.running && ollamaCheck.models) {
      for (const model of OLLAMA_MODELS) {
        const modelName = model.replace('ollama:', '');
        if (ollamaCheck.models.some(m => m.includes(modelName))) {
          available.push(model);
          log(`✓ ${model} available (local)`);
        }
      }
    }
  } catch (e) {
    log(`ℹ️  Ollama not available (local models disabled)`);
  }
  
  return available;
}

/**
 * Run quintuple verification: 5-stage progressive validation
 * @param {Object} item - Item to verify (e.g., fix proposal, security finding)
 * @param {ModelStrategy} strategy - Strategy with getVerificationStages()
 * @returns {Promise<Object>} Verified result with confidence scores per stage
 */
async function runQuintupleVerification(item, strategy) {
  const stages = strategy.getVerificationStages();
  const results = { item, stages: {} };
  
  // Stage 1: Propose (already done - item is the proposal)
  results.stages.propose = { input: item, passed: true };
  
  // Stage 2: Peer Review - independent reviews
  phase(stages.review.phase);
  const reviews = await parallel(
    stages.review.models.map(model => () =>
      agent(`Peer review this proposal:\n\n${JSON.stringify(item)}\n\nIs it sound?`, {
        model,
        label: `${model} Review`,
        schema: {
          type: 'object',
          properties: {
            approved: {type: 'boolean'},
            concerns: {type: 'array', items: {type: 'string'}},
            confidence: {type: 'number', minimum: 0, maximum: 100}
          }
        }
      })
    )
  ).then(r => r.filter(Boolean));
  
  const reviewScore = reviews.filter(r => r.approved).length / reviews.length;
  results.stages.review = { reviews, passed: reviewScore >= 0.5, score: reviewScore };
  
  if (!results.stages.review.passed) {
    return { ...results, finalVerdict: 'REJECTED_AT_REVIEW', confidence: reviewScore * 100 };
  }
  
  // Stage 3: Adversarial Verification - try to break it
  phase(stages.verify.phase);
  const verifications = await parallel(
    stages.verify.models.map(model => () =>
      agent(`Adversarially verify - try to REFUTE this:\n\n${JSON.stringify(item)}\n\nFind flaws.`, {
        model,
        label: `${model} Verify`,
        schema: {
          type: 'object',
          properties: {
            refuted: {type: 'boolean'},
            flaws: {type: 'array', items: {type: 'string'}},
            confidence: {type: 'number'}
          }
        }
      })
    )
  ).then(r => r.filter(Boolean));
  
  const verifyScore = verifications.filter(v => !v.refuted).length / verifications.length;
  results.stages.verify = { verifications, passed: verifyScore >= 0.6, score: verifyScore };
  
  if (!results.stages.verify.passed) {
    return { ...results, finalVerdict: 'REFUTED_AT_VERIFICATION', confidence: verifyScore * 100 };
  }
  
  // Stage 4: Integration Validation - does it work in context?
  phase(stages.validate.phase);
  const validations = await parallel(
    stages.validate.models.map(model => () =>
      agent(`Validate integration:\n\n${JSON.stringify(item)}\n\nDoes it work in context?`, {
        model,
        label: `${model} Validate`,
        schema: {
          type: 'object',
          properties: {
            valid: {type: 'boolean'},
            integration_issues: {type: 'array'},
            confidence: {type: 'number'}
          }
        }
      })
    )
  ).then(r => r.filter(Boolean));
  
  const validateScore = validations.filter(v => v.valid).length / validations.length;
  results.stages.validate = { validations, passed: validateScore >= 0.5, score: validateScore };
  
  if (!results.stages.validate.passed) {
    return { ...results, finalVerdict: 'FAILED_VALIDATION', confidence: validateScore * 100 };
  }
  
  // Stage 5: Final Confirmation - arbiter decides
  phase(stages.confirm.phase);
  const confirmation = await runArbiterWithFallback(
    `Final confirmation:\n\n${JSON.stringify(item)}\n\nAll stages passed. Approve?`,
    strategy
  );
  
  results.stages.confirm = confirmation;
  
  const finalVerdict = confirmation.approved ? 'CONFIRMED' : 'REJECTED_AT_CONFIRMATION';
  const finalConfidence = (reviewScore + verifyScore + validateScore) / 3 * 100;
  
  return {
    ...results,
    finalVerdict,
    confidence: finalConfidence,
    arbiterConfidence: confirmation.confidence
  };
}
```

## Built-in Strategies

```javascript
/**
 * Quality-first: Most capable models, comprehensive analysis
 * Use for: Production, critical bugs, security audits
 * ALL MODELS for maximum coverage
 */
class QualityFirstStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku'];
    return this.filterAvailable(ideal);
  }
}

/**
 * Cost-optimized: Efficient models first, capable models as fallback
 * Use for: Development, testing, non-critical reviews
 * Balances coverage with cost
 */
class CostOptimizedStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['sonnet', 'haiku', 'gemini', 'gpt-4o'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['sonnet', 'haiku', 'opus', 'fable'];
    return this.filterAvailable(ideal);
  }
}

/**
 * Speed-optimized: Fastest models for rapid iteration
 * Use for: Quick checks, prototyping, exploratory work
 * Prioritizes fast models but includes capable fallbacks
 */
class SpeedOptimizedStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['haiku', 'sonnet', 'gemini'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['haiku', 'sonnet', 'opus', 'fable'];
    return this.filterAvailable(ideal);
  }
}

/**
 * Balanced: Mix of speed, cost, and quality
 * Use for: General purpose work
 * Good coverage across all model tiers
 */
class BalancedStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['opus', 'fable', 'sonnet', 'haiku'];
    return this.filterAvailable(ideal);
  }
}

/**
 * Free tier: Models available on free tier only
 * Use for: Limited API access
 */
class FreeTierStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['sonnet', 'haiku'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['sonnet', 'haiku'];
    return this.filterAvailable(ideal);
  }
}

/**
 * External diversity: Emphasize cross-provider perspectives
 * Use for: Maximum diversity, avoiding Claude-only blind spots
 * Full model spectrum with emphasis on external providers
 */
class ExternalDiversityStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['opus', 'fable', 'gemini', 'gpt-4o', 'sonnet'];
    return this.filterAvailable(ideal);
  }
}

/**
 * Maximum coverage: ALL available models for exhaustive analysis
 * Use for: Critical security audits, comprehensive reviews, zero-miss requirement
 * Most expensive but most thorough
 */
class MaximumCoverageStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
    return this.filterAvailable(ideal);
  }
}

/**
 * Quantized/Local models: Use local quantized models (Ollama) for workers, cloud for arbiter
 * Use for: Cost optimization, privacy, offline capability
 * Free workers (local), paid arbiter only
 */
class QuantizedStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['ollama:llama3', 'ollama:mistral', 'ollama:codellama', 'haiku', 'sonnet'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['fable', 'opus', 'sonnet'];  // Always use cloud for final decision
    return this.filterAvailable(ideal);
  }
}

/**
 * Quintuple Verification: 5-stage validation with progressive filtering
 * Use for: Mission-critical changes, high-risk deployments
 * Stages: Propose → Review → Verify → Validate → Confirm
 */
class QuintupleVerificationStrategy extends ModelStrategy {
  getWorkerModels() {
    const ideal = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'];
    return this.filterAvailable(ideal);
  }
  
  getArbiterFallback() {
    const ideal = ['fable', 'opus'];  // Only most capable for final confirmation
    return this.filterAvailable(ideal);
  }
  
  // Quintuple verification stages
  getVerificationStages() {
    return {
      propose: { models: this.getWorkerModels(), phase: 'Propose Solutions' },
      review: { models: this.getWorkerModels(), phase: 'Peer Review' },
      verify: { models: this.getWorkerModels(), phase: 'Adversarial Verification' },
      validate: { models: ['opus', 'sonnet'], phase: 'Integration Validation' },
      confirm: { models: this.getArbiterFallback(), phase: 'Final Confirmation' }
    }
  }
}
```

## Usage in Workflows

```javascript
// Default export strategies
export const meta = {
  name: 'example-workflow',
  description: 'Example with strategy pattern',
  phases: [{title: 'Analysis'}]
};

// Import or define strategy (would be passed via args in real implementation)
const strategy = new QualityFirstStrategy();  // Or CostOptimizedStrategy(), etc.

// Use strategy for workers
const workers = await parallel(
  items.flatMap(item => 
    strategy.getWorkerModels().map(model => () => 
      agent(prompt, {
        label: `${item.name}-${model}`,
        model: model
      })
    )
  )
).then(results => results.filter(Boolean));

// Use strategy for arbiter with fallback
async function runArbiterWithFallback(prompt) {
  const fallbackChain = strategy.getArbiterFallback();
  
  for (const model of fallbackChain) {
    try {
      return await agent(prompt, {model, phase: 'Arbiter'});
    } catch (e) {
      log(`⚠ ${model} arbiter failed: ${e.message}, trying next fallback`);
    }
  }
  throw new Error('All arbiter models failed');
}

const arbiter = await runArbiterWithFallback(arbiterPrompt);
```

## Passing Strategy via Workflow Args

```javascript
// Invoke workflow with strategy name
Workflow({
  scriptPath: '/path/to/workflow.js',
  args: {
    strategy: 'quality-first',  // or 'cost-optimized', 'speed-optimized', etc.
    items: [...]
  }
});

// In workflow script - AUTO-DISCOVER available models
phase('Discovery');
const availableModels = await discoverAvailableModels();
log(`Available models: ${availableModels.join(', ')}`);

const STRATEGIES = {
  'quality-first': new QualityFirstStrategy(availableModels),
  'cost-optimized': new CostOptimizedStrategy(availableModels),
  'speed-optimized': new SpeedOptimizedStrategy(availableModels),
  'balanced': new BalancedStrategy(availableModels),
  'free-tier': new FreeTierStrategy(availableModels),
  'external-diversity': new ExternalDiversityStrategy(availableModels),
  'maximum-coverage': new MaximumCoverageStrategy(availableModels),
  'quantized': new QuantizedStrategy(availableModels),  // NEW: Local models + cloud arbiter
  'quintuple-verification': new QuintupleVerificationStrategy(availableModels),  // NEW: 5-stage validation
};

const strategy = STRATEGIES[args.strategy || 'quality-first'];

// OR: Pass available models explicitly (skip discovery)
const strategy = new QualityFirstStrategy(['fable', 'opus', 'sonnet', 'haiku']);
```

## Python Implementation

```python
from abc import ABC, abstractmethod
from typing import List, Dict

class ModelStrategy(ABC):
    """Multi-model selection strategy"""
    
    @abstractmethod
    def get_worker_models(self) -> List[Dict[str, str]]:
        """Get worker models for parallel analysis"""
        pass
    
    @abstractmethod
    def get_arbiter_fallback(self) -> List[Dict[str, str]]:
        """Get arbiter fallback chain (priority order)"""
        pass
    
    def get_preferred_arbiter(self) -> Dict[str, str]:
        """Get preferred arbiter model"""
        return self.get_arbiter_fallback()[0]

class QualityFirstStrategy(ModelStrategy):
    def get_worker_models(self):
        return [
            {"provider": "anthropic", "model": "claude-fable-5"},
            {"provider": "anthropic", "model": "claude-opus-4-8"},
            {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            {"provider": "anthropic", "model": "claude-haiku-4-5"},
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "google", "model": "gemini-1.5-pro"}
        ]
    
    def get_arbiter_fallback(self):
        return [
            {"provider": "anthropic", "model": "claude-fable-5"},
            {"provider": "anthropic", "model": "claude-opus-4-8"},
            {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            {"provider": "anthropic", "model": "claude-haiku-4-5"}
        ]

class CostOptimizedStrategy(ModelStrategy):
    def get_worker_models(self):
        return [
            {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            {"provider": "anthropic", "model": "claude-haiku-4-5"},
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "google", "model": "gemini-1.5-pro"}
        ]
    
    def get_arbiter_fallback(self):
        return [
            {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            {"provider": "anthropic", "model": "claude-haiku-4-5"},
            {"provider": "anthropic", "model": "claude-opus-4-8"},
            {"provider": "anthropic", "model": "claude-fable-5"}
        ]

# Usage in Python SDLC
strategy = QualityFirstStrategy()  # Or get from config

role_config = RoleConfig(
    worker_models=strategy.get_worker_models(),
    arbiter_model=strategy.get_preferred_arbiter(),
    arbiter_fallback=strategy.get_arbiter_fallback()
)
```

**Benefits:**
- ✅ Single place to change model selection logic
- ✅ Easy to test different strategies
- ✅ Reusable across all workflows
- ✅ Type-safe and self-documenting
- ✅ Environment-specific optimization (dev vs prod)
- ✅ Cost control via strategy selection

**Apply to:** All arbiter/worker workflows (code-review, security, testing, SDLC, etc.)

**Related:** [[feedback_arbiter_worker_multi_model]], [[feedback_gemini_arbiter_fallback]]
