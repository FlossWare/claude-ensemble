/**
 * Model Configuration Loader
 * Reads ~/.claude/rh-toolkit-models.yaml to get available models
 * Falls back to hardcoded defaults if config file not found
 */

import fs from 'node:fs'
import path from 'node:path'
import yaml from 'js-yaml'

function loadUserModelConfig() {
  const configPath = path.join(process.env.HOME || '', '.claude', 'rh-toolkit-models.yaml')

  try {
    if (!fs.existsSync(configPath)) {
      console.warn(`[ModelConfig] Config not found at ${configPath}, using defaults`)
      return null
    }

    const content = fs.readFileSync(configPath, 'utf8')
    const config = yaml.load(content)

    console.log(`[ModelConfig] Loaded from ${configPath}`)
    return config
  } catch (err) {
    console.warn(`[ModelConfig] Failed to load config: ${err.message}, using defaults`)
    return null
  }
}

function getAvailableModels(config) {
  if (!config || !config.models) return null

  return Object.entries(config.models)
    .filter(([name, model]) => model.available === true)
    .map(([name, model]) => ({
      name,
      id: model.id,
      provider: model.provider,
      pricing: model.pricing,
      capabilities: model.capabilities || []
    }))
}

function getModelPricing(config, modelId) {
  if (!config || !config.models) return null

  for (const [name, model] of Object.entries(config.models)) {
    if (model.id === modelId && model.available) {
      return {
        model: modelId,
        input_per_m: model.pricing?.input_per_m || 0,
        output_per_m: model.pricing?.output_per_m || 0
      }
    }
  }

  return null
}

function getSkillWorkers(config, skillName) {
  if (!config || !config.skill_defaults || !config.skill_defaults[skillName]) {
    return null
  }

  const skillConfig = config.skill_defaults[skillName]
  const availableModels = getAvailableModels(config)
  const configuredModels = skillConfig.models || skillConfig.enabled_models || skillConfig.workers || []

  if (!availableModels) return configuredModels

  return configuredModels.filter(modelName => {
    const model = config.models[modelName]
    return model && model.available === true
  })
}

function getSkillArbiter(config, skillName) {
  if (!config || !config.skill_defaults || !config.skill_defaults[skillName]) {
    return 'opus'  // Default
  }

  return config.skill_defaults[skillName].arbiter || 'opus'
}

function calculateCostFromConfig(config, model, inputTokens, outputTokens) {
  if (!config || !config.models) return 0

  for (const [name, modelCfg] of Object.entries(config.models)) {
    if ((modelCfg.id === model || name === model) && modelCfg.available) {
      const pricing = modelCfg.pricing
      const inputCost = (inputTokens / 1_000_000) * (pricing.input_per_m || 0)
      const outputCost = (outputTokens / 1_000_000) * (pricing.output_per_m || 0)
      return inputCost + outputCost
    }
  }

  return 0
}

export {
  loadUserModelConfig,
  getAvailableModels,
  getModelPricing,
  getSkillWorkers,
  getSkillArbiter,
  calculateCostFromConfig
}
