import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  calculateQualityScore,
  meetsQualityThreshold,
  formatQualityReport,
  categorizeIssuesBySeverity,
  prioritizeIssuesForFix,
  hasImproved,
  hasConverged,
  shouldContinueImproving
} from './quality-scorer.js'

// ========================================
// calculateQualityScore Tests
// ========================================

test('calculateQualityScore - empty array returns perfect score', () => {
  const result = calculateQualityScore([])
  assert.deepEqual(result, {
    score: 100,
    critical_count: 0,
    high_count: 0,
    medium_count: 0,
    low_count: 0,
    meets_threshold: true
  })
})

test('calculateQualityScore - null/undefined returns perfect score', () => {
  const resultNull = calculateQualityScore(null)
  assert.deepEqual(resultNull, {
    score: 100,
    critical_count: 0,
    high_count: 0,
    low_count: 0,
    medium_count: 0,
    meets_threshold: true
  })

  const resultUndefined = calculateQualityScore(undefined)
  assert.deepEqual(resultUndefined, {
    score: 100,
    critical_count: 0,
    high_count: 0,
    medium_count: 0,
    low_count: 0,
    meets_threshold: true
  })
})

test('calculateQualityScore - single critical issue', () => {
  const issues = [{ severity: 'critical', message: 'Critical bug' }]
  const result = calculateQualityScore(issues)
  assert.equal(result.score, 90) // 100 - 10
  assert.equal(result.critical_count, 1)
  assert.equal(result.high_count, 0)
  assert.equal(result.medium_count, 0)
  assert.equal(result.low_count, 0)
  assert.equal(result.meets_threshold, true) // Score is exactly 90
})

test('calculateQualityScore - mixed severities', () => {
  const issues = [
    { severity: 'critical', message: 'Critical 1' },
    { severity: 'P0', message: 'Critical 2' },
    { severity: 'high', message: 'High 1' },
    { severity: 'major', message: 'High 2' },
    { severity: 'P1', message: 'High 3' },
    { severity: 'medium', message: 'Medium 1' },
    { severity: 'P2', message: 'Medium 2' },
    { severity: 'low', message: 'Low 1' },
    { severity: 'minor', message: 'Low 2' },
    { severity: 'P3', message: 'Low 3' },
    { severity: 'P4', message: 'Low 4' }
  ]
  const result = calculateQualityScore(issues)
  // 2 critical × 10 = 20
  // 3 high × 5 = 15
  // 2 medium × 1 = 2
  // Total: 37 points deducted
  assert.equal(result.score, 63) // 100 - 37
  assert.equal(result.critical_count, 2)
  assert.equal(result.high_count, 3)
  assert.equal(result.medium_count, 2)
  assert.equal(result.low_count, 4)
  assert.equal(result.meets_threshold, false)
})

test('calculateQualityScore - edge case score=0', () => {
  const issues = Array(15).fill({ severity: 'critical' })
  const result = calculateQualityScore(issues)
  // 15 critical × 10 = 150, but score is clamped to 0
  assert.equal(result.score, 0)
  assert.equal(result.critical_count, 15)
  assert.equal(result.meets_threshold, false)
})

test('calculateQualityScore - low severity issues do not affect score', () => {
  const issues = [
    { severity: 'low', message: 'Low 1' },
    { severity: 'minor', message: 'Low 2' },
    { severity: 'P3', message: 'Low 3' },
    { severity: 'P4', message: 'Low 4' }
  ]
  const result = calculateQualityScore(issues)
  assert.equal(result.score, 100) // Low severity has no penalty
  assert.equal(result.low_count, 4)
})

// ========================================
// meetsQualityThreshold Tests
// ========================================

test('meetsQualityThreshold - default threshold 90', () => {
  const score90 = { score: 90 }
  const score89 = { score: 89 }
  const score91 = { score: 91 }

  assert.equal(meetsQualityThreshold(score90), true)
  assert.equal(meetsQualityThreshold(score89), false)
  assert.equal(meetsQualityThreshold(score91), true)
})

test('meetsQualityThreshold - custom threshold', () => {
  const score = { score: 75 }

  assert.equal(meetsQualityThreshold(score, 70), true)
  assert.equal(meetsQualityThreshold(score, 75), true)
  assert.equal(meetsQualityThreshold(score, 80), false)
})

// ========================================
// formatQualityReport Tests
// ========================================

test('formatQualityReport - all severity levels', () => {
  const qualityScore = {
    score: 63,
    critical_count: 2,
    high_count: 3,
    medium_count: 2,
    low_count: 4
  }

  const report = formatQualityReport(qualityScore)

  assert.match(report, /Quality Score.*63\/100/)
  assert.match(report, /Critical: 2/)
  assert.match(report, /High: 3/)
  assert.match(report, /Medium: 2/)
  assert.match(report, /Low: 4/)
  assert.match(report, /Total Impact.*-37/)
})

test('formatQualityReport - emoji for different scores', () => {
  const perfect = formatQualityReport({ score: 100, critical_count: 0, high_count: 0, medium_count: 0, low_count: 0 })
  assert.match(perfect, /✅/)

  const good = formatQualityReport({ score: 90, critical_count: 1, high_count: 0, medium_count: 0, low_count: 0 })
  assert.match(good, /✅/)

  const warning = formatQualityReport({ score: 85, critical_count: 0, high_count: 3, medium_count: 0, low_count: 0 })
  assert.match(warning, /🟡/)

  const caution = formatQualityReport({ score: 75, critical_count: 0, high_count: 5, medium_count: 0, low_count: 0 })
  assert.match(caution, /⚠️/)

  const critical = formatQualityReport({ score: 50, critical_count: 5, high_count: 0, medium_count: 0, low_count: 0 })
  assert.match(critical, /❌/)
})

// ========================================
// categorizeIssuesBySeverity Tests
// ========================================

test('categorizeIssuesBySeverity - correct bucketing of P0-P4 and named severities', () => {
  const issues = [
    { severity: 'critical', message: 'C1' },
    { severity: 'P0', message: 'C2' },
    { severity: 'high', message: 'H1' },
    { severity: 'major', message: 'H2' },
    { severity: 'P1', message: 'H3' },
    { severity: 'medium', message: 'M1' },
    { severity: 'P2', message: 'M2' },
    { severity: 'low', message: 'L1' },
    { severity: 'minor', message: 'L2' },
    { severity: 'P3', message: 'L3' },
    { severity: 'P4', message: 'L4' }
  ]

  const categorized = categorizeIssuesBySeverity(issues)

  assert.equal(categorized.critical.length, 2)
  assert.equal(categorized.high.length, 3)
  assert.equal(categorized.medium.length, 2)
  assert.equal(categorized.low.length, 4)

  assert.deepEqual(categorized.critical.map(i => i.message), ['C1', 'C2'])
  assert.deepEqual(categorized.high.map(i => i.message), ['H1', 'H2', 'H3'])
  assert.deepEqual(categorized.medium.map(i => i.message), ['M1', 'M2'])
  assert.deepEqual(categorized.low.map(i => i.message), ['L1', 'L2', 'L3', 'L4'])
})

test('categorizeIssuesBySeverity - empty array', () => {
  const categorized = categorizeIssuesBySeverity([])
  assert.equal(categorized.critical.length, 0)
  assert.equal(categorized.high.length, 0)
  assert.equal(categorized.medium.length, 0)
  assert.equal(categorized.low.length, 0)
})

// ========================================
// prioritizeIssuesForFix Tests
// ========================================

test('prioritizeIssuesForFix - sorting order', () => {
  const issues = [
    { severity: 'low', message: 'L1' },
    { severity: 'critical', message: 'C1' },
    { severity: 'medium', message: 'M1' },
    { severity: 'high', message: 'H1' },
    { severity: 'P4', message: 'L2' },
    { severity: 'P0', message: 'C2' },
    { severity: 'P2', message: 'M2' },
    { severity: 'major', message: 'H2' }
  ]

  const prioritized = prioritizeIssuesForFix(issues, 100)

  // Should be ordered: critical, high, medium, low
  assert.deepEqual(prioritized.map(i => i.message), ['C1', 'C2', 'H1', 'H2', 'M1', 'M2', 'L1', 'L2'])
})

test('prioritizeIssuesForFix - maxIssues limit', () => {
  const issues = Array(20).fill(null).map((_, i) => ({
    severity: 'medium',
    message: `Issue ${i + 1}`
  }))

  const prioritized = prioritizeIssuesForFix(issues, 5)
  assert.equal(prioritized.length, 5)
})

test('prioritizeIssuesForFix - confidence sorting for same severity', () => {
  const issues = [
    { severity: 'high', message: 'H1', confidence: 0.5 },
    { severity: 'high', message: 'H2', confidence: 0.9 },
    { severity: 'high', message: 'H3', confidence: 0.7 }
  ]

  const prioritized = prioritizeIssuesForFix(issues, 100)

  // Should be ordered by confidence (higher first) within same severity
  assert.deepEqual(prioritized.map(i => i.message), ['H2', 'H3', 'H1'])
})

test('prioritizeIssuesForFix - default maxIssues is 10', () => {
  const issues = Array(20).fill(null).map((_, i) => ({
    severity: 'medium',
    message: `Issue ${i + 1}`
  }))

  const prioritized = prioritizeIssuesForFix(issues)
  assert.equal(prioritized.length, 10)
})

// ========================================
// hasImproved Tests
// ========================================

test('hasImproved - score comparison', () => {
  const prev = { score: 75 }
  const current = { score: 80 }
  const currentSame = { score: 75 }
  const currentWorse = { score: 70 }

  assert.equal(hasImproved(prev, current), true)
  assert.equal(hasImproved(prev, currentSame), false)
  assert.equal(hasImproved(prev, currentWorse), false)
})

// ========================================
// hasConverged Tests
// ========================================

test('hasConverged - within tolerance and no critical issues', () => {
  const prev = { score: 90, critical_count: 1 }
  const current1 = { score: 91, critical_count: 0 } // Within tolerance, no critical
  const current2 = { score: 92, critical_count: 1 } // Within tolerance, but has critical
  const current3 = { score: 95, critical_count: 0 } // Outside tolerance, no critical

  assert.equal(hasConverged(prev, current1, 2), true)
  assert.equal(hasConverged(prev, current2, 2), false)
  assert.equal(hasConverged(prev, current3, 2), false)
})

test('hasConverged - custom tolerance', () => {
  const prev = { score: 90, critical_count: 0 }
  const current = { score: 95, critical_count: 0 }

  assert.equal(hasConverged(prev, current, 5), true)
  assert.equal(hasConverged(prev, current, 4), false)
})

test('hasConverged - exact same score', () => {
  const prev = { score: 90, critical_count: 0 }
  const current = { score: 90, critical_count: 0 }

  assert.equal(hasConverged(prev, current, 2), true)
})

// ========================================
// shouldContinueImproving Tests
// ========================================

test('shouldContinueImproving - target score reached', () => {
  const qualityScore = { score: 95 }
  const result = shouldContinueImproving(qualityScore, 95, 10, 1)

  assert.equal(result.continue, false)
  assert.equal(result.reason, 'target_score_reached')
})

test('shouldContinueImproving - max iterations reached', () => {
  const qualityScore = { score: 80 }
  const result = shouldContinueImproving(qualityScore, 95, 10, 10)

  assert.equal(result.continue, false)
  assert.equal(result.reason, 'max_iterations_reached')
})

test('shouldContinueImproving - perfect score', () => {
  // When score is 100 and targetScore < 100, returns target_score_reached
  const qualityScore = { score: 100 }
  const result1 = shouldContinueImproving(qualityScore, 95, 10, 1)
  assert.equal(result1.continue, false)
  assert.equal(result1.reason, 'target_score_reached')

  // When score is 100 and targetScore = 100, also returns target_score_reached
  const result2 = shouldContinueImproving(qualityScore, 100, 10, 1)
  assert.equal(result2.continue, false)
  assert.equal(result2.reason, 'target_score_reached')

  // The perfect_score reason is only reachable when score < targetScore but score === 100,
  // which is impossible since targetScore defaults to 95 and max score is 100.
  // So perfect_score is unreachable dead code in current implementation.
})

test('shouldContinueImproving - improvements needed', () => {
  const qualityScore = { score: 85 }
  const result = shouldContinueImproving(qualityScore, 95, 10, 5)

  assert.equal(result.continue, true)
  assert.equal(result.reason, 'improvements_needed')
})

test('shouldContinueImproving - target exceeded still stops', () => {
  const qualityScore = { score: 97 }
  const result = shouldContinueImproving(qualityScore, 95, 10, 1)

  assert.equal(result.continue, false)
  assert.equal(result.reason, 'target_score_reached')
})
