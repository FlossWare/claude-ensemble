/**
 * Pattern-Enhanced Workflow Wrapper
 *
 * Automatically augments workflow tasks with consensus-validated reasoning patterns.
 * Integrates with workflow-storage-adapter for transparent pattern application.
 *
 * Usage:
 *   const { enhanceWorkflowWithPatterns } = require('./pattern-enhanced-workflow.cjs');
 *
 *   export default enhanceWorkflowWithPatterns(async ({ phase, parallel, agent, log }) => {
 *     // Your workflow code here
 *     // Task descriptions are automatically augmented with relevant patterns
 *   });
 *
 * Created: 2026-07-03
 */

const { getConsensusPatterns } = require('./consensus-pattern-adapter.cjs');
const { getWorkflowStorage } = require('./workflow-storage-adapter.cjs');

/**
 * Enhance a workflow function with automatic pattern injection
 *
 * @param {Function} workflowFn - Original workflow function
 * @param {Object} options - Enhancement options
 * @param {boolean} options.enablePatterns - Enable pattern injection (default: true)
 * @param {number} options.minConfidence - Minimum pattern confidence (default: 0.7)
 * @param {number} options.maxPatterns - Max patterns per task (default: 2)
 * @param {boolean} options.storePatternUsage - Store pattern usage metadata (default: true)
 * @returns {Function} Enhanced workflow function
 */
function enhanceWorkflowWithPatterns(workflowFn, options = {}) {
  const {
    enablePatterns = true,
    minConfidence = 0.7,
    maxPatterns = 2,
    storePatternUsage = true
  } = options;

  return async function enhancedWorkflow(context) {
    // If patterns disabled, run original workflow
    if (!enablePatterns) {
      return await workflowFn(context);
    }

    const patternDB = getConsensusPatterns();
    const workflowDB = getWorkflowStorage();

    // Track pattern usage for this workflow
    const patternUsageStats = {
      patternsApplied: 0,
      categoriesDetected: [],
      confidenceScores: []
    };

    // Wrap the agent function to inject patterns
    const originalAgent = context.agent;
    context.agent = async function patternEnhancedAgent(taskDescription, agentOptions = {}) {
      // Check if this specific agent call has patterns disabled
      if (agentOptions.disablePatterns === true) {
        return originalAgent(taskDescription, agentOptions);
      }

      let enhancedTask = taskDescription;
      let patternsUsed = [];

      try {
        // Get relevant patterns for this task
        const patterns = await patternDB.getPatternsForTask(
          taskDescription,
          minConfidence,
          maxPatterns
        );

        if (patterns.length > 0) {
          // Augment task with patterns
          enhancedTask = await patternDB.augmentTaskWithPatterns(
            taskDescription,
            minConfidence,
            maxPatterns
          );

          // Track usage
          patternsUsed = patterns.map(p => ({
            category: p.problem_category,
            confidence: p.pattern_confidence,
            models_used: p.models_used
          }));

          patternUsageStats.patternsApplied += patterns.length;
          patternUsageStats.categoriesDetected.push(...patterns.map(p => p.problem_category));
          patternUsageStats.confidenceScores.push(...patterns.map(p => p.pattern_confidence));

          console.log(`[pattern-enhanced] Applied ${patterns.length} patterns to task (categories: ${patterns.map(p => p.problem_category).join(', ')})`);
        }
      } catch (err) {
        console.warn(`[pattern-enhanced] Failed to apply patterns: ${err.message}`);
        // Continue with original task on error
      }

      // Call original agent with enhanced task
      const result = await originalAgent(enhancedTask, agentOptions);

      // Store pattern usage metadata if enabled
      if (storePatternUsage && patternsUsed.length > 0) {
        try {
          // Attach pattern metadata to result (if result is an object)
          if (result && typeof result === 'object') {
            result._patternMetadata = {
              patternsApplied: patternsUsed,
              originalTask: taskDescription.substring(0, 200),
              enhancedTask: enhancedTask.length > taskDescription.length
            };
          }
        } catch (err) {
          // Non-fatal metadata attachment failure
          console.warn(`[pattern-enhanced] Failed to attach pattern metadata: ${err.message}`);
        }
      }

      return result;
    };

    // Wrap the parallel function to inject patterns
    const originalParallel = context.parallel;
    context.parallel = async function patternEnhancedParallel(tasks) {
      // Process each task to inject patterns
      const enhancedTasks = await Promise.all(
        tasks.map(async (task) => {
          // If task is a string, treat as task description
          if (typeof task === 'string') {
            try {
              const patterns = await patternDB.getPatternsForTask(
                task,
                minConfidence,
                maxPatterns
              );

              if (patterns.length > 0) {
                const enhancedTask = await patternDB.augmentTaskWithPatterns(
                  task,
                  minConfidence,
                  maxPatterns
                );

                patternUsageStats.patternsApplied += patterns.length;
                patternUsageStats.categoriesDetected.push(...patterns.map(p => p.problem_category));
                patternUsageStats.confidenceScores.push(...patterns.map(p => p.pattern_confidence));

                return enhancedTask;
              }
            } catch (err) {
              console.warn(`[pattern-enhanced] Failed to enhance parallel task: ${err.message}`);
            }
            return task;
          }

          // If task is an object with description field, enhance it
          if (task && typeof task === 'object' && task.description) {
            try {
              const patterns = await patternDB.getPatternsForTask(
                task.description,
                minConfidence,
                maxPatterns
              );

              if (patterns.length > 0) {
                const enhancedDescription = await patternDB.augmentTaskWithPatterns(
                  task.description,
                  minConfidence,
                  maxPatterns
                );

                patternUsageStats.patternsApplied += patterns.length;
                patternUsageStats.categoriesDetected.push(...patterns.map(p => p.problem_category));
                patternUsageStats.confidenceScores.push(...patterns.map(p => p.pattern_confidence));

                return { ...task, description: enhancedDescription };
              }
            } catch (err) {
              console.warn(`[pattern-enhanced] Failed to enhance parallel task: ${err.message}`);
            }
          }

          return task;
        })
      );

      // Call original parallel with enhanced tasks
      return originalParallel(enhancedTasks);
    };

    // Add pattern stats to context for workflow access
    context.patternStats = patternUsageStats;

    // Execute original workflow with enhanced context
    let result;
    let workflowError = null;

    try {
      result = await workflowFn(context);
    } catch (err) {
      workflowError = err;
      throw err;
    } finally {
      // Log pattern usage summary
      if (patternUsageStats.patternsApplied > 0) {
        const uniqueCategories = [...new Set(patternUsageStats.categoriesDetected)];
        const avgConfidence = patternUsageStats.confidenceScores.length > 0
          ? (patternUsageStats.confidenceScores.reduce((a, b) => a + b, 0) / patternUsageStats.confidenceScores.length).toFixed(2)
          : 0;

        console.log(`[pattern-enhanced] Workflow completed with ${patternUsageStats.patternsApplied} patterns applied`);
        console.log(`[pattern-enhanced] Categories: ${uniqueCategories.join(', ')}`);
        console.log(`[pattern-enhanced] Average confidence: ${avgConfidence}`);

        // Store pattern usage in workflow metadata (if workflow ID available in context)
        if (storePatternUsage && context.workflowExecutionId) {
          try {
            await workflowDB.pool.query(
              `UPDATE workflow.executions
               SET metadata = jsonb_set(
                 COALESCE(metadata, '{}'::jsonb),
                 '{pattern_usage}',
                 $2::jsonb
               )
               WHERE id = $1`,
              [
                context.workflowExecutionId,
                JSON.stringify({
                  patterns_applied: patternUsageStats.patternsApplied,
                  categories: uniqueCategories,
                  avg_confidence: parseFloat(avgConfidence)
                })
              ]
            );
          } catch (err) {
            console.warn(`[pattern-enhanced] Failed to store pattern usage: ${err.message}`);
          }
        }
      }
    }

    return result;
  };
}

/**
 * Create a pattern-aware agent wrapper
 * Use this when you need more control than the full workflow wrapper
 *
 * @param {Function} agentFn - Original agent function
 * @param {Object} options - Enhancement options
 * @returns {Function} Enhanced agent function
 */
function createPatternAwareAgent(agentFn, options = {}) {
  const {
    minConfidence = 0.7,
    maxPatterns = 2
  } = options;

  return async function patternAwareAgent(taskDescription, agentOptions = {}) {
    if (agentOptions.disablePatterns === true) {
      return agentFn(taskDescription, agentOptions);
    }

    const patternDB = getConsensusPatterns();

    try {
      const enhancedTask = await patternDB.augmentTaskWithPatterns(
        taskDescription,
        minConfidence,
        maxPatterns
      );

      return await agentFn(enhancedTask, agentOptions);
    } catch (err) {
      console.warn(`[pattern-aware-agent] Pattern enhancement failed: ${err.message}`);
      return await agentFn(taskDescription, agentOptions);
    }
  };
}

/**
 * Get pattern suggestions for a task (without executing)
 * Useful for debugging or manual inspection
 *
 * @param {string} taskDescription - Task description
 * @param {Object} options - Options
 * @returns {Promise<Array>} Array of pattern suggestions
 */
async function getPatternSuggestions(taskDescription, options = {}) {
  const {
    minConfidence = 0.7,
    maxPatterns = 3
  } = options;

  const patternDB = getConsensusPatterns();
  const patterns = await patternDB.getPatternsForTask(
    taskDescription,
    minConfidence,
    maxPatterns
  );

  return patterns.map(p => ({
    category: p.problem_category,
    confidence: p.pattern_confidence,
    models_used: p.models_used,
    approach: p.successful_approach,
    steps: p.common_reasoning_steps,
    avoid: p.error_patterns_to_avoid
  }));
}

module.exports = {
  enhanceWorkflowWithPatterns,
  createPatternAwareAgent,
  getPatternSuggestions
};
