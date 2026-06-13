// load-multi-ai-config.test.js - Unit tests for load-multi-ai-config utility
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'fs'

describe('load-multi-ai-config.js default config structure', () => {
  let loadMultiAIConfig

  it('should load the function from file', () => {
    const fileContent = readFileSync('/home/sfloess/Development/redhat/scm/gitlab/cee/sfloess/claude-global-skills/load-multi-ai-config.js', 'utf8')

    // Execute the file content and extract the function
    loadMultiAIConfig = new Function(fileContent + '; return loadMultiAIConfig;')()

    assert.ok(loadMultiAIConfig, 'loadMultiAIConfig function should be loaded')
    assert.strictEqual(typeof loadMultiAIConfig, 'function', 'loadMultiAIConfig should be a function')
  })

  it('should return a config object', () => {
    const config = loadMultiAIConfig()

    assert.ok(config, 'Config should be returned')
    assert.strictEqual(typeof config, 'object', 'Config should be an object')
  })

  it('should have enabled field set to true', () => {
    const config = loadMultiAIConfig()

    assert.ok('enabled' in config, 'Config should have enabled field')
    assert.strictEqual(config.enabled, true, 'enabled should be true')
  })

  it('should have default_strategy field', () => {
    const config = loadMultiAIConfig()

    assert.ok('default_strategy' in config, 'Config should have default_strategy field')
    assert.strictEqual(typeof config.default_strategy, 'string', 'default_strategy should be a string')
    assert.strictEqual(config.default_strategy, 'maximum-coverage', 'default_strategy should be maximum-coverage')
  })

  it('should have workers object with models array', () => {
    const config = loadMultiAIConfig()

    assert.ok('workers' in config, 'Config should have workers field')
    assert.strictEqual(typeof config.workers, 'object', 'workers should be an object')
    assert.ok('models' in config.workers, 'workers should have models field')
    assert.ok(Array.isArray(config.workers.models), 'workers.models should be an array')
  })

  it('should have workers.models with exactly 6 entries', () => {
    const config = loadMultiAIConfig()

    assert.strictEqual(config.workers.models.length, 6, 'workers.models should have 6 entries')

    // Verify expected models
    const expectedModels = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
    assert.deepStrictEqual(config.workers.models, expectedModels, 'workers.models should contain all 6 expected models')
  })

  it('should have workers.count set to 6', () => {
    const config = loadMultiAIConfig()

    assert.ok('count' in config.workers, 'workers should have count field')
    assert.strictEqual(config.workers.count, 6, 'workers.count should be 6')
  })

  it('should have arbiter object', () => {
    const config = loadMultiAIConfig()

    assert.ok('arbiter' in config, 'Config should have arbiter field')
    assert.strictEqual(typeof config.arbiter, 'object', 'arbiter should be an object')
  })

  it('should have arbiter.enabled set to true', () => {
    const config = loadMultiAIConfig()

    assert.ok('enabled' in config.arbiter, 'arbiter should have enabled field')
    assert.strictEqual(config.arbiter.enabled, true, 'arbiter.enabled should be true')
  })

  it('should have arbiter.model field', () => {
    const config = loadMultiAIConfig()

    assert.ok('model' in config.arbiter, 'arbiter should have model field')
    assert.strictEqual(typeof config.arbiter.model, 'string', 'arbiter.model should be a string')
    assert.strictEqual(config.arbiter.model, 'fable', 'arbiter.model should be fable')
  })

  it('should have arbiter.fallback array', () => {
    const config = loadMultiAIConfig()

    assert.ok('fallback' in config.arbiter, 'arbiter should have fallback field')
    assert.ok(Array.isArray(config.arbiter.fallback), 'arbiter.fallback should be an array')
    assert.ok(config.arbiter.fallback.length > 0, 'arbiter.fallback should have at least one entry')

    // Verify fallback contains expected models
    const expectedFallback = ['fable', 'opus', 'sonnet', 'haiku']
    assert.deepStrictEqual(config.arbiter.fallback, expectedFallback, 'arbiter.fallback should contain expected fallback models')
  })

  it('should have all required fields in complete structure', () => {
    const config = loadMultiAIConfig()

    // Comprehensive check of entire structure
    const requiredStructure = {
      enabled: true,
      default_strategy: 'maximum-coverage',
      workers: {
        models: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
        count: 6
      },
      arbiter: {
        enabled: true,
        model: 'fable',
        fallback: ['fable', 'opus', 'sonnet', 'haiku']
      }
    }

    assert.deepStrictEqual(config, requiredStructure, 'Config should match required structure exactly')
  })
})
