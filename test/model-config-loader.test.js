import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  DEFAULT_MODEL_CONFIG_PATH,
  loadUserModelConfig
} from '../shared/model-config-loader.js'

test('default model config path uses the current home directory', () => {
  assert.equal(
    DEFAULT_MODEL_CONFIG_PATH,
    path.join(os.homedir(), '.claude', 'rh-toolkit-models.yaml')
  )
})

test('explicit config path loads the requested configuration', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-ensemble-'))
  const configPath = path.join(tempDir, 'models.yaml')

  try {
    fs.writeFileSync(
      configPath,
      'models:\n  test-model:\n    id: test-model\n    available: true\n'
    )

    assert.deepEqual(loadUserModelConfig(configPath), {
      models: {
        'test-model': {
          id: 'test-model',
          available: true
        }
      }
    })
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
})

test('missing config returns the documented fallback', () => {
  const missingPath = path.join(
    os.tmpdir(),
    'claude-ensemble-missing-models.yaml'
  )

  assert.equal(loadUserModelConfig(missingPath), null)
})
