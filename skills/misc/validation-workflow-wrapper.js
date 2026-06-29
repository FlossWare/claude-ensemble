/**
 * Validation Workflow Wrapper
 *
 * Wraps validation workflows to integrate GitHub issue tracking.
 * Automatically creates issues for blockers/bugs and closes them on fix.
 *
 * Usage in workflows:
 *   import { wrapValidationWorkflow } from './validation-workflow-wrapper.js';
 *
 *   export const meta = { ... };
 *
 *   export default wrapValidationWorkflow(async (context) => {
 *     // Your validation logic
 *     const result = await someValidationTask();
 *     return result;
 *   }, {
 *     workflowName: 'smoke-test',
 *     trackIssues: true,
 *     autoCloseOnPass: true
 *   });
 */

const {
  createValidationIssue,
  updateIssueWithFix,
  closeIssue,
  getWorkflowState,
  detectRepository
} = require('./github-issue-integration.cjs');

/**
 * Wrap validation workflow to track GitHub issues
 *
 * @param {Function} workflowFn - The validation workflow function
 * @param {Object} options - Wrapper options
 * @param {string} options.workflowName - Name of the workflow (for tracking)
 * @param {boolean} [options.trackIssues=true] - Track issues in GitHub
 * @param {boolean} [options.autoCloseOnPass=true] - Auto-close issues when validation passes
 * @param {boolean} [options.dryRun=false] - Don't actually create GitHub issues
 *
 * @returns {Function} Wrapped workflow function
 */
function wrapValidationWorkflow(workflowFn, options = {}) {
  const {
    workflowName = 'validation',
    trackIssues = true,
    autoCloseOnPass = true,
    dryRun = false
  } = options;

  return async function wrappedWorkflow(context = {}) {
    const workflowRunId = generateWorkflowRunId(workflowName);
    const results = {
      workflowName,
      workflowRunId,
      startTime: new Date().toISOString(),
      issues: [],
      passed: 0,
      failed: 0,
      blockers: [],
      bugs: []
    };

    console.log(`[${workflowName}] Starting workflow run: ${workflowRunId}`);

    try {
      // Execute the actual workflow
      const workflowResult = await workflowFn(context);

      // Process results
      if (Array.isArray(workflowResult)) {
        // Multiple test results
        workflowResult.forEach(result => {
          if (result.status === 'PASS') {
            results.passed++;
          } else if (result.status === 'FAIL') {
            results.failed++;

            // Determine severity
            if (result.isBlocker) {
              results.blockers.push(result);
            } else {
              results.bugs.push(result);
            }

            // Create GitHub issue if tracking enabled
            if (trackIssues) {
              const issuePromise = createValidationIssue({
                title: result.title || `${workflowName}: ${result.test_name || 'Unnamed test'}`,
                body: buildResultBody(result),
                severity: result.isBlocker ? 'blocker' : 'bug',
                workflowRunId,
                failureDetails: result.failure_details || {},
                labels: result.labels || [],
                dryRun
              }).catch(err => {
                console.error(`Failed to create issue for ${result.test_name}: ${err.message}`);
                return null;
              });

              // Track issue creation (non-blocking)
              issuePromise.then(issue => {
                if (issue) {
                  results.issues.push(issue);
                  result.issueNumber = issue.number;
                  result.issueUrl = issue.url;
                }
              });
            }
          }
        });
      } else if (workflowResult && typeof workflowResult === 'object') {
        // Single result object
        if (workflowResult.status === 'PASS') {
          results.passed = 1;
        } else if (workflowResult.status === 'FAIL') {
          results.failed = 1;
          results.bugs.push(workflowResult);

          if (trackIssues) {
            const issue = await createValidationIssue({
              title: workflowResult.title || `${workflowName}: Validation failed`,
              body: buildResultBody(workflowResult),
              severity: 'blocker',
              workflowRunId,
              failureDetails: workflowResult.failure_details || {},
              dryRun
            }).catch(err => {
              console.error(`Failed to create issue: ${err.message}`);
              return null;
            });

            if (issue) {
              results.issues.push(issue);
              workflowResult.issueNumber = issue.number;
              workflowResult.issueUrl = issue.url;
            }
          }
        }
      }

      results.endTime = new Date().toISOString();
      results.duration = new Date(results.endTime) - new Date(results.startTime);
      results.status = results.failed === 0 ? 'PASS' : 'FAIL';

      // Log summary
      const summary = `[${workflowName}] ${results.passed} passed, ${results.failed} failed`;
      console.log(summary);
      if (results.issues.length > 0) {
        console.log(`[${workflowName}] Created ${results.issues.length} GitHub issues`);
      }

      return {
        ...workflowResult,
        ...results,
        originalResult: workflowResult
      };
    } catch (error) {
      results.endTime = new Date().toISOString();
      results.duration = new Date(results.endTime) - new Date(results.startTime);
      results.status = 'ERROR';
      results.error = error.message;

      // Create blocker issue for workflow errors
      if (trackIssues) {
        try {
          const issue = await createValidationIssue({
            title: `${workflowName}: Workflow error`,
            body: `Workflow encountered an error:\n\n\`\`\`\n${error.stack}\n\`\`\``,
            severity: 'blocker',
            workflowRunId,
            failureDetails: { error: error.message, stack: error.stack },
            dryRun
          });
          results.issues.push(issue);
        } catch (err) {
          console.error(`Failed to create error issue: ${err.message}`);
        }
      }

      console.error(`[${workflowName}] Workflow error: ${error.message}`);

      return {
        ...results,
        error: error.message,
        stack: error.stack
      };
    }
  };
}

/**
 * Validation fix wrapper
 *
 * Wraps fix workflows to update GitHub issues with fix details
 *
 * @param {Function} fixWorkflowFn - The fix workflow function
 * @param {Object} options - Wrapper options
 * @param {string} options.workflowName - Name of the fix workflow
 * @param {boolean} [options.trackIssues=true] - Track fixes in GitHub
 * @param {boolean} [options.dryRun=false] - Dry run mode
 *
 * @returns {Function} Wrapped fix workflow
 */
function wrapFixWorkflow(fixWorkflowFn, options = {}) {
  const {
    workflowName = 'fix',
    trackIssues = true,
    dryRun = false
  } = options;

  return async function wrappedFixWorkflow(context = {}) {
    const fixRunId = generateWorkflowRunId(`${workflowName}-fix`);
    const results = {
      workflowName,
      fixRunId,
      startTime: new Date().toISOString(),
      issuesFixed: [],
      issuesClosed: []
    };

    console.log(`[${workflowName}] Starting fix workflow: ${fixRunId}`);

    try {
      // Execute the fix workflow
      const fixResult = await fixWorkflowFn(context);

      // Process fix results
      if (fixResult && typeof fixResult === 'object') {
        if (Array.isArray(fixResult.fixes)) {
          // Multiple fixes
          for (const fix of fixResult.fixes) {
            if (trackIssues && fix.issueNumber) {
              try {
                // Update issue with fix details
                await updateIssueWithFix({
                  issueNumber: fix.issueNumber,
                  fixDetails: fix.description || 'Applied fix',
                  commitShas: fix.commits || [],
                  dryRun
                });
                results.issuesFixed.push(fix.issueNumber);

                // Close if validation passed
                if (fix.validationPassed) {
                  await closeIssue({
                    issueNumber: fix.issueNumber,
                    reason: `Fixed by ${workflowName} workflow`,
                    dryRun
                  });
                  results.issuesClosed.push(fix.issueNumber);
                }
              } catch (err) {
                console.error(`Failed to update issue #${fix.issueNumber}: ${err.message}`);
              }
            }
          }
        }

        // Validate fixes
        if (fixResult.validationPassed) {
          console.log(`[${workflowName}] All fixes validated successfully`);
        }
      }

      results.endTime = new Date().toISOString();
      results.duration = new Date(results.endTime) - new Date(results.startTime);
      results.status = 'PASS';

      console.log(`[${workflowName}] Fixed ${results.issuesFixed.length} issues, closed ${results.issuesClosed.length}`);

      return {
        ...fixResult,
        ...results,
        originalResult: fixResult
      };
    } catch (error) {
      results.endTime = new Date().toISOString();
      results.duration = new Date(results.endTime) - new Date(results.startTime);
      results.status = 'ERROR';
      results.error = error.message;

      console.error(`[${workflowName}] Fix workflow error: ${error.message}`);

      return {
        ...results,
        error: error.message,
        stack: error.stack
      };
    }
  };
}

/**
 * Workflow state query helper
 *
 * Get state of issues created by a workflow
 *
 * @param {string} workflowRunId - Workflow run identifier
 * @returns {Object} Workflow state { issues, status, createdAt }
 */
async function queryWorkflowState(workflowRunId) {
  try {
    const state = await getWorkflowState(workflowRunId);
    return state;
  } catch (error) {
    console.error(`Failed to query workflow state: ${error.message}`);
    return { issues: [], status: 'unknown' };
  }
}

/**
 * Generate unique workflow run ID
 */
function generateWorkflowRunId(workflowName) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
  const random = Math.random().toString(36).substring(2, 8);
  return `${workflowName}-${timestamp}-${random}`;
}

/**
 * Build human-readable result body for GitHub issue
 */
function buildResultBody(result) {
  let body = '';

  if (result.description) {
    body += result.description + '\n\n';
  }

  if (result.issues && Array.isArray(result.issues)) {
    body += '## Issues\n';
    result.issues.forEach(issue => {
      body += `- ${issue}\n`;
    });
    body += '\n';
  }

  if (result.evidence && Array.isArray(result.evidence)) {
    body += '## Evidence\n';
    result.evidence.forEach(ev => {
      body += `- ${ev}\n`;
    });
    body += '\n';
  }

  if (result.error) {
    body += `## Error\n\`\`\`\n${result.error}\n\`\`\`\n\n`;
  }

  if (result.suggestion) {
    body += `## Suggested Fix\n${result.suggestion}\n`;
  }

  return body.trim();
}

module.exports = {
  wrapValidationWorkflow,
  wrapFixWorkflow,
  queryWorkflowState,
  generateWorkflowRunId
};
