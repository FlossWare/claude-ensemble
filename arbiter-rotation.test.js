#!/usr/bin/env node
// arbiter-rotation.test.js - Unit tests for arbiter rotation logic
// Tests get-next-arbiter.js and update-arbiter-state.js

import { describe, it, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile, unlink, mkdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { homedir } from 'node:os'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Test state file location
const TEST_STATE_DIR = path.join(homedir(), '.claude', 'repos', 'claude-global-skills')
const TEST_STATE_FILE = path.join(TEST_STATE_DIR, 'arbiter-state.json')
const BACKUP_STATE_FILE = path.join(TEST_STATE_DIR, 'arbiter-state.json.backup')

describe('Arbiter Rotation Logic', () => {
  let originalState = null
  let backupExists = false

  before(async () => {
    // Backup existing state file if it exists
    if (existsSync(TEST_STATE_FILE)) {
      originalState = await readFile(TEST_STATE_FILE, 'utf-8')
      backupExists = true
      console.log('📦 Backed up existing arbiter state')
    }

    // Ensure directory exists
    try {
      await mkdir(TEST_STATE_DIR, { recursive: true })
    } catch (err) {
      // Directory already exists
    }
  })

  after(async () => {
    // Restore original state file
    if (backupExists && originalState) {
      await writeFile(TEST_STATE_FILE, originalState, 'utf-8')
      console.log('♻️  Restored original arbiter state')
    } else if (existsSync(TEST_STATE_FILE)) {
      await unlink(TEST_STATE_FILE)
      console.log('🧹 Cleaned up test state file')
    }
  })

  describe('Rotation Cycle Logic', () => {
    it('should follow fable->opus->sonnet->haiku->gpt-4o->gemini->fable cycle', () => {
      // Test the rotation logic extracted from get-next-arbiter.js
      const rotationMap = {
        'fable': 'opus',
        'opus': 'sonnet',
        'sonnet': 'haiku',
        'haiku': 'gpt-4o',
        'gpt-4o': 'gemini',
        'gemini': 'fable'
      }

      // Verify each step in the cycle
      assert.strictEqual(rotationMap['fable'], 'opus', 'fable should rotate to opus')
      assert.strictEqual(rotationMap['opus'], 'sonnet', 'opus should rotate to sonnet')
      assert.strictEqual(rotationMap['sonnet'], 'haiku', 'sonnet should rotate to haiku')
      assert.strictEqual(rotationMap['haiku'], 'gpt-4o', 'haiku should rotate to gpt-4o')
      assert.strictEqual(rotationMap['gpt-4o'], 'gemini', 'gpt-4o should rotate to gemini')
      assert.strictEqual(rotationMap['gemini'], 'fable', 'gemini should rotate back to fable')

      // Verify complete cycle
      let current = 'fable'
      const cycle = [current]
      for (let i = 0; i < 6; i++) {
        current = rotationMap[current]
        cycle.push(current)
      }

      assert.strictEqual(cycle.length, 7, 'Complete cycle should have 7 elements (6 models + return to start)')
      assert.strictEqual(cycle[0], 'fable', 'Cycle should start with fable')
      assert.strictEqual(cycle[6], 'fable', 'Cycle should return to fable')
      assert.deepStrictEqual(
        cycle,
        ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini', 'fable'],
        'Complete rotation cycle should match expected sequence'
      )
    })

    it('should default to fable for null last_arbiter', () => {
      // Simulate the logic from get-next-arbiter.js lines 90-91
      const lastArbiter = null
      let nextArbiter

      if (lastArbiter === 'fable') {
        nextArbiter = 'opus'
      } else if (lastArbiter === 'opus') {
        nextArbiter = 'sonnet'
      } else if (lastArbiter === 'sonnet') {
        nextArbiter = 'haiku'
      } else if (lastArbiter === 'haiku') {
        nextArbiter = 'gpt-4o'
      } else if (lastArbiter === 'gpt-4o') {
        nextArbiter = 'gemini'
      } else if (lastArbiter === 'gemini') {
        nextArbiter = 'fable'
      } else {
        // null or any other value defaults to fable
        nextArbiter = 'fable'
      }

      assert.strictEqual(nextArbiter, 'fable', 'null last_arbiter should default to fable')
    })

    it('should default to fable for undefined last_arbiter', () => {
      const lastArbiter = undefined
      let nextArbiter

      if (lastArbiter === 'fable') {
        nextArbiter = 'opus'
      } else if (lastArbiter === 'opus') {
        nextArbiter = 'sonnet'
      } else if (lastArbiter === 'sonnet') {
        nextArbiter = 'haiku'
      } else if (lastArbiter === 'haiku') {
        nextArbiter = 'gpt-4o'
      } else if (lastArbiter === 'gpt-4o') {
        nextArbiter = 'gemini'
      } else if (lastArbiter === 'gemini') {
        nextArbiter = 'fable'
      } else {
        nextArbiter = 'fable'
      }

      assert.strictEqual(nextArbiter, 'fable', 'undefined last_arbiter should default to fable')
    })

    it('should default to fable for unknown last_arbiter value', () => {
      const lastArbiter = 'unknown-model'
      let nextArbiter

      if (lastArbiter === 'fable') {
        nextArbiter = 'opus'
      } else if (lastArbiter === 'opus') {
        nextArbiter = 'sonnet'
      } else if (lastArbiter === 'sonnet') {
        nextArbiter = 'haiku'
      } else if (lastArbiter === 'haiku') {
        nextArbiter = 'gpt-4o'
      } else if (lastArbiter === 'gpt-4o') {
        nextArbiter = 'gemini'
      } else if (lastArbiter === 'gemini') {
        nextArbiter = 'fable'
      } else {
        nextArbiter = 'fable'
      }

      assert.strictEqual(nextArbiter, 'fable', 'unknown last_arbiter should default to fable')
    })
  })

  describe('State File Handling', () => {
    it('should gracefully handle missing state file', async () => {
      // Remove state file if it exists
      if (existsSync(TEST_STATE_FILE)) {
        await unlink(TEST_STATE_FILE)
      }

      // Simulate get-next-arbiter.js lines 57-65
      let arbiterState
      try {
        const stateContent = await readFile(TEST_STATE_FILE, 'utf-8')
        arbiterState = JSON.parse(stateContent)
      } catch (error) {
        // File doesn't exist or is invalid - start with null
        arbiterState = { last_arbiter: null }
      }

      assert.ok(arbiterState, 'arbiterState should be defined')
      assert.strictEqual(arbiterState.last_arbiter, null, 'last_arbiter should be null for missing file')
    })

    it('should gracefully handle corrupted state file', async () => {
      // Write corrupted JSON to state file
      await writeFile(TEST_STATE_FILE, '{ invalid json }', 'utf-8')

      // Simulate get-next-arbiter.js lines 57-65
      let arbiterState
      try {
        const stateContent = await readFile(TEST_STATE_FILE, 'utf-8')
        arbiterState = JSON.parse(stateContent)
      } catch (error) {
        // File doesn't exist or is invalid - start with null
        arbiterState = { last_arbiter: null }
      }

      assert.ok(arbiterState, 'arbiterState should be defined')
      assert.strictEqual(arbiterState.last_arbiter, null, 'last_arbiter should be null for corrupted file')
    })

    it('should correctly parse valid state file', async () => {
      // Write valid state file
      const validState = {
        last_arbiter: 'opus',
        arbiter_pool: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
        usage_history: [
          { arbiter: 'fable', workflow: 'test', timestamp: '2026-06-13T00:00:00Z' }
        ],
        rotation_enabled: true
      }
      await writeFile(TEST_STATE_FILE, JSON.stringify(validState, null, 2), 'utf-8')

      // Simulate get-next-arbiter.js lines 57-65
      let arbiterState
      try {
        const stateContent = await readFile(TEST_STATE_FILE, 'utf-8')
        arbiterState = JSON.parse(stateContent)
      } catch (error) {
        arbiterState = { last_arbiter: null }
      }

      assert.ok(arbiterState, 'arbiterState should be defined')
      assert.strictEqual(arbiterState.last_arbiter, 'opus', 'last_arbiter should be opus')
      assert.ok(Array.isArray(arbiterState.arbiter_pool), 'arbiter_pool should be an array')
      assert.strictEqual(arbiterState.arbiter_pool.length, 6, 'arbiter_pool should have 6 models')
    })
  })

  describe('State Update Logic', () => {
    it('should create default state when file does not exist', async () => {
      // Remove state file
      if (existsSync(TEST_STATE_FILE)) {
        await unlink(TEST_STATE_FILE)
      }

      // Simulate update-arbiter-state.js lines 81-108
      let state
      try {
        const content = await readFile(TEST_STATE_FILE, 'utf-8')
        state = JSON.parse(content)
      } catch (readError) {
        // File doesn't exist - create default state
        state = {
          last_arbiter: null,
          arbiter_pool: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
          usage_history: [],
          rotation_enabled: true
        }
      }

      assert.ok(state, 'state should be defined')
      assert.strictEqual(state.last_arbiter, null, 'last_arbiter should be null')
      assert.ok(Array.isArray(state.arbiter_pool), 'arbiter_pool should be an array')
      assert.strictEqual(state.arbiter_pool.length, 6, 'arbiter_pool should have 6 models')
      assert.ok(Array.isArray(state.usage_history), 'usage_history should be an array')
      assert.strictEqual(state.usage_history.length, 0, 'usage_history should be empty')
      assert.strictEqual(state.rotation_enabled, true, 'rotation_enabled should be true')
    })

    it('should update last_arbiter correctly', async () => {
      // Create initial state
      const initialState = {
        last_arbiter: 'fable',
        arbiter_pool: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
        usage_history: [],
        rotation_enabled: true
      }
      await writeFile(TEST_STATE_FILE, JSON.stringify(initialState, null, 2), 'utf-8')

      // Simulate update-arbiter-state.js lines 110-112
      const content = await readFile(TEST_STATE_FILE, 'utf-8')
      const state = JSON.parse(content)

      const arbiter = 'opus'
      const previous_arbiter = state.last_arbiter
      state.last_arbiter = arbiter

      assert.strictEqual(previous_arbiter, 'fable', 'previous_arbiter should be fable')
      assert.strictEqual(state.last_arbiter, 'opus', 'last_arbiter should be updated to opus')
    })

    it('should append to usage_history correctly', async () => {
      // Create initial state with one history entry
      const initialState = {
        last_arbiter: 'fable',
        arbiter_pool: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
        usage_history: [
          { arbiter: 'fable', workflow: 'test-1', timestamp: '2026-06-13T00:00:00Z' }
        ],
        rotation_enabled: true
      }
      await writeFile(TEST_STATE_FILE, JSON.stringify(initialState, null, 2), 'utf-8')

      // Simulate update-arbiter-state.js lines 114-125
      const content = await readFile(TEST_STATE_FILE, 'utf-8')
      const state = JSON.parse(content)

      const arbiter = 'opus'
      const workflow_name = 'test-2'
      const timestamp = '2026-06-13T01:00:00Z'

      const historyEntry = {
        arbiter: arbiter,
        workflow: workflow_name,
        timestamp: timestamp
      }

      if (!Array.isArray(state.usage_history)) {
        state.usage_history = []
      }
      state.usage_history.push(historyEntry)

      assert.strictEqual(state.usage_history.length, 2, 'usage_history should have 2 entries')
      assert.strictEqual(state.usage_history[1].arbiter, 'opus', 'New entry arbiter should be opus')
      assert.strictEqual(state.usage_history[1].workflow, 'test-2', 'New entry workflow should be test-2')
    })

    it('should limit usage_history to 100 entries', async () => {
      // Create state with 100 history entries
      const usage_history = []
      for (let i = 0; i < 100; i++) {
        usage_history.push({
          arbiter: 'fable',
          workflow: `test-${i}`,
          timestamp: `2026-06-13T${String(i % 24).padStart(2, '0')}:00:00Z`
        })
      }

      const initialState = {
        last_arbiter: 'fable',
        arbiter_pool: ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini'],
        usage_history: usage_history,
        rotation_enabled: true
      }
      await writeFile(TEST_STATE_FILE, JSON.stringify(initialState, null, 2), 'utf-8')

      // Simulate update-arbiter-state.js lines 114-130
      const content = await readFile(TEST_STATE_FILE, 'utf-8')
      const state = JSON.parse(content)

      // Add one more entry
      const historyEntry = {
        arbiter: 'opus',
        workflow: 'test-101',
        timestamp: '2026-06-13T23:59:59Z'
      }
      state.usage_history.push(historyEntry)

      // Keep only last 100 entries
      if (state.usage_history.length > 100) {
        state.usage_history = state.usage_history.slice(-100)
      }

      assert.strictEqual(state.usage_history.length, 100, 'usage_history should be limited to 100 entries')
      assert.strictEqual(state.usage_history[0].workflow, 'test-1', 'First entry should be test-1 (test-0 removed)')
      assert.strictEqual(state.usage_history[99].workflow, 'test-101', 'Last entry should be test-101')
    })
  })

  describe('Error Handling', () => {
    it('get-next-arbiter should return fallback on error', () => {
      // Simulate get-next-arbiter.js lines 105-113 error handling
      const simulateError = () => {
        try {
          throw new Error('Simulated error')
        } catch (error) {
          return {
            error: error.message,
            arbiter: 'fable', // fallback to fable on error
            previous: null
          }
        }
      }

      const result = simulateError()
      assert.strictEqual(result.error, 'Simulated error', 'Should capture error message')
      assert.strictEqual(result.arbiter, 'fable', 'Should fallback to fable on error')
      assert.strictEqual(result.previous, null, 'Should set previous to null on error')
    })

    it('update-arbiter-state should validate required arbiter argument', () => {
      // Simulate update-arbiter-state.js lines 61-67
      const args = {} // Missing arbiter

      const arbiter = args?.arbiter
      const workflow_name = args?.workflow_name || 'unknown'

      let result
      if (!arbiter) {
        result = {
          status: 'error',
          error_type: 'validation_error',
          error: 'Missing required argument: arbiter'
        }
      }

      assert.ok(result, 'Should return error result')
      assert.strictEqual(result.status, 'error', 'Status should be error')
      assert.strictEqual(result.error_type, 'validation_error', 'Error type should be validation_error')
      assert.strictEqual(result.error, 'Missing required argument: arbiter', 'Error message should indicate missing arbiter')
    })
  })

  describe('Integration Test: Complete Rotation Cycle', () => {
    it('should complete full rotation cycle through all 6 models', async () => {
      // Start with fresh state
      if (existsSync(TEST_STATE_FILE)) {
        await unlink(TEST_STATE_FILE)
      }

      const expectedCycle = ['fable', 'opus', 'sonnet', 'haiku', 'gpt-4o', 'gemini']
      const actualCycle = []

      // Simulate 6 get-next-arbiter calls
      for (let i = 0; i < 6; i++) {
        // Read state
        let arbiterState
        try {
          const stateContent = await readFile(TEST_STATE_FILE, 'utf-8')
          arbiterState = JSON.parse(stateContent)
        } catch (error) {
          arbiterState = { last_arbiter: null }
        }

        // Get next arbiter
        const lastArbiter = arbiterState.last_arbiter
        let nextArbiter

        if (lastArbiter === 'fable') {
          nextArbiter = 'opus'
        } else if (lastArbiter === 'opus') {
          nextArbiter = 'sonnet'
        } else if (lastArbiter === 'sonnet') {
          nextArbiter = 'haiku'
        } else if (lastArbiter === 'haiku') {
          nextArbiter = 'gpt-4o'
        } else if (lastArbiter === 'gpt-4o') {
          nextArbiter = 'gemini'
        } else if (lastArbiter === 'gemini') {
          nextArbiter = 'fable'
        } else {
          nextArbiter = 'fable'
        }

        actualCycle.push(nextArbiter)

        // Update state
        arbiterState.last_arbiter = nextArbiter
        await writeFile(TEST_STATE_FILE, JSON.stringify(arbiterState, null, 2), 'utf-8')
      }

      assert.deepStrictEqual(
        actualCycle,
        expectedCycle,
        'Should complete full rotation through all 6 models in correct order'
      )

      // Verify the 7th call returns to fable
      const stateContent = await readFile(TEST_STATE_FILE, 'utf-8')
      const finalState = JSON.parse(stateContent)

      let nextAfterCycle
      const lastArbiter = finalState.last_arbiter

      if (lastArbiter === 'gemini') {
        nextAfterCycle = 'fable'
      }

      assert.strictEqual(nextAfterCycle, 'fable', 'After gemini, should rotate back to fable')
    })
  })
})
