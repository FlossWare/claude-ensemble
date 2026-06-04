// Quality Scoring System
// Used by: code-improve, code-solve, pr-review
// Consistent quality calculation across workflows

export function calculateQualityScore(issues) {
  if (!Array.isArray(issues) || issues.length === 0) {
    return {
      score: 100,
      critical_count: 0,
      high_count: 0,
      medium_count: 0,
      low_count: 0,
      meets_threshold: true
    }
  }

  const critical = issues.filter(i =>
    i.severity === 'critical' || i.severity === 'P0'
  ).length

  const high = issues.filter(i =>
    i.severity === 'high' || i.severity === 'major' || i.severity === 'P1'
  ).length

  const medium = issues.filter(i =>
    i.severity === 'medium' || i.severity === 'P2'
  ).length

  const low = issues.filter(i =>
    i.severity === 'low' || i.severity === 'minor' || i.severity === 'P3' || i.severity === 'P4'
  ).length

  // Score calculation: 100 - (critical×10 + high×5 + medium×1)
  // Low severity issues don't affect score
  const score = Math.max(0, 100 - (critical * 10 + high * 5 + medium * 1))

  return {
    score,
    critical_count: critical,
    high_count: high,
    medium_count: medium,
    low_count: low,
    meets_threshold: score >= 90 // Default threshold
  }
}

export function meetsQualityThreshold(qualityScore, threshold = 90) {
  return qualityScore.score >= threshold
}

export function formatQualityReport(qualityScore) {
  const { score, critical_count, high_count, medium_count, low_count } = qualityScore

  let emoji = '✅'
  if (score < 60) emoji = '❌'
  else if (score < 80) emoji = '⚠️'
  else if (score < 90) emoji = '🟡'

  return `${emoji} **Quality Score**: ${score}/100

**Issues Breakdown**:
- Critical: ${critical_count} (×10 points each)
- High: ${high_count} (×5 points each)
- Medium: ${medium_count} (×1 point each)
- Low: ${low_count} (no penalty)

**Total Impact**: -${100 - score} points
`
}

export function categorizeIssuesBySeverity(issues) {
  return {
    critical: issues.filter(i => i.severity === 'critical' || i.severity === 'P0'),
    high: issues.filter(i => i.severity === 'high' || i.severity === 'major' || i.severity === 'P1'),
    medium: issues.filter(i => i.severity === 'medium' || i.severity === 'P2'),
    low: issues.filter(i => i.severity === 'low' || i.severity === 'minor' || i.severity === 'P3' || i.severity === 'P4'),
  }
}

export function prioritizeIssuesForFix(issues, maxIssues = 10) {
  // Sort by severity (critical first, then high, then medium, then low)
  const severityOrder = { 'critical': 0, 'P0': 0, 'high': 1, 'major': 1, 'P1': 1, 'medium': 2, 'P2': 2, 'low': 3, 'minor': 3, 'P3': 3, 'P4': 3 }

  const sorted = [...issues].sort((a, b) => {
    const aSev = severityOrder[a.severity] ?? 99
    const bSev = severityOrder[b.severity] ?? 99

    if (aSev !== bSev) return aSev - bSev

    // If same severity, sort by confidence (higher first)
    return (b.confidence || 0) - (a.confidence || 0)
  })

  return sorted.slice(0, maxIssues)
}

export function hasImproved(previousScore, currentScore) {
  return currentScore.score > previousScore.score
}

export function hasConverged(previousScore, currentScore, tolerance = 2) {
  // Converged if score difference is within tolerance and no critical issues
  const scoreDiff = Math.abs(currentScore.score - previousScore.score)
  return scoreDiff <= tolerance && currentScore.critical_count === 0
}

export function shouldContinueImproving(qualityScore, targetScore = 95, maxIterations = 10, currentIteration = 1) {
  // Stop if:
  // 1. Target score reached
  if (qualityScore.score >= targetScore) {
    return { continue: false, reason: 'target_score_reached' }
  }

  // 2. Max iterations reached
  if (currentIteration >= maxIterations) {
    return { continue: false, reason: 'max_iterations_reached' }
  }

  // 3. No issues found (perfect score)
  if (qualityScore.score === 100) {
    return { continue: false, reason: 'perfect_score' }
  }

  // Otherwise, continue
  return { continue: true, reason: 'improvements_needed' }
}
