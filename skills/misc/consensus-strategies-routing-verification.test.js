// Additional routing logic verification test
// This test verifies the autoSelectStrategy routing by code inspection
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

describe('autoSelectStrategy routing logic verification (code inspection)', () => {
  let sourceCode

  it('should load source code', () => {
    sourceCode = readFileSync('./consensus-strategies.js', 'utf8')
    assert.ok(sourceCode, 'Source code should be loaded')
  })

  it('should verify critical=true routes to rotatingArbiter', () => {
    // Find the autoSelectStrategy function
    const fnMatch = sourceCode.match(/export async function autoSelectStrategy[\s\S]*?^}/m)
    assert.ok(fnMatch, 'Should find autoSelectStrategy function')

    const fnBody = fnMatch[0]

    // Verify the routing logic structure
    assert.ok(fnBody.includes('if (critical)'), 'Should check critical flag')
    assert.ok(fnBody.includes('return rotatingArbiter(workers, prompt, schema)'), 'Should route to rotatingArbiter when critical')

    // Verify critical comes first (highest priority)
    const criticalIndex = fnBody.indexOf('if (critical)')
    const fastIndex = fnBody.indexOf('if (fast)')
    const diverseIndex = fnBody.indexOf('if (diverse)')

    assert.ok(criticalIndex < fastIndex, 'critical check should come before fast check')
    assert.ok(criticalIndex < diverseIndex, 'critical check should come before diverse check')
  })

  it('should verify fast=true routes to majorityVote', () => {
    const fnMatch = sourceCode.match(/export async function autoSelectStrategy[\s\S]*?^}/m)
    const fnBody = fnMatch[0]

    assert.ok(fnBody.includes('if (fast)'), 'Should check fast flag')
    assert.ok(fnBody.includes('return majorityVote(workers, prompt, schema)'), 'Should route to majorityVote when fast')

    // Verify fast comes after critical but before diverse
    const criticalIndex = fnBody.indexOf('if (critical)')
    const fastIndex = fnBody.indexOf('if (fast)')
    const diverseIndex = fnBody.indexOf('if (diverse)')

    assert.ok(fastIndex > criticalIndex, 'fast check should come after critical check')
    assert.ok(fastIndex < diverseIndex, 'fast check should come before diverse check')
  })

  it('should verify diverse=true routes to pairwiseComparison', () => {
    const fnMatch = sourceCode.match(/export async function autoSelectStrategy[\s\S]*?^}/m)
    const fnBody = fnMatch[0]

    assert.ok(fnBody.includes('if (diverse)'), 'Should check diverse flag')
    assert.ok(fnBody.includes('return pairwiseComparison(workers, prompt, schema)'), 'Should route to pairwiseComparison when diverse')

    // Verify diverse comes after critical and fast
    const criticalIndex = fnBody.indexOf('if (critical)')
    const fastIndex = fnBody.indexOf('if (fast)')
    const diverseIndex = fnBody.indexOf('if (diverse)')

    assert.ok(diverseIndex > criticalIndex, 'diverse check should come after critical check')
    assert.ok(diverseIndex > fastIndex, 'diverse check should come after fast check')
  })

  it('should verify default routes to rotatingArbiter', () => {
    const fnMatch = sourceCode.match(/export async function autoSelectStrategy[\s\S]*?^}/m)
    const fnBody = fnMatch[0]

    // After all if statements, should default to rotatingArbiter
    assert.ok(fnBody.includes('return rotatingArbiter(workers, prompt, schema)'), 'Should have rotatingArbiter return statement')

    // Count how many times rotatingArbiter is returned
    const rotatingReturns = (fnBody.match(/return rotatingArbiter\(workers, prompt, schema\)/g) || []).length
    assert.strictEqual(rotatingReturns, 2, 'Should return rotatingArbiter twice: once for critical, once for default')
  })

  it('should verify context parameter destructuring', () => {
    const fnMatch = sourceCode.match(/export async function autoSelectStrategy[\s\S]*?^}/m)
    const fnBody = fnMatch[0]

    // Should destructure critical, fast, diverse from context
    assert.ok(fnBody.includes('critical = false'), 'Should destructure critical with default false')
    assert.ok(fnBody.includes('fast = false'), 'Should destructure fast with default false')
    assert.ok(fnBody.includes('diverse = false'), 'Should destructure diverse with default false')
  })

  it('should verify log messages for each route', () => {
    const fnMatch = sourceCode.match(/export async function autoSelectStrategy[\s\S]*?^}/m)
    const fnBody = fnMatch[0]

    // Each route should have a log message
    assert.ok(fnBody.includes("log('Auto-selected: rotating arbiter (critical task)')"), 'Should log critical route')
    assert.ok(fnBody.includes("log('Auto-selected: majority vote (fast result needed)')"), 'Should log fast route')
    assert.ok(fnBody.includes("log('Auto-selected: pairwise comparison (diverse solutions expected)')"), 'Should log diverse route')
    assert.ok(fnBody.includes("log('Auto-selected: rotating arbiter (maximum quality)')"), 'Should log default route')
  })
})
