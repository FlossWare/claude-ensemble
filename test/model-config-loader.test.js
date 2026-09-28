import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  DEFAULT_MODEL_CONFIG_PATH,
  ModelConfigValidationError,
  getSkillArbiter,
  getSkillModels,
  loadUserModelConfig
} from '../shared/model-config-loader.js'

test('default model config path uses the current home directory', () => {
  assert.equal(DEFAULT_MODEL_CONFIG_PATH, path.join(os.homedir(), '.claude', 'rh-toolkit-models.yaml'))
})

test('explicit config path loads a valid models and skill_defaults configuration', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-ensemble-'))
  const configPath = path.join(tempDir, 'models.yaml')
  try {
    fs.writeFileSync(configPath, 'models:\n  test-model:\n    id: test-model\n    available: true\nskill_defaults:\n  test-skill:\n    models: [test-model]\n    arbiter: test-model\n')
    const config = loadUserModelConfig(configPath)
    assert.deepEqual(getSkillModels(config, 'test-skill'), ['test-model'])
    assert.equal(getSkillArbiter(config, 'test-skill'), 'test-model')
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
})

test('unavailable configured models are filtered from skill routing', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-ensemble-'))
  const configPath = path.join(tempDir, 'models.yaml')
  try {
    fs.writeFileSync(configPath, 'models:\n  available-model:\n    id: available-model\n    available: true\n  unavailable-model:\n    id: unavailable-model\n    available: false\nskill_defaults:\n  test-skill:\n    models: [available-model, unavailable-model]\n    arbiter: available-model\n')
    const config = loadUserModelConfig(configPath)
    assert.deepEqual(getSkillModels(config, 'test-skill'), ['available-model'])
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
})

test('invalid skill model references fail with a useful error', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-ensemble-'))
  const configPath = path.join(tempDir, 'models.yaml')
  try {
    fs.writeFileSync(configPath, 'models:\n  test-model:\n    id: test-model\n    available: true\nskill_defaults:\n  test-skill:\n    models: [missing-model]\n    arbiter: test-model\n')
    assert.throws(() => loadUserModelConfig(configPath), error =>
      error instanceof ModelConfigValidationError &&
      error.message.includes("skill_defaults.test-skill.models references unknown model 'missing-model'")
    )
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
})

test('unavailable arbiter references fail validation', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-ensemble-'))
  const configPath = path.join(tempDir, 'models.yaml')
  try {
    fs.writeFileSync(configPath, 'models:\n  worker-model:\n    id: worker-model\n    available: true\n  arbiter-model:\n    id: arbiter-model\n    available: false\nskill_defaults:\n  test-skill:\n    models: [worker-model]\n    arbiter: arbiter-model\n')
    assert.throws(() => loadUserModelConfig(configPath), error =>
      error instanceof ModelConfigValidationError &&
      error.message.includes("skill_defaults.test-skill.arbiter references unavailable model 'arbiter-model'")
    )
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
})

test('missing config returns the documented fallback', () => {
  const missingPath = path.join(os.tmpdir(), 'claude-ensemble-missing-models.yaml')
  assert.equal(loadUserModelConfig(missingPath), null)
})
