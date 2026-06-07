export const meta = {
  name: 'code-app-test',
  description: 'Auto-detect project type and run smoke tests with multi-agent verification',
  whenToUse: 'Verify app builds, launches, and responds to basic interactions. Catches integration bugs that unit tests miss.',
  phases: [
    { title: 'Detect', detail: 'Identify project type (TUI, CLI, server, GUI, library)' },
    { title: 'Build', detail: 'Compile/build the application' },
    { title: 'Test', detail: 'Parallel smoke tests: launch, interact, verify' },
    { title: 'Generate Tests', detail: 'Create integration tests for failures' },
    { title: 'Create Issues', detail: 'Open GitHub issues for bugs found' },
    { title: 'Verify', detail: 'Multi-agent consensus on pass/fail' },
  ],
}

const SCHEMAS = {
  PROJECT_TYPE: {
    type: 'object',
    properties: {
      type: {
        type: 'string',
        enum: ['tui', 'cli', 'server', 'gui', 'library', 'unknown'],
        description: 'Detected project type'
      },
      confidence: { type: 'number', minimum: 0, maximum: 100 },
      evidence: {
        type: 'array',
        items: { type: 'string' },
        description: 'Files/patterns that led to this classification'
      },
      buildCommand: {
        type: 'string',
        description: 'Command to build (e.g., "mvn compile", "npm run build")'
      },
      testCommand: {
        type: 'string',
        description: 'Command to run tests (e.g., "mvn test", "npm test")'
      },
      launchCommand: {
        type: 'string',
        description: 'Command to launch app (e.g., "./run-interactive.sh", "npm start")'
      },
    },
    required: ['type', 'confidence', 'evidence', 'buildCommand'],
  },

  SMOKE_TEST_RESULT: {
    type: 'object',
    properties: {
      test_name: { type: 'string' },
      status: { type: 'string', enum: ['PASS', 'FAIL', 'FLAKY', 'SKIP'] },
      duration_ms: { type: 'number' },
      evidence: {
        type: 'array',
        items: { type: 'string' },
        description: 'Evidence: output snippets, screenshots, logs'
      },
      issues: {
        type: 'array',
        items: { type: 'string' },
        description: 'Problems found (crashes, errors, unexpected output)'
      },
    },
    required: ['test_name', 'status', 'evidence'],
  },

  FINAL_VERDICT: {
    type: 'object',
    properties: {
      overall_status: { type: 'string', enum: ['PASS', 'FAIL', 'FLAKY'] },
      passed_tests: { type: 'number' },
      failed_tests: { type: 'number' },
      flaky_tests: { type: 'number' },
      critical_issues: {
        type: 'array',
        items: { type: 'string' },
        description: 'Show-stopper issues found'
      },
      recommendations: {
        type: 'array',
        items: { type: 'string' },
        description: 'Actionable next steps'
      },
    },
    required: ['overall_status', 'passed_tests', 'failed_tests'],
  },
}

// Phase 1: Detect project type
phase('Detect')
log('Detecting project type...')

const detection = await agent(
  `Analyze the current directory and detect the project type.

  Look for:
  - TUI: ncurses, blessed, lanterna, ftxui dependencies; run scripts in tmux
  - CLI: main() with arg parsing, command-line tool setup
  - Server: HTTP server, REST API, web framework dependencies
  - GUI: Electron, Qt, JavaFX, desktop app frameworks
  - Library: SDK/library with no main entrypoint

  Check:
  - pom.xml, package.json, Cargo.toml, go.mod for dependencies
  - README.md for "demo", "run", "interactive" sections
  - Existing run scripts (*.sh, *.bat, *.ps1)
  - Source code structure

  Return the project type, confidence level, evidence, and suggested build/test/launch commands.`,
  {
    label: 'detect-project-type',
    phase: 'Detect',
    schema: SCHEMAS.PROJECT_TYPE,
  }
)

if (!detection) {
  return {
    status: 'FAIL',
    error: 'Could not detect project type',
    recommendation: 'Manually specify project type with --type flag',
  }
}

log(`Detected: ${detection.type} (${detection.confidence}% confidence)`)

// Phase 2: Build
phase('Build')
log(`Building with: ${detection.buildCommand}`)

const buildResult = await agent(
  `Build the application using: ${detection.buildCommand}

  Execute the build command and report:
  - Did it succeed? (exit code 0)
  - Build time
  - Any warnings or errors
  - Output artifacts (JAR, executable, bundle, etc.)

  If build fails, capture the error and suggest fixes.`,
  {
    label: 'build-app',
    phase: 'Build',
    schema: SCHEMAS.SMOKE_TEST_RESULT,
  }
)

if (!buildResult || buildResult.status === 'FAIL') {
  return {
    status: 'FAIL',
    phase: 'Build',
    error: 'Build failed',
    issues: buildResult?.issues || ['Build command failed'],
    recommendation: 'Fix build errors before testing',
  }
}

// Phase 3: Run smoke tests in parallel
phase('Test')
log('Running smoke tests in parallel...')

const smokeTests = [
  // Test 1: App launches without crashing
  () => agent(
    `Smoke test: Launch the app and verify it starts without crashing.

    Project type: ${detection.type}
    Launch command: ${detection.launchCommand || 'auto-detect'}

    For TUI apps:
    - Launch in tmux session
    - Wait 2 seconds
    - Capture screen output
    - Check for errors in stderr
    - Send Ctrl+C or 'q' to exit

    For CLI apps:
    - Run with --help or --version
    - Check exit code and output

    For servers:
    - Launch in background
    - Wait for port to open
    - Check health endpoint
    - Shutdown gracefully

    For GUI apps:
    - Launch under xvfb
    - Wait for window to appear
    - Screenshot the window
    - Close gracefully

    Return PASS if app launches successfully, FAIL if crashes, FLAKY if intermittent.`,
    {
      label: 'test-launch',
      phase: 'Test',
      schema: SCHEMAS.SMOKE_TEST_RESULT,
    }
  ),

  // Test 2: Basic interaction works
  () => agent(
    `Smoke test: Interact with the app and verify it responds.

    Project type: ${detection.type}

    For TUI apps:
    - Send TAB key (navigation)
    - Send SPACE key (activation)
    - Capture screen output
    - Verify UI updated

    For CLI apps:
    - Run a basic command
    - Verify output is correct

    For servers:
    - Send GET request to main endpoint
    - Verify 200 response
    - Check response body

    For GUI apps:
    - Click a button
    - Screenshot the result
    - Verify UI changed

    Return PASS if interaction works, FAIL if no response or error.`,
    {
      label: 'test-interaction',
      phase: 'Test',
      schema: SCHEMAS.SMOKE_TEST_RESULT,
    }
  ),

  // Test 3: Error handling (stderr, exceptions, logs)
  () => agent(
    `Smoke test: Check for errors, exceptions, and warnings during app execution.

    Examine:
    - stderr output during launch
    - Exception stack traces
    - Error logs
    - Segmentation faults or crashes
    - Memory leaks (if detectable)

    Return PASS if no errors, FAIL if errors found, FLAKY if intermittent errors.`,
    {
      label: 'test-errors',
      phase: 'Test',
      schema: SCHEMAS.SMOKE_TEST_RESULT,
    }
  ),

  // Test 4: Performance check
  () => agent(
    `Smoke test: Measure performance metrics.

    Check:
    - Startup time (< 5 seconds for most apps)
    - Response time (< 1 second for interactions)
    - Memory usage (reasonable for app type)
    - CPU usage (not pegged at 100%)

    Return PASS if performance is reasonable, FAIL if extremely slow or hung.`,
    {
      label: 'test-performance',
      phase: 'Test',
      schema: SCHEMAS.SMOKE_TEST_RESULT,
    }
  ),
]

const testResults = await parallel(smokeTests)

// Count results
const results = testResults.filter(Boolean)
const passed = results.filter(r => r.status === 'PASS').length
const failed = results.filter(r => r.status === 'FAIL').length
const flaky = results.filter(r => r.status === 'FLAKY').length

log(`Test results: ${passed} passed, ${failed} failed, ${flaky} flaky`)

// Phase 4: Generate integration tests for failures
phase('Generate Tests')
const failedTests = results.filter(r => r.status === 'FAIL' || r.status === 'FLAKY')

let generatedTests = []
if (failedTests.length > 0) {
  log(`Generating integration tests for ${failedTests.length} failures...`)

  generatedTests = await parallel(failedTests.map(failure => () =>
    agent(
      `Generate an integration test that reproduces this failure.

      Failed test: ${failure.test_name}
      Status: ${failure.status}
      Issues: ${failure.issues?.join('; ') || 'none'}
      Evidence: ${failure.evidence?.join('; ') || 'none'}

      Analyze the failure and create a JUnit integration test (*IT.java) that:
      1. Reproduces the exact failure scenario
      2. Has clear setup, execution, and assertion phases
      3. Uses existing test utilities (IntegrationTestBase, MockNcursesBridge, etc.)
      4. Follows project testing conventions
      5. Will FAIL until the bug is fixed, then PASS

      Return the complete test class code as a string, with:
      - Package declaration
      - Imports
      - Test class name ending in IT
      - @Test methods with descriptive names
      - Comments explaining what's being tested

      Example for bounds checking bug:

      package org.flossware.curses.integration;
      import org.junit.jupiter.api.Test;
      import static org.junit.jupiter.api.Assertions.*;
      class WidgetBoundsIT extends IntegrationTestBase {
          @Test
          void testWidgetPositionWithinTerminalBounds() {
              // Reproduces: ArrayIndexOutOfBoundsException when Y exceeds terminal height
          }
      }

      Return just the Java code, no markdown fences.`,
      {
        label: `generate-test-${failure.test_name.substring(0, 20)}`,
        phase: 'Generate Tests',
      }
    )
  ))

  log(`Generated \${generatedTests.filter(Boolean).length} integration tests`)
} else {
  log('No failures - skipping test generation')
}

// Phase 5: Create GitHub issues for bugs
phase('Create Issues')
const criticalFailures = results.filter(r =>
  (r.status === 'FAIL' || r.status === 'FLAKY') && r.issues && r.issues.length > 0
)

let createdIssues = []
if (criticalFailures.length > 0) {
  log(`Creating GitHub issues for \${criticalFailures.length} bugs...`)

  createdIssues = await parallel(criticalFailures.map(failure => () =>
    agent(
      `Create a GitHub issue for this bug.

      Bug from: \${failure.test_name}
      Status: \${failure.status}
      Issues: \${failure.issues?.join('; ') || 'none'}
      Evidence: \${failure.evidence?.join('; ') || 'none'}

      Use the Bash tool to run \`gh issue create\` with:
      - Title: Clear, actionable bug title (e.g., "App crashes with ArrayIndexOutOfBoundsException when widget exceeds terminal bounds")
      - Body: Include problem, location (file/line if known), error message, root cause, impact, fix suggestions, priority
      - Label: "bug"

      Return the GitHub issue URL after creating it.`,
      {
        label: `create-issue-\${failure.test_name.substring(0, 20)}`,
        phase: 'Create Issues',
      }
    )
  ))

  log(`Created \${createdIssues.filter(Boolean).length} GitHub issues`)
} else {
  log('No critical failures - skipping issue creation')
}

// Phase 6: Verify with consensus
phase('Verify')
log('Multi-agent consensus on final verdict...')

const verdict = await agent(
  `Review all smoke test results and provide final verdict.

  Test results:
  ${results.map((r, i) => `
  Test ${i + 1}: ${r.test_name}
  Status: ${r.status}
  Duration: ${r.duration_ms || 'N/A'}ms
  Evidence: ${r.evidence?.join(', ') || 'none'}
  Issues: ${r.issues?.join(', ') || 'none'}
  `).join('\n')}

  Provide:
  - Overall status: PASS (all critical tests pass), FAIL (any critical test fails), FLAKY (intermittent issues)
  - Critical issues found (show-stoppers)
  - Recommendations for next steps

  Critical tests: launch, interaction
  Non-critical tests: performance, error handling (can have warnings)`,
  {
    label: 'final-verdict',
    phase: 'Verify',
    schema: SCHEMAS.FINAL_VERDICT,
  }
)

// Return final report
return {
  project_type: detection.type,
  build_command: detection.buildCommand,
  test_results: results,
  overall_status: verdict.overall_status,
  passed: passed,
  failed: failed,
  flaky: flaky,
  critical_issues: verdict.critical_issues || [],
  recommendations: verdict.recommendations || [],
  generated_tests: generatedTests.filter(Boolean),
  created_issues: createdIssues.filter(Boolean),
  evidence: {
    build: buildResult.evidence || [],
    tests: results.map(r => ({
      name: r.test_name,
      status: r.status,
      evidence: r.evidence || [],
      issues: r.issues || [],
    })),
  },
}
