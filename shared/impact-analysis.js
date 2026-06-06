// Impact Analysis Utility
// Analyzes how code changes might break other parts of the codebase
// Used by pr-review to detect breaking changes and ripple effects

/**
 * Analyzes impact of changed files on the rest of the codebase
 *
 * @param {Function} agent - The agent function
 * @param {Object} changes - Change information
 * @param {string[]} changes.files - List of changed files
 * @param {string} changes.diff - Full diff of changes
 * @param {Object} options - Analysis options
 * @returns {Promise<Object>} Impact analysis results
 */
export async function analyzeImpact(agent, changes, options = {}) {
  const {
    includeTests = true,
    maxDepth = 2, // How many levels deep to analyze dependencies
    checkBreakingChanges = true
  } = options

  const results = {
    high_risk_changes: [],
    impacted_files: [],
    breaking_changes: [],
    missing_tests: [],
    recommendations: []
  }

  // Phase 1: Identify what changed (functions, classes, exports, interfaces)
  log('🔍 Phase 1: Analyzing what changed...')
  const changedEntities = await identifyChangedEntities(agent, changes)

  // Phase 2: Find what depends on the changed code
  log('🔍 Phase 2: Finding dependencies...')
  const dependencies = await findDependencies(agent, changedEntities, changes.files)

  // Phase 3: Check if usages are still valid
  log('🔍 Phase 3: Checking for breaking changes...')
  if (checkBreakingChanges) {
    const breakingChanges = await detectBreakingChanges(agent, changedEntities, dependencies, changes.diff)
    results.breaking_changes = breakingChanges
  }

  // Phase 4: Identify high-risk changes
  log('🔍 Phase 4: Assessing risk...')
  const riskAssessment = await assessRisk(agent, changedEntities, dependencies)
  results.high_risk_changes = riskAssessment.high_risk
  results.impacted_files = dependencies.impacted_files || []

  // Phase 5: Check test coverage for impacted areas
  if (includeTests) {
    log('🔍 Phase 5: Checking test coverage...')
    const testCoverage = await checkTestCoverage(agent, dependencies.impacted_files)
    results.missing_tests = testCoverage.missing_tests
  }

  // Phase 6: Generate recommendations
  results.recommendations = generateRecommendations(results)

  return results
}

/**
 * Identifies what entities changed (functions, classes, exports, types)
 */
async function identifyChangedEntities(agent, changes) {
  const result = await agent(`Analyze this diff and identify what changed.

Files changed: ${changes.files.join(', ')}

Diff:
${changes.diff}

Identify:
1. Functions added/modified/removed
2. Classes added/modified/removed
3. Exports added/modified/removed
4. Type/interface changes
5. API signature changes

Return structured data about what changed.`, {
    label: 'Identify Changes',
    schema: {
      type: 'object',
      properties: {
        functions: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              file: { type: 'string' },
              change_type: { type: 'string', enum: ['added', 'modified', 'removed'] },
              signature_changed: { type: 'boolean' },
              old_signature: { type: 'string' },
              new_signature: { type: 'string' }
            }
          }
        },
        classes: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              file: { type: 'string' },
              change_type: { type: 'string' },
              methods_changed: { type: 'array', items: { type: 'string' } }
            }
          }
        },
        exports: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              file: { type: 'string' },
              change_type: { type: 'string' }
            }
          }
        },
        types: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              name: { type: 'string' },
              file: { type: 'string' },
              change_type: { type: 'string' },
              breaking: { type: 'boolean' }
            }
          }
        }
      }
    }
  })

  return result
}

/**
 * Finds files that depend on the changed code
 */
async function findDependencies(agent, changedEntities, changedFiles) {
  // Build search patterns for each changed entity
  const searchPatterns = []

  changedEntities.functions?.forEach(f => {
    searchPatterns.push({ type: 'function', name: f.name, file: f.file })
  })

  changedEntities.classes?.forEach(c => {
    searchPatterns.push({ type: 'class', name: c.name, file: c.file })
  })

  changedEntities.exports?.forEach(e => {
    searchPatterns.push({ type: 'export', name: e.name, file: e.file })
  })

  const result = await agent(`Find all files that import or use the changed code.

Changed files: ${changedFiles.join(', ')}

Changed entities:
${JSON.stringify(searchPatterns, null, 2)}

Search the codebase for:
1. Import statements for these files
2. References to these functions/classes
3. Files that depend on these exports

Execute:
# Find imports
${changedFiles.map(f => `grep -r "from ['\"].*${f.replace(/^.*\//, '')}['\"]" . --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx" | head -50`).join('\n')}

# Find direct references
${searchPatterns.map(p => `grep -r "\\b${p.name}\\b" . --include="*.js" --include="*.ts" --include="*.jsx" --include="*.tsx" | head -50`).join('\n')}

Return list of impacted files.`, {
    label: 'Find Dependencies',
    schema: {
      type: 'object',
      properties: {
        impacted_files: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              file: { type: 'string' },
              imports: { type: 'array', items: { type: 'string' } },
              references: { type: 'array', items: { type: 'string' } },
              risk_level: { type: 'string', enum: ['low', 'medium', 'high'] }
            }
          }
        },
        total_impacted: { type: 'number' }
      }
    }
  })

  return result
}

/**
 * Detects breaking changes by checking if API changes are compatible
 */
async function detectBreakingChanges(agent, changedEntities, dependencies, diff) {
  const breakingChanges = []

  // Check function signature changes
  for (const func of (changedEntities.functions || [])) {
    if (func.signature_changed && func.change_type === 'modified') {
      const analysis = await agent(`Analyze if this function signature change is breaking.

Function: ${func.name}
Old signature: ${func.old_signature || 'unknown'}
New signature: ${func.new_signature}

Files that use this function: ${dependencies.impacted_files?.filter(f =>
  f.references?.includes(func.name)
).map(f => f.file).join(', ') || 'none found'}

Diff context:
${diff}

Is this a breaking change? Will existing callers break?`, {
        label: `Check ${func.name}`,
        schema: {
          type: 'object',
          properties: {
            is_breaking: { type: 'boolean' },
            reason: { type: 'string' },
            affected_files: { type: 'array', items: { type: 'string' } },
            severity: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] },
            fix_suggestion: { type: 'string' }
          }
        }
      })

      if (analysis.is_breaking) {
        breakingChanges.push({
          type: 'function_signature',
          entity: func.name,
          ...analysis
        })
      }
    }
  }

  // Check removed exports
  for (const exp of (changedEntities.exports || [])) {
    if (exp.change_type === 'removed') {
      breakingChanges.push({
        type: 'removed_export',
        entity: exp.name,
        is_breaking: true,
        severity: 'high',
        reason: `Export "${exp.name}" was removed, breaking any files that import it`,
        affected_files: dependencies.impacted_files?.filter(f =>
          f.imports?.includes(exp.name)
        ).map(f => f.file) || []
      })
    }
  }

  // Check type/interface changes
  for (const type of (changedEntities.types || [])) {
    if (type.breaking) {
      breakingChanges.push({
        type: 'type_change',
        entity: type.name,
        is_breaking: true,
        severity: 'high',
        reason: `Type/interface "${type.name}" has breaking changes`,
        affected_files: dependencies.impacted_files?.map(f => f.file) || []
      })
    }
  }

  return breakingChanges
}

/**
 * Assesses risk level of changes
 */
async function assessRisk(agent, changedEntities, dependencies) {
  const result = await agent(`Assess the risk level of these changes.

Changed entities:
- Functions: ${changedEntities.functions?.length || 0}
- Classes: ${changedEntities.classes?.length || 0}
- Exports: ${changedEntities.exports?.length || 0}
- Types: ${changedEntities.types?.length || 0}

Impacted files: ${dependencies.total_impacted || 0}

Files using changed code:
${dependencies.impacted_files?.slice(0, 10).map(f =>
  `- ${f.file} (${f.risk_level} risk)`
).join('\n') || 'none'}

Categorize changes by risk:
- HIGH: Changes that affect many files or core functionality
- MEDIUM: Changes with some downstream impact
- LOW: Isolated changes with minimal impact

Return risk assessment.`, {
    label: 'Assess Risk',
    schema: {
      type: 'object',
      properties: {
        high_risk: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              entity: { type: 'string' },
              reason: { type: 'string' },
              impacted_count: { type: 'number' },
              mitigation: { type: 'string' }
            }
          }
        },
        medium_risk: { type: 'array' },
        low_risk: { type: 'array' },
        overall_risk: { type: 'string', enum: ['low', 'medium', 'high', 'critical'] }
      }
    }
  })

  return result
}

/**
 * Checks if tests exist for impacted areas
 */
async function checkTestCoverage(agent, impactedFiles) {
  const result = await agent(`Check if tests exist for these impacted files.

Impacted files:
${impactedFiles?.map(f => f.file).join('\n') || 'none'}

For each file, check:
1. Does a test file exist? (*.test.js, *.spec.js, __tests__/)
2. Are the changed functions/classes tested?
3. Are integration tests needed?

Return files missing adequate tests.`, {
    label: 'Check Tests',
    schema: {
      type: 'object',
      properties: {
        missing_tests: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              file: { type: 'string' },
              reason: { type: 'string' },
              test_type_needed: { type: 'string' }
            }
          }
        },
        test_coverage_percentage: { type: 'number' }
      }
    }
  })

  return result
}

/**
 * Generates recommendations based on impact analysis
 */
function generateRecommendations(results) {
  const recommendations = []

  if (results.breaking_changes.length > 0) {
    recommendations.push({
      priority: 'critical',
      message: `⚠️ ${results.breaking_changes.length} breaking change(s) detected`,
      action: 'Review breaking changes and update affected files or add deprecation warnings'
    })
  }

  if (results.high_risk_changes.length > 0) {
    recommendations.push({
      priority: 'high',
      message: `🔥 ${results.high_risk_changes.length} high-risk change(s)`,
      action: 'Add integration tests for high-risk changes'
    })
  }

  if (results.missing_tests.length > 0) {
    recommendations.push({
      priority: 'medium',
      message: `📝 ${results.missing_tests.length} file(s) lack test coverage`,
      action: 'Add tests for impacted areas before merging'
    })
  }

  if (results.impacted_files.length > 10) {
    recommendations.push({
      priority: 'medium',
      message: `📊 ${results.impacted_files.length} files impacted`,
      action: 'Consider breaking this PR into smaller, focused changes'
    })
  }

  return recommendations
}

/**
 * Formats impact analysis as markdown for PR comments
 */
export function formatImpactAnalysis(impact) {
  let md = `## 🎯 Impact Analysis\n\n`

  // Overall summary
  md += `**Files Impacted**: ${impact.impacted_files.length}\n`
  md += `**Breaking Changes**: ${impact.breaking_changes.length}\n`
  md += `**High Risk Changes**: ${impact.high_risk_changes.length}\n\n`

  // Breaking changes (CRITICAL)
  if (impact.breaking_changes.length > 0) {
    md += `### ⚠️ Breaking Changes Detected\n\n`
    impact.breaking_changes.forEach(bc => {
      md += `#### ${bc.entity} (${bc.severity})\n`
      md += `**Type**: ${bc.type}\n`
      md += `**Reason**: ${bc.reason}\n`
      md += `**Affected Files**: ${bc.affected_files.length}\n`
      if (bc.affected_files.length > 0 && bc.affected_files.length <= 5) {
        md += `${bc.affected_files.map(f => `  - ${f}`).join('\n')}\n`
      }
      if (bc.fix_suggestion) {
        md += `**Fix**: ${bc.fix_suggestion}\n`
      }
      md += `\n`
    })
  }

  // High risk changes
  if (impact.high_risk_changes.length > 0) {
    md += `### 🔥 High Risk Changes\n\n`
    impact.high_risk_changes.forEach(hr => {
      md += `- **${hr.entity}**: ${hr.reason} (${hr.impacted_count} files impacted)\n`
      if (hr.mitigation) {
        md += `  - Mitigation: ${hr.mitigation}\n`
      }
    })
    md += `\n`
  }

  // Impacted files
  if (impact.impacted_files.length > 0) {
    md += `### 📊 Impacted Files (${impact.impacted_files.length})\n\n`

    const highRisk = impact.impacted_files.filter(f => f.risk_level === 'high')
    const mediumRisk = impact.impacted_files.filter(f => f.risk_level === 'medium')

    if (highRisk.length > 0) {
      md += `**High Risk** (${highRisk.length}):\n`
      highRisk.slice(0, 5).forEach(f => {
        md += `- ${f.file}\n`
      })
      if (highRisk.length > 5) {
        md += `  _(+${highRisk.length - 5} more)_\n`
      }
      md += `\n`
    }

    if (mediumRisk.length > 0) {
      md += `<details>\n<summary>Medium Risk (${mediumRisk.length})</summary>\n\n`
      mediumRisk.slice(0, 10).forEach(f => {
        md += `- ${f.file}\n`
      })
      if (mediumRisk.length > 10) {
        md += `  _(+${mediumRisk.length - 10} more)_\n`
      }
      md += `\n</details>\n\n`
    }
  }

  // Missing tests
  if (impact.missing_tests.length > 0) {
    md += `### 📝 Missing Test Coverage\n\n`
    impact.missing_tests.slice(0, 5).forEach(mt => {
      md += `- **${mt.file}**: ${mt.reason}\n`
      md += `  - Add: ${mt.test_type_needed}\n`
    })
    if (impact.missing_tests.length > 5) {
      md += `\n_(+${impact.missing_tests.length - 5} more files need tests)_\n`
    }
    md += `\n`
  }

  // Recommendations
  if (impact.recommendations.length > 0) {
    md += `### 💡 Recommendations\n\n`
    impact.recommendations.forEach(rec => {
      const icon = rec.priority === 'critical' ? '🚨' :
                   rec.priority === 'high' ? '⚠️' :
                   rec.priority === 'medium' ? '📋' : 'ℹ️'
      md += `${icon} **${rec.message}**\n`
      md += `   ${rec.action}\n\n`
    })
  }

  return md
}

// ============================================================================
// INLINE VERSION (for workflows that can't use imports)
// ============================================================================

export const INLINE_IMPACT_ANALYSIS = `
// Inline impact analysis (simplified version)

async function analyzeImpact(agent, changedFiles, diff) {
  // Find what depends on changed files
  const grepCmd = changedFiles.map(f =>
    \`grep -r "from ['\"].*\${f.replace(/^.*\\//, '')}['\"]" . --include="*.js" --include="*.ts" | head -20\`
  ).join('; ')

  const dependencies = await agent(\`Find files that import these changed files:
\${changedFiles.join(', ')}

Execute: \${grepCmd}

Return list of impacted files and risk assessment.\`, {
    schema: {
      type: 'object',
      properties: {
        impacted_files: { type: 'array', items: { type: 'string' } },
        breaking_changes: { type: 'array' },
        risk_level: { type: 'string' }
      }
    }
  })

  return dependencies
}
`
