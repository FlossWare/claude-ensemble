// AUTONOMOUS WORKFLOW - Test Quality Analysis
// Reviews test suite quality, coverage, flakiness, and value

export const meta = {
  name: 'code-test-review',
  description: 'Comprehensive test quality review: coverage gaps, flaky tests, test value, performance (AUTONOMOUS)',
  phases: [
    { title: 'Test Discovery', detail: 'Find all test files and analyze structure' },
    { title: 'Coverage Analysis', detail: 'Identify coverage gaps and untested code' },
    { title: 'Flaky Test Detection', detail: 'Find intermittent/unreliable tests' },
    { title: 'Test Quality', detail: 'Assess test value and effectiveness' },
    { title: 'Performance', detail: 'Find slow tests and bottlenecks' },
    { title: 'Multi-Model Consensus', detail: 'Verify findings with multiple AIs' },
    { title: 'Create Issues', detail: 'Create GitHub/GitLab issues for findings' },
  ],
}

// Configuration
const AUTONOMOUS = args?.autonomous !== false
const USE_MULTI_MODEL = args?.multiModel !== false
const MAX_TEST_FILES = args?.maxFiles || 20
const CONFIDENCE_THRESHOLD = 75

log(`🧪 TEST QUALITY REVIEW`)
log('═'.repeat(80))
log(`Mode: ${AUTONOMOUS ? 'AUTONOMOUS' : 'INTERACTIVE'}`)
log(`Analyzing: Test coverage, quality, flakiness, performance`)
log('═'.repeat(80))

const allFindings = []

// PHASE 1: Test Discovery
phase('Test Discovery')
log('🔍 Discovering test files...')

const testDiscovery = await agent(`Find all test files in the repository.

Execute these commands to find tests:
find . -type f \\( -name "*test*" -o -name "*spec*" \\) \\
  -not -path "*/node_modules/*" \\
  -not -path "*/vendor/*" \\
  -not -path "*/.git/*" \\
  -not -path "*/build/*" \\
  -not -path "*/dist/*" \\
  2>/dev/null | head -50

Also detect test framework (Jest, pytest, JUnit, RSpec, etc.) from package.json, requirements.txt, pom.xml, or Gemfile.

Return structured data about test files and framework.`, {
  label: 'Discover Tests',
  schema: {
    type: 'object',
    properties: {
      test_files: {
        type: 'array',
        items: { type: 'string' }
      },
      framework: { type: 'string' },
      total_test_files: { type: 'number' },
      test_patterns: {
        type: 'object',
        properties: {
          unit_tests: { type: 'number' },
          integration_tests: { type: 'number' },
          e2e_tests: { type: 'number' }
        }
      }
    },
    required: ['test_files', 'framework', 'total_test_files']
  }
})

log(`✅ Found ${testDiscovery.total_test_files} test files`)
log(`   Framework: ${testDiscovery.framework}`)

// PHASE 2: Coverage Analysis
phase('Coverage Analysis')
log('📊 Analyzing test coverage...')

const coverageAnalysis = await agent(`Analyze test coverage for this codebase.

Test framework: ${testDiscovery.framework}

Try to run coverage analysis:
- For Jest: npm test -- --coverage || npx jest --coverage
- For pytest: pytest --cov=. --cov-report=term
- For JUnit: mvn test jacoco:report
- For Go: go test -cover ./...
- For Ruby: bundle exec rspec --format documentation

If coverage tools aren't available, manually analyze which files are tested vs untested.

Return coverage statistics and gaps.`, {
  label: 'Coverage Analysis',
  schema: {
    type: 'object',
    properties: {
      coverage_available: { type: 'boolean' },
      overall_coverage: { type: 'number', minimum: 0, maximum: 100 },
      untested_files: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file: { type: 'string' },
            reason: { type: 'string' },
            severity: { type: 'string', enum: ['critical', 'major', 'minor'] }
          }
        }
      },
      coverage_gaps: {
        type: 'array',
        items: { type: 'string' }
      }
    },
    required: ['coverage_available', 'untested_files']
  }
})

if (coverageAnalysis.coverage_available) {
  log(`✅ Coverage: ${coverageAnalysis.overall_coverage}%`)
}
log(`   Untested files: ${coverageAnalysis.untested_files?.length || 0}`)

// Add untested critical files to findings
coverageAnalysis.untested_files
  ?.filter(f => f.severity === 'critical')
  .forEach(f => {
    allFindings.push({
      type: 'coverage_gap',
      severity: 'critical',
      description: `Critical file untested: ${f.file} - ${f.reason}`,
      file: f.file,
      category: 'test_coverage'
    })
  })

// PHASE 3: Flaky Test Detection
phase('Flaky Test Detection')
log('🔄 Detecting flaky tests...')

const flakyTests = await pipeline(
  testDiscovery.test_files.slice(0, MAX_TEST_FILES),

  // Stage 1: Analyze each test file for flakiness indicators
  testFile => agent(`Analyze test file for flakiness indicators: ${testFile}

Read the file and look for:
- Timing/sleep dependencies (setTimeout, sleep, wait)
- Random data generation without seeds
- External service calls without mocks
- Race conditions in async tests
- Hardcoded dates/times
- Network dependencies
- File system dependencies
- Global state mutations

Return any flakiness indicators found.`, {
    label: `Flaky Check: ${testFile.split('/').pop()}`,
    schema: {
      type: 'object',
      properties: {
        test_file: { type: 'string' },
        has_flakiness_indicators: { type: 'boolean' },
        indicators: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              type: { type: 'string' },
              description: { type: 'string' },
              line_hint: { type: 'string' },
              confidence: { type: 'number', minimum: 0, maximum: 100 }
            }
          }
        }
      }
    }
  })
)

const flakyFindings = flakyTests
  .filter(Boolean)
  .filter(t => t.has_flakiness_indicators)

log(`✅ Found ${flakyFindings.length} potentially flaky test files`)

flakyFindings.forEach(f => {
  f.indicators?.forEach(indicator => {
    if (indicator.confidence >= CONFIDENCE_THRESHOLD) {
      allFindings.push({
        type: 'flaky_test',
        severity: 'major',
        description: `Flaky test indicator: ${indicator.description}`,
        file: f.test_file,
        line_hint: indicator.line_hint,
        category: 'test_reliability',
        confidence: indicator.confidence
      })
    }
  })
})

// PHASE 4: Test Quality Assessment
phase('Test Quality')
log('⚖️  Assessing test quality...')

const qualityReviews = await pipeline(
  testDiscovery.test_files.slice(0, MAX_TEST_FILES),

  // Stage 1: Multi-model quality review
  testFile => {
    if (!USE_MULTI_MODEL) {
      return agent(`Review test quality: ${testFile}

Assess:
- Do tests actually test behavior or just mocks?
- Are edge cases covered?
- Are assertions meaningful?
- Is there excessive mocking?
- Are tests brittle (coupled to implementation)?
- Are tests readable and maintainable?

Return quality assessment.`, {
        label: `Quality: ${testFile.split('/').pop()}`,
        schema: {
          type: 'object',
          properties: {
            issues: { type: 'array', items: { type: 'object' } }
          }
        }
      })
    }

    // Multi-model review
    const models = ['opus', 'sonnet', 'haiku']
    return parallel(models.map(model => () =>
      agent(`Review test quality: ${testFile}

Assess:
- Test value (do they catch real bugs?)
- Edge case coverage
- Mock overuse (testing mocks, not real code)
- Assertion quality
- Test brittleness
- Readability

Find ALL quality issues.`, {
        label: `${model} Quality: ${testFile.split('/').pop()}`,
        model,
        schema: {
          type: 'object',
          properties: {
            test_file: { type: 'string' },
            issues: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
                  category: { type: 'string' },
                  description: { type: 'string' },
                  line_hint: { type: 'string' },
                  confidence: { type: 'number', minimum: 0, maximum: 100 }
                }
              }
            }
          }
        }
      })
    )).then(reviews => ({
      test_file: testFile,
      reviews: reviews.filter(Boolean)
    }))
  }
)

log(`✅ Reviewed ${qualityReviews.length} test files for quality`)

// Extract quality issues
qualityReviews.filter(Boolean).forEach(review => {
  if (review.reviews) {
    // Multi-model: flatten all issues
    review.reviews.forEach(r => {
      r.issues?.forEach(issue => {
        if (issue.confidence >= CONFIDENCE_THRESHOLD) {
          allFindings.push({
            ...issue,
            type: 'test_quality',
            file: review.test_file,
            category: 'test_quality'
          })
        }
      })
    })
  } else {
    // Single model
    review.issues?.forEach(issue => {
      allFindings.push({
        ...issue,
        type: 'test_quality',
        file: review.test_file,
        category: 'test_quality'
      })
    })
  }
})

// PHASE 5: Performance Analysis
phase('Performance')
log('⚡ Analyzing test performance...')

const perfAnalysis = await agent(`Analyze test suite performance.

Try to run tests with timing:
- For Jest: npm test -- --verbose
- For pytest: pytest --durations=10
- For JUnit: Look for test timing in output
- For RSpec: rspec --profile 10

Identify:
- Slow tests (>1s for unit, >5s for integration)
- Test suite bottlenecks
- Parallelization opportunities

Return performance findings.`, {
  label: 'Performance Analysis',
  schema: {
    type: 'object',
    properties: {
      performance_data_available: { type: 'boolean' },
      total_test_time: { type: 'number' },
      slow_tests: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            test_file: { type: 'string' },
            test_name: { type: 'string' },
            duration_ms: { type: 'number' },
            severity: { type: 'string', enum: ['critical', 'major', 'minor'] }
          }
        }
      }
    }
  }
})

perfAnalysis.slow_tests?.forEach(test => {
  allFindings.push({
    type: 'slow_test',
    severity: test.severity,
    description: `Slow test: ${test.test_name} (${test.duration_ms}ms)`,
    file: test.test_file,
    category: 'test_performance'
  })
})

log(`✅ Found ${perfAnalysis.slow_tests?.length || 0} slow tests`)

// PHASE 6: Consensus & Deduplication
phase('Multi-Model Consensus')
log('⚖️  Running consensus verification...')

// Deduplicate findings
const uniqueFindings = []
const seen = new Set()

allFindings.forEach(finding => {
  const key = `${finding.file}:${finding.description}`
  if (!seen.has(key)) {
    seen.add(key)
    uniqueFindings.push(finding)
  }
})

log(`✅ ${uniqueFindings.length} unique findings (${allFindings.length} total before dedup)`)

// PHASE 7: Create Issues
phase('Create Issues')

if (!AUTONOMOUS) {
  log(`Found ${uniqueFindings.length} test quality issues`)
  return { findings: uniqueFindings }
}

log(`📝 Creating issues for ${uniqueFindings.length} findings...`)

// Detect platform
const platform = await agent(`Detect platform (GitHub or GitLab).

Execute:
if git remote -v | grep -q 'github.com'; then echo "github"
elif git remote -v | grep -q 'gitlab'; then echo "gitlab"
else echo "unknown"; fi`, {
  label: 'Detect Platform',
  schema: {
    type: 'object',
    properties: {
      platform: { type: 'string', enum: ['github', 'gitlab', 'unknown'] }
    }
  }
})

if (platform.platform === 'unknown') {
  log('⚠️  Platform not detected, skipping issue creation')
  return { findings: uniqueFindings, issues_created: 0 }
}

const isGitHub = platform.platform === 'github'

// Create issues
const createdIssues = []

for (const finding of uniqueFindings) {
  const title = `[Test Quality] ${finding.description.slice(0, 80)}`
  const body = `## Test Quality Issue

**Type:** ${finding.type}
**Severity:** ${finding.severity}
**Category:** ${finding.category}
**File:** ${finding.file}
${finding.line_hint ? `**Location:** ${finding.line_hint}` : ''}

### Description

${finding.description}

${finding.confidence ? `**Confidence:** ${finding.confidence}%` : ''}

---
🤖 Generated by /code-test-review workflow
`

  const createCmd = isGitHub
    ? `gh issue create --title "${title}" --body "${body}" --label "test-quality,${finding.severity}"`
    : `glab issue create --title "${title}" --description "${body}" --label "test-quality,${finding.severity}"`

  try {
    const result = await agent(`Create issue for finding.

Execute:
${createCmd}

Return the issue URL.`, {
      label: `Create Issue: ${finding.type}`,
      schema: {
        type: 'object',
        properties: {
          issue_url: { type: 'string' },
          issue_number: { type: 'number' }
        }
      }
    })

    createdIssues.push(result)
    log(`✓ Created issue #${result.issue_number}`)
  } catch (err) {
    log(`✗ Failed to create issue: ${err.message}`)
  }
}

log('═'.repeat(80))
log(`✅ TEST QUALITY REVIEW COMPLETE`)
log(`   Total findings: ${uniqueFindings.length}`)
log(`   Issues created: ${createdIssues.length}`)
log('═'.repeat(80))

return {
  findings: uniqueFindings,
  issues_created: createdIssues.length,
  coverage: coverageAnalysis.overall_coverage,
  flaky_tests: flakyFindings.length,
  slow_tests: perfAnalysis.slow_tests?.length || 0
}
